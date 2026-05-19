"""Tests for local_extraction_worker — mock LLM, no real API calls."""

import json
from unittest.mock import patch

from services.local_extraction_worker import (
    build_local_extraction_messages,
    run_local_extraction_for_chunk,
)

FAKE_CHUNK_ID = "chunk-test-001"
FAKE_CHUNK_TEXT = "第一章 张三站在窗前望着远处。"

VALID_EXTRACTION_JSON = json.dumps(
    {
        "analysis_type": "local_extraction",
        "chunk_id": FAKE_CHUNK_ID,
        "local_characters": [
            {
                "character_id_hint": "zhang_san",
                "name": "张三",
                "source_chunk_ids": [FAKE_CHUNK_ID],
                "evidence_quotes": ["张三站在窗前"],
                "confidence": 0.9,
            }
        ],
        "local_events": [],
        "local_relations": [],
    }
)


class MockResponse:
    def __init__(self, content, model="mock-model", usage=None):
        self.content = content
        self.model = model
        self.usage = usage or {
            "prompt_tokens": 500,
            "completion_tokens": 200,
            "total_tokens": 700,
        }


def test_build_messages_basic():
    prompt, messages = build_local_extraction_messages(
        chunk_id=FAKE_CHUNK_ID,
        chunk_text=FAKE_CHUNK_TEXT,
    )
    assert len(messages) == 2
    assert messages[0].role == "system"
    assert messages[1].role == "user"
    assert FAKE_CHUNK_ID in messages[1].content
    assert FAKE_CHUNK_TEXT in messages[1].content


def test_build_messages_with_metadata():
    prompt, messages = build_local_extraction_messages(
        chunk_id=FAKE_CHUNK_ID,
        chunk_text=FAKE_CHUNK_TEXT,
        chapter_index=3,
        chunk_index=1,
        chapter_title="第三章 转折",
    )
    user = messages[1].content
    assert "chapter_index: 3" in user
    assert "chunk_index: 1" in user
    assert "第三章 转折" in user


