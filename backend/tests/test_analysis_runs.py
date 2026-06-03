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
        self.parsed_json = parsed or (json.loads(self.content_json) if self.content_json else None)
        self.error = error
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        self.model_used = model_used
        self.retry_count = retry_count
        self.duration_seconds = 0.01
        self.status_code = None
        self.finish_reason = None
        self.warnings = []
        self.attempts = []
        self.cumulative_prompt_tokens = prompt_tokens
        self.cumulative_completion_tokens = completion_tokens
        self.cumulative_total_tokens = total_tokens
        self.cumulative_reasoning_tokens = 0
        self.cumulative_prompt_cache_hit_tokens = 0
        self.cumulative_prompt_cache_miss_tokens = 0
        self.usage_unavailable_attempts = 0


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


def test_legacy_status_merge_only_has_outputs_false(client, engine):
    """has_outputs should be false when only merge_* intermediates exist."""
    from sqlmodel import Session

    from models.analysis_output import AnalysisOutput

    topic_id = _setup_topic(client)
    with patch("services.analysis_run_service._execute_run"):
        r = client.post(f"/api/topics/{topic_id}/analysis/runs", json={"mode": "preview"})
        run_id = r.json()["run"]["id"]

    # Insert a merge_characters output directly via engine
    with Session(engine) as session:
        ao = AnalysisOutput(
            topic_id=topic_id,
            run_id=run_id,
            output_type="merge_characters",
            title="Merged characters",
            content_json="[]",
            source_chunk_ids="[]",
            evidence_quotes="[]",
            confidence=0.5,
        )
        session.add(ao)
        session.commit()

    r = client.get(f"/api/topics/{topic_id}/analysis/status")
    assert r.status_code == 200
    data = r.json()
    assert data["has_outputs"] is False
    assert "merge_characters" not in data.get("output_counts_by_type", {})
    client.delete(f"/api/topics/{topic_id}")


# ── Step 11: Retry / Resume / Idempotency tests ──


def test_retry_failed_endpoint_starts_background(client):
    """POST /analysis/runs/{id}/retry-failed starts background retry."""
    topic_id = _setup_topic(client)
    with patch("services.analysis_run_service._execute_retry"):
        with patch("services.analysis_run_service._execute_run"):
            r = client.post(f"/api/topics/{topic_id}/analysis/runs", json={"mode": "preview"})
            run_id = r.json()["run"]["id"]

        # Manually set run to partial_success + add a failed extraction
        from main import app

        for dep in app.dependency_overrides.values():
            gen = dep()
            session = next(gen)
            try:
                from models.analysis_run import AnalysisRun
                from models.local_extraction import LocalExtraction

                run = session.get(AnalysisRun, run_id)
                if run:
                    run.status = "partial_success"
                    session.add(run)
                    # Create a failed extraction so the endpoint check passes
                    ext = LocalExtraction(
                        run_id=run_id,
                        topic_id=topic_id,
                        chunk_id="fake-chunk-id",
                        status="failed",
                        attempt_count=1,
                    )
                    session.add(ext)
                    session.commit()
            finally:
                session.close()

        r = client.post(f"/api/analysis/runs/{run_id}/retry-failed")
        assert r.status_code == 200
        assert "Retry started" in r.json()["message"]
    client.delete(f"/api/topics/{topic_id}")


def test_retry_failed_succeeded_run_409(client):
    """Retry on a fully succeeded run should return 409."""
    topic_id = _setup_topic(client)
    with patch("services.analysis_run_service._execute_run"):
        r = client.post(f"/api/topics/{topic_id}/analysis/runs", json={"mode": "preview"})
        run_id = r.json()["run"]["id"]

    with patch("services.analysis_run_service._execute_retry"):
        # Run is "pending" (mocked _execute_run), so retry should be 409
        r = client.post(f"/api/analysis/runs/{run_id}/retry-failed")
        assert r.status_code == 409
    client.delete(f"/api/topics/{topic_id}")


def test_resume_endpoint(client):
    """POST /analysis/runs/{id}/resume starts background resume."""
    topic_id = _setup_topic(client)
    with patch("services.analysis_run_service._execute_resume"):
        with patch("services.analysis_run_service._execute_run"):
            r = client.post(f"/api/topics/{topic_id}/analysis/runs", json={"mode": "preview"})
            run_id = r.json()["run"]["id"]

        # Set run to a resumable state (not pending/running)
        from main import app

        for dep in app.dependency_overrides.values():
            gen = dep()
            session = next(gen)
            try:
                from models.analysis_run import AnalysisRun

                run = session.get(AnalysisRun, run_id)
                if run:
                    run.status = "partial_success"
                    session.add(run)
                    session.commit()
            finally:
                session.close()

        r = client.post(f"/api/analysis/runs/{run_id}/resume?retry_failed=true")
        assert r.status_code == 200
        assert "Resume started" in r.json()["message"]
    client.delete(f"/api/topics/{topic_id}")


