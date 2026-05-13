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


def _mock_topic_analysis(messages, model, temperature, max_tokens, response_format):
    from services.llm_client import LLMResponse

    return LLMResponse(
        content='{"title":"T","source_chunk_ids":[],"evidence_quotes":["测试。"],"confidence":0.9}',
        model="test",
        usage={},
    )
