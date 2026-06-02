import json

import httpx
import pytest

from services.llm_client import LLMClientError, LLMMessage, OpenAICompatibleLLMClient


def _fake_response(status_code=200, json_data=None, text=""):
    """Build a fake httpx.Response for monkeypatching."""
    resp = httpx.Response(status_code=status_code, text=text or json.dumps(json_data or {}))
    # httpx.Response._content needs to be set for .json() to work
    resp._content = (text or json.dumps(json_data or {})).encode("utf-8")
    return resp


class TestLLMClient:
    def test_chat_success(self, monkeypatch):
        def mock_post(url, *args, **kwargs):
            return _fake_response(
                200,
                {
                    "choices": [{"message": {"content": "OK"}}],
                    "model": "test-model",
                    "usage": {"total_tokens": 5},
                },
            )

        monkeypatch.setattr(httpx, "post", mock_post)

        client = OpenAICompatibleLLMClient(
            base_url="https://api.example.com",
            api_key="sk-test-key-12345",
        )
        result = client.chat(
            messages=[LLMMessage(role="user", content="Hello")],
            model="test-model",
        )
        assert result.content == "OK"
        assert result.model == "test-model"
        assert result.usage == {"total_tokens": 5}

    def test_chat_http_401(self, monkeypatch):
        def mock_post(url, *args, **kwargs):
            return _fake_response(401, {"error": {"message": "Invalid API key"}})

        monkeypatch.setattr(httpx, "post", mock_post)

        client = OpenAICompatibleLLMClient(
            base_url="https://api.example.com",
            api_key="sk-bad-key",
        )
        with pytest.raises(LLMClientError) as exc:
            client.chat(
                messages=[LLMMessage(role="user", content="Hello")],
                model="test-model",
            )
        assert "401" in str(exc.value)
        assert "Invalid API key" in str(exc.value)

    def test_chat_network_error(self, monkeypatch):
        def mock_post(url, *args, **kwargs):
            raise httpx.NetworkError("Connection refused")

        monkeypatch.setattr(httpx, "post", mock_post)

        client = OpenAICompatibleLLMClient(
            base_url="https://api.example.com",
            api_key="sk-test-key-12345",
        )
        with pytest.raises(LLMClientError) as exc:
            client.chat(
                messages=[LLMMessage(role="user", content="Hello")],
                model="test-model",
            )
        assert "Network error" in str(exc.value)
        # Error should not contain the api key
        assert "sk-test-key-12345" not in str(exc.value)

    def test_chat_invalid_json(self, monkeypatch):
        def mock_post(url, *args, **kwargs):
            return _fake_response(200, text="not valid json {{{")

        monkeypatch.setattr(httpx, "post", mock_post)

        client = OpenAICompatibleLLMClient(
            base_url="https://api.example.com",
            api_key="sk-test-key-12345",
        )
        with pytest.raises(LLMClientError) as exc:
            client.chat(
                messages=[LLMMessage(role="user", content="Hello")],
                model="test-model",
            )
        assert "Invalid JSON" in str(exc.value)

    def test_chat_empty_choices(self, monkeypatch):
        def mock_post(url, *args, **kwargs):
            return _fake_response(200, {"choices": []})

        monkeypatch.setattr(httpx, "post", mock_post)

        client = OpenAICompatibleLLMClient(
            base_url="https://api.example.com",
            api_key="sk-test-key-12345",
        )
        with pytest.raises(LLMClientError) as exc:
            client.chat(
                messages=[LLMMessage(role="user", content="Hello")],
                model="test-model",
            )
        assert "empty choices" in str(exc.value)

    def test_chat_missing_content(self, monkeypatch):
        def mock_post(url, *args, **kwargs):
            return _fake_response(200, {"choices": [{"message": {}}]})

        monkeypatch.setattr(httpx, "post", mock_post)

        client = OpenAICompatibleLLMClient(
            base_url="https://api.example.com",
            api_key="sk-test-key-12345",
        )
        with pytest.raises(LLMClientError) as exc:
            client.chat(
                messages=[LLMMessage(role="user", content="Hello")],
                model="test-model",
            )
        assert "missing content" in str(exc.value).lower()

    def test_error_does_not_leak_api_key(self, monkeypatch):
        """Even when the server echoes back headers, our error should be safe."""

        def mock_post(url, *args, **kwargs):
            return _fake_response(401, {"error": {"message": "Bad key"}})

        monkeypatch.setattr(httpx, "post", mock_post)

        client = OpenAICompatibleLLMClient(
            base_url="https://api.example.com",
            api_key="sk-secret-do-not-leak",
        )
        with pytest.raises(LLMClientError) as exc:
            client.chat(
                messages=[LLMMessage(role="user", content="Hello")],
                model="test-model",
            )
        assert "sk-secret-do-not-leak" not in str(exc.value)

    def test_retry_on_timeout(self, monkeypatch):
        call_count = 0

        def mock_post(url, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.TimeoutException("timed out")
            return _fake_response(200, {"choices": [{"message": {"content": "finally"}}]})

        monkeypatch.setattr(httpx, "post", mock_post)

        client = OpenAICompatibleLLMClient(
            base_url="https://api.example.com",
            api_key="sk-test-key-12345",
            max_retries=2,
        )
        result = client.chat(
            messages=[LLMMessage(role="user", content="Hello")],
            model="test-model",
        )
        assert result.content == "finally"
        assert call_count == 3

    def test_transport_error_caught(self, monkeypatch):
        """httpx.TransportError should be wrapped as LLMClientError, not bubble up."""

        def mock_post(url, *args, **kwargs):
            raise httpx.RemoteProtocolError("peer closed connection")

        monkeypatch.setattr(httpx, "post", mock_post)

        client = OpenAICompatibleLLMClient(
            base_url="https://api.example.com",
            api_key="sk-test-key-12345",
            max_retries=0,
        )
        with pytest.raises(LLMClientError) as exc:
            client.chat(
                messages=[LLMMessage(role="user", content="Hello")],
                model="test-model",
            )
        assert "Transport error" in str(exc.value)

    def test_transport_error_retried(self, monkeypatch):
        call_count = 0

        def mock_post(url, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise httpx.RemoteProtocolError("incomplete chunked read")
            return _fake_response(200, {"choices": [{"message": {"content": "ok"}}]})

        monkeypatch.setattr(httpx, "post", mock_post)

        client = OpenAICompatibleLLMClient(
            base_url="https://api.example.com",
            api_key="sk-test-key-12345",
            max_retries=1,
        )
        result = client.chat(
            messages=[LLMMessage(role="user", content="Hello")],
            model="test-model",
        )
        assert result.content == "ok"
        assert call_count == 2

    def test_finish_reason_returned(self, monkeypatch):
        def mock_post(url, *args, **kwargs):
            return _fake_response(
                200,
                {
                    "choices": [
                        {
                            "message": {"content": "OK"},
                            "finish_reason": "length",
                        }
                    ],
                    "model": "test-model",
                    "usage": {"completion_tokens": 8192},
                },
            )

        monkeypatch.setattr(httpx, "post", mock_post)

        client = OpenAICompatibleLLMClient(
            base_url="https://api.example.com",
            api_key="sk-test-key-12345",
        )
        result = client.chat(
            messages=[LLMMessage(role="user", content="Hello")],
            model="test-model",
        )
        assert result.finish_reason == "length"
        assert result.usage == {"completion_tokens": 8192}

    def test_finish_reason_none_when_missing(self, monkeypatch):
        def mock_post(url, *args, **kwargs):
            return _fake_response(
                200,
                {"choices": [{"message": {"content": "OK"}}]},
            )

        monkeypatch.setattr(httpx, "post", mock_post)

        client = OpenAICompatibleLLMClient(
            base_url="https://api.example.com",
            api_key="sk-test-key-12345",
        )
        result = client.chat(
            messages=[LLMMessage(role="user", content="Hello")],
            model="test-model",
        )
        assert result.finish_reason is None
