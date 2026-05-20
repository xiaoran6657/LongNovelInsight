"""Tests for v0.2 AnalysisRun orchestrator — mock LLM, real orchestration."""

import io
import json
from unittest.mock import patch

from sqlmodel import Session, select

from services.analysis_run_service import (
    _execute_run,
    cancel_analysis_run,
    create_analysis_run,
    get_analysis_run_status,
    list_analysis_runs,
)

MOCK_EXTRACTION_JSON = json.dumps(
    {
        "analysis_type": "local_extraction",
        "chunk_id": "chunk-1",
        "local_characters": [
            {
                "character_id_hint": "zhang",
                "name": "张三",
                "source_chunk_ids": ["chunk-1"],
                "evidence_quotes": ["test"],
                "confidence": 0.9,
            }
        ],
    }
)


def _setup_topic(client, provider=True):
    """Create topic + upload + parse. Optionally create a provider."""
    if provider:
        r = client.post(
            "/api/providers",
            json={
                "name": "Test Provider",
                "provider_type": "openai_compatible",
                "base_url": "http://test",
                "api_key": "sk-test",
                "model_name": "test-model",
            },
        )
        assert r.status_code in (201, 409)

    r = client.post("/api/topics", json={"name": "Orchestrator Test"})
    assert r.status_code == 201
    topic_id = r.json()["id"]

    prov = client.get("/api/providers").json()["providers"]
    if prov:
        client.put(
            f"/api/topics/{topic_id}/provider-config",
            json={
                "provider_id": prov[0]["id"],
                "model_name_override": "test-model",
            },
        )

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
        r = client.post(
            f"/api/topics/{topic_id}/analysis/runs",
            json={
                "mode": "preview",
                "limit_chunks": 2,
                "requested_types": ["characters"],
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["run"]["mode"] == "preview"
        assert data["run"]["status"] == "pending"
        assert "status_url" in data
    client.delete(f"/api/topics/{topic_id}")


def test_create_run_no_provider_409(client):
    r = client.post("/api/topics", json={"name": "No Provider"})
    topic_id = r.json()["id"]
    client.post(
        f"/api/topics/{topic_id}/documents/upload",
        files={"file": ("n.txt", io.BytesIO("第一章\n".encode()), "text/plain")},
    )
    client.post(f"/api/topics/{topic_id}/parse")
    r = client.post(f"/api/topics/{topic_id}/analysis/runs", json={"mode": "preview"})
    assert r.status_code == 409
    client.delete(f"/api/topics/{topic_id}")


def test_create_run_no_chunks_409(client):
    r = client.post("/api/topics", json={"name": "No Chunks"})
    topic_id = r.json()["id"]
    # Create provider so topic has one
    r = client.post(
        "/api/providers",
        json={
            "name": "P",
            "provider_type": "openai_compatible",
            "base_url": "http://t",
            "api_key": "sk",
            "model_name": "m",
        },
    )
    prov_id = r.json()["id"]
    client.put(
        f"/api/topics/{topic_id}/provider-config",
        json={
            "provider_id": prov_id,
        },
    )
    # Don't upload/parse — no chunks
    r = client.post(f"/api/topics/{topic_id}/analysis/runs", json={"mode": "preview"})
    assert r.status_code == 409
    client.delete(f"/api/topics/{topic_id}")


def test_create_run_invalid_mode_422(client):
    topic_id = _setup_topic(client)
    with patch("services.analysis_run_service._execute_run"):
        r = client.post(f"/api/topics/{topic_id}/analysis/runs", json={"mode": "invalid_mode"})
        assert r.status_code == 422
    client.delete(f"/api/topics/{topic_id}")


def test_create_run_invalid_range_422(client):
    topic_id = _setup_topic(client)
    r = client.post(
        f"/api/topics/{topic_id}/analysis/runs",
        json={
            "mode": "range",
            "chunk_index_start": 5,
            "chunk_index_end": 2,
        },
    )
    assert r.status_code == 422
    client.delete(f"/api/topics/{topic_id}")


def test_list_runs(client):
    topic_id = _setup_topic(client)
    topic_id2 = _setup_topic(client)
    with patch("services.analysis_run_service._execute_run"):
        client.post(f"/api/topics/{topic_id}/analysis/runs", json={"mode": "preview"})
        client.post(f"/api/topics/{topic_id2}/analysis/runs", json={"mode": "full"})
    r = client.get(f"/api/topics/{topic_id}/analysis/runs")
    assert r.status_code == 200
    assert len(r.json()["runs"]) >= 1
    r2 = client.get(f"/api/topics/{topic_id2}/analysis/runs")
    assert r2.status_code == 200
    assert len(r2.json()["runs"]) >= 1
    client.delete(f"/api/topics/{topic_id}")
    client.delete(f"/api/topics/{topic_id2}")


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
    assert "merge" in data
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
    def __init__(
        self,
        ok=True,
        content=None,
        parsed=None,
        error=None,
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        model_used="mock-v4-flash",
        retry_count=0,
    ):
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
        self.status_code = None
        self.warnings = []


def test_full_mocked_pipeline(engine):
    """End-to-end: create run -> mock extractions -> check results with merge."""
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.model_provider import ModelProvider
    from models.topic import Topic

    with Session(engine) as session:
        prov = ModelProvider(
            name="Mock P",
            provider_type="openai_compatible",
            base_url="http://mock",
            api_key="sk-mock",
            model_name="mock-model",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="Pipeline", provider_id=prov.id, status="parsed")
        session.add(topic)
        session.flush()
        doc = Document(
            topic_id=topic.id,
            original_filename="t.txt",
            file_size_bytes=100,
            char_count=50,
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
            end_char=50,
            char_count=50,
        )
        session.add(ch)
        session.flush()
        ck = Chunk(
            topic_id=topic.id,
            document_id=doc.id,
            chapter_id=ch.id,
            chapter_index=0,
            chunk_index=0,
            text="第一章 测试",
            start_char=0,
            end_char=10,
            char_count=10,
            estimated_tokens=7,
        )
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
            assert status["run"]["merge_succeeded"] >= 1
            assert "merge" in status
            runs = list_analysis_runs(session, tid)
            assert len(runs) >= 1


def test_range_selection_executes_correct_chunks(engine):
    """Range mode: only chunks in range should be extracted."""
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.model_provider import ModelProvider
    from models.topic import Topic

    with Session(engine) as session:
        prov = ModelProvider(
            name="Range P",
            provider_type="openai_compatible",
            base_url="http://mock",
            api_key="sk-m",
            model_name="m",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="Range", provider_id=prov.id, status="parsed")
        session.add(topic)
        session.flush()
        doc = Document(
            topic_id=topic.id,
            original_filename="t.txt",
            file_size_bytes=100,
            char_count=50,
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
            end_char=50,
            char_count=50,
        )
        session.add(ch)
        session.flush()
        # Create chunks 0, 1, 2
        chunk_ids = []
        for i in range(3):
            ck = Chunk(
                topic_id=topic.id,
                document_id=doc.id,
                chapter_id=ch.id,
                chapter_index=0,
                chunk_index=i,
                text=f"text_{i}",
                start_char=i * 10,
                end_char=(i + 1) * 10,
                char_count=10,
                estimated_tokens=7,
            )
            session.add(ck)
            session.flush()
            chunk_ids.append(ck.id)
        session.commit()
        tid = topic.id

    def mock_extract(**kwargs):
        return MockExtractionResult()

    with patch(
        "services.local_extraction_worker.run_local_extraction_for_chunk",
        side_effect=mock_extract,
    ) as mock_extract:
        with Session(engine) as session:
            run = create_analysis_run(
                session, tid, mode="range", chunk_index_start=1, chunk_index_end=1
            )
            run_id = run.id

        _execute_run(run_id, engine=engine)

        # Should only have called with chunk_index=1
        called_chunk_ids = {
            kw["chunk_id"] for call in mock_extract.call_args_list for kw in [call.kwargs]
        }
        assert chunk_ids[1] in called_chunk_ids
        assert chunk_ids[0] not in called_chunk_ids
        assert chunk_ids[2] not in called_chunk_ids


def test_partial_extraction_failure(engine):
    """One chunk fails, one succeeds -> partial_success."""
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.model_provider import ModelProvider
    from models.topic import Topic

    with Session(engine) as session:
        prov = ModelProvider(
            name="Partial P",
            provider_type="openai_compatible",
            base_url="http://mock",
            api_key="sk-m",
            model_name="m",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="Partial", provider_id=prov.id, status="parsed")
        session.add(topic)
        session.flush()
        doc = Document(
            topic_id=topic.id,
            original_filename="t.txt",
            file_size_bytes=100,
            char_count=50,
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
            end_char=50,
            char_count=50,
        )
        session.add(ch)
        session.flush()
        for i in range(2):
            ck = Chunk(
                topic_id=topic.id,
                document_id=doc.id,
                chapter_id=ch.id,
                chapter_index=0,
                chunk_index=i,
                text=f"text_{i}",
                start_char=i * 10,
                end_char=(i + 1) * 10,
                char_count=10,
                estimated_tokens=7,
            )
            session.add(ck)
        session.commit()
        tid = topic.id

    call_count = [0]

    def mock_extract(**kwargs):
        call_count[0] += 1
        if call_count[0] == 1:
            return MockExtractionResult(
                ok=False, error="intentional failure", content=None, parsed=None
            )
        return MockExtractionResult()

    with patch(
        "services.local_extraction_worker.run_local_extraction_for_chunk",
        side_effect=mock_extract,
    ):
        with Session(engine) as session:
            run = create_analysis_run(session, tid, mode="full")
            run_id = run.id

        _execute_run(run_id, engine=engine)

        with Session(engine) as session:
            status = get_analysis_run_status(session, run_id)
            assert status["run"]["status"] == "partial_success"
            assert status["run"]["extraction_succeeded"] == 1
            assert status["run"]["extraction_failed"] == 1


def test_cancel_during_execution(engine):
    """Cancel a run before extraction starts."""
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.model_provider import ModelProvider
    from models.topic import Topic

    with Session(engine) as session:
        prov = ModelProvider(
            name="Cancel P",
            provider_type="openai_compatible",
            base_url="http://mock",
            api_key="sk-mock",
            model_name="mock-model",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="Cancel", provider_id=prov.id, status="parsed")
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


def test_cancel_before_merge_not_called(engine):
    """Cancel before merge stage -> merge should not be called."""
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.model_provider import ModelProvider
    from models.topic import Topic

    with Session(engine) as session:
        prov = ModelProvider(
            name="CancelMerge P",
            provider_type="openai_compatible",
            base_url="http://mock",
            api_key="sk-m",
            model_name="m",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="CancelMerge", provider_id=prov.id, status="parsed")
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
        session.commit()
        tid = topic.id

    run_id_holder = {}

    def mock_extract(**kwargs):
        # Cancel mid-flight using the run_id from holder
        with Session(engine) as session:
            from services.analysis_run_service import cancel_analysis_run as cancel_fn

            cancel_fn(session, run_id_holder["id"])
        return MockExtractionResult()

    with patch(
        "services.local_extraction_worker.run_local_extraction_for_chunk",
        side_effect=mock_extract,
    ):
        with Session(engine) as session:
            run = create_analysis_run(session, tid, mode="preview", limit_chunks=1)
            run_id_holder["id"] = run.id

        with patch("services.merge_service.run_merge_stage") as mock_merge:
            _execute_run(run_id_holder["id"], engine=engine)
            mock_merge.assert_not_called()

    with Session(engine) as session:
        status = get_analysis_run_status(session, run_id_holder["id"])
        assert status["run"]["status"] == "cancelled"


def test_run_exception_failed(engine):
    """Unhandled exception in _execute_run should mark run as failed."""
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.model_provider import ModelProvider
    from models.topic import Topic

    with Session(engine) as session:
        prov = ModelProvider(
            name="Exc P",
            provider_type="openai_compatible",
            base_url="http://mock",
            api_key="sk-m",
            model_name="m",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="Exc", provider_id=prov.id, status="parsed")
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
        session.commit()
        tid = topic.id

    with Session(engine) as session:
        run = create_analysis_run(session, tid, mode="preview", limit_chunks=1)
        run_id = run.id

    # Inject a failure that happens before extraction
    with patch(
        "services.local_extraction_worker.run_local_extraction_for_chunk",
        side_effect=RuntimeError("simulated crash"),
    ):
        _execute_run(run_id, engine=engine)

    with Session(engine) as session:
        status = get_analysis_run_status(session, run_id)
        # Should be failed, not running
        assert status["run"]["status"] == "failed"
        assert status["run"]["error_message"] is not None


def test_topic_provider_config_api_key_used(engine):
    """TopicProviderConfig.provider_id should be used for api_key resolution."""
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.model_provider import ModelProvider
    from models.topic import Topic
    from models.topic_provider_config import TopicProviderConfig

    with Session(engine) as session:
        # Default provider (should NOT be used)
        default_p = ModelProvider(
            name="Default P",
            provider_type="openai_compatible",
            base_url="http://default",
            api_key="sk-default",
            model_name="default-m",
            is_default=True,
        )
        session.add(default_p)
        # Topic-level provider (should be used)
        topic_p = ModelProvider(
            name="Topic P",
            provider_type="openai_compatible",
            base_url="http://topic",
            api_key="sk-topic-specific",
            model_name="topic-m",
        )
        session.add(topic_p)
        session.flush()

        topic = Topic(name="TPC Key", status="parsed")  # No provider_id on topic!
        session.add(topic)
        session.flush()

        # TopicProviderConfig points to topic_p
        tpc = TopicProviderConfig(topic_id=topic.id, provider_id=topic_p.id)
        session.add(tpc)
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
        session.commit()
        tid = topic.id

    captured_keys = []

    def mock_extract(**kwargs):
        captured_keys.append(kwargs.get("api_key", ""))
        return MockExtractionResult()

    with patch(
        "services.local_extraction_worker.run_local_extraction_for_chunk",
        side_effect=mock_extract,
    ):
        with Session(engine) as session:
            run = create_analysis_run(session, tid, mode="preview", limit_chunks=1)
            run_id = run.id

        _execute_run(run_id, engine=engine)

    assert len(captured_keys) > 0
    assert captured_keys[0] == "sk-topic-specific"


def test_error_message_does_not_leak_api_key(engine):
    """Error messages should not contain the api_key."""
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.model_provider import ModelProvider
    from models.topic import Topic

    with Session(engine) as session:
        prov = ModelProvider(
            name="Leak P",
            provider_type="openai_compatible",
            base_url="http://mock",
            api_key="sk-secret-key-12345",
            model_name="m",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="Leak", provider_id=prov.id, status="parsed")
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
        session.commit()
        tid = topic.id

    with Session(engine) as session:
        run = create_analysis_run(session, tid, mode="preview", limit_chunks=1)
        run_id = run.id

    # Simulate runtime error that might contain api_key
    with patch(
        "services.local_extraction_worker.run_local_extraction_for_chunk",
        side_effect=RuntimeError("auth with sk-secret-key-12345 failed"),
    ):
        _execute_run(run_id, engine=engine)

    with Session(engine) as session:
        status = get_analysis_run_status(session, run_id)
        err = status["run"]["error_message"] or ""
        assert "sk-secret-key-12345" not in err


def test_invalid_requested_types_422(client):
    """POST with unknown requested_types should return 422."""
    topic_id = _setup_topic(client)
    r = client.post(
        f"/api/topics/{topic_id}/analysis/runs",
        json={"mode": "preview", "requested_types": ["bad_type", "also_bad"]},
    )
    assert r.status_code == 422
    client.delete(f"/api/topics/{topic_id}")


def test_all_extraction_failure(engine):
    """All chunks fail extraction -> run.status == failed, DB has failed LocalExtractions."""
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.local_extraction import LocalExtraction
    from models.model_provider import ModelProvider
    from models.topic import Topic

    with Session(engine) as session:
        prov = ModelProvider(
            name="AllFail P",
            provider_type="openai_compatible",
            base_url="http://mock",
            api_key="sk-m",
            model_name="m",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="AllFail", provider_id=prov.id, status="parsed")
        session.add(topic)
        session.flush()
        doc = Document(
            topic_id=topic.id,
            original_filename="t.txt",
            file_size_bytes=100,
            char_count=50,
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
            end_char=50,
            char_count=50,
        )
        session.add(ch)
        session.flush()
        for i in range(2):
            ck = Chunk(
                topic_id=topic.id,
                document_id=doc.id,
                chapter_id=ch.id,
                chapter_index=0,
                chunk_index=i,
                text=f"text_{i}",
                start_char=i * 10,
                end_char=(i + 1) * 10,
                char_count=10,
                estimated_tokens=7,
            )
            session.add(ck)
        session.commit()
        tid = topic.id

    with patch(
        "services.local_extraction_worker.run_local_extraction_for_chunk",
        return_value=MockExtractionResult(ok=False, error="failure", content=None, parsed=None),
    ):
        with Session(engine) as session:
            run = create_analysis_run(session, tid, mode="full")
            run_id = run.id
        _execute_run(run_id, engine=engine)

    with Session(engine) as session:
        status = get_analysis_run_status(session, run_id)
        assert status["run"]["status"] == "failed"
        exts = session.exec(select(LocalExtraction).where(LocalExtraction.run_id == run_id)).all()
        assert len(exts) == 2
        for e in exts:
            assert e.status == "failed"


def test_worker_exception_saves_failed_local_extraction(engine):
    """RuntimeError in worker -> failed LocalExtraction row persisted in DB."""
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.local_extraction import LocalExtraction
    from models.model_provider import ModelProvider
    from models.topic import Topic

    with Session(engine) as session:
        prov = ModelProvider(
            name="WrkExc P",
            provider_type="openai_compatible",
            base_url="http://mock",
            api_key="sk-m",
            model_name="m",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="WrkExc", provider_id=prov.id, status="parsed")
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
        session.commit()
        tid = topic.id

    with Session(engine) as session:
        run = create_analysis_run(session, tid, mode="preview", limit_chunks=1)
        run_id = run.id

    with patch(
        "services.local_extraction_worker.run_local_extraction_for_chunk",
        side_effect=RuntimeError("worker crash"),
    ):
        _execute_run(run_id, engine=engine)

    with Session(engine) as session:
        status = get_analysis_run_status(session, run_id)
        assert status["run"]["status"] in ("failed", "partial_success")
        exts = session.exec(select(LocalExtraction).where(LocalExtraction.run_id == run_id)).all()
        assert len(exts) == 1
        assert exts[0].status == "failed"
        assert exts[0].error_message is not None


def test_fail_run_masks_api_key(engine):
    """_fail_run() should mask all known api_keys in error_message."""
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.model_provider import ModelProvider
    from models.topic import Topic

    with Session(engine) as session:
        prov = ModelProvider(
            name="FailRunMask P",
            provider_type="openai_compatible",
            base_url="http://mock",
            api_key="sk-very-secret-key",
            model_name="m",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="FailRunMask", provider_id=prov.id, status="parsed")
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
        session.commit()
        tid = topic.id

    with Session(engine) as session:
        run = create_analysis_run(session, tid, mode="preview", limit_chunks=1)
        run_id = run.id

    # Crash ThreadPoolExecutor so the error propagates to _fail_run
    with patch(
        "services.analysis_run_service.ThreadPoolExecutor",
        side_effect=RuntimeError("Connection refused using key sk-very-secret-key"),
    ):
        _execute_run(run_id, engine=engine)

    with Session(engine) as session:
        status = get_analysis_run_status(session, run_id)
        err = status["run"]["error_message"] or ""
        assert "sk-very-secret-key" not in err


def test_full_pipeline_e2e(engine):
    """Full v2 pipeline: extraction → merge → final outputs all succeed."""
    from models.analysis_output import AnalysisOutput
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.model_provider import ModelProvider
    from models.topic import Topic

    with Session(engine) as session:
        prov = ModelProvider(
            name="E2E P",
            provider_type="openai_compatible",
            base_url="http://mock",
            api_key="sk-m",
            model_name="mock-model",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="E2E", provider_id=prov.id, status="parsed")
        session.add(topic)
        session.flush()
        doc = Document(
            topic_id=topic.id,
            original_filename="t.txt",
            file_size_bytes=100,
            char_count=50,
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
            end_char=50,
            char_count=50,
        )
        session.add(ch)
        session.flush()
        ck = Chunk(
            topic_id=topic.id,
            document_id=doc.id,
            chapter_id=ch.id,
            chapter_index=0,
            chunk_index=0,
            text="第一章 测试",
            start_char=0,
            end_char=10,
            char_count=10,
            estimated_tokens=7,
        )
        session.add(ck)
        session.commit()
        tid = topic.id

    with patch(
        "services.local_extraction_worker.run_local_extraction_for_chunk",
        return_value=MockExtractionResult(),
    ):
        with Session(engine) as session:
            run = create_analysis_run(session, tid, mode="preview", limit_chunks=1)
            run_id = run.id
        _execute_run(run_id, engine=engine)

    with Session(engine) as session:
        status = get_analysis_run_status(session, run_id)
        assert status["run"]["status"] == "succeeded"
        assert status["run"]["extraction_succeeded"] == 1
        assert status["run"]["merge_succeeded"] >= 1
        assert status["run"]["final_succeeded"] >= 1
        assert "final" in status
        assert len(status["final"]["outputs"]) >= 1

        # Verify final AnalysisOutput rows exist with correct output_types
        outputs = session.exec(select(AnalysisOutput).where(AnalysisOutput.run_id == run_id)).all()
        final_types = {o.output_type for o in outputs if not o.output_type.startswith("merge_")}
        assert "characters" in final_types or "overview" in final_types


def test_pipeline_metadata_has_stage_timings(engine):
    """metadata_json should contain stage_timings after successful run."""
    from models.analysis_run import AnalysisRun
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.model_provider import ModelProvider
    from models.topic import Topic

    with Session(engine) as session:
        prov = ModelProvider(
            name="Timing P",
            provider_type="openai_compatible",
            base_url="http://mock",
            api_key="sk-m",
            model_name="m",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="Timing", provider_id=prov.id, status="parsed")
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
        session.commit()
        tid = topic.id

    with patch(
        "services.local_extraction_worker.run_local_extraction_for_chunk",
        return_value=MockExtractionResult(),
    ):
        with Session(engine) as session:
            run = create_analysis_run(session, tid, mode="preview", limit_chunks=1)
            run_id = run.id
        _execute_run(run_id, engine=engine)

    with Session(engine) as session:
        run = session.get(AnalysisRun, run_id)
        metadata = run.get_metadata()
        assert "stage_timings" in metadata
        timings = metadata["stage_timings"]
        assert "extraction" in timings
        assert "merge" in timings
        assert "final" in timings
        assert timings["extraction"] >= 0
        assert "usage_by_stage" in metadata
        assert "failed_merge_types" in metadata
        assert "failed_final_types" in metadata


def test_legacy_status_includes_latest_v2_run(client):
    """GET /api/topics/{id}/analysis/status should include latest_v2_run."""
    topic_id = _setup_topic(client)
    with patch("services.analysis_run_service._execute_run"):
        client.post(f"/api/topics/{topic_id}/analysis/runs", json={"mode": "preview"})
    r = client.get(f"/api/topics/{topic_id}/analysis/status")
    assert r.status_code == 200
    data = r.json()
    assert "latest_v2_run" in data
    assert "v2_available" in data
    assert data["v2_available"] is True
    if data["latest_v2_run"]:
        assert data["latest_v2_run"]["mode"] == "preview"
    client.delete(f"/api/topics/{topic_id}")


def test_create_run_while_active_returns_409(client):
    """Creating a second v2 run while one is pending should return 409."""
    topic_id = _setup_topic(client)
    with patch("services.analysis_run_service._execute_run"):
        r = client.post(f"/api/topics/{topic_id}/analysis/runs", json={"mode": "preview"})
        assert r.status_code == 201
        # Second run should be rejected
        r2 = client.post(f"/api/topics/{topic_id}/analysis/runs", json={"mode": "preview"})
        assert r2.status_code == 409
    client.delete(f"/api/topics/{topic_id}")


def test_legacy_pipeline_v2_active_run_409(client):
    """Legacy pipeline=v2 should also be blocked by active-run guard."""
    topic_id = _setup_topic(client)
    with patch("services.analysis_run_service._execute_run"):
        r = client.post(f"/api/topics/{topic_id}/analysis/runs", json={"mode": "preview"})
        assert r.status_code == 201
    r2 = client.post(f"/api/topics/{topic_id}/analysis/run?pipeline=v2")
    assert r2.status_code == 409
    client.delete(f"/api/topics/{topic_id}")


def test_create_run_after_completed_allowed(engine):
    """A completed/failed/cancelled run should not block a new one."""
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.model_provider import ModelProvider
    from models.topic import Topic

    with Session(engine) as session:
        prov = ModelProvider(
            name="CompleteBlock P",
            provider_type="openai_compatible",
            base_url="http://mock",
            api_key="sk-m",
            model_name="m",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="CompleteBlock", provider_id=prov.id, status="parsed")
        session.add(topic)
        session.flush()
        doc = Document(
            topic_id=topic.id,
            original_filename="t.txt",
            file_size_bytes=100,
            char_count=50,
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
            end_char=50,
            char_count=50,
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
        session.commit()
        tid = topic.id

    with patch(
        "services.local_extraction_worker.run_local_extraction_for_chunk",
        return_value=MockExtractionResult(),
    ):
        with Session(engine) as session:
            run = create_analysis_run(session, tid, mode="preview", limit_chunks=1)
            run_id = run.id
        _execute_run(run_id, engine=engine)

    # After completed, a new run should be allowed
    with Session(engine) as session:
        run2 = create_analysis_run(session, tid, mode="preview", limit_chunks=1)
        assert run2.id != run_id
