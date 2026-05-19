"""Tests for v0.2 AnalysisRun orchestrator — mock LLM, real orchestration."""

import io
import json
from unittest.mock import patch

from sqlmodel import Session

from services.analysis_run_service import (
    _execute_run,
    cancel_analysis_run,
    create_analysis_run,
    get_analysis_run_status,
    list_analysis_runs,
)

MOCK_EXTRACTION_JSON = json.dumps({
    "analysis_type": "local_extraction",
    "chunk_id": "chunk-1",
    "local_characters": [
        {"character_id_hint": "zhang", "name": "张三",
         "source_chunk_ids": ["chunk-1"], "evidence_quotes": ["test"], "confidence": 0.9}
    ],
})


def _setup_topic(client, provider=True):
    """Create topic + upload + parse. Optionally create a provider."""
    if provider:
        r = client.post("/api/providers", json={
            "name": "Test Provider", "provider_type": "openai_compatible",
            "base_url": "http://test", "api_key": "sk-test", "model_name": "test-model",
        })
        assert r.status_code in (201, 409)

    r = client.post("/api/topics", json={"name": "Orchestrator Test"})
    assert r.status_code == 201
    topic_id = r.json()["id"]

    prov = client.get("/api/providers").json()["providers"]
    if prov:
        client.put(f"/api/topics/{topic_id}/provider-config", json={
            "provider_id": prov[0]["id"], "model_name_override": "test-model",
        })

    client.post(
        f"/api/topics/{topic_id}/documents/upload",
        files={"file": ("n.txt", io.BytesIO("第一章 测试\n内容。\n".encode()), "text/plain")},
    )
    r = client.post(f"/api/topics/{topic_id}/parse")
    assert r.status_code == 200
    return topic_id


# ── API tests ──


def test_create_run_preview(client):
    topic_id = _setup_topic(client)
    with patch("services.analysis_run_service._execute_run"):
        r = client.post(f"/api/topics/{topic_id}/analysis/runs", json={
            "mode": "preview", "limit_chunks": 2, "requested_types": ["characters"],
        })
        assert r.status_code == 201
        data = r.json()
        assert data["run"]["mode"] == "preview"
        assert data["run"]["status"] == "pending"
        assert "status_url" in data
    client.delete(f"/api/topics/{topic_id}")


def test_create_run_no_provider_409(client):
    r = client.post("/api/topics", json={"name": "No Provider"})
    topic_id = r.json()["id"]
    client.post(f"/api/topics/{topic_id}/documents/upload",
        files={"file": ("n.txt", io.BytesIO("第一章\n".encode()), "text/plain")})
    client.post(f"/api/topics/{topic_id}/parse")
    r = client.post(f"/api/topics/{topic_id}/analysis/runs", json={"mode": "preview"})
    assert r.status_code == 409
    client.delete(f"/api/topics/{topic_id}")


def test_list_runs(client):
    topic_id = _setup_topic(client)
    with patch("services.analysis_run_service._execute_run"):
        client.post(f"/api/topics/{topic_id}/analysis/runs", json={"mode": "preview"})
        client.post(f"/api/topics/{topic_id}/analysis/runs", json={"mode": "full"})
    r = client.get(f"/api/topics/{topic_id}/analysis/runs")
    assert r.status_code == 200
    assert len(r.json()["runs"]) >= 2
    client.delete(f"/api/topics/{topic_id}")


