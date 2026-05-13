import json
import time
from dataclasses import dataclass, field

import httpx


@dataclass
class LLMMessage:
    role: str  # "system" | "user" | "assistant"
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict = field(default_factory=dict)


class LLMClientError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class OpenAICompatibleLLMClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 120.0,
        max_retries: int = 2,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries

    def chat(
        self,
        messages: list[LLMMessage],
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 8192,
        response_format: dict | None = None,
    ) -> LLMResponse:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = httpx.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
            except httpx.TimeoutException:
                last_error = LLMClientError(f"Request timed out after {self.timeout}s")
                if attempt < self.max_retries:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                raise last_error
            except httpx.NetworkError as e:
                last_error = LLMClientError(f"Network error: {e}")
                if attempt < self.max_retries:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                raise last_error

            if response.status_code != 200:
                detail = self._extract_error_detail(response)
                raise LLMClientError(
                    f"HTTP {response.status_code}: {detail}",
                    status_code=response.status_code,
                )

            try:
                data = response.json()
            except (json.JSONDecodeError, ValueError) as e:
                last_error = LLMClientError(f"Invalid JSON response: {e}")
                if attempt < self.max_retries:
                    time.sleep(1.0 * (attempt + 1))
                    continue
                raise last_error

            choices = data.get("choices", [])
            if not choices:
                raise LLMClientError("LLM returned empty choices")

            message = choices[0].get("message", {})
            content = message.get("content")
            if content is None:
                raise LLMClientError("LLM response missing content")

            return LLMResponse(
                content=content,
                model=data.get("model", model),
                usage=data.get("usage", {}),
            )

        assert last_error is not None
        raise last_error

    def _extract_error_detail(self, response: httpx.Response) -> str:
        try:
            body = response.json()
            error = body.get("error", {})
            if isinstance(error, dict):
                return error.get("message", response.text)
            return str(error)
        except (json.JSONDecodeError, ValueError):
            return response.text[:500]
