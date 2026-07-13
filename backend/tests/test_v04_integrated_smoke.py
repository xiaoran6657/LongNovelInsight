"""Isolated v0.4 Work smoke flow using the real backend API and pipeline."""

import io
import json
from pathlib import Path
from unittest.mock import patch

from sqlmodel import Session, select

from models.analysis_output import AnalysisOutput
from models.analysis_run import AnalysisRun
from models.chunk import Chunk
from models.document import Document
from models.local_extraction import LocalExtraction
from services.local_extraction_worker import LocalExtractionResult

SAMPLE_NOVEL = (
    "第一章 初遇\n\n"
    "林川第一次来到云州，在旧书铺遇见了守店人苏禾。"
    "苏禾交给他一封没有署名的信，提醒他不要在月圆之夜进入北塔。\n\n"
    "第二章 北塔\n\n"
    "月圆之夜，林川仍然来到北塔。他在塔门前再次遇见苏禾，"
    "两人决定共同调查信件背后的秘密。"
)


def _mock_extraction(**kwargs) -> LocalExtractionResult:
    chunk_id = kwargs["chunk_id"]
    parsed = {
        "analysis_type": "local_extraction",
        "chunk_id": chunk_id,
        "chapter_index": kwargs.get("chapter_index", 0),
        "local_characters": [
            {
                "character_id_hint": "lin-chuan",
                "name": "林川",
                "traits": ["curious", "determined"],
                "source_chunk_ids": [chunk_id],
                "evidence_quotes": ["林川仍然来到北塔"],
                "confidence": 0.95,
            }
        ],
    }
    content = json.dumps(parsed, ensure_ascii=False)
    return LocalExtractionResult(
        chunk_id=chunk_id,
        ok=True,
        content_json=content,
        parsed_json=parsed,
        duration_seconds=0.01,
        prompt_tokens=120,
        completion_tokens=60,
        total_tokens=180,
        model_used="isolated-smoke-model",
        cumulative_prompt_tokens=120,
        cumulative_completion_tokens=60,
        cumulative_total_tokens=180,
    )


