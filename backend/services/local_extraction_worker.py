"""Worker for single-chunk local_extraction LLM call.

Pure function pattern: no DB access, returns result dataclass.
Caller is responsible for writing LocalExtraction and ExtractedAtom rows.
"""

import json
import time
from dataclasses import dataclass, field
from typing import Any

from models.model_provider import mask_api_key
from services.analysis_response_parser import (
    parse_json_object,
    validate_local_extraction_response,
)
from services.llm_client import LLMClientError, LLMMessage, OpenAICompatibleLLMClient
from services.prompt_loader import load_local_extraction_prompt

RETRYABLE_HTTP_CODES = {429, 500, 502, 503, 504}
RETRYABLE_KEYWORDS = [
    "rate limit",
    "rate_limit",
    "insufficient_system_resource",
    "timeout",
    "timed out",
    "transport error",
    "network error",
    "peer closed",
    "incomplete chunked read",
]
DEFAULT_MAX_TOKENS = 4096
RETRY_MAX_TOKENS = 16384
# Completion tokens within this margin of max_tokens are treated as likely truncated
TRUNCATION_TOKEN_MARGIN = 8


@dataclass
class AttemptUsage:
    """Token usage for a single LLM attempt."""

    attempt_index: int
    ok: bool
    max_tokens: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    reasoning_tokens: int = 0
    prompt_cache_hit_tokens: int = 0
    prompt_cache_miss_tokens: int = 0
    finish_reason: str | None = None
    status_code: int | None = None
    error: str | None = None
    usage_available: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt_index": self.attempt_index,
            "ok": self.ok,
            "max_tokens": self.max_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "prompt_cache_hit_tokens": self.prompt_cache_hit_tokens,
            "prompt_cache_miss_tokens": self.prompt_cache_miss_tokens,
            "finish_reason": self.finish_reason,
            "status_code": self.status_code,
            "error": self.error,
            "usage_available": self.usage_available,
        }


@dataclass
class LocalExtractionResult:
    chunk_id: str
    ok: bool
    content_json: str | None = None
    parsed_json: dict[str, Any] | None = None
    error: str | None = None
    duration_seconds: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model_used: str | None = None
    retry_count: int = 0
    status_code: int | None = None
    finish_reason: str | None = None
    warnings: list[str] = field(default_factory=list)
    # Cumulative across all attempts
    attempts: list[AttemptUsage] = field(default_factory=list)
    cumulative_prompt_tokens: int = 0
    cumulative_completion_tokens: int = 0
    cumulative_total_tokens: int = 0
    cumulative_reasoning_tokens: int = 0
    cumulative_prompt_cache_hit_tokens: int = 0
    cumulative_prompt_cache_miss_tokens: int = 0
    usage_unavailable_attempts: int = 0


def _extract_usage_fields(usage: dict) -> dict:
    """Extract token usage fields from an API usage dict, including thinking/cache tokens.

    DeepSeek returns prompt_cache_hit_tokens / prompt_cache_miss_tokens directly.
    OpenAI-compatible APIs use prompt_tokens_details.cached_tokens as a fallback.
    """
    details = usage.get("completion_tokens_details", {})
    if not isinstance(details, dict):
        details = {}
    prompt_tokens = usage.get("prompt_tokens", 0)

    # Cache: prefer DeepSeek-style flat fields, fallback to OpenAI-style nested
    cache_hit = usage.get("prompt_cache_hit_tokens")
    cache_miss = usage.get("prompt_cache_miss_tokens")
    if cache_hit is None or cache_miss is None:
        prompt_details = usage.get("prompt_tokens_details", {})
        if not isinstance(prompt_details, dict):
            prompt_details = {}
        cached = prompt_details.get("cached_tokens", 0)
        cache_hit = cached if cache_hit is None else cache_hit
        cache_miss = max(0, prompt_tokens - cached) if cache_miss is None else cache_miss

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        "reasoning_tokens": details.get("reasoning_tokens", 0),
        "prompt_cache_hit_tokens": int(cache_hit or 0),
        "prompt_cache_miss_tokens": int(cache_miss or 0),
    }