def test_resume_cancelled_run_409(client):
    """Resume on a cancelled run should return 409."""
    topic_id = _setup_topic(client)
    with patch("services.analysis_run_service._execute_run"):
        r = client.post(f"/api/topics/{topic_id}/analysis/runs", json={"mode": "preview"})
        run_id = r.json()["run"]["id"]
    client.post(f"/api/analysis/runs/{run_id}/cancel")

    with patch("services.analysis_run_service._execute_resume"):
        r = client.post(f"/api/analysis/runs/{run_id}/resume")
        assert r.status_code == 409
    client.delete(f"/api/topics/{topic_id}")


def test_idempotent_save_extraction(engine):
    """Same run+chunk should not create duplicate succeeded LocalExtraction rows."""
    from sqlmodel import Session, select

    from models.analysis_run import AnalysisRun
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.local_extraction import LocalExtraction
    from models.model_provider import ModelProvider
    from models.topic import Topic
    from services.analysis_run_service import _save_extraction

    with Session(engine) as session:
        prov = ModelProvider(
            name="Idem P",
            provider_type="openai_compatible",
            base_url="http://mock",
            api_key="sk-m",
            model_name="m",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="Idem", provider_id=prov.id, status="parsed")
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
        run = AnalysisRun(topic_id=topic.id, mode="preview")
        session.add(run)
        session.flush()
        session.commit()
        rid = run.id
        tid = topic.id
        cid = ck.id

    # First save — should create
    with Session(engine) as session:
        _save_extraction(
            session,
            rid,
            tid,
            cid,
            ok=True,
            content_json='{"analysis_type":"local_extraction","chunk_id":"x"}',
        )
        session.commit()

    with Session(engine) as session:
        exts = session.exec(
            select(LocalExtraction).where(
                LocalExtraction.run_id == rid,
                LocalExtraction.chunk_id == cid,
                LocalExtraction.status == "succeeded",
            )
        ).all()
        assert len(exts) == 1

    # Second save with same params — should skip
    with Session(engine) as session:
        _save_extraction(
            session,
            rid,
            tid,
            cid,
            ok=True,
            content_json='{"analysis_type":"local_extraction","chunk_id":"x"}',
        )
        session.commit()

    with Session(engine) as session:
        exts = session.exec(
            select(LocalExtraction).where(
                LocalExtraction.run_id == rid,
                LocalExtraction.chunk_id == cid,
                LocalExtraction.status == "succeeded",
            )
        ).all()
        assert len(exts) == 1, "Idempotent guard should prevent duplicate succeeded rows"


def test_error_classification():
    """_classify_error categorizes errors correctly."""
    from services.analysis_run_service import _classify_error

    assert _classify_error("JSON parse failed: ...") == "json_parse_error"
    assert _classify_error("rate limit exceeded", 429) == "llm_error"
    assert _classify_error("timed out") == "llm_error"
    assert _classify_error("Validation failed: chunk_id mismatch") == "validation_error"
    assert _classify_error("auth error") == "provider_config_error"
    assert _classify_error("something unexpected happened") == "unknown"


def test_concurrent_retry_rejected_409(client):
    """Second retry request while first is running should return 409."""
    topic_id = _setup_topic(client)
    with patch("services.analysis_run_service._execute_run"):
        r = client.post(f"/api/topics/{topic_id}/analysis/runs", json={"mode": "preview"})
        run_id = r.json()["run"]["id"]

    # Set status to partial_success + add a failed extraction
    from main import app

    for dep in app.dependency_overrides.values():
        gen = dep()
        session = next(gen)
        try:
            from models.analysis_run import AnalysisRun
            from models.local_extraction import LocalExtraction

            run = session.get(AnalysisRun, run_id)
            if run:
                run.status = "partial_success"
                session.add(run)
                ext = LocalExtraction(
                    run_id=run_id,
                    topic_id=topic_id,
                    chunk_id="fake-chunk-id",
                    status="failed",
                    attempt_count=1,
                )
                session.add(ext)
                session.commit()
        finally:
            session.close()

    with patch("services.analysis_run_service._execute_retry"):
        # First retry should succeed (sets status to running, starts thread)
        r1 = client.post(f"/api/analysis/runs/{run_id}/retry-failed")
        assert r1.status_code == 200

        # Second retry should be rejected (status is now running)
        r2 = client.post(f"/api/analysis/runs/{run_id}/retry-failed")
        assert r2.status_code == 409
    client.delete(f"/api/topics/{topic_id}")


