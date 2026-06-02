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

    # ── First attempt ──
    last_result = _attempt_call(
        client, messages, model_name, temperature, max_tokens, extra_body, chunk_id, api_key,
        thinking_mode=thinking_mode,
    )
    if last_result.ok:
        last_result.duration_seconds = time.monotonic() - start
        return last_result

    # ── Retry logic ──
    err_lower = (last_result.error or "").lower()
    is_json_error = "json" in err_lower and "parse" in err_lower
    is_truncated = is_json_error and (
        "truncated" in err_lower
        or last_result.finish_reason == "length"
        or last_result.completion_tokens >= max_tokens - TRUNCATION_TOKEN_MARGIN
    )
    if not _is_retryable_result(
        error_msg=last_result.error or "",
        status_code=last_result.status_code,
        is_json_error=is_json_error,
    ):
        last_result.duration_seconds = time.monotonic() - start
        return last_result

    for attempt in range(2):
        retry_tokens = max_tokens
        if is_json_error:
            retry_tokens = min(max_tokens * 2, RETRY_MAX_TOKENS)

        # Longer backoff for 429; shorter for JSON truncation; moderate for transport
        if last_result.status_code == 429:
            time.sleep(15.0 + 15.0 * attempt)
        elif is_truncated or is_json_error:
            time.sleep(1.5 * (attempt + 1))
        else:
            time.sleep(3.0 * (attempt + 1))

        retry_result = _attempt_call(
            client, messages, model_name, temperature, retry_tokens, extra_body, chunk_id, api_key,
            thinking_mode=thinking_mode,
        )
        retry_result.retry_count = attempt + 1
        if retry_result.ok:
            retry_result.duration_seconds = time.monotonic() - start
            return retry_result
        last_result = retry_result

        # If still truncated, escalate to RETRY_MAX_TOKENS on next attempt
        retry_err_lower = (retry_result.error or "").lower()
        retry_is_json = "json" in retry_err_lower and "parse" in retry_err_lower
        if retry_is_json and (
            "truncated" in retry_err_lower
            or retry_result.finish_reason == "length"
            or retry_result.completion_tokens >= retry_tokens - TRUNCATION_TOKEN_MARGIN
        ):
            is_truncated = True

    last_result.duration_seconds = time.monotonic() - start
    return last_result


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
        result = LocalExtractionResult(
            chunk_id=chunk_id,
            ok=False,
            error=masked,
            status_code=e.status_code,
            warnings=warnings,
        )
        return result

    usage = response.usage or {}
    model_used = response.model or model_name
    finish_reason = response.finish_reason
    completion_tokens = usage.get("completion_tokens", 0)

    parsed = parse_json_object(response.content)
    if not parsed.ok:
        error_msg = f"JSON parse failed: {parsed.error}"
        # Detect likely truncation
        is_likely_truncated = (
            finish_reason == "length"
            or completion_tokens >= max_tokens - TRUNCATION_TOKEN_MARGIN
        )
        if is_likely_truncated:
            error_msg += (
                f"; likely truncated at max_tokens={max_tokens}"
                f" (finish_reason={finish_reason}, completion_tokens={completion_tokens})"
            )
        return LocalExtractionResult(
            chunk_id=chunk_id,
            ok=False,
            content_json=None,
            error=error_msg,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=completion_tokens,
            total_tokens=usage.get("total_tokens", 0),
            model_used=model_used,
            finish_reason=finish_reason,
            warnings=warnings + parsed.warnings,
        )

    # Validate parsed JSON against contract
    validation = validate_local_extraction_response(parsed.parsed, chunk_id)
    all_warnings = warnings + parsed.warnings + validation.warnings

    if validation.errors:
        error_summary = "; ".join(validation.errors[:3])
        if len(validation.errors) > 3:
            error_summary += f" (+{len(validation.errors) - 3} more)"
        return LocalExtractionResult(
            chunk_id=chunk_id,
            ok=False,
            content_json=json.dumps(parsed.parsed, ensure_ascii=False)[:500],
            error=f"Validation failed: {error_summary}",
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            model_used=model_used,
            finish_reason=finish_reason,
            warnings=all_warnings,
        )

    return LocalExtractionResult(
        chunk_id=chunk_id,
        ok=True,
        content_json=json.dumps(parsed.parsed, ensure_ascii=False),
        parsed_json=parsed.parsed,
        duration_seconds=0.0,  # filled by caller
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
        total_tokens=usage.get("total_tokens", 0),
        model_used=model_used,
        finish_reason=finish_reason,
        warnings=all_warnings,
    )
