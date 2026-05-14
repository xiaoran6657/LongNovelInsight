import time
from typing import Any

from sqlmodel import Session

from models.model_provider import ModelProvider, mask_api_key
from services.llm_client import LLMClientError, LLMMessage, OpenAICompatibleLLMClient


def test_provider(provider_id: str, session: Session) -> dict[str, Any]:
    provider = session.get(ModelProvider, provider_id)
    if provider is None:
        return {
            "success": False,
            "provider_id": provider_id,
            "model_name": "",
            "latency_ms": 0,
            "message": "Provider not found",
        }

    client = OpenAICompatibleLLMClient(
        base_url=provider.base_url,
        api_key=provider.api_key,
        timeout=60.0,
        max_retries=0,
    )

    messages = [
        LLMMessage(role="system", content="You are a connection test assistant."),
        LLMMessage(role="user", content="Return exactly: OK"),
    ]

    start = time.monotonic()
    try:
        response = client.chat(
            messages=messages,
            model=provider.model_name,
            temperature=0,
            max_tokens=8,
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        return {
            "success": True,
            "provider_id": provider_id,
            "model_name": provider.model_name,
            "latency_ms": latency_ms,
            "message": "Connection successful",
        }
    except LLMClientError as e:
        latency_ms = int((time.monotonic() - start) * 1000)
        safe_msg = _sanitize_error(e.message, provider.api_key)
        return {
            "success": False,
            "provider_id": provider_id,
            "model_name": provider.model_name,
            "latency_ms": latency_ms,
            "message": safe_msg,
        }
    except Exception as e:
        latency_ms = int((time.monotonic() - start) * 1000)
        return {
            "success": False,
            "provider_id": provider_id,
            "model_name": provider.model_name,
            "latency_ms": latency_ms,
            "message": f"Unexpected error: {e}",
        }


def _sanitize_error(message: str, api_key: str) -> str:
    return message.replace(api_key, mask_api_key(api_key))
