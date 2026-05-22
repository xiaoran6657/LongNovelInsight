def test_health_returns_ok(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.2.0-dev"
    assert "topic_count" in data
    assert "total_disk_usage_bytes" in data