def test_run_success():
    with patch("services.local_extraction_worker.OpenAICompatibleLLMClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.chat.return_value = MockResponse(VALID_EXTRACTION_JSON)

        result = run_local_extraction_for_chunk(
            chunk_id=FAKE_CHUNK_ID,
            chunk_text=FAKE_CHUNK_TEXT,
            base_url="http://test",
            api_key="sk-test",
            model_name="test-model",
        )

        assert result.ok
        assert result.chunk_id == FAKE_CHUNK_ID
        assert result.parsed_json is not None
        assert result.parsed_json["local_characters"][0]["name"] == "张三"
        assert result.prompt_tokens == 500
        assert result.completion_tokens == 200
        assert result.total_tokens == 700
        assert result.model_used == "mock-model"


def test_run_json_parse_failure():
    with patch("services.local_extraction_worker.OpenAICompatibleLLMClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.chat.return_value = MockResponse("not valid json!!!")

        result = run_local_extraction_for_chunk(
            chunk_id=FAKE_CHUNK_ID,
            chunk_text=FAKE_CHUNK_TEXT,
            base_url="http://test",
            api_key="sk-test",
            model_name="test-model",
        )

        assert not result.ok
        assert "json" in result.error.lower()


def test_run_llm_error():
    from services.llm_client import LLMClientError

    with patch("services.local_extraction_worker.OpenAICompatibleLLMClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.chat.side_effect = LLMClientError("service unavailable", 503)

        result = run_local_extraction_for_chunk(
            chunk_id=FAKE_CHUNK_ID,
            chunk_text=FAKE_CHUNK_TEXT,
            base_url="http://test",
            api_key="sk-test",
            model_name="test-model",
        )

        assert not result.ok
        assert "unavailable" in result.error.lower()


def test_run_retry_on_retryable_error():
    from services.llm_client import LLMClientError

    with patch("services.local_extraction_worker.OpenAICompatibleLLMClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.chat.side_effect = [
            LLMClientError("rate limit exceeded", 429),
            MockResponse(VALID_EXTRACTION_JSON),
        ]

        result = run_local_extraction_for_chunk(
            chunk_id=FAKE_CHUNK_ID,
            chunk_text=FAKE_CHUNK_TEXT,
            base_url="http://test",
            api_key="sk-test",
            model_name="test-model",
        )

        assert result.ok
        assert result.retry_count >= 1
        assert mock_client.chat.call_count == 2


def test_run_thinking_mode_disabled():
    with patch("services.local_extraction_worker.OpenAICompatibleLLMClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.chat.return_value = MockResponse(VALID_EXTRACTION_JSON)

        run_local_extraction_for_chunk(
            chunk_id=FAKE_CHUNK_ID,
            chunk_text=FAKE_CHUNK_TEXT,
            base_url="http://test",
            api_key="sk-test",
            model_name="test-model",
            thinking_mode="disabled",
        )

        call_kwargs = mock_client.chat.call_args.kwargs
        assert call_kwargs["extra_body"] == {"thinking": {"type": "disabled"}}


def test_run_thinking_mode_enabled():
    with patch("services.local_extraction_worker.OpenAICompatibleLLMClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.chat.return_value = MockResponse(VALID_EXTRACTION_JSON)

        run_local_extraction_for_chunk(
            chunk_id=FAKE_CHUNK_ID,
            chunk_text=FAKE_CHUNK_TEXT,
            base_url="http://test",
            api_key="sk-test",
            model_name="test-model",
            thinking_mode="enabled",
        )

        call_kwargs = mock_client.chat.call_args.kwargs
        assert call_kwargs["extra_body"] == {"thinking": {"type": "enabled"}}


def test_result_duration_tracked():
    with patch("services.local_extraction_worker.OpenAICompatibleLLMClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.chat.return_value = MockResponse(VALID_EXTRACTION_JSON)

        result = run_local_extraction_for_chunk(
            chunk_id=FAKE_CHUNK_ID,
            chunk_text=FAKE_CHUNK_TEXT,
            base_url="http://test",
            api_key="sk-test",
            model_name="test-model",
        )

        assert result.duration_seconds >= 0


def test_fenced_json_returns_canonical_content_json():
    """Fenced JSON response should have content_json as canonical JSON, not markdown."""
    fenced = "```json\n" + VALID_EXTRACTION_JSON + "\n```"
    with patch("services.local_extraction_worker.OpenAICompatibleLLMClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.chat.return_value = MockResponse(fenced)

        result = run_local_extraction_for_chunk(
            chunk_id=FAKE_CHUNK_ID,
            chunk_text=FAKE_CHUNK_TEXT,
            base_url="http://test",
            api_key="sk-test",
            model_name="test-model",
        )

        assert result.ok
        assert result.content_json is not None
        parsed = json.loads(result.content_json)
        assert parsed["analysis_type"] == "local_extraction"
        assert "```" not in result.content_json


def test_wrong_chunk_id_validation_fails():
    """If parsed JSON has wrong chunk_id, validation should fail."""
    bad_json = json.dumps(
        {
            "analysis_type": "local_extraction",
            "chunk_id": "wrong-chunk-id",
            "local_characters": [
                {"name": "X", "source_chunk_ids": ["wrong-chunk-id"], "evidence_quotes": ["e"]}
            ],
        }
    )
    with patch("services.local_extraction_worker.OpenAICompatibleLLMClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.chat.return_value = MockResponse(bad_json)

        result = run_local_extraction_for_chunk(
            chunk_id=FAKE_CHUNK_ID,
            chunk_text=FAKE_CHUNK_TEXT,
            base_url="http://test",
            api_key="sk-test",
            model_name="test-model",
        )

        assert not result.ok
        assert "mismatch" in (result.error or "").lower()


def test_503_retry_then_success():
    """503 first attempt should retry and succeed on second."""
    from services.llm_client import LLMClientError

    with patch("services.local_extraction_worker.OpenAICompatibleLLMClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.chat.side_effect = [
            LLMClientError("service unavailable", 503),
            MockResponse(VALID_EXTRACTION_JSON),
        ]

        result = run_local_extraction_for_chunk(
            chunk_id=FAKE_CHUNK_ID,
            chunk_text=FAKE_CHUNK_TEXT,
            base_url="http://test",
            api_key="sk-test",
            model_name="test-model",
        )

        assert result.ok
        assert result.retry_count >= 1
        assert mock_client.chat.call_count == 2


def test_api_key_masked_in_error():
    """Error message must not contain the api_key."""
    from services.llm_client import LLMClientError

    with patch("services.local_extraction_worker.OpenAICompatibleLLMClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.chat.side_effect = LLMClientError("auth failed with key sk-test-1234567", 401)

        result = run_local_extraction_for_chunk(
            chunk_id=FAKE_CHUNK_ID,
            chunk_text=FAKE_CHUNK_TEXT,
            base_url="http://test",
            api_key="sk-test-1234567",
            model_name="test-model",
        )

        assert not result.ok
        assert result.error is not None
        assert "sk-test-1234567" not in result.error
        assert "sk-..." in result.error or "***" in result.error


def test_retry_exhausted_returns_last_error():
    """When all retries fail, return last attempt's error, not first."""
    from services.llm_client import LLMClientError

    with patch("services.local_extraction_worker.OpenAICompatibleLLMClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.chat.side_effect = [
            LLMClientError("first error: service unavailable", 503),
            MockResponse("not json {{{"),  # JSON parse fail
            LLMClientError("last error: server overloaded", 503),
        ]

        result = run_local_extraction_for_chunk(
            chunk_id=FAKE_CHUNK_ID,
            chunk_text=FAKE_CHUNK_TEXT,
            base_url="http://test",
            api_key="sk-test",
            model_name="test-model",
        )

        assert not result.ok
        assert result.retry_count > 0
        assert "last error" in (result.error or "").lower()
        assert "first error" not in (result.error or "").lower()