def test_isolated_work_upload_parse_analysis_smoke(engine, client, tmp_path: Path):
    """Exercise the authoritative Work flow without live data or network calls."""
    provider = client.post(
        "/api/providers",
        json={
            "name": "Isolated Smoke Provider",
            "provider_type": "openai_compatible",
            "base_url": "https://invalid.example.test/v1",
            "api_key": "sk-isolated-smoke",
            "model_name": "isolated-smoke-model",
            "is_default": True,
        },
    )
    assert provider.status_code == 201, provider.text
    provider_id = provider.json()["id"]

    topic = client.post(
        "/api/topics",
        json={"name": "Isolated Work Smoke", "provider_id": provider_id},
    )
    assert topic.status_code == 201, topic.text
    topic_id = topic.json()["id"]

    work = client.post(
        f"/api/topics/{topic_id}/works",
        json={"title": "North Tower", "author": "Test Author", "series_index": 1},
    )
    assert work.status_code == 201, work.text
    work_id = work.json()["id"]

    upload = client.post(
        f"/api/works/{work_id}/documents/upload",
        files={
            "file": (
                "north-tower.txt",
                io.BytesIO(SAMPLE_NOVEL.encode("utf-8")),
                "text/plain",
            )
        },
    )
    assert upload.status_code == 201, upload.text
    assert upload.json()["work_id"] == work_id
    document_id = upload.json()["id"]

    parsed = client.post(f"/api/works/{work_id}/parse")
    assert parsed.status_code == 200, parsed.text
    assert parsed.json()["chapter_count"] >= 1
    assert parsed.json()["chunk_count"] >= 1

    chunks_response = client.get(f"/api/works/{work_id}/chunks?include_text=true")
    assert chunks_response.status_code == 200
    chunks = chunks_response.json()["chunks"]
    assert chunks
    assert all(chunk["document_id"] == document_id for chunk in chunks)
    assert any("林川" in chunk["text"] for chunk in chunks)

    from services import analysis_run_service

    def execute_synchronously(run_id: str) -> bool:
        analysis_run_service._execute_run(run_id, engine=engine)
        return True

    with (
        patch(
            "services.local_extraction_worker.run_local_extraction_for_chunk",
            side_effect=_mock_extraction,
        ) as extraction_mock,
        patch(
            "services.analysis_run_service.start_analysis_run",
            side_effect=execute_synchronously,
        ),
        patch(
            "services.llm_client.OpenAICompatibleLLMClient.chat",
            side_effect=AssertionError("isolated smoke must not call an external LLM"),
        ) as llm_mock,
    ):
        created_run = client.post(
            f"/api/works/{work_id}/analysis/runs",
            json={
                "mode": "preview",
                "limit_chunks": 1,
                "requested_types": ["characters"],
            },
        )

    assert created_run.status_code == 201, created_run.text
    run_id = created_run.json()["run"]["id"]
    extraction_mock.assert_called_once()
    llm_mock.assert_not_called()

    status = client.get(f"/api/analysis/runs/{run_id}")
    assert status.status_code == 200, status.text
    status_data = status.json()
    assert status_data["run"]["status"] == "succeeded"
    assert status_data["run"]["work_id"] == work_id
    assert status_data["run"]["extraction_succeeded"] == 1
    assert len(status_data["extractions"]) == 1
    assert status_data["extractions"][0]["status"] == "succeeded"
    assert status_data["merge"]["succeeded"] == 1
    assert status_data["final"]["succeeded"] == 1
    assert status_data["run"]["total_tokens"] == 180

    runs = client.get(f"/api/works/{work_id}/analysis/runs")
    assert runs.status_code == 200
    assert runs.json()["total"] == 1
    assert runs.json()["runs"][0]["id"] == run_id
    assert runs.json()["runs"][0]["work_id"] == work_id

    outputs = client.get(f"/api/works/{work_id}/analysis/outputs")
    assert outputs.status_code == 200
    assert outputs.json()["total"] == 1
    assert outputs.json()["outputs"][0]["run_id"] == run_id
    assert outputs.json()["outputs"][0]["output_type"] == "characters"

    analyzed_work = client.get(f"/api/works/{work_id}")
    assert analyzed_work.status_code == 200
    assert analyzed_work.json()["status"] == "analyzed"

    with Session(engine) as session:
        import config

        run = session.get(AnalysisRun, run_id)
        document = session.get(Document, document_id)
        selected_ids = set(run.get_chunk_selection()["selected_chunk_ids"]) if run else set()
        work_chunk_ids = {
            chunk.id
            for chunk in session.exec(select(Chunk).where(Chunk.document_id == document_id)).all()
        }
        assert run is not None
        assert document is not None and document.work_id == work_id
        assert not Path(document.storage_path).is_absolute()
        assert (config.DATA_DIR / document.storage_path).is_file()
        assert selected_ids and selected_ids <= work_chunk_ids
        assert session.exec(select(LocalExtraction).where(LocalExtraction.run_id == run_id)).one()
        final_output = session.exec(
            select(AnalysisOutput)
            .where(AnalysisOutput.run_id == run_id)
            .where(AnalysisOutput.output_type == "characters")
        ).one()
        assert "林川" in final_output.content_json

    deleted = client.delete(f"/api/topics/{topic_id}")
    assert deleted.status_code == 200, deleted.text
    assert client.get(f"/api/works/{work_id}").status_code == 404
    assert client.get(f"/api/analysis/runs/{run_id}").status_code == 404
    assert not (tmp_path / "test_data" / "topics" / topic_id).exists()

    provider_deleted = client.delete(f"/api/providers/{provider_id}")
    assert provider_deleted.status_code == 200, provider_deleted.text