def _build_attempt(
    attempt_index: int,
    ok: bool,
    max_tokens: int,
    usage: dict | None = None,
    finish_reason: str | None = None,
    status_code: int | None = None,
    error: str | None = None,
) -> AttemptUsage:
    fields = _extract_usage_fields(usage or {})
    return AttemptUsage(
        attempt_index=attempt_index,
        ok=ok,
        max_tokens=max_tokens,
        prompt_tokens=fields["prompt_tokens"],
        completion_tokens=fields["completion_tokens"],
        total_tokens=fields["total_tokens"],
        reasoning_tokens=fields["reasoning_tokens"],
        prompt_cache_hit_tokens=fields["prompt_cache_hit_tokens"],
        prompt_cache_miss_tokens=fields["prompt_cache_miss_tokens"],
        finish_reason=finish_reason,
        status_code=status_code,
        error=error,
        usage_available=usage is not None and len(usage) > 0,
    )


def _mask_error(error_msg: str, api_key: str) -> str:
    """Mask any occurrences of the api_key in error messages."""
    if api_key and len(api_key) > 8:
        return error_msg.replace(api_key, mask_api_key(api_key))
    return error_msg


def build_local_extraction_messages(
    chunk_id: str,
    chunk_text: str,
    chapter_index: int | None = None,
    chunk_index: int | None = None,
    chapter_title: str | None = None,
) -> tuple[str, list[LLMMessage]]:
    """Build system + user messages for local_extraction LLM call.

    Returns (prompt_text, messages).
    """
    prompt = load_local_extraction_prompt()

    meta_lines = ["## Chunk Metadata"]
    meta_lines.append(f"chunk_id: {chunk_id}")
    if chapter_index is not None:
        meta_lines.append(f"chapter_index: {chapter_index}")
    if chunk_index is not None:
        meta_lines.append(f"chunk_index: {chunk_index}")
    if chapter_title:
        meta_lines.append(f"chapter_title: {chapter_title}")

    user_content = (
        f"{chr(10).join(meta_lines)}\n\n"
        f"## Chunk Text\n\n{chunk_text}\n\n"
        f"Extract all local analysis atoms from the chunk text above. "
        f"Return valid JSON only."
    )

    system_msg = LLMMessage(role="system", content=prompt)
    user_msg = LLMMessage(role="user", content=user_content)

    return prompt, [system_msg, user_msg]


def _is_retryable_result(
    error_obj: Exception | None = None,
    status_code: int | None = None,
    error_msg: str = "",
    is_json_error: bool = False,
) -> bool:
    """Determine if a failed extraction should be retried."""
    if is_json_error:
        return True
    if status_code and status_code in RETRYABLE_HTTP_CODES:
        return True
    if isinstance(error_obj, LLMClientError):
        sc = error_obj.status_code
        if sc and sc in RETRYABLE_HTTP_CODES:
            return True
        msg = error_obj.message.lower()
        return any(kw in msg for kw in RETRYABLE_KEYWORDS)
    if error_msg:
        msg_lower = error_msg.lower()
        return any(kw in msg_lower for kw in RETRYABLE_KEYWORDS)
    return False


