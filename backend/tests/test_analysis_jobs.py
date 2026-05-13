import io


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


# ── Create job ──


def test_create_analysis_job_success(client):
    tid = _setup_topic(client)
    r = client.post(f"/api/topics/{tid}/analysis/jobs")
    assert r.status_code == 201
    data = r.json()
    assert data["job"]["status"] == "SUCCEEDED"
    assert data["job"]["job_type"] == "ANALYSIS_ALL"
    assert data["job"]["progress_current"] == 6
    assert data["job"]["progress_total"] == 6
    assert len(data["items"]) == 6


def test_job_items_all_succeeded(client):
    tid = _setup_topic(client)
    r = client.post(f"/api/topics/{tid}/analysis/jobs")
    for item in r.json()["items"]:
        assert item["status"] == "SUCCEEDED"


def test_job_items_have_all_types(client):
    tid = _setup_topic(client)
    r = client.post(f"/api/topics/{tid}/analysis/jobs")
    types = {i["item_type"] for i in r.json()["items"]}
    assert types == {"OVERVIEW", "CHARACTERS", "RELATIONS", "EVENTS", "CAUSALITY", "THEMES"}


def test_create_specific_job_type(client):
    tid = _setup_topic(client)
    r = client.post(
        f"/api/topics/{tid}/analysis/jobs",
        params={"job_type": "ANALYSIS_CHARACTERS"},
    )
    assert r.status_code == 201
    assert r.json()["job"]["job_type"] == "ANALYSIS_CHARACTERS"


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
    r = client.post(f"/api/topics/{tid}/analysis/jobs")
    job_id = r.json()["job"]["id"]

    r = client.post(f"/api/analysis/jobs/{job_id}/cancel")
    assert r.status_code == 200
    # Already succeeded, cancel should be no-op
    assert r.json()["job"]["status"] in ("SUCCEEDED", "CANCELLED")


def test_cancel_job_404(client):
    r = client.post("/api/analysis/jobs/nonexistent/cancel")
    assert r.status_code == 404
