"""Tests for v0.4 work-scoped analysis runs."""

import io
import json
from unittest.mock import patch

from sqlmodel import Session

from models.document import Document
from models.model_provider import ModelProvider
from models.topic import Topic
from models.work import Work

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


class MockExtractionResult:
    def __init__(self, ok=True, chunk_id="chunk-1"):
        self.ok = ok
        self.content_json = MOCK_EXTRACTION_JSON
        self.parsed_json = json.loads(MOCK_EXTRACTION_JSON)
        self.error = None
        self.prompt_tokens = 100
        self.completion_tokens = 50
        self.total_tokens = 150
        self.model_used = "mock-model"
        self.retry_count = 0
        self.duration_seconds = 0.01
        self.status_code = None
        self.finish_reason = None
        self.warnings = []
        self.attempts = []
        self.cumulative_prompt_tokens = 100
        self.cumulative_completion_tokens = 50
        self.cumulative_total_tokens = 150
        self.cumulative_reasoning_tokens = 0
        self.cumulative_prompt_cache_hit_tokens = 0
        self.cumulative_prompt_cache_miss_tokens = 0
        self.usage_unavailable_attempts = 0


def _setup_parsed_work(engine, client) -> tuple[str, str]:
    """Create a topic with parsed Work. Returns (topic_id, work_id)."""
    with Session(engine) as session:
        prov = ModelProvider(
            name="AnaP", provider_type="openai_compatible",
            base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
        )
        session.add(prov); session.flush()
        topic = Topic(name="AnaTopic", provider_id=prov.id, status="created")
        session.add(topic); session.flush()
        work = Work(topic_id=topic.id, title="Analysis Work", series_index=1)
        session.add(work)
        session.commit()
        tid = topic.id
        wid = work.id
        pid = prov.id

    client.put(
        f"/api/topics/{tid}/provider-config",
        json={"provider_id": pid, "max_output_tokens_override": 4096},
    )

    # Upload + parse
    client.post(
        f"/api/works/{wid}/documents/upload",
        files={"file": ("novel.txt", io.BytesIO("第一章 测试\n内容。\n".encode()), "text/plain")},
    )
    client.post(f"/api/works/{wid}/parse")

    return tid, wid