def run_local_extraction_for_chunk(
    *,
    chunk_id: str,
    chunk_text: str,
    base_url: str,
    api_key: str,
    model_name: str,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = 0.1,
    thinking_mode: str = "disabled",
    chapter_index: int | None = None,
    chunk_index: int | None = None,
    chapter_title: str | None = None,
) -> LocalExtractionResult:
    """Run local_extraction LLM call for a single chunk.

    No DB access. Returns a result dataclass.
    Caller writes LocalExtraction + ExtractedAtom rows.
    """
    start = time.monotonic()
    _, messages = build_local_extraction_messages(
        chunk_id, chunk_text, chapter_index, chunk_index, chapter_title
    )

    client = OpenAICompatibleLLMClient(
        base_url=base_url,
        api_key=api_key,
        timeout=180.0,
        max_retries=0,
    )

    extra_body = None
    if thinking_mode == "disabled":
        extra_body = {"thinking": {"type": "disabled"}}
    elif thinking_mode == "enabled":
        extra_body = {"thinking": {"type": "enabled"}}

    attempts: list[AttemptUsage] = []
    usage_unavailable = 0

    # ── First attempt ──
    last_result = _attempt_call(
        client,
        messages,
        model_name,
        temperature,
        max_tokens,
        extra_body,
        chunk_id,
        api_key,
        thinking_mode=thinking_mode,
        attempt_index=0,
    )
    if last_result.attempts:
        attempts.append(last_result.attempts[0])
        if not last_result.attempts[0].usage_available:
            usage_unavailable += 1

    if last_result.ok:
        last_result.duration_seconds = time.monotonic() - start
        _finalize_cumulative(last_result, attempts, usage_unavailable)
        return last_result

    # ── Retry logic with per-attempt re-evaluation ──
    original_max_tokens = max_tokens

    for attempt in range(2):
        # Re-evaluate error classification from current last_result
        err_lower = (last_result.error or "").lower()
        is_json_error = "json" in err_lower and "parse" in err_lower
        is_truncated = is_json_error and (
            "truncated" in err_lower
            or last_result.finish_reason == "length"
            or last_result.completion_tokens >= max_tokens - TRUNCATION_TOKEN_MARGIN
        )
        is_retryable = _is_retryable_result(
            error_msg=last_result.error or "",
            status_code=last_result.status_code,
            is_json_error=is_json_error,
        )
        if not is_retryable:
            last_result.duration_seconds = time.monotonic() - start
            _finalize_cumulative(last_result, attempts, usage_unavailable)
            return last_result

        # Adaptive token escalation: original → min(x2, RETRY_MAX_TOKENS) → RETRY_MAX_TOKENS
        if is_json_error:
            if attempt == 0:
                max_tokens = min(original_max_tokens * 2, RETRY_MAX_TOKENS)
            else:
                max_tokens = RETRY_MAX_TOKENS

        # Longer backoff for 429; shorter for JSON truncation; moderate for transport
        if last_result.status_code == 429:
            time.sleep(15.0 + 15.0 * attempt)
        elif is_truncated or is_json_error:
            time.sleep(1.5 * (attempt + 1))
        else:
            time.sleep(3.0 * (attempt + 1))

        retry_idx = attempt + 1
        retry_result = _attempt_call(
            client,
            messages,
            model_name,
            temperature,
            max_tokens,
            extra_body,
            chunk_id,
            api_key,
            thinking_mode=thinking_mode,
            attempt_index=retry_idx,
        )
        retry_result.retry_count = retry_idx
        if retry_result.attempts:
            attempts.append(retry_result.attempts[0])
            if not retry_result.attempts[0].usage_available:
                usage_unavailable += 1

        if retry_result.ok:
            retry_result.duration_seconds = time.monotonic() - start
            _finalize_cumulative(retry_result, attempts, usage_unavailable)
            return retry_result
        last_result = retry_result

    last_result.duration_seconds = time.monotonic() - start
    _finalize_cumulative(last_result, attempts, usage_unavailable)
    return last_result


def _finalize_cumulative(
    result: LocalExtractionResult,
    attempts: list[AttemptUsage],
    usage_unavailable: int,
) -> None:
    """Set cumulative token fields on the result from all recorded attempts."""
    result.attempts = attempts
    result.usage_unavailable_attempts = usage_unavailable
    result.cumulative_prompt_tokens = sum(a.prompt_tokens for a in attempts)
    result.cumulative_completion_tokens = sum(a.completion_tokens for a in attempts)
    result.cumulative_total_tokens = sum(a.total_tokens for a in attempts)
    result.cumulative_reasoning_tokens = sum(a.reasoning_tokens for a in attempts)
    result.cumulative_prompt_cache_hit_tokens = sum(a.prompt_cache_hit_tokens for a in attempts)
    result.cumulative_prompt_cache_miss_tokens = sum(a.prompt_cache_miss_tokens for a in attempts)
    # For backward compatibility, set top-level fields to cumulative values
    result.prompt_tokens = result.cumulative_prompt_tokens
    result.completion_tokens = result.cumulative_completion_tokens
    result.total_tokens = result.cumulative_total_tokens


