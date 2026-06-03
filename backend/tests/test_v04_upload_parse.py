"""Tests for v0.4 work-scoped upload and parse."""

import io

from sqlmodel import Session

from models.model_provider import ModelProvider
from models.topic import Topic
from models.work import Work


def _setup_work(engine, client) -> str:
    """Create a topic, provider, and Work. Return work_id."""
    with Session(engine) as session:
        prov = ModelProvider(
            name="WUpP", provider_type="openai_compatible",
            base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
        )
        session.add(prov); session.flush()
        topic = Topic(name="WUpTopic", provider_id=prov.id, status="created")
        session.add(topic); session.flush()
        work = Work(topic_id=topic.id, title="Test Work", series_index=1)
        session.add(work)
        session.commit()
        return work.id


class TestWorkUpload:
    def test_upload_txt_to_work(self, engine, client):
        wid = _setup_work(engine, client)
        r = client.post(
            f"/api/works/{wid}/documents/upload",
            files={"file": ("novel.txt", io.BytesIO("第一章\n内容。\n".encode()), "text/plain")},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["file_type"] == "txt"
        assert data["work_id"] == wid

    def test_upload_epub_to_work(self, engine, client):
        """Upload a minimal valid EPUB to a Work."""
        wid = _setup_work(engine, client)
        # Minimal valid EPUB bytes
        epub_bytes = _minimal_epub()
        r = client.post(
            f"/api/works/{wid}/documents/upload",
            files={"file": ("novel.epub", io.BytesIO(epub_bytes), "application/epub+zip")},
        )
        assert r.status_code == 201
        assert r.json()["file_type"] == "epub"

    def test_second_upload_to_work_409(self, engine, client):
        wid = _setup_work(engine, client)
        client.post(
            f"/api/works/{wid}/documents/upload",
            files={"file": ("a.txt", io.BytesIO("第一章\n".encode()), "text/plain")},
        )
        r = client.post(
            f"/api/works/{wid}/documents/upload",
            files={"file": ("b.txt", io.BytesIO("第二章\n".encode()), "text/plain")},
        )
        assert r.status_code == 409

    def test_get_work_document(self, engine, client):
        wid = _setup_work(engine, client)
        client.post(
            f"/api/works/{wid}/documents/upload",
            files={"file": ("novel.txt", io.BytesIO("第一章\n内容。\n".encode()), "text/plain")},
        )
        r = client.get(f"/api/works/{wid}/documents/current")
        assert r.status_code == 200
        assert r.json()["file_type"] == "txt"

    def test_get_work_document_not_found(self, engine, client):
        wid = _setup_work(engine, client)
        r = client.get(f"/api/works/{wid}/documents/current")
        assert r.status_code == 404


class TestWorkParse:
    def test_parse_work(self, engine, client):
        wid = _setup_work(engine, client)
        client.post(
            f"/api/works/{wid}/documents/upload",
            files={"file": ("novel.txt", io.BytesIO("第一章 测试\n内容。\n第二章 更多\n内容。\n".encode()), "text/plain")},
        )
        r = client.post(f"/api/works/{wid}/parse")
        assert r.status_code == 200
        data = r.json()
        assert data["chapter_count"] >= 1
        assert data["chunk_count"] >= 1

    def test_list_work_chapters(self, engine, client):
        wid = _setup_work(engine, client)
        client.post(
            f"/api/works/{wid}/documents/upload",
            files={"file": ("novel.txt", io.BytesIO("第一章 测试\n内容。\n".encode()), "text/plain")},
        )
        client.post(f"/api/works/{wid}/parse")
        r = client.get(f"/api/works/{wid}/chapters")
        assert r.status_code == 200
        assert len(r.json()["chapters"]) >= 1

    def test_list_work_chunks(self, engine, client):
        wid = _setup_work(engine, client)
        client.post(
            f"/api/works/{wid}/documents/upload",
            files={"file": ("novel.txt", io.BytesIO("第一章 测试\n内容。\n".encode()), "text/plain")},
        )
        client.post(f"/api/works/{wid}/parse")
        r = client.get(f"/api/works/{wid}/chunks")
        assert r.status_code == 200
        assert len(r.json()["chunks"]) >= 1

    def test_parse_work_not_found(self, engine, client):
        r = client.post("/api/works/nonexistent/parse")
        assert r.status_code == 409

    def test_parse_without_document(self, engine, client):
        wid = _setup_work(engine, client)
        r = client.post(f"/api/works/{wid}/parse")
        assert r.status_code == 409


class TestLegacyCompatibility:
    def test_legacy_upload_creates_default_work(self, engine, client):
        """Legacy topic-level upload → default Work created, document has work_id."""
        from models.model_provider import ModelProvider
        from models.topic import Topic

        # Create a topic directly (no Work)
        with Session(engine) as session:
            prov = ModelProvider(
                name="LegacyUpP", provider_type="openai_compatible",
                base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
            )
            session.add(prov); session.flush()
            topic = Topic(name="LegacyUpload", provider_id=prov.id, status="created")
            session.add(topic)
            session.commit()
            tid = topic.id

        r = client.post(
            f"/api/topics/{tid}/documents/upload",
            files={"file": ("legacy.txt", io.BytesIO("第一章\n旧书。\n".encode()), "text/plain")},
        )
        assert r.status_code == 201
        assert r.json()["work_id"] is not None

    def test_legacy_parse_uses_default_work(self, engine, client):
        """Legacy topic-level parse resolves default Work."""
        from models.model_provider import ModelProvider
        from models.topic import Topic

        with Session(engine) as session:
            prov = ModelProvider(
                name="LegacyParseP", provider_type="openai_compatible",
                base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
            )
            session.add(prov); session.flush()
            topic = Topic(name="LegacyParse", provider_id=prov.id, status="created")
            session.add(topic)
            session.commit()
            tid = topic.id

        client.post(
            f"/api/topics/{tid}/documents/upload",
            files={"file": ("novel.txt", io.BytesIO("第一章 测试\n内容。\n".encode()), "text/plain")},
        )
        r = client.post(f"/api/topics/{tid}/parse")
        assert r.status_code == 200
        assert r.json()["chapter_count"] >= 1

    def test_legacy_get_current_document(self, engine, client):
        """Legacy GET /topics/{id}/documents/current resolves default Work."""
        from models.model_provider import ModelProvider
        from models.topic import Topic

        with Session(engine) as session:
            prov = ModelProvider(
                name="LegacyGetP", provider_type="openai_compatible",
                base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
            )
            session.add(prov); session.flush()
            topic = Topic(name="LegacyGet", provider_id=prov.id, status="created")
            session.add(topic)
            session.commit()
            tid = topic.id

        client.post(
            f"/api/topics/{tid}/documents/upload",
            files={"file": ("novel.txt", io.BytesIO("第一章\n".encode()), "text/plain")},
        )
        r = client.get(f"/api/topics/{tid}/documents/current")
        assert r.status_code == 200
        assert r.json()["file_type"] == "txt"


def _minimal_epub() -> bytes:
    """Build a minimal valid EPUB in memory."""
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?><container version="1.0" '
            'xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            "<rootfiles><rootfile full-path='content.opf' "
            "media-type='application/oebps-package+xml'/></rootfiles></container>",
        )
        zf.writestr(
            "content.opf",
            '<?xml version="1.0"?><package version="2.0" '
            'xmlns="http://www.idpf.org/2007/opf">'
            "<metadata><dc:title>Test</dc:title></metadata>"
            "<manifest><item id='c1' href='ch1.xhtml' media-type='application/xhtml+xml'/></manifest>"
            "<spine><itemref idref='c1'/></spine></package>",
        )
        zf.writestr(
            "ch1.xhtml",
            "<html><body><p>第一章 测试</p></body></html>",
        )
    return buf.getvalue()
