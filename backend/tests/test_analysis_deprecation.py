"""Contract tests for the authoritative AnalysisRun API and deprecated executors."""

LEGACY_OPERATIONS = [
    ("/api/topics/{topic_id}/analysis/run", "post"),
    ("/api/topics/{topic_id}/analysis/run-async", "post"),
    ("/api/topics/{topic_id}/analysis/run/{output_type}", "post"),
    ("/api/topics/{topic_id}/analysis/jobs", "post"),
    ("/api/topics/{topic_id}/analysis/jobs", "get"),
    ("/api/topics/{topic_id}/analysis/status", "get"),
    ("/api/analysis/jobs/{job_id}", "get"),
    ("/api/analysis/jobs/{job_id}/cancel", "post"),
]

AUTHORITATIVE_OPERATIONS = [
    ("/api/topics/{topic_id}/analysis/runs", "post"),
    ("/api/topics/{topic_id}/analysis/runs", "get"),
    ("/api/works/{work_id}/analysis/runs", "post"),
    ("/api/analysis/runs/{run_id}", "get"),
    ("/api/analysis/runs/{run_id}/cancel", "post"),
    ("/api/analysis/runs/{run_id}/retry-failed", "post"),
    ("/api/analysis/runs/{run_id}/resume", "post"),
    ("/api/topics/{topic_id}/analysis/outputs", "get"),
    ("/api/topics/{topic_id}/analysis/outputs", "delete"),
]


def test_legacy_analysis_executors_are_deprecated_in_openapi(client):
    schema = client.get("/openapi.json").json()

    for path, method in LEGACY_OPERATIONS:
        assert schema["paths"][path][method]["deprecated"] is True


def test_analysis_run_and_output_contracts_are_not_deprecated(client):
    schema = client.get("/openapi.json").json()

    for path, method in AUTHORITATIVE_OPERATIONS:
        assert schema["paths"][path][method].get("deprecated") is not True
