import io
from unittest.mock import patch

from models.analysis_output import AnalysisOutput
from models.enums import AnalysisType, JobStatus

# Patch path for run_single_analysis_output
RUN_SINGLE_PATH = "services.job_service.analysis_service.run_single_analysis_output"


def _create_topic(client, name="Job Test"):
    r = client.post("/api/topics", json={"name": name})
    assert r.status_code == 201
    return r.json()["id"]


def _upload(client, topic_id):
    content = "第一章 开始\n这是第一章的内容。\n第二章 结束\n这是第二章的内容。\n"
    r = client.post(
        f"/api/topics/{topic_id}/documents/upload",
        files={"file": ("novel.txt", io.BytesIO(content.encode("utf-8")), "text/plain")},
    )
    assert r.status_code == 201
    return r.json()


def _parse(client, topic_id):
    r = client.post(f"/api/topics/{topic_id}/parse")
    assert r.status_code == 200
    return r.json()


def _setup_topic(client):
    tid = _create_topic(client)
    _upload(client, tid)
    _parse(client, tid)
    return tid


def _mock_output(topic_id, output_type, session, **kwargs):
    """Return a fake AnalysisOutput for run_single_analysis_output."""
    import json

    return AnalysisOutput(
        topic_id=topic_id,
        output_type=output_type,
        title=f"{output_type} result",
        content_json=json.dumps(
            {
                "title": f"{output_type} test",
                "source_chunk_ids": [],
                "evidence_quotes": ["test"],
                "confidence": 0.9,
            }
        ),
        source_chunk_ids=json.dumps([]),
        evidence_quotes=json.dumps(["test"]),
        confidence=0.9,
    )


# ── Validation ──


def test_no_topic_returns_404(client):
    r = client.post("/api/topics/nonexistent/analysis/jobs")
    assert r.status_code == 404


def test_no_document_returns_409(client):
    tid = _create_topic(client)
    r = client.post(f"/api/topics/{tid}/analysis/jobs")
    assert r.status_code == 409


def test_not_parsed_returns_409(client):
    tid = _create_topic(client)
    _upload(client, tid)
    r = client.post(f"/api/topics/{tid}/analysis/jobs")
    assert r.status_code == 409


# ── Create job with real execution mocked ──


def test_create_analysis_job_success(client):
    tid = _setup_topic(client)
    with patch(RUN_SINGLE_PATH, side_effect=_mock_output):
        r = client.post(f"/api/topics/{tid}/analysis/jobs")
    assert r.status_code == 201
    data = r.json()
    assert data["job"]["status"] == JobStatus.SUCCEEDED
    assert data["job"]["job_type"] == "analysis"
    assert data["job"]["progress_current"] == 6
    assert data["job"]["progress_total"] == 6
    assert len(data["items"]) == 6


def test_job_items_all_succeeded(client):
    tid = _setup_topic(client)
    with patch(RUN_SINGLE_PATH, side_effect=_mock_output):
        r = client.post(f"/api/topics/{tid}/analysis/jobs")
    for item in r.json()["items"]:
        assert item["status"] == JobStatus.SUCCEEDED


def test_job_items_have_all_types(client):
    tid = _setup_topic(client)
    with patch(RUN_SINGLE_PATH, side_effect=_mock_output):
        r = client.post(f"/api/topics/{tid}/analysis/jobs")
    types = {i["item_type"] for i in r.json()["items"]}
    assert types == {t.value for t in AnalysisType}


def test_create_analysis_job_with_parse_type(client):
    """JobType.parse creates a parse job (stub-only, no analysis items)."""
    tid = _setup_topic(client)
    r = client.post(
        f"/api/topics/{tid}/analysis/jobs",
        params={"job_type": "parse"},
    )
    assert r.status_code == 201
    assert r.json()["job"]["job_type"] == "parse"
    # parse jobs don't run analysis items
    assert r.json()["job"]["status"] == JobStatus.SUCCEEDED


def test_create_analysis_job_with_analysis_type(client):
    """JobType.analysis creates an analysis job with real execution."""
    tid = _setup_topic(client)
    with patch(RUN_SINGLE_PATH, side_effect=_mock_output):
        r = client.post(
            f"/api/topics/{tid}/analysis/jobs",
            params={"job_type": "analysis"},
        )
    assert r.status_code == 201
    assert r.json()["job"]["job_type"] == "analysis"


def test_invalid_job_type_422(client):
    tid = _setup_topic(client)
    r = client.post(
        f"/api/topics/{tid}/analysis/jobs",
        params={"job_type": "INVALID_TYPE"},
    )
    assert r.status_code == 422


# ── List jobs ──


def test_list_jobs(client):
    tid = _setup_topic(client)
    with patch(RUN_SINGLE_PATH, side_effect=_mock_output):
        client.post(f"/api/topics/{tid}/analysis/jobs")
        client.post(f"/api/topics/{tid}/analysis/jobs")
    r = client.get(f"/api/topics/{tid}/analysis/jobs")
    assert r.status_code == 200
    assert len(r.json()["jobs"]) == 2


def test_list_jobs_empty(client):
    tid = _create_topic(client)
    r = client.get(f"/api/topics/{tid}/analysis/jobs")
    assert r.status_code == 200
    assert r.json()["jobs"] == []


# ── Analysis status ──


