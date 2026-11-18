"""OpenAIAPIProvider (T072 – FR-011, R-05). Provider dự phòng – chỉ dùng khi được cấu hình rõ ràng.

Cùng interface `LLMProvider`; Chat Completions với `response_format=json_schema`; `max_retries=0`.
"""

from __future__ import annotations

import json
import time
from typing import Any

import httpx2
import openai

from nichepilot.ai.providers.base import (
    ConnectionCheckResult,
    DataOrigin,
    LLMRequest,
    LLMResponse,
    ProviderAuthError,
    ProviderBadRequestError,
    ProviderError,
    ProviderName,
    ProviderNetworkError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    TokenUsage,
    ToolCall,
)

OPENAI_BASE_URL = "https://api.openai.com/v1"
_NOT_SENT_CAUSES = (httpx2.ConnectError, httpx2.ConnectTimeout)


def _was_sent(exc: BaseException) -> bool:
    return not isinstance(exc.__cause__ or exc.__context__, _NOT_SENT_CAUSES)


def map_openai_error(exc: Exception) -> ProviderError:
    if isinstance(exc, openai.APITimeoutError):
        return ProviderTimeoutError(str(exc), sent=_was_sent(exc))
    if isinstance(exc, openai.APIConnectionError):
        return ProviderNetworkError(str(exc), sent=_was_sent(exc))
    if isinstance(exc, (openai.AuthenticationError, openai.PermissionDeniedError)):
        return ProviderAuthError(str(exc), sent=True)
    if isinstance(exc, openai.RateLimitError):
        raw = exc.response.headers.get("retry-after")
        return ProviderRateLimitedError(
            str(exc), sent=True, retry_after_s=float(raw) if raw and raw.isdigit() else None
        )
    if isinstance(exc, openai.APIStatusError):
        if exc.status_code >= 500:
            return ProviderUnavailableError(str(exc), sent=True)
        return ProviderBadRequestError(str(exc), sent=True)
    return ProviderUnavailableError(str(exc), sent=True)


def _wire_name(name: str) -> str:
    return name.replace(".", "_")


class OpenAIAPIProvider:
    name: ProviderName = "openai"
    data_origin: DataOrigin = "REAL"
    paid = True

    def __init__(
        self, api_key: str, *, base_url: str = OPENAI_BASE_URL, http_client: httpx2.AsyncClient | None = None
    ) -> None:
        if not api_key:
            raise ValueError("Thiếu OPENAI_API_KEY")
        self.client = openai.AsyncOpenAI(api_key=api_key, base_url=base_url, max_retries=0, http_client=http_client)

    def _params(self, req: LLMRequest) -> dict[str, Any]:
        if req.mock_scenario is not None:
            raise ValueError("mock_scenario chỉ hợp lệ với MockAIProvider")
        messages: list[dict[str, Any]] = [{"role": "system", "content": req.system}]
        for m in req.messages:
            if isinstance(m.content, str):
                messages.append({"role": m.role, "content": m.content})
            else:
                text = "\n".join(
                    b.get("text") or json.dumps(b.get("content", b), ensure_ascii=False) for b in m.content
                )
                messages.append({"role": m.role, "content": text})
        params: dict[str, Any] = {
            "model": req.model,
            "messages": messages,
            "max_completion_tokens": req.max_output_tokens,
        }
        if req.output_schema is not None:
            params["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "output", "schema": req.output_schema, "strict": False},
            }
        if req.tools:
            params["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": _wire_name(t.name),
                        "description": t.description,
                        "parameters": t.input_schema,
                    },
                }
                for t in req.tools
            ]
        return params

    async def count_input_tokens(self, req: LLMRequest) -> int:
        # Không có endpoint đếm token miễn phí tương đương → ước tính bảo thủ (ký tự ÷ 3).
        size = len(req.system) + sum(len(json.dumps(m.content, ensure_ascii=False)) for m in req.messages)
        return size // 3 + 1

    async def generate(self, req: LLMRequest) -> LLMResponse:
        params = self._params(req)
        names = {_wire_name(t.name): t.name for t in req.tools}
        started = time.monotonic()
        try:
            completion = await self.client.chat.completions.create(**params, timeout=req.timeout_s)
        except Exception as exc:
            raise map_openai_error(exc) from exc
        choice = completion.choices[0]
        u = completion.usage
        cached = getattr(getattr(u, "prompt_tokens_details", None), "cached_tokens", 0) or 0 if u else 0
        usage = TokenUsage(
            input_tokens=u.prompt_tokens if u else 0,
            output_tokens=u.completion_tokens if u else 0,
            cache_read_tokens=cached,
        )
        text = choice.message.content
        common: dict[str, Any] = {
            "stop_reason": choice.finish_reason,
            "content_text": text,
            "usage": usage,
            "provider_request_id": completion.id,
            "raw_model": completion.model,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "data_origin": "REAL",
        }
        if choice.message.refusal:
            return LLMResponse(outcome="REFUSED", refusal_explanation=choice.message.refusal, **common)
        if choice.finish_reason == "length":
            return LLMResponse(outcome="TRUNCATED", **common)
        tool_calls = [
            ToolCall(
                id=c.id,
                name=names.get(c.function.name, c.function.name),
                input=json.loads(c.function.arguments or "{}"),
            )
            for c in (choice.message.tool_calls or [])
            if getattr(c, "function", None) is not None
        ]
        parsed: dict[str, Any] | None = None
        if req.output_schema is not None and text:
            try:
                loaded = json.loads(text)
                parsed = loaded if isinstance(loaded, dict) else None
            except json.JSONDecodeError:
                parsed = None
        return LLMResponse(outcome="SUCCESS", tool_calls=tool_calls, parsed_output=parsed, **common)

    async def check_connection(self) -> ConnectionCheckResult:
        try:
            await self.client.models.list()
        except Exception as exc:
            err = map_openai_error(exc)
            result = (
                "INVALID_KEY"
                if err.outcome == "AUTH_ERROR"
                else ("NETWORK_ERROR" if err.outcome in ("NETWORK_ERROR", "TIMEOUT") else "PROVIDER_ERROR")
            )
            return ConnectionCheckResult(provider="openai", result=result)
        return ConnectionCheckResult(provider="openai", result="OK")
