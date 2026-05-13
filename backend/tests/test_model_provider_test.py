from unittest.mock import patch

from sqlmodel import Session

from models.model_provider import ModelProvider


def _create_provider(
    session: Session, name: str = "Test", is_default: bool = False
) -> ModelProvider:
    provider = ModelProvider(
        name=name,
        provider_type="openai_compatible",
        base_url="https://api.example.com",
        api_key="sk-test-key-12345",
        model_name="test-model",
        is_default=is_default,
    )
    session.add(provider)
    session.commit()
    session.refresh(provider)
    return provider


class TestProviderTestEndpoint:
    def test_success(self, client):
        with client as c:
            # Create a provider first
            resp = c.post(
                "/api/model-providers",
                json={
                    "name": "Test Provider",
                    "provider_type": "openai_compatible",
                    "base_url": "https://api.example.com",
                    "api_key": "sk-test-key-12345",
                    "model_name": "test-model",
                },
            )
            provider_id = resp.json()["id"]

            # Mock the LLM client to return OK
            with patch(
                "services.provider_test_service.OpenAICompatibleLLMClient.chat"
            ) as mock_chat:
                from services.llm_client import LLMResponse

                mock_chat.return_value = LLMResponse(
                    content="OK",
                    model="test-model",
                    usage={"total_tokens": 3},
                )

                resp = c.post(f"/api/model-providers/{provider_id}/test")
                assert resp.status_code == 200
                data = resp.json()
                assert data["success"] is True
                assert data["provider_id"] == provider_id
                assert data["model_name"] == "test-model"
                assert data["latency_ms"] >= 0
                assert "Connection successful" in data["message"]
                # No plaintext api_key in response
                assert "sk-test-key-12345" not in str(data)

    def test_provider_not_found(self, client):
        with client as c:
            resp = c.post("/api/model-providers/nonexistent-id/test")
            assert resp.status_code == 404
            assert "not found" in resp.json()["detail"].lower()

    def test_llm_error(self, client):
        with client as c:
            resp = c.post(
                "/api/model-providers",
                json={
                    "name": "Error Provider",
                    "provider_type": "openai_compatible",
                    "base_url": "https://api.example.com",
                    "api_key": "sk-test-key-12345",
                    "model_name": "test-model",
                },
            )
            provider_id = resp.json()["id"]

            with patch(
                "services.provider_test_service.OpenAICompatibleLLMClient.chat"
            ) as mock_chat:
                from services.llm_client import LLMClientError

                mock_chat.side_effect = LLMClientError("HTTP 401: Invalid API key", status_code=401)

                resp = c.post(f"/api/model-providers/{provider_id}/test")
                assert resp.status_code == 200  # endpoint returns 200 with success=false
                data = resp.json()
                assert data["success"] is False
                assert data["provider_id"] == provider_id
                assert "sk-test-key-12345" not in str(data)
                # The error message should be sanitized
                assert "401" in data["message"]

    def test_no_api_key_leak_in_response(self, client):
        with client as c:
            resp = c.post(
                "/api/model-providers",
                json={
                    "name": "Leak Test",
                    "provider_type": "openai_compatible",
                    "base_url": "https://api.example.com",
                    "api_key": "sk-very-secret-key-do-not-leak",
                    "model_name": "test-model",
                },
            )
            provider_id = resp.json()["id"]

            with patch(
                "services.provider_test_service.OpenAICompatibleLLMClient.chat"
            ) as mock_chat:
                from services.llm_client import LLMResponse

                mock_chat.return_value = LLMResponse(
                    content="OK",
                    model="test-model",
                    usage={},
                )

                resp = c.post(f"/api/model-providers/{provider_id}/test")
                data = resp.json()
                assert "sk-very-secret-key-do-not-leak" not in str(data)
                assert "very-secret" not in str(data)
