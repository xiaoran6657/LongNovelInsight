def _create(client, **kwargs):
    defaults = {
        "name": "Test Provider",
        "provider_type": "openai_compatible",
        "base_url": "https://api.deepseek.com",
        "api_key": "sk-test-key-12345678",
        "model_name": "deepseek-chat",
    }
    defaults.update(kwargs)
    return client.post("/api/model-providers", json=defaults)


def test_create_provider(client):
    response = _create(client)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Provider"
    assert data["provider_type"] == "openai_compatible"
    assert data["base_url"] == "https://api.deepseek.com"
    assert "api_key" not in data
    assert data["masked_api_key"] is not None
    assert data["id"] is not None


def test_mask_short_api_key(client):
    response = _create(client, name="Short Key", api_key="abc")
    assert response.status_code == 201
    data = response.json()
    assert data["masked_api_key"] == "***"


def test_mask_long_api_key(client):
    response = _create(client, name="Long Key", api_key="sk-1234567890abcdef")
    assert response.status_code == 201
    data = response.json()
    assert data["masked_api_key"].startswith("sk-")
    assert data["masked_api_key"].endswith("cdef")
    assert "..." in data["masked_api_key"]


def test_list_providers(client):
    _create(client, name="P1")
    _create(client, name="P2")
    response = client.get("/api/model-providers")
    assert response.status_code == 200
    assert len(response.json()["providers"]) == 2


def test_get_provider(client):
    r = _create(client, name="Find Me")
    pid = r.json()["id"]
    response = client.get(f"/api/model-providers/{pid}")
    assert response.status_code == 200
    assert response.json()["name"] == "Find Me"


def test_get_provider_404(client):
    response = client.get("/api/model-providers/nonexistent")
    assert response.status_code == 404


def test_update_provider(client):
    r = _create(client, name="Original")
    pid = r.json()["id"]
    response = client.patch(
        f"/api/model-providers/{pid}",
        json={"name": "Updated", "temperature": 0.5},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Updated"
    assert response.json()["temperature"] == 0.5


def test_update_provider_404(client):
    response = client.patch("/api/model-providers/nonexistent", json={"name": "X"})
    assert response.status_code == 404


def test_delete_provider(client):
    r = _create(client, name="Delete Me")
    pid = r.json()["id"]
    response = client.delete(f"/api/model-providers/{pid}")
    assert response.status_code == 200
    assert response.json()["deleted"] is True


def test_delete_provider_404(client):
    response = client.delete("/api/model-providers/nonexistent")
    assert response.status_code == 404


def test_delete_provider_in_use_409(client):
    r = _create(client, name="In Use")
    pid = r.json()["id"]
    # Bind this provider to a topic
    client.post("/api/topics", json={"name": "T", "provider_id": pid})
    response = client.delete(f"/api/model-providers/{pid}")
    assert response.status_code == 409


def test_invalid_provider_type(client):
    response = _create(client, name="Bad", provider_type="anthropic")
    assert response.status_code == 422


def test_duplicate_name(client):
    _create(client, name="Only One")
    response = _create(client, name="Only One")
    assert response.status_code == 409


def test_is_default_uniqueness(client):
    _create(client, name="First Default", is_default=True)
    _create(client, name="Second Default", is_default=True)
    # Both should have been created successfully, but only the latest
    # should be the default after _set_default runs
    response = client.get("/api/model-providers")
    providers = response.json()["providers"]
    defaults = [p for p in providers if p["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["name"] == "Second Default"


def test_default_unchanged_on_non_default_create(client):
    _create(client, name="Default", is_default=True)
    _create(client, name="Not Default", is_default=False)
    response = client.get("/api/model-providers")
    providers = response.json()["providers"]
    defaults = [p for p in providers if p["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["name"] == "Default"


def test_update_unset_default(client):
    r = _create(client, name="Default", is_default=True)
    pid = r.json()["id"]
    response = client.patch(f"/api/model-providers/{pid}", json={"is_default": False})
    assert response.status_code == 200
    assert response.json()["is_default"] is False
