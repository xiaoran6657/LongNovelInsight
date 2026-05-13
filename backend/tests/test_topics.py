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
        "/api/model-providers",
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
