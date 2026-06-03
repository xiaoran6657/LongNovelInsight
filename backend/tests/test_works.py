"""Tests for v0.4 Work CRUD API."""

from sqlmodel import Session


def _create_provider_and_topic(client) -> str:
    """Create a provider and topic via API, return topic_id."""
    r = client.post(
        "/api/providers",
        json={
            "name": "WorkP", "provider_type": "openai_compatible",
            "base_url": "http://mock", "api_key": "sk-m", "model_name": "m",
        },
    )
    # 200 or 409 if already exists from another test
    assert r.status_code in (201, 409)
    provs = client.get("/api/providers").json()["providers"]
    pid = provs[0]["id"]

    r = client.post("/api/topics", json={"name": "WorkTopic"})
    assert r.status_code == 201
    tid = r.json()["id"]
    client.put(
        f"/api/topics/{tid}/provider-config",
        json={"provider_id": pid},
    )
    return tid


class TestWorkCRUD:
    def test_create_work(self, client):
        tid = _create_provider_and_topic(client)
        r = client.post(
            f"/api/topics/{tid}/works",
            json={"title": "Book One", "series_index": 1},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["title"] == "Book One"
        assert data["series_index"] == 1
        assert data["status"] == "empty"

    def test_list_works(self, client):
        tid = _create_provider_and_topic(client)
        client.post(f"/api/topics/{tid}/works", json={"title": "A", "series_index": 2})
        client.post(f"/api/topics/{tid}/works", json={"title": "B", "series_index": 1})
        r = client.get(f"/api/topics/{tid}/works")
        assert r.status_code == 200
        works = r.json()["works"]
        assert len(works) == 2
        assert works[0]["series_index"] == 1
        assert works[1]["series_index"] == 2

    def test_list_works_empty(self, client):
        tid = _create_provider_and_topic(client)
        r = client.get(f"/api/topics/{tid}/works")
        assert r.status_code == 200
        assert r.json()["works"] == []

    def test_get_work(self, client):
        tid = _create_provider_and_topic(client)
        r = client.post(
            f"/api/topics/{tid}/works",
            json={"title": "Single", "author": "Author Name"},
        )
        wid = r.json()["id"]
        r2 = client.get(f"/api/works/{wid}")
        assert r2.status_code == 200
        assert r2.json()["author"] == "Author Name"

    def test_get_work_not_found(self, client):
        r = client.get("/api/works/nonexistent-id")
        assert r.status_code == 404

    def test_update_work(self, client):
        tid = _create_provider_and_topic(client)
        r = client.post(
            f"/api/topics/{tid}/works",
            json={"title": "Old Title", "series_index": 1},
        )
        wid = r.json()["id"]
        r2 = client.patch(
            f"/api/works/{wid}",
            json={"title": "New Title", "author": "New Author"},
        )
        assert r2.status_code == 200
        assert r2.json()["title"] == "New Title"
        assert r2.json()["author"] == "New Author"
        assert r2.json()["series_index"] == 1  # unchanged

    def test_delete_empty_work(self, client):
        tid = _create_provider_and_topic(client)
        r = client.post(f"/api/topics/{tid}/works", json={"title": "ToDelete"})
        wid = r.json()["id"]
        r2 = client.delete(f"/api/works/{wid}")
        assert r2.status_code == 200
        assert r2.json()["deleted"] is True
        # Verify deleted
        r3 = client.get(f"/api/works/{wid}")
        assert r3.status_code == 404

    def test_delete_non_empty_work_409(self, engine, client):
        """Work with a Document should be rejected for deletion."""
        from models.chapter import Chapter
        from models.document import Document
        from models.topic import Topic
        from models.work import Work

        with Session(engine) as session:
            topic = Topic(name="DeleteWork", status="parsed")
            session.add(topic); session.flush()
            work = Work(topic_id=topic.id, title="HasDoc", series_index=1)
            session.add(work); session.flush()
            doc = Document(
                topic_id=topic.id, work_id=work.id,
                original_filename="test.txt", file_size_bytes=100,
                char_count=50, status="parsed",
            )
            session.add(doc); session.flush()
            ch = Chapter(
                topic_id=topic.id, document_id=doc.id,
                chapter_index=0, title="Ch1",
                start_char=0, end_char=50, char_count=50,
            )
            session.add(ch)
            session.commit()
            wid = work.id

        r = client.delete(f"/api/works/{wid}")
        assert r.status_code == 409
        assert "not supported" in r.json()["detail"].lower()

    def test_create_work_nonexistent_topic(self, client):
        r = client.post("/api/topics/nonexistent/works", json={"title": "X"})
        assert r.status_code == 404

    def test_create_work_defaults(self, client):
        tid = _create_provider_and_topic(client)
        r = client.post(
            f"/api/topics/{tid}/works",
            json={"title": "Defaults"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["subtitle"] is None
        assert data["author"] is None
        assert data["description"] is None
        assert data["series_index"] is None
        assert data["status"] == "empty"

    def test_delete_work_with_document_only_409(self, engine, client):
        """Work with uploaded Document but no chapters → non-empty, delete 409."""
        from models.document import Document
        from models.topic import Topic
        from models.work import Work

        with Session(engine) as session:
            topic = Topic(name="DocOnlyDel", status="uploaded")
            session.add(topic); session.flush()
            work = Work(topic_id=topic.id, title="DocOnly", series_index=1)
            session.add(work); session.flush()
            doc = Document(
                topic_id=topic.id, work_id=work.id,
                original_filename="just_uploaded.txt",
                file_size_bytes=100, char_count=50, status="uploaded",
            )
            session.add(doc)
            session.commit()
            wid = work.id
            did = doc.id

        r = client.delete(f"/api/works/{wid}")
        assert r.status_code == 409

        # Verify Work and Document still exist
        r2 = client.get(f"/api/works/{wid}")
        assert r2.status_code == 200
        with Session(engine) as session:
            doc = session.get(Document, did)
            assert doc is not None
            assert doc.work_id == wid

    def test_list_works_backfills_legacy_document(self, engine, client):
        """Topic with Document but no Work → list_works creates default Work and backfills."""
        from models.document import Document
        from models.topic import Topic

        with Session(engine) as session:
            topic = Topic(name="LegacyList", status="parsed")
            session.add(topic); session.flush()
            doc = Document(
                topic_id=topic.id, original_filename="legacy.txt",
                file_size_bytes=100, char_count=50, status="parsed",
                work_id=None,
            )
            session.add(doc)
            session.commit()
            tid = topic.id
            did = doc.id

        r = client.get(f"/api/topics/{tid}/works")
        assert r.status_code == 200
        works = r.json()["works"]
        assert len(works) == 1, "legacy Document should trigger default Work creation"
        assert works[0]["series_index"] == 1
        assert works[0]["title"] == "legacy"

        # Document should be backfilled
        with Session(engine) as session:
            doc = session.get(Document, did)
            assert doc is not None
            assert doc.work_id == works[0]["id"]