def test_analysis_status(client):
    tid = _setup_topic(client)
    with patch(RUN_SINGLE_PATH, side_effect=_mock_output):
        client.post(f"/api/topics/{tid}/analysis/jobs")
    r = client.get(f"/api/topics/{tid}/analysis/status")
    assert r.status_code == 200
    data = r.json()
    assert data["has_jobs"] is True
    assert len(data["analysis_types_completed"]) == 6
    assert data["latest_job"] is not None


def test_analysis_status_no_jobs(client):
    tid = _create_topic(client)
    r = client.get(f"/api/topics/{tid}/analysis/status")
    assert r.status_code == 200
    assert r.json()["has_jobs"] is False


# ── Job detail ──


def test_get_job_detail(client):
    tid = _setup_topic(client)
    with patch(RUN_SINGLE_PATH, side_effect=_mock_output):
        r = client.post(f"/api/topics/{tid}/analysis/jobs")
        job_id = r.json()["job"]["id"]
    r = client.get(f"/api/analysis/jobs/{job_id}")
    assert r.status_code == 200
    assert r.json()["job"]["id"] == job_id
    assert len(r.json()["items"]) == 6


def test_get_job_detail_404(client):
    r = client.get("/api/analysis/jobs/nonexistent")
    assert r.status_code == 404


# ── Cancel job ──


def test_cancel_job(client):
    tid = _setup_topic(client)
    with patch(RUN_SINGLE_PATH, side_effect=_mock_output):
        r = client.post(f"/api/topics/{tid}/analysis/jobs")
    job_id = r.json()["job"]["id"]
    r = client.post(f"/api/analysis/jobs/{job_id}/cancel")
    assert r.status_code == 200
    assert r.json()["job"]["status"] in (JobStatus.SUCCEEDED, JobStatus.CANCELLED)


def test_cancel_job_404(client):
    r = client.post("/api/analysis/jobs/nonexistent/cancel")
    assert r.status_code == 404


# ── Fix 012: Single item failure ──


def test_single_item_failure_job_failed(client):
    """A failed item causes job status = FAILED, other items still succeed."""
    tid = _setup_topic(client)

    def fail_events(topic_id, output_type, session, **kwargs):
        if output_type == "events":
            raise ValueError("LLM error for events: HTTP 500: Server error")
        return _mock_output(topic_id, output_type, session, **kwargs)

    with patch(RUN_SINGLE_PATH, side_effect=fail_events):
        r = client.post(f"/api/topics/{tid}/analysis/jobs")
    assert r.status_code == 201
    data = r.json()
    assert data["job"]["status"] == JobStatus.FAILED
    assert "1 failed" in data["job"]["message"].lower()

    items = data["items"]
    succeeded = [i for i in items if i["status"] == JobStatus.SUCCEEDED]
    failed = [i for i in items if i["status"] == JobStatus.FAILED]
    assert len(succeeded) == 5
    assert len(failed) == 1
    assert failed[0]["item_type"] == "events"
    assert "LLM error" in failed[0]["message"]


# ── Fix 012: Cancelled job skips execution ──


def test_cancelled_job_does_not_run_analysis(client):
    """A cancelled job should not execute any analysis."""
    from db import get_session
    from main import app
    from services import job_service

    tid = _setup_topic(client)

    # Get a real session
    session_gen = app.dependency_overrides.get(get_session, get_session)
    session = next(session_gen())

    # Create job and cancel it
    job = job_service.create_analysis_job(tid, "analysis", session)
    job_service.create_default_analysis_items(job.id, session)
    session.commit()
    job = job_service.cancel_job(job.id, session)

    # Now run — should return immediately
    with patch(RUN_SINGLE_PATH) as mock_run:
        job = job_service.run_analysis_job(job.id, session)
        mock_run.assert_not_called()

    assert job.status == JobStatus.CANCELLED


# ── Fix 012: No duplicate AnalysisOutput on re-run ──


def test_rerun_same_type_no_duplicates(client):
    """Running the same output_type twice only keeps one AnalysisOutput."""
    # Create a default provider needed by analysis/run
    r = client.post(
        "/api/providers",
        json={
            "name": "DedupP",
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
        json={"name": "DedupT", "provider_id": provider_id},
    )
    tid = r.json()["id"]
    _upload(client, tid)
    _parse(client, tid)

    with patch(
        "services.analysis_service.OpenAICompatibleLLMClient.chat",
        side_effect=_mock_analysis_llm,
    ):
        r = client.post(f"/api/topics/{tid}/analysis/run?limit_chunks=3")
        assert r.status_code == 200
        count1 = r.json()["count"]
        r = client.post(f"/api/topics/{tid}/analysis/run?limit_chunks=3")
        count2 = r.json()["count"]

    assert count1 == 6
    assert count2 == 6

    r = client.get(f"/api/topics/{tid}/analysis/outputs")
    outputs = r.json()["outputs"]
    assert r.json()["count"] == 6
    type_counts = {}
    for o in outputs:
        t = o["output_type"]
        type_counts[t] = type_counts.get(t, 0) + 1
    for count in type_counts.values():
        assert count == 1, f"Duplicate found: {type_counts}"


def _mock_analysis_llm(messages, model, temperature, max_tokens, response_format):
    import json

    from services.llm_client import LLMResponse

    return LLMResponse(
        content=json.dumps(
            {
                "title": "Test",
                "source_chunk_ids": [],
                "evidence_quotes": ["test."],
                "confidence": 0.9,
            }
        ),
        model="test",
        usage={},
    )