class TestWorkAnalysis:
    def test_create_work_analysis_run(self, engine, client):
        tid, wid = _setup_parsed_work(engine, client)

        with patch("services.analysis_run_service._execute_run"):
            r = client.post(
                f"/api/works/{wid}/analysis/runs",
                json={"mode": "preview", "limit_chunks": 1, "requested_types": ["characters"]},
            )
            assert r.status_code == 201
            data = r.json()
            assert data["run"]["mode"] == "preview"
            assert data["run"]["status"] == "pending"

    def test_work_analysis_run_needs_parsed_document(self, engine, client):
        """Work without parsed document → 409."""
        with Session(engine) as session:
            prov = ModelProvider(
                name="NoDocAnaP", provider_type="openai_compatible",
                base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
            )
            session.add(prov); session.flush()
            topic = Topic(name="NoDocAna", provider_id=prov.id, status="created")
            session.add(topic); session.flush()
            work = Work(topic_id=topic.id, title="No Doc Work", series_index=1)
            session.add(work)
            session.commit()
            wid = work.id

        r = client.post(
            f"/api/works/{wid}/analysis/runs",
            json={"mode": "preview", "limit_chunks": 1},
        )
        assert r.status_code == 409

    def test_list_work_analysis_runs(self, engine, client):
        tid, wid = _setup_parsed_work(engine, client)

        with patch("services.analysis_run_service._execute_run"):
            client.post(
                f"/api/works/{wid}/analysis/runs",
                json={"mode": "preview", "limit_chunks": 1},
            )

        r = client.get(f"/api/works/{wid}/analysis/runs")
        assert r.status_code == 200
        assert len(r.json()["runs"]) >= 1

    def test_list_work_analysis_outputs(self, engine, client):
        tid, wid = _setup_parsed_work(engine, client)

        r = client.get(f"/api/works/{wid}/analysis/outputs")
        assert r.status_code == 200
        assert "outputs" in r.json()

    def test_work_status_analyzed_after_run(self, engine, client):
        tid, wid = _setup_parsed_work(engine, client)

        with patch(
            "services.local_extraction_worker.run_local_extraction_for_chunk",
            return_value=MockExtractionResult(),
        ):
            with Session(engine) as session:
                from services.analysis_run_service import (
                    _execute_run,
                    create_analysis_run,
                )

                run = create_analysis_run(
                    session, tid, mode="preview",
                    limit_chunks=1, work_id=wid,
                )
                rid = run.id
            _execute_run(rid, engine=engine)

        with Session(engine) as session:
            work = session.get(Work, wid)
            assert work is not None
            assert work.status == "analyzed", (
                f"Work status should be 'analyzed' after successful run, got '{work.status}'"
            )

    def test_two_works_independent_analysis(self, engine, client):
        """Two Works in same Topic → analysis only uses chunks from each Work."""
        from models.chapter import Chapter
        from models.chunk import Chunk

        with Session(engine) as session:
            prov = ModelProvider(
                name="TwoWorkP", provider_type="openai_compatible",
                base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
            )
            session.add(prov); session.flush()
            topic = Topic(name="TwoWorkTopic", provider_id=prov.id, status="created")
            session.add(topic); session.flush()

            w1 = Work(topic_id=topic.id, title="Work 1", series_index=1)
            w2 = Work(topic_id=topic.id, title="Work 2", series_index=2)
            session.add(w1); session.add(w2); session.flush()

            d1 = Document(
                topic_id=topic.id, work_id=w1.id,
                original_filename="w1.txt", file_size_bytes=100,
                char_count=50, status="parsed",
            )
            d2 = Document(
                topic_id=topic.id, work_id=w2.id,
                original_filename="w2.txt", file_size_bytes=100,
                char_count=50, status="parsed",
            )
            session.add(d1); session.add(d2); session.flush()

            ch1 = Chapter(
                topic_id=topic.id, document_id=d1.id,
                chapter_index=0, title="Ch1",
                start_char=0, end_char=50, char_count=50,
            )
            ch2 = Chapter(
                topic_id=topic.id, document_id=d2.id,
                chapter_index=0, title="Ch1",
                start_char=0, end_char=50, char_count=50,
            )
            session.add(ch1); session.add(ch2); session.flush()

            ck1 = Chunk(
                topic_id=topic.id, document_id=d1.id, chapter_id=ch1.id,
                chapter_index=0, chunk_index=0, text="work1 text here",
                start_char=0, end_char=50, char_count=50, estimated_tokens=34,
            )
            ck2 = Chunk(
                topic_id=topic.id, document_id=d2.id, chapter_id=ch2.id,
                chapter_index=0, chunk_index=0, text="work2 text here",
                start_char=0, end_char=50, char_count=50, estimated_tokens=34,
            )
            session.add(ck1); session.add(ck2)
            session.flush()
            ck1_id = ck1.id
            ck2_id = ck2.id
            session.commit()
            tid = topic.id
            w1_id = w1.id

        # Run analysis for Work 1
        called_chunks = []

        def mock_extract(**kwargs):
            called_chunks.append(kwargs["chunk_id"])
            return MockExtractionResult(chunk_id=kwargs["chunk_id"])

        with patch(
            "services.local_extraction_worker.run_local_extraction_for_chunk",
            side_effect=mock_extract,
        ):
            with Session(engine) as session:
                from services.analysis_run_service import (
                    _execute_run,
                    create_analysis_run,
                )

                run = create_analysis_run(
                    session, tid, mode="full", work_id=w1_id,
                )
                rid = run.id
            _execute_run(rid, engine=engine)

        # Only Work 1's chunk should be analyzed
        assert ck1_id in called_chunks, "Work 1's chunk should be analyzed"
        assert ck2_id not in called_chunks, "Work 2's chunk should NOT be analyzed"

    def test_run_status_includes_work_id(self, engine):
        """Run status response should include work_id from chunk selection."""
        from models.chapter import Chapter
        from models.chunk import Chunk

        with Session(engine) as session:
            prov = ModelProvider(
                name="WidStatusP", provider_type="openai_compatible",
                base_url="http://mock", api_key="sk-m", model_name="m", is_default=True,
            )
            session.add(prov); session.flush()
            topic = Topic(name="WidStatus", provider_id=prov.id, status="parsed")
            session.add(topic); session.flush()
            work = Work(topic_id=topic.id, title="Wid Work", series_index=1)
            session.add(work); session.flush()
            doc = Document(
                topic_id=topic.id, work_id=work.id,
                original_filename="w.txt", file_size_bytes=100,
                char_count=50, status="parsed",
            )
            session.add(doc); session.flush()
            ch = Chapter(
                topic_id=topic.id, document_id=doc.id,
                chapter_index=0, title="Ch1",
                start_char=0, end_char=50, char_count=50,
            )
            session.add(ch); session.flush()
            ck = Chunk(
                topic_id=topic.id, document_id=doc.id, chapter_id=ch.id,
                chapter_index=0, chunk_index=0, text="test",
                start_char=0, end_char=50, char_count=50, estimated_tokens=34,
            )
            session.add(ck)
            session.commit()
            tid = topic.id
            wid = work.id
            rid = None

        with patch(
            "services.local_extraction_worker.run_local_extraction_for_chunk",
            return_value=MockExtractionResult(),
        ):
            with Session(engine) as session:
                from services.analysis_run_service import (
                    _execute_run,
                    create_analysis_run,
                    get_analysis_run_status,
                )

                run = create_analysis_run(
                    session, tid, mode="full", work_id=wid,
                )
                rid = run.id
            _execute_run(rid, engine=engine)

        with Session(engine) as session:
            status = get_analysis_run_status(session, rid)
            assert status["run"]["work_id"] == wid, (
                f"Run status should include work_id, got {status['run'].get('work_id')}"
            )