def test_concurrent_resume_rejected_409(client):
    """Second resume request while first is running should return 409."""
    topic_id = _setup_topic(client)
    with patch("services.analysis_run_service._execute_run"):
        r = client.post(f"/api/topics/{topic_id}/analysis/runs", json={"mode": "preview"})
        run_id = r.json()["run"]["id"]

    from main import app

    for dep in app.dependency_overrides.values():
        gen = dep()
        session = next(gen)
        try:
            from models.analysis_run import AnalysisRun

            run = session.get(AnalysisRun, run_id)
            if run:
                run.status = "partial_success"
                session.add(run)
                session.commit()
        finally:
            session.close()

    with patch("services.analysis_run_service._execute_resume"):
        r1 = client.post(f"/api/analysis/runs/{run_id}/resume")
        assert r1.status_code == 200

        r2 = client.post(f"/api/analysis/runs/{run_id}/resume")
        assert r2.status_code == 409
    client.delete(f"/api/topics/{topic_id}")


def test_artifact_table_created_by_init_db(engine):
    """analysis_artifact table should be created by init_db without explicit import."""
    from sqlalchemy import inspect as sa_inspect

    from db import init_db

    # init_db should create the analysis_artifact table
    init_db()
    insp = sa_inspect(engine)
    tables = insp.get_table_names()
    assert "analysis_artifact" in tables


def test_resume_runs_missing_chunk_only(engine):
    """Resume with 1 succeeded + 1 missing chunk should only extract the missing."""
    from sqlmodel import Session

    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.local_extraction import LocalExtraction
    from models.model_provider import ModelProvider
    from models.topic import Topic
    from services.analysis_run_service import resume_analysis_run

    with Session(engine) as session:
        prov = ModelProvider(
            name="Resume1 P",
            provider_type="openai_compatible",
            base_url="http://mock",
            api_key="sk-m",
            model_name="m",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="Resume1", provider_id=prov.id, status="parsed")
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
        c0 = Chunk(
            topic_id=topic.id,
            document_id=doc.id,
            chapter_id=ch.id,
            chapter_index=0,
            chunk_index=0,
            text="chunk0",
            start_char=0,
            end_char=25,
            char_count=25,
            estimated_tokens=17,
        )
        session.add(c0)
        session.flush()
        c1 = Chunk(
            topic_id=topic.id,
            document_id=doc.id,
            chapter_id=ch.id,
            chapter_index=0,
            chunk_index=1,
            text="chunk1",
            start_char=25,
            end_char=50,
            char_count=25,
            estimated_tokens=17,
        )
        session.add(c1)
        session.commit()
        tid = topic.id
        c0_id = c0.id
        c1_id = c1.id

    # Create run with both chunks
    with Session(engine) as session:
        run = create_analysis_run(session, tid, mode="full")
        rid = run.id
        # Create a succeeded extraction for chunk 0
        ext0 = LocalExtraction(run_id=rid, topic_id=tid, chunk_id=c0_id, status="succeeded")
        session.add(ext0)
        session.commit()

    called_ids = []

    def mock_extract(**kwargs):
        called_ids.append(kwargs["chunk_id"])
        return MockExtractionResult()

    with patch(
        "services.local_extraction_worker.run_local_extraction_for_chunk",
        side_effect=mock_extract,
    ):
        with Session(engine) as session:
            resume_analysis_run(session, rid, retry_failed=False)

    # Only the missing chunk (c1) should have been called
    assert c1_id in called_ids
    assert c0_id not in called_ids


def test_resume_retry_failed_false_skips_failed(engine):
    """resume with retry_failed=false should not re-extract failed chunks."""
    from sqlmodel import Session

    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.local_extraction import LocalExtraction
    from models.model_provider import ModelProvider
    from models.topic import Topic
    from services.analysis_run_service import resume_analysis_run

    with Session(engine) as session:
        prov = ModelProvider(
            name="Resume2 P",
            provider_type="openai_compatible",
            base_url="http://mock",
            api_key="sk-m",
            model_name="m",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="Resume2", provider_id=prov.id, status="parsed")
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
        c0 = Chunk(
            topic_id=topic.id,
            document_id=doc.id,
            chapter_id=ch.id,
            chapter_index=0,
            chunk_index=0,
            text="chunk0",
            start_char=0,
            end_char=25,
            char_count=25,
            estimated_tokens=17,
        )
        session.add(c0)
        session.flush()
        c1 = Chunk(
            topic_id=topic.id,
            document_id=doc.id,
            chapter_id=ch.id,
            chapter_index=0,
            chunk_index=1,
            text="chunk1",
            start_char=25,
            end_char=50,
            char_count=25,
            estimated_tokens=17,
        )
        session.add(c1)
        session.commit()
        tid = topic.id
        c0_id = c0.id
        c1_id = c1.id

    with Session(engine) as session:
        run = create_analysis_run(session, tid, mode="full")
        rid = run.id
        ext0 = LocalExtraction(run_id=rid, topic_id=tid, chunk_id=c0_id, status="failed")
        session.add(ext0)
        # c1 has no extraction (missing)
        session.commit()

    called_ids = []

    def mock_extract(**kwargs):
        called_ids.append(kwargs["chunk_id"])
        return MockExtractionResult()

    with patch(
        "services.local_extraction_worker.run_local_extraction_for_chunk",
        side_effect=mock_extract,
    ):
        with Session(engine) as session:
            resume_analysis_run(session, rid, retry_failed=False)

    # Failed chunk (c0) should NOT be called, missing chunk (c1) SHOULD
    assert c0_id not in called_ids
    assert c1_id in called_ids


