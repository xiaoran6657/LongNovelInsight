def test_create_topic(client):
    response = client.post("/api/topics", json={"name": "Test Topic"})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Topic"
    assert data["id"] is not None
    assert data["provider_id"] is None


def test_create_topic_with_description(client):
    response = client.post("/api/topics", json={"name": "Topic", "description": "A description"})
    assert response.status_code == 201
    assert response.json()["description"] == "A description"


def test_list_topics(client):
    client.post("/api/topics", json={"name": "Topic 1"})
    client.post("/api/topics", json={"name": "Topic 2"})
    response = client.get("/api/topics")
    assert response.status_code == 200
    assert len(response.json()["topics"]) == 2


def test_list_topics_empty(client):
    response = client.get("/api/topics")
    assert response.status_code == 200
    assert response.json()["topics"] == []


def test_get_topic(client):
    r = client.post("/api/topics", json={"name": "Find Me"})
    topic_id = r.json()["id"]
    response = client.get(f"/api/topics/{topic_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Find Me"
    assert response.json()["document"] is None


def test_get_topic_404(client):
    response = client.get("/api/topics/nonexistent-id")
    assert response.status_code == 404


def test_delete_topic(client):
    r = client.post("/api/topics", json={"name": "Delete Me"})
    topic_id = r.json()["id"]
    response = client.delete(f"/api/topics/{topic_id}")
    assert response.status_code == 200
    assert response.json()["deleted"] is True


def test_delete_topic_404(client):
    response = client.delete("/api/topics/nonexistent-id")
    assert response.status_code == 404


def test_deleted_topic_not_in_list(client):
    r = client.post("/api/topics", json={"name": "Gone"})
    topic_id = r.json()["id"]
    client.delete(f"/api/topics/{topic_id}")
    response = client.get("/api/topics")
    assert len(response.json()["topics"]) == 0


def test_create_topic_with_valid_provider(client):
    """Topic.provider_id referencing an existing provider should succeed."""
    # Create a provider first
    r = client.post(
        "/api/providers",
        json={
            "name": "ValidP",
            "provider_type": "openai_compatible",
            "base_url": "https://api.example.com",
            "api_key": "sk-key",
            "model_name": "m",
        },
    )
    provider_id = r.json()["id"]

    # Create topic with valid provider_id
    r = client.post(
        "/api/topics",
        json={"name": "Topic With Provider", "provider_id": provider_id},
    )
    assert r.status_code == 201
    assert r.json()["provider_id"] == provider_id


def test_create_topic_with_nonexistent_provider_404(client):
    """Topic.provider_id referencing a nonexistent provider should fail."""
    r = client.post(
        "/api/topics",
        json={"name": "Bad Topic", "provider_id": "nonexistent-id"},
    )
    assert r.status_code == 404


def test_topic_detail_document_not_null(client):
    """After uploading a document, topic detail returns document data."""
    r = client.post("/api/topics", json={"name": "DocDetail"})
    topic_id = r.json()["id"]

    from io import BytesIO

    client.post(
        f"/api/topics/{topic_id}/documents/upload",
        files={"file": ("test.txt", BytesIO(b"Hello world.\n"), "text/plain")},
    )

    resp = client.get(f"/api/topics/{topic_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["document"] is not None
    assert data["document"]["original_filename"] == "test.txt"
    assert data["document"]["file_size_bytes"] > 0


def test_topic_detail_analysis_summary_not_empty(client):
    """After running analysis, topic detail returns non-empty analysis_summary."""
    # Create provider
    r = client.post(
        "/api/providers",
        json={
            "name": "TP",
            "provider_type": "openai_compatible",
            "base_url": "https://api.example.com",
            "api_key": "sk-key",
            "model_name": "m",
            "is_default": True,
        },
    )
    provider_id = r.json()["id"]

    r = client.post(
        "/api/topics",
        json={"name": "AnalysisDetail", "provider_id": provider_id},
    )
    topic_id = r.json()["id"]

    from io import BytesIO

    client.post(
        f"/api/topics/{topic_id}/documents/upload",
        files={
            "file": (
                "test.txt",
                BytesIO("第一章 开始\n张三走进长安城。\n".encode("utf-8")),
                "text/plain",
            )
        },
    )
    client.post(f"/api/topics/{topic_id}/parse")

    from unittest.mock import patch

    with patch(
        "services.analysis_service.OpenAICompatibleLLMClient.chat",
        side_effect=_mock_topic_analysis,
    ):
        client.post(f"/api/topics/{topic_id}/analysis/run?limit_chunks=3")

    resp = client.get(f"/api/topics/{topic_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["analysis_summary"] != {}
    assert "overview" in data["analysis_summary"]


def test_delete_topic_cascades_data(client):
    """Deleting a topic removes document/chunks/analysis/chat."""
    r = client.post(
        "/api/providers",
        json={
            "name": "CascadeP",
            "provider_type": "openai_compatible",
            "base_url": "https://api.example.com",
            "api_key": "sk-key",
            "model_name": "m",
            "is_default": True,
        },
    )
    provider_id = r.json()["id"]

    r = client.post(
        "/api/topics",
        json={"name": "CascadeT", "provider_id": provider_id},
    )
    topic_id = r.json()["id"]

    from io import BytesIO

    client.post(
        f"/api/topics/{topic_id}/documents/upload",
        files={
            "file": (
                "test.txt",
                BytesIO("第一章 测试\n这是测试。\n".encode("utf-8")),
                "text/plain",
            )
        },
    )
    client.post(f"/api/topics/{topic_id}/parse")

    # Create chat session as well
    client.post(
        f"/api/topics/{topic_id}/chat/sessions",
        json={"title": "Cascade Chat"},
    )

    resp = client.delete(f"/api/topics/{topic_id}")
    assert resp.status_code == 200
    assert resp.json()["deleted"] is True

    # Verify topic is gone
    resp = client.get(f"/api/topics/{topic_id}")
    assert resp.status_code == 404

    # Verify chapter/chunk endpoints return 404
    resp = client.get(f"/api/topics/{topic_id}/chapters")
    assert resp.status_code == 404

    resp = client.get(f"/api/topics/{topic_id}/chunks")
    assert resp.status_code == 404

    # Verify chat sessions return 404
    resp = client.get(f"/api/topics/{topic_id}/chat/sessions")
    assert resp.status_code == 404


def test_bind_provider_to_topic(client):
    """PUT /api/topics/{id}/provider binds a provider to a topic."""
    # Create provider
    r = client.post(
        "/api/providers",
        json={
            "name": "BindP",
            "provider_type": "openai_compatible",
            "base_url": "https://api.example.com",
            "api_key": "sk-key",
            "model_name": "m",
        },
    )
    provider_id = r.json()["id"]

    # Create topic without provider
    r = client.post("/api/topics", json={"name": "Unbound"})
    topic_id = r.json()["id"]
    assert r.json()["provider_id"] is None

    # Bind provider
    r = client.put(
        f"/api/topics/{topic_id}/provider",
        json={"provider_id": provider_id},
    )
    assert r.status_code == 200
    assert r.json()["provider_id"] == provider_id


def test_bind_provider_to_nonexistent_topic_404(client):
    r = client.put(
        "/api/topics/nonexistent/provider",
        json={"provider_id": "some-id"},
    )
    assert r.status_code == 404


def test_bind_nonexistent_provider_404(client):
    r = client.post("/api/topics", json={"name": "T"})
    topic_id = r.json()["id"]

    r = client.put(
        f"/api/topics/{topic_id}/provider",
        json={"provider_id": "nonexistent-id"},
    )
    assert r.status_code == 404


def _mock_topic_analysis(messages, model, temperature, max_tokens, response_format):
    from services.llm_client import LLMResponse

    return LLMResponse(
        content='{"title":"T","source_chunk_ids":[],"evidence_quotes":["测试。"],"confidence":0.9}',
        model="test",
        usage={},
    )


def test_delete_topic_cascades_v2_data(engine):
    """Deleting a topic should cascade-delete v2 AnalysisRun/LocalExtraction/ExtractedAtom."""
    from sqlmodel import Session, select

    from models.analysis_run import AnalysisRun
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.extracted_atom import ExtractedAtom
    from models.local_extraction import LocalExtraction
    from models.model_provider import ModelProvider
    from models.topic import Topic
    from services.topic_service import delete_topic

    with Session(engine) as session:
        prov = ModelProvider(
            name="CascadeV2 P",
            provider_type="openai_compatible",
            base_url="http://mock",
            api_key="sk-m",
            model_name="m",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="CascadeV2", provider_id=prov.id, status="parsed")
        session.add(topic)
        session.flush()
        doc = Document(
            topic_id=topic.id,
            original_filename="t.txt",
            file_size_bytes=10,
            char_count=10,
            status="parsed",
        )
        session.add(doc)
        session.flush()
        ch = Chapter(
            topic_id=topic.id,
            document_id=doc.id,
            chapter_index=0,
            title="Ch1",
            start_char=0,
            end_char=10,
            char_count=10,
        )
        session.add(ch)
        session.flush()
        ck = Chunk(
            topic_id=topic.id,
            document_id=doc.id,
            chapter_id=ch.id,
            chapter_index=0,
            chunk_index=0,
            text="t",
            start_char=0,
            end_char=1,
            char_count=1,
            estimated_tokens=1,
        )
        session.add(ck)
        session.flush()
        ck_id = ck.id
        session.commit()
        tid = topic.id

    # Create v2 run + extraction + atom
    with Session(engine) as session:
        run = AnalysisRun(topic_id=tid, mode="preview")
        session.add(run)
        session.flush()
        rid = run.id
        ext = LocalExtraction(run_id=rid, topic_id=tid, chunk_id=ck_id, status="succeeded")
        session.add(ext)
        session.flush()
        atom = ExtractedAtom(
            run_id=rid,
            topic_id=tid,
            local_extraction_id=ext.id,
            chunk_id=ck_id,
            atom_type="character",
            stable_id="char_x",
        )
        session.add(atom)
        session.commit()

    # Verify v2 rows exist
    with Session(engine) as session:
        assert len(session.exec(select(AnalysisRun).where(AnalysisRun.topic_id == tid)).all()) == 1
        assert (
            len(session.exec(select(LocalExtraction).where(LocalExtraction.topic_id == tid)).all())
            == 1
        )
        assert (
            len(session.exec(select(ExtractedAtom).where(ExtractedAtom.topic_id == tid)).all()) == 1
        )

    # Delete topic
    with Session(engine) as session:
        delete_topic(tid, session)

    # Verify v2 rows are gone
    with Session(engine) as session:
        assert len(session.exec(select(AnalysisRun).where(AnalysisRun.topic_id == tid)).all()) == 0
        assert (
            len(session.exec(select(LocalExtraction).where(LocalExtraction.topic_id == tid)).all())
            == 0
        )
        assert (
            len(session.exec(select(ExtractedAtom).where(ExtractedAtom.topic_id == tid)).all()) == 0
        )