def _attempt_call(
    client: OpenAICompatibleLLMClient,
    messages: list[LLMMessage],
    model_name: str,
    temperature: float,
    max_tokens: int,
    extra_body: dict | None,
    chunk_id: str,
    api_key: str,
    thinking_mode: str = "disabled",
    attempt_index: int = 0,
) -> LocalExtractionResult:
    warnings: list[str] = []
    if thinking_mode == "enabled":
        warnings.append(
            "thinking mode enabled for local extraction may increase latency and output size risk"
        )

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
        masked = _mask_error(e.message, api_key)
        attempt = _build_attempt(
            attempt_index=attempt_index,
            ok=False,
            max_tokens=max_tokens,
            usage=None,
            finish_reason=None,
            status_code=e.status_code,
            error=masked,
        )
        return LocalExtractionResult(
            chunk_id=chunk_id,
            ok=False,
            error=masked,
            status_code=e.status_code,
            warnings=warnings,
            attempts=[attempt],
            usage_unavailable_attempts=1,
        )

    usage = response.usage or {}
    model_used = response.model or model_name
    finish_reason = response.finish_reason
    completion_tokens = usage.get("completion_tokens", 0)

    parsed = parse_json_object(response.content)
    if not parsed.ok:
        error_msg = f"JSON parse failed: {parsed.error}"
        # Detect likely truncation
        is_likely_truncated = (
            finish_reason == "length" or completion_tokens >= max_tokens - TRUNCATION_TOKEN_MARGIN
        )
        if is_likely_truncated:
            error_msg += (
                f"; likely truncated at max_tokens={max_tokens}"
                f" (finish_reason={finish_reason}, completion_tokens={completion_tokens})"
            )
        attempt = _build_attempt(
            attempt_index=attempt_index,
            ok=False,
            max_tokens=max_tokens,
            usage=usage,
            finish_reason=finish_reason,
            status_code=None,
            error=error_msg,
        )
        return LocalExtractionResult(
            chunk_id=chunk_id,
            ok=False,
            content_json=None,
            error=error_msg,
            prompt_tokens=attempt.prompt_tokens,
            completion_tokens=attempt.completion_tokens,
            total_tokens=attempt.total_tokens,
            model_used=model_used,
            finish_reason=finish_reason,
            warnings=warnings + parsed.warnings,
            attempts=[attempt],
        )

    # Validate parsed JSON against contract
    validation = validate_local_extraction_response(parsed.parsed, chunk_id)
    all_warnings = warnings + parsed.warnings + validation.warnings

    if validation.errors:
        error_summary = "; ".join(validation.errors[:3])
        if len(validation.errors) > 3:
            error_summary += f" (+{len(validation.errors) - 3} more)"
        attempt = _build_attempt(
            attempt_index=attempt_index,
            ok=False,
            max_tokens=max_tokens,
            usage=usage,
            finish_reason=finish_reason,
            status_code=None,
            error=f"Validation failed: {error_summary}",
        )
        return LocalExtractionResult(
            chunk_id=chunk_id,
            ok=False,
            content_json=json.dumps(parsed.parsed, ensure_ascii=False)[:500],
            error=f"Validation failed: {error_summary}",
            prompt_tokens=attempt.prompt_tokens,
            completion_tokens=attempt.completion_tokens,
            total_tokens=attempt.total_tokens,
            model_used=model_used,
            finish_reason=finish_reason,
            warnings=all_warnings,
            attempts=[attempt],
        )

    attempt = _build_attempt(
        attempt_index=attempt_index,
        ok=True,
        max_tokens=max_tokens,
        usage=usage,
        finish_reason=finish_reason,
        status_code=None,
        error=None,
    )
    return LocalExtractionResult(
        chunk_id=chunk_id,
        ok=True,
        content_json=json.dumps(parsed.parsed, ensure_ascii=False),
        parsed_json=parsed.parsed,
        duration_seconds=0.0,  # filled by caller
        prompt_tokens=attempt.prompt_tokens,
        completion_tokens=attempt.completion_tokens,
        total_tokens=attempt.total_tokens,
        model_used=model_used,
        finish_reason=finish_reason,
        warnings=all_warnings,
        attempts=[attempt],
    )