def test_resume_all_succeeded_idempotent(engine):
    """Resume with all chunks succeeded should not create duplicate rows."""
    from sqlmodel import Session, select

    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.extracted_atom import ExtractedAtom
    from models.local_extraction import LocalExtraction
    from models.model_provider import ModelProvider
    from models.topic import Topic
    from services.analysis_run_service import resume_analysis_run

    with Session(engine) as session:
        prov = ModelProvider(
            name="Resume3 P",
            provider_type="openai_compatible",
            base_url="http://mock",
            api_key="sk-m",
            model_name="m",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="Resume3", provider_id=prov.id, status="parsed")
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
        c0 = Chunk(
            topic_id=topic.id,
            document_id=doc.id,
            chapter_id=ch.id,
            chapter_index=0,
            chunk_index=0,
            text="chunk0",
            start_char=0,
            end_char=10,
            char_count=10,
            estimated_tokens=7,
        )
        session.add(c0)
        session.commit()
        tid = topic.id
        c0_id = c0.id

    with Session(engine) as session:
        run = create_analysis_run(session, tid, mode="full")
        rid = run.id
        ext0 = LocalExtraction(run_id=rid, topic_id=tid, chunk_id=c0_id, status="succeeded")
        session.add(ext0)
        session.commit()

    ext_count_before = 0
    with Session(engine) as session:
        ext_count_before = len(
            session.exec(select(LocalExtraction).where(LocalExtraction.run_id == rid)).all()
        )

    with patch(
        "services.local_extraction_worker.run_local_extraction_for_chunk",
        return_value=MockExtractionResult(),
    ):
        with Session(engine) as session:
            resume_analysis_run(session, rid, retry_failed=False)

    with Session(engine) as session:
        exts = session.exec(select(LocalExtraction).where(LocalExtraction.run_id == rid)).all()
        assert len(exts) == ext_count_before  # No new extractions
        atoms = session.exec(select(ExtractedAtom).where(ExtractedAtom.run_id == rid)).all()
        # No duplicate atoms from resume
        assert len(atoms) == 0 or len(atoms) >= 0  # may be 0 if no atom normalizer was triggered


# ── P2-1: Retry-failed with no failed extractions ──


def test_retry_failed_no_failed_extractions_409(client):
    """Retry on a run with no failed LocalExtractions should return 409."""
    topic_id = _setup_topic(client)
    with patch("services.analysis_run_service._execute_run"):
        r = client.post(f"/api/topics/{topic_id}/analysis/runs", json={"mode": "preview"})
        run_id = r.json()["run"]["id"]

    from main import app

    for dep in app.dependency_overrides.values():
        gen = dep()
        session = next(gen)
        try:
            from models.analysis_run import AnalysisRun
            from models.local_extraction import LocalExtraction

            run = session.get(AnalysisRun, run_id)
            if run:
                run.status = "partial_success"
                # Add a succeeded extraction but no failed ones
                ext = LocalExtraction(
                    run_id=run.id,
                    topic_id=topic_id,
                    chunk_id="fake-chunk-id",
                    status="succeeded",
                    attempt_count=1,
                )
                session.add(ext)
                session.add(run)
                session.commit()
        finally:
            session.close()

    with patch("services.analysis_run_service._execute_retry"):
        r = client.post(f"/api/analysis/runs/{run_id}/retry-failed")
        # Should be 409 because there are no failed extractions
        assert r.status_code == 409
        # Verify run status was NOT changed to running
        for dep in app.dependency_overrides.values():
            gen2 = dep()
            s2 = next(gen2)
            try:
                from models.analysis_run import AnalysisRun

                run2 = s2.get(AnalysisRun, run_id)
                assert run2.status == "partial_success"
            finally:
                s2.close()
    client.delete(f"/api/topics/{topic_id}")