def test_get_run_status(client):
    topic_id = _setup_topic(client)
    with patch("services.analysis_run_service._execute_run"):
        r = client.post(f"/api/topics/{topic_id}/analysis/runs", json={"mode": "preview"})
        run_id = r.json()["run"]["id"]
    r = client.get(f"/api/analysis/runs/{run_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["run"]["id"] == run_id
    assert "extractions" in data
    client.delete(f"/api/topics/{topic_id}")


def test_get_run_not_found_404(client):
    r = client.get("/api/analysis/runs/nonexistent")
    assert r.status_code == 404


def test_cancel_run(client):
    topic_id = _setup_topic(client)
    with patch("services.analysis_run_service._execute_run"):
        r = client.post(f"/api/topics/{topic_id}/analysis/runs", json={"mode": "preview"})
        run_id = r.json()["run"]["id"]
    r = client.post(f"/api/analysis/runs/{run_id}/cancel")
    assert r.status_code == 200
    assert r.json()["run"]["status"] == "cancelled"
    client.delete(f"/api/topics/{topic_id}")


def test_cancel_nonexistent_404(client):
    r = client.post("/api/analysis/runs/nonexistent/cancel")
    assert r.status_code == 404


# ── Service-level tests: mock extraction pipeline ──


class MockExtractionResult:
    def __init__(self, ok=True, content=None, parsed=None, error=None,
                 prompt_tokens=100, completion_tokens=50, total_tokens=150,
                 model_used="mock-v4-flash", retry_count=0):
        self.ok = ok
        self.content_json = content or MOCK_EXTRACTION_JSON
        self.parsed_json = parsed or json.loads(self.content_json)
        self.error = error
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        self.model_used = model_used
        self.retry_count = retry_count
        self.duration_seconds = 0.01


def test_full_mocked_pipeline(engine):
    """End-to-end: create run → mock extractions → check results."""
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.model_provider import ModelProvider
    from models.topic import Topic

    with Session(engine) as session:
        prov = ModelProvider(
            name="Mock P", provider_type="openai_compatible",
            base_url="http://mock", api_key="sk-mock", model_name="mock-model",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="Pipeline", provider_id=prov.id, status="parsed")
        session.add(topic)
        session.flush()
        doc = Document(topic_id=topic.id, original_filename="t.txt",
                       file_size_bytes=100, char_count=50, status="parsed")
        session.add(doc)
        session.flush()
        ch = Chapter(topic_id=topic.id, document_id=doc.id, chapter_index=0,
                     title="Ch1", start_char=0, end_char=50, char_count=50)
        session.add(ch)
        session.flush()
        ck = Chunk(topic_id=topic.id, document_id=doc.id, chapter_id=ch.id,
                   chapter_index=0, chunk_index=0, text="第一章 测试",
                   start_char=0, end_char=10, char_count=10, estimated_tokens=7)
        session.add(ck)
        session.commit()
        tid = topic.id

    with patch(
        "services.local_extraction_worker.run_local_extraction_for_chunk",
        return_value=MockExtractionResult(),
    ) as mock_extract:
        with Session(engine) as session:
            run = create_analysis_run(session, tid, mode="preview", limit_chunks=1)
            run_id = run.id

        _execute_run(run_id, engine=engine)

        assert mock_extract.called, "Mock extraction worker was never called"

        with Session(engine) as session:
            status = get_analysis_run_status(session, run_id)
            assert status is not None
            assert status["run"]["status"] == "succeeded"
            assert status["run"]["extraction_succeeded"] >= 1
            runs = list_analysis_runs(session, tid)
            assert len(runs) >= 1


def test_cancel_during_execution(engine):
    """Cancel a run before extraction starts."""
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.model_provider import ModelProvider
    from models.topic import Topic

    with Session(engine) as session:
        prov = ModelProvider(
            name="Cancel P", provider_type="openai_compatible",
            base_url="http://mock", api_key="sk-mock", model_name="mock-model",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="Cancel", provider_id=prov.id, status="parsed")
        session.add(topic)
        session.flush()
        doc = Document(topic_id=topic.id, original_filename="t.txt",
                       file_size_bytes=10, char_count=10, status="parsed")
        session.add(doc)
        session.flush()
        ch = Chapter(topic_id=topic.id, document_id=doc.id, chapter_index=0,
                     title="Ch1", start_char=0, end_char=10, char_count=10)
        session.add(ch)
        session.flush()
        ck = Chunk(topic_id=topic.id, document_id=doc.id, chapter_id=ch.id,
                   chapter_index=0, chunk_index=0, text="t", start_char=0,
                   end_char=1, char_count=1, estimated_tokens=1)
        session.add(ck)
        session.commit()
        tid = topic.id

    with Session(engine) as session:
        run = create_analysis_run(session, tid, mode="preview", limit_chunks=1)
        run_id = run.id

    with Session(engine) as session:
        cancel_analysis_run(session, run_id)

    with Session(engine) as session:
        status = get_analysis_run_status(session, run_id)
        assert status["run"]["status"] == "cancelled"
