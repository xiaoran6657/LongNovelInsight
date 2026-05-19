"""Worker for running a single analysis type. No DB access, pure LLM call."""

import json
import time
from dataclasses import dataclass, field
from typing import Any

from services.llm_client import LLMClientError, LLMMessage, OpenAICompatibleLLMClient
from services.prompt_loader import load_prompt

# Per-type max output tokens (overridden by effective config if set)
ANALYSIS_MAX_TOKENS_BY_TYPE: dict[str, int] = {
    "overview": 1024,
    "characters": 3072,
    "relations": 2048,
    "events": 3072,
    "causality": 2048,
    "themes": 1536,
}

RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}
RETRYABLE_KEYWORDS = ["rate limit", "rate_limit", "insufficient_system_resource"]


@dataclass
class AnalysisTypeResult:
    output_type: str
    ok: bool
    parsed_json: dict[str, Any] | None = None
    raw_text: str | None = None
    error: str | None = None
    duration_seconds: float = 0.0
    usage: dict[str, Any] = field(default_factory=dict)
    finish_reason: str | None = None
    model_name: str | None = None
    retry_count: int = 0


def _build_messages(
    output_type: str,
    chunks_text: str,
    deepen_previous: str | None = None,
) -> tuple[str, list[LLMMessage]]:
    """Build prompt-cache-friendly messages with shared prefix."""
    prompt = load_prompt(output_type)
    if deepen_previous:
        from services.analysis_service import DEEPEN_INSTRUCTION

        deepen = DEEPEN_INSTRUCTION.format(
            previous_analysis=deepen_previous, output_type=output_type
        )
        prompt = prompt + deepen

    system_msg = LLMMessage(role="system", content=prompt)
    user_msg = LLMMessage(
        role="user",
        content=f"Analyze the following novel excerpts:\n\n{chunks_text}",
    )
    return prompt, [system_msg, user_msg]


def _is_retryable(error: Exception) -> bool:
    if isinstance(error, LLMClientError):
        if error.status_code and error.status_code in RETRYABLE_HTTP_CODES:
            return True
        msg = error.message.lower()
        return any(kw in msg for kw in RETRYABLE_KEYWORDS)
    return False


def run_one_analysis_type(
    *,
    topic_id: str,
    output_type: str,
    chunks_text: str,
    base_url: str,
    api_key: str,
    model_name: str,
    max_tokens: int,
    temperature: float,
    thinking_mode: str = "disabled",
    reasoning_effort: str | None = None,
    deepen_previous: str | None = None,
) -> AnalysisTypeResult:
    """Run a single output_type analysis. No DB access, returns result only."""
    start = time.monotonic()

    client = OpenAICompatibleLLMClient(
        base_url=base_url,
        api_key=api_key,
        timeout=180.0,
        max_retries=0,  # we handle retries ourselves
    )

    _, messages = _build_messages(output_type, chunks_text, deepen_previous)

    # Extra body for thinking mode (DeepSeek-compatible)
    extra = None
    if thinking_mode == "disabled":
        extra = {"thinking": {"type": "disabled"}}
    elif thinking_mode == "enabled":
        extra = {"thinking": {"type": "enabled"}}
        if reasoning_effort:
            extra["thinking"]["reasoning_effort"] = reasoning_effort  # type: ignore[index]

    # ── First attempt ──
    result = _attempt_call(client, messages, model_name, temperature, max_tokens, extra)
    if result.ok:
        result.duration_seconds = time.monotonic() - start
        return result

    # ── Retry logic ──
    max_retries = 2
    for attempt in range(max_retries):
        retry_max_tokens = max_tokens
        # If JSON parse failed due to length, double max_tokens
        if result.error and "json" in result.error.lower():
            retry_max_tokens = min(max_tokens * 2, 8192)
            if retry_max_tokens == max_tokens:
                break  # already at cap

        if (
            not _is_retryable(ValueError(result.error or "unknown"))
            and "json" not in (result.error or "").lower()
        ):
            break

        time.sleep(1.5 * (attempt + 1))  # exponential-ish backoff
        retry_result = _attempt_call(
            client,
            messages,
            model_name,
            temperature,
            retry_max_tokens,
            extra,
        )
        retry_result.retry_count = attempt + 1
        if retry_result.ok:
            retry_result.duration_seconds = time.monotonic() - start
            return retry_result

    result.duration_seconds = time.monotonic() - start
    return result


def _attempt_call(
    client: OpenAICompatibleLLMClient,
    messages: list[LLMMessage],
    model_name: str,
    temperature: float,
    max_tokens: int,
    extra_body: dict | None,
) -> AnalysisTypeResult:
    try:
        response = client.chat(
            messages=messages,
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            extra_body=extra_body,
        )
    except LLMClientError as e:
        return AnalysisTypeResult(
            output_type="",
            ok=False,
            error=e.message,
        )

    usage = response.usage or {}
    finish_reason = usage.get("finish_reason") or (
        response.usage.get("choices", [{}])[0].get("finish_reason")
        if isinstance(response.usage, dict)
        else None
    )

    try:
        parsed = json.loads(response.content)
    except json.JSONDecodeError as e:
        return AnalysisTypeResult(
            output_type="",
            ok=False,
            raw_text=response.content[:500],
            error=f"JSON parse failed: {e}",
            usage=usage,
            finish_reason=finish_reason,
            model_name=response.model,
        )

    return AnalysisTypeResult(
        output_type="",
        ok=True,
        parsed_json=parsed,
        raw_text=response.content,
        usage=usage,
        finish_reason=finish_reason,
        model_name=response.model,
    )