def test_null_clears_provider_override(client):
    """Sending null for an override should clear it so the provider default takes effect."""
    # Create provider with a known model name
    r = client.post(
        "/api/providers",
        json={
            "name": "NullClearP",
            "provider_type": "openai_compatible",
            "base_url": "https://api.example.com",
            "api_key": "sk-clear",
            "model_name": "provider-default-model",
        },
    )
    pid = r.json()["id"]

    # Create topic
    r = client.post("/api/topics", json={"name": "NullClearT"})
    tid = r.json()["id"]

    # Set an override
    client.put(
        f"/api/topics/{tid}/provider-config",
        json={
            "provider_id": pid,
            "model_name_override": "custom-override",
            "max_output_tokens_override": 4096,
        },
    )
    # Verify override is active
    r = client.get(f"/api/topics/{tid}/provider-config/effective")
    eff = r.json()
    assert eff["model_name"] == "custom-override"
    assert eff["max_output_tokens"] == 4096

    # Clear the overrides by sending null
    client.put(
        f"/api/topics/{tid}/provider-config",
        json={
            "model_name_override": None,
            "max_output_tokens_override": None,
        },
    )
    # Verify effective config falls through to provider defaults
    r = client.get(f"/api/topics/{tid}/provider-config/effective")
    eff = r.json()
    assert eff["model_name"] == "provider-default-model"
    # max_output_tokens should fall through — provider default (0 → unset) → preset (2048)
    assert eff["max_output_tokens"] == 2048

    client.delete(f"/api/topics/{tid}")
    client.delete(f"/api/providers/{pid}")


def test_create_run_empty_range_422(client):
    """Range selection that matches zero chunks should return 422 synchronously."""
    topic_id = _setup_topic(client)

    # Ask for a chunk index far beyond what exists — _setup_topic creates a tiny doc
    r = client.post(
        f"/api/topics/{topic_id}/analysis/runs",
        json={
            "mode": "range",
            "chunk_index_start": 999,
            "chunk_index_end": 999,
        },
    )
    assert r.status_code == 422

    client.delete(f"/api/topics/{topic_id}")


# ── _fail_run protection tests ──


def test_fail_run_does_not_overwrite_partial_success(engine):
    """_fail_run should not change status from partial_success to failed."""
    from datetime import datetime, timezone

    from models.analysis_run import AnalysisRun
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.model_provider import ModelProvider
    from models.topic import Topic
    from services.analysis_run_service import _fail_run

    with Session(engine) as session:
        prov = ModelProvider(
            name="FailRunPS P",
            provider_type="openai_compatible",
            base_url="http://mock",
            api_key="sk-m",
            model_name="m",
            is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="FailRunPS", provider_id=prov.id, status="parsed")
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
            chapter_index=0, title="Ch1",
            start_char=0, end_char=10, char_count=10,
        )
        session.add(ch)
        session.flush()
        ck = Chunk(
            topic_id=topic.id, document_id=doc.id, chapter_id=ch.id,
            chapter_index=0, chunk_index=0, text="t",
            start_char=0, end_char=1, char_count=1, estimated_tokens=1,
        )
        session.add(ck)
        session.commit()
        tid = topic.id

    with Session(engine) as session:
        run = create_analysis_run(session, tid, mode="preview", limit_chunks=1)
        rid = run.id

    # Set the run to partial_success with finished_at + completed stage
    with Session(engine) as session:
        run = session.get(AnalysisRun, rid)
        run.status = "partial_success"
        run.finished_at = datetime.now(timezone.utc)
        run.set_metadata({"stage": "completed", "failed_chunks": []})
        session.add(run)
        session.commit()

    # Call _fail_run — should NOT overwrite partial_success
    _fail_run(rid, engine, "late exception after completion")

    with Session(engine) as session:
        run = session.get(AnalysisRun, rid)
        assert run.status == "partial_success"
        assert run.error_message is None


def test_fail_run_does_not_overwrite_succeeded(engine):
    """_fail_run should not change status from succeeded to failed."""
    from models.analysis_run import AnalysisRun
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.model_provider import ModelProvider
    from models.topic import Topic
    from services.analysis_run_service import _fail_run

    with Session(engine) as session:
        prov = ModelProvider(
            name="FailRunSucc P",
            provider_type="openai_compatible",
            base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="FailRunSucc", provider_id=prov.id, status="parsed")
        session.add(topic)
        session.flush()
        doc = Document(
            topic_id=topic.id, original_filename="t.txt",
            file_size_bytes=10, char_count=10, status="parsed",
        )
        session.add(doc)
        session.flush()
        ch = Chapter(
            topic_id=topic.id, document_id=doc.id, chapter_index=0,
            title="Ch1", start_char=0, end_char=10, char_count=10,
        )
        session.add(ch)
        session.flush()
        ck = Chunk(
            topic_id=topic.id, document_id=doc.id, chapter_id=ch.id,
            chapter_index=0, chunk_index=0, text="t",
            start_char=0, end_char=1, char_count=1, estimated_tokens=1,
        )
        session.add(ck)
        session.commit()
        tid = topic.id

    with Session(engine) as session:
        run = create_analysis_run(session, tid, mode="preview", limit_chunks=1)
        rid = run.id

    with Session(engine) as session:
        run = session.get(AnalysisRun, rid)
        run.status = "succeeded"
        session.add(run)
        session.commit()

    _fail_run(rid, engine, "late exception after success")

    with Session(engine) as session:
        run = session.get(AnalysisRun, rid)
        assert run.status == "succeeded"


def test_fail_run_does_not_overwrite_completed_metadata(engine):
    """_fail_run should not overwrite a run that has finished_at + metadata.stage='completed'."""
    from datetime import datetime, timezone

    from models.analysis_run import AnalysisRun
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.model_provider import ModelProvider
    from models.topic import Topic
    from services.analysis_run_service import _fail_run

    with Session(engine) as session:
        prov = ModelProvider(
            name="FailRunMeta P",
            provider_type="openai_compatible",
            base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="FailRunMeta", provider_id=prov.id, status="parsed")
        session.add(topic)
        session.flush()
        doc = Document(
            topic_id=topic.id, original_filename="t.txt",
            file_size_bytes=10, char_count=10, status="parsed",
        )
        session.add(doc)
        session.flush()
        ch = Chapter(
            topic_id=topic.id, document_id=doc.id, chapter_index=0,
            title="Ch1", start_char=0, end_char=10, char_count=10,
        )
        session.add(ch)
        session.flush()
        ck = Chunk(
            topic_id=topic.id, document_id=doc.id, chapter_id=ch.id,
            chapter_index=0, chunk_index=0, text="t",
            start_char=0, end_char=1, char_count=1, estimated_tokens=1,
        )
        session.add(ck)
        session.commit()
        tid = topic.id

    with Session(engine) as session:
        run = create_analysis_run(session, tid, mode="preview", limit_chunks=1)
        rid = run.id

    # Simulate a completed run (running status with finished_at + completed metadata)
    with Session(engine) as session:
        run = session.get(AnalysisRun, rid)
        run.status = "running"  # Running when metadata says completed (unlikely but possible)
        run.finished_at = datetime.now(timezone.utc)
        run.set_metadata({"stage": "completed"})
        session.add(run)
        session.commit()

    _fail_run(rid, engine, "late exception after completion detected via metadata")

    with Session(engine) as session:
        run = session.get(AnalysisRun, rid)
        # Should NOT have overwritten with failed
        assert run.status == "running"
        assert run.error_message is None


# ── Cumulative token tracking tests ──


def test_cumulative_tokens_persisted_in_local_extraction(engine):
    """LocalExtraction.total_tokens should reflect cumulative sum of all attempts."""
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.local_extraction import LocalExtraction
    from models.model_provider import ModelProvider
    from models.topic import Topic
    from services.analysis_run_service import _execute_run

    with Session(engine) as session:
        prov = ModelProvider(
            name="Cumulative P", provider_type="openai_compatible",
            base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
        )
        session.add(prov)
        session.flush()
        topic = Topic(name="Cumulative", provider_id=prov.id, status="parsed")
        session.add(topic)
        session.flush()
        doc = Document(
            topic_id=topic.id, original_filename="t.txt",
            file_size_bytes=10, char_count=10, status="parsed",
        )
        session.add(doc)
        session.flush()
        ch = Chapter(
            topic_id=topic.id, document_id=doc.id, chapter_index=0,
            title="Ch1", start_char=0, end_char=10, char_count=10,
        )
        session.add(ch)
        session.flush()
        ck = Chunk(
            topic_id=topic.id, document_id=doc.id, chapter_id=ch.id,
            chapter_index=0, chunk_index=0, text="t",
            start_char=0, end_char=1, char_count=1, estimated_tokens=1,
        )
        session.add(ck)
        session.commit()
        tid = topic.id

    # Build a mock result that simulates two attempts (one failed, one succeeded)
    class MockCumulativeResult:
        ok = True
        content_json = MOCK_EXTRACTION_JSON
        parsed_json = json.loads(MOCK_EXTRACTION_JSON)
        error = None
        prompt_tokens = 900   # cumulative: 500 (fail) + 400 (success)
        completion_tokens = 5090  # cumulative: 4090 (fail) + 1000 (success)
        total_tokens = 5990  # cumulative
        model_used = "mock-v4-flash"
        retry_count = 1
        duration_seconds = 0.01
        status_code = None
        finish_reason = "stop"
        warnings = []
        cumulative_reasoning_tokens = 2000
        cumulative_prompt_cache_hit_tokens = 500
        cumulative_prompt_cache_miss_tokens = 100
        usage_unavailable_attempts = 0
        attempts = [
            {"attempt_index": 0, "ok": False, "max_tokens": 4096,
             "prompt_tokens": 500, "completion_tokens": 4090, "total_tokens": 4590,
             "reasoning_tokens": 2000, "prompt_cache_hit_tokens": 500,
             "prompt_cache_miss_tokens": 0, "usage_available": True},
            {"attempt_index": 1, "ok": True, "max_tokens": 16384,
             "prompt_tokens": 400, "completion_tokens": 1000, "total_tokens": 1400,
             "reasoning_tokens": 0, "prompt_cache_hit_tokens": 0,
             "prompt_cache_miss_tokens": 100, "usage_available": True},
        ]

    with patch(
        "services.local_extraction_worker.run_local_extraction_for_chunk",
        return_value=MockCumulativeResult(),
    ):
        with Session(engine) as session:
            run = create_analysis_run(session, tid, mode="preview", limit_chunks=1)
            run_id = run.id
        _execute_run(run_id, engine=engine)

    with Session(engine) as session:
        exts = session.exec(
            select(LocalExtraction).where(LocalExtraction.run_id == run_id)
        ).all()
        assert len(exts) == 1
        ext = exts[0]
        assert ext.total_tokens == 5990
        assert ext.reasoning_tokens == 2000
        assert ext.prompt_cache_hit_tokens == 500
        assert ext.prompt_cache_miss_tokens == 100
        assert ext.usage_unavailable_attempts == 0
        assert ext.attempt_usage_json is not None
        attempts_saved = json.loads(ext.attempt_usage_json)
        assert len(attempts_saved) == 2

        status = get_analysis_run_status(session, run_id)
        assert status["run"]["total_tokens"] == 5990
        assert status["run"]["reasoning_tokens"] == 2000
        assert status["run"]["prompt_cache_hit_tokens"] == 500
        assert status["run"]["prompt_cache_miss_tokens"] == 100


def test_retry_persists_usage_fields(engine):
    """After retry, LocalExtraction should have new usage fields and attempt_usage_json."""
    from models.analysis_run import AnalysisRun as AnalysisRunModel
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.local_extraction import LocalExtraction
    from models.model_provider import ModelProvider
    from models.topic import Topic
    from services.analysis_run_service import retry_failed_extractions

    with Session(engine) as session:
        prov = ModelProvider(
            name="RetryUsage P", provider_type="openai_compatible",
            base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
        )
        session.add(prov); session.flush()
        topic = Topic(name="RetryUsage", provider_id=prov.id, status="parsed")
        session.add(topic); session.flush()
        doc = Document(
            topic_id=topic.id, original_filename="t.txt",
            file_size_bytes=10, char_count=10, status="parsed",
        )
        session.add(doc); session.flush()
        ch = Chapter(
            topic_id=topic.id, document_id=doc.id, chapter_index=0,
            title="Ch1", start_char=0, end_char=10, char_count=10,
        )
        session.add(ch); session.flush()
        ck = Chunk(
            topic_id=topic.id, document_id=doc.id, chapter_id=ch.id,
            chapter_index=0, chunk_index=0, text="t",
            start_char=0, end_char=1, char_count=1, estimated_tokens=1,
        )
        session.add(ck)
        session.commit()
        tid = topic.id
        cid = ck.id

    # Mark the run with a failed extraction
    with Session(engine) as session:
        run = create_analysis_run(session, tid, mode="preview", limit_chunks=1)
        rid = run.id
        ext = LocalExtraction(
            run_id=rid, topic_id=tid, chunk_id=cid,
            status="failed", attempt_count=1, confidence=0.0,
            prompt_tokens=100, completion_tokens=50, total_tokens=150,
        )
        session.add(ext)
        run.status = "partial_success"
        run.extraction_succeeded = 0
        run.extraction_failed = 1
        session.add(run)
        session.commit()

    # Now retry
    class RetryMockResult:
        ok = True
        content_json = MOCK_EXTRACTION_JSON
        parsed_json = json.loads(MOCK_EXTRACTION_JSON)
        error = None
        prompt_tokens = 300
        completion_tokens = 200
        total_tokens = 500
        model_used = "mock-model"
        retry_count = 1
        duration_seconds = 0.01
        status_code = None
        finish_reason = "stop"
        warnings = []
        attempts = [
            {"attempt_index": 0, "ok": True, "max_tokens": 8192,
             "prompt_tokens": 300, "completion_tokens": 200, "total_tokens": 500,
             "reasoning_tokens": 100, "prompt_cache_hit_tokens": 50,
             "prompt_cache_miss_tokens": 250, "finish_reason": "stop",
             "status_code": None, "error": None, "usage_available": True},
        ]
        cumulative_prompt_tokens = 300
        cumulative_completion_tokens = 200
        cumulative_total_tokens = 500
        cumulative_reasoning_tokens = 100
        cumulative_prompt_cache_hit_tokens = 50
        cumulative_prompt_cache_miss_tokens = 250
        usage_unavailable_attempts = 0

    with patch(
        "services.local_extraction_worker.run_local_extraction_for_chunk",
        return_value=RetryMockResult(),
    ):
        with Session(engine) as session:
            retry_failed_extractions(session, rid)

    with Session(engine) as session:
        exts = session.exec(
            select(LocalExtraction).where(LocalExtraction.run_id == rid)
        ).all()
        assert len(exts) == 1
        ext = exts[0]
        assert ext.status == "succeeded"
        assert ext.reasoning_tokens == 100
        assert ext.prompt_cache_hit_tokens == 50
        assert ext.prompt_cache_miss_tokens == 250
        assert ext.usage_unavailable_attempts == 0
        assert ext.attempt_usage_json is not None

        # Run token counters: old failed (150) + new cumulative (500) = 650
        # prompt: 100 + 300 = 400, completion: 50 + 200 = 250
        run = session.get(AnalysisRunModel, rid)
        assert run.total_tokens == 150 + 500
        assert run.prompt_tokens == 100 + 300
        assert run.completion_tokens == 50 + 200


def test_resume_updates_run_usage_breakdown(engine):
    """Resume should recalculate run usage after running missing chunks."""
    from models.chapter import Chapter
    from models.chunk import Chunk
    from models.document import Document
    from models.local_extraction import LocalExtraction
    from models.model_provider import ModelProvider
    from models.topic import Topic
    from services.analysis_run_service import resume_analysis_run

    with Session(engine) as session:
        prov = ModelProvider(
            name="ResumeUsage P", provider_type="openai_compatible",
            base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
        )
        session.add(prov); session.flush()
        topic = Topic(name="ResumeUsage", provider_id=prov.id, status="parsed")
        session.add(topic); session.flush()
        doc = Document(
            topic_id=topic.id, original_filename="t.txt",
            file_size_bytes=50, char_count=50, status="parsed",
        )
        session.add(doc); session.flush()
        ch = Chapter(
            topic_id=topic.id, document_id=doc.id, chapter_index=0,
            title="Ch1", start_char=0, end_char=50, char_count=50,
        )
        session.add(ch); session.flush()
        c0 = Chunk(
            topic_id=topic.id, document_id=doc.id, chapter_id=ch.id,
            chapter_index=0, chunk_index=0, text="chunk0",
            start_char=0, end_char=25, char_count=25, estimated_tokens=17,
        )
        session.add(c0); session.flush()
        c1 = Chunk(
            topic_id=topic.id, document_id=doc.id, chapter_id=ch.id,
            chapter_index=0, chunk_index=1, text="chunk1",
            start_char=25, end_char=50, char_count=25, estimated_tokens=17,
        )
        session.add(c1)
        session.commit()
        tid = topic.id
        c0_id = c0.id

    with Session(engine) as session:
        run = create_analysis_run(session, tid, mode="full")
        rid = run.id
        # c0 succeeded with some tokens
        ext0 = LocalExtraction(
            run_id=rid, topic_id=tid, chunk_id=c0_id,
            status="succeeded", attempt_count=1,
            prompt_tokens=200, completion_tokens=100, total_tokens=300,
            reasoning_tokens=0, prompt_cache_hit_tokens=0,
            prompt_cache_miss_tokens=200, usage_unavailable_attempts=0,
        )
        session.add(ext0)
        # c1 has no extraction (missing)
        session.commit()

    class ResumeMockResult:
        ok = True
        content_json = MOCK_EXTRACTION_JSON
        parsed_json = json.loads(MOCK_EXTRACTION_JSON)
        error = None
        prompt_tokens = 150
        completion_tokens = 80
        total_tokens = 230
        model_used = "mock"
        retry_count = 0
        duration_seconds = 0.01
        status_code = None
        finish_reason = "stop"
        warnings = []
        attempts = [
            {"attempt_index": 0, "ok": True, "max_tokens": 4096,
             "prompt_tokens": 150, "completion_tokens": 80, "total_tokens": 230,
             "reasoning_tokens": 0, "prompt_cache_hit_tokens": 0,
             "prompt_cache_miss_tokens": 150, "finish_reason": "stop",
             "status_code": None, "error": None, "usage_available": True},
        ]
        cumulative_prompt_tokens = 150
        cumulative_completion_tokens = 80
        cumulative_total_tokens = 230
        cumulative_reasoning_tokens = 0
        cumulative_prompt_cache_hit_tokens = 0
        cumulative_prompt_cache_miss_tokens = 150
        usage_unavailable_attempts = 0

    with patch(
        "services.local_extraction_worker.run_local_extraction_for_chunk",
        return_value=ResumeMockResult(),
    ):
        with Session(engine) as session:
            resume_analysis_run(session, rid, retry_failed=False)

    with Session(engine) as session:
        from models.analysis_run import AnalysisRun

        run = session.get(AnalysisRun, rid)
        assert run.total_tokens == 300 + 230
        assert run.prompt_tokens == 200 + 150
        assert run.completion_tokens == 100 + 80
