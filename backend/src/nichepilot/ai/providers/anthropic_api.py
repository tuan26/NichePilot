"""AnthropicAPIProvider (T071 – FR-010, FR-014, FR-017, FR-019b; research.md R-03).

- Chỉ xác thực bằng API key chính thức truyền tường minh; truyền cả `base_url` để biến môi trường/hồ sơ OAuth
  không thể thay đổi đích hoặc thông tin xác thực.
- `max_retries=0`: retry do AIGateway kiểm soát (mỗi lần thử đều kiểm tra ngân sách và ghi usage).
- Structured output qua `output_config.format`; tool `strict` + `tool_choice=auto`; không gửi temperature/prefill.
- Lỗi được chuẩn hóa kèm cờ `sent` (yêu cầu có thể đã rời hệ thống hay chưa) để phân loại chi phí (FR-047).
"""

from __future__ import annotations

import json
import time
from typing import Any

import anthropic
import httpx2

from nichepilot.ai.providers.base import (
    ConnectionCheckResult,
    DataOrigin,
    LLMMessage,
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

ANTHROPIC_BASE_URL = "https://api.anthropic.com"
_NOT_SENT_CAUSES = (httpx2.ConnectError, httpx2.ConnectTimeout)


def wire_tool_name(name: str) -> str:
    """Tên tool của Anthropic chỉ cho phép [a-zA-Z0-9_-]: `system.runtime_info` → `system_runtime_info`."""
    return name.replace(".", "_")


def _was_sent(exc: BaseException) -> bool:
    cause = exc.__cause__ or exc.__context__
    return not isinstance(cause, _NOT_SENT_CAUSES)


def _retry_after(exc: anthropic.APIStatusError) -> float | None:
    raw = exc.response.headers.get("retry-after")
    try:
        return float(raw) if raw else None
    except ValueError:
        return None


def map_anthropic_error(exc: Exception) -> ProviderError:
    if isinstance(exc, anthropic.APITimeoutError):
        return ProviderTimeoutError(str(exc), sent=_was_sent(exc))
    if isinstance(exc, anthropic.APIConnectionError):
        return ProviderNetworkError(str(exc), sent=_was_sent(exc))
    if isinstance(exc, (anthropic.AuthenticationError, anthropic.PermissionDeniedError)):
        return ProviderAuthError(str(exc), sent=True)
    if isinstance(exc, anthropic.RateLimitError):
        return ProviderRateLimitedError(str(exc), sent=True, retry_after_s=_retry_after(exc))
    if isinstance(exc, anthropic.APIStatusError):
        if exc.status_code >= 500:
            return ProviderUnavailableError(str(exc), sent=True)
        return ProviderBadRequestError(str(exc), sent=True)
    return ProviderUnavailableError(str(exc), sent=True)


def _to_wire_messages(messages: list[LLMMessage]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        if isinstance(m.content, str):
            out.append({"role": m.role, "content": m.content})
            continue
        blocks: list[dict[str, Any]] = []
        for b in m.content:
            if b.get("type") == "tool_use":
                blocks.append({**b, "name": wire_tool_name(str(b["name"]))})
            else:
                blocks.append(b)
        out.append({"role": m.role, "content": blocks})
    return out


class AnthropicAPIProvider:
    name: ProviderName = "anthropic"
    data_origin: DataOrigin = "REAL"
    paid = True

    def __init__(
        self, api_key: str, *, base_url: str = ANTHROPIC_BASE_URL, http_client: httpx2.AsyncClient | None = None
    ) -> None:
        if not api_key:
            raise ValueError("Thiếu ANTHROPIC_API_KEY")
        self.client = anthropic.AsyncAnthropic(
            api_key=api_key, base_url=base_url, max_retries=0, http_client=http_client
        )

    def _params(self, req: LLMRequest) -> dict[str, Any]:
        if req.mock_scenario is not None:
            raise ValueError("mock_scenario chỉ hợp lệ với MockAIProvider")
        params: dict[str, Any] = {
            "model": req.model,
            "max_tokens": req.max_output_tokens,
            "system": [{"type": "text", "text": req.system, "cache_control": {"type": "ephemeral"}}],
            "messages": _to_wire_messages(req.messages),
        }
        output_config: dict[str, Any] = {}
        if req.effort:
            output_config["effort"] = req.effort
        if req.output_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": req.output_schema}
        if output_config:
            params["output_config"] = output_config
        if req.tools:
            params["tools"] = [
                {
                    "name": wire_tool_name(t.name),
                    "description": t.description,
                    "input_schema": t.input_schema,
                    "strict": True,
                }
                for t in req.tools
            ]
            params["tool_choice"] = {"type": "auto"}
        return params

    async def count_input_tokens(self, req: LLMRequest) -> int:
        params = self._params(req)
        params.pop("max_tokens")
        try:
            result = await self.client.messages.count_tokens(**params)
        except Exception as exc:
            raise map_anthropic_error(exc) from exc
        return int(result.input_tokens)

    async def generate(self, req: LLMRequest) -> LLMResponse:
        params = self._params(req)
        names = {wire_tool_name(t.name): t.name for t in req.tools}
        started = time.monotonic()
        try:
            msg = await self.client.messages.create(**params, timeout=req.timeout_s)
        except Exception as exc:
            raise map_anthropic_error(exc) from exc
        latency = int((time.monotonic() - started) * 1000)
        usage = TokenUsage(
            input_tokens=msg.usage.input_tokens or 0,
            output_tokens=msg.usage.output_tokens or 0,
            cache_read_tokens=msg.usage.cache_read_input_tokens or 0,
            cache_write_tokens=msg.usage.cache_creation_input_tokens or 0,
        )
        text = "".join(getattr(b, "text", "") for b in msg.content if b.type == "text") or None
        tool_calls = [
            ToolCall(id=b.id, name=names.get(b.name, b.name), input=dict(b.input))
            for b in msg.content
            if b.type == "tool_use"
        ]
        common: dict[str, Any] = {
            "stop_reason": msg.stop_reason,
            "content_text": text,
            "usage": usage,
            "provider_request_id": msg.id,
            "raw_model": msg.model,
            "latency_ms": latency,
            "data_origin": "REAL",
        }
        if msg.stop_reason == "refusal":
            details = msg.stop_details
            return LLMResponse(
                outcome="REFUSED",
                refusal_category=getattr(details, "category", None),
                refusal_explanation=getattr(details, "explanation", None),
                **common,
            )
        if msg.stop_reason in ("max_tokens", "model_context_window_exceeded"):
            return LLMResponse(outcome="TRUNCATED", **common)
        parsed: dict[str, Any] | None = None
        if req.output_schema is not None and text is not None:
            try:
                loaded = json.loads(text)
                parsed = loaded if isinstance(loaded, dict) else None
            except json.JSONDecodeError:
                parsed = None
        return LLMResponse(outcome="SUCCESS", tool_calls=tool_calls, parsed_output=parsed, **common)

    async def check_connection(self) -> ConnectionCheckResult:
        """Gọi Models API – không tính phí token."""
        try:
            await self.client.models.list(limit=1)
        except Exception as exc:
            err = map_anthropic_error(exc)
            result = {"AUTH_ERROR": "INVALID_KEY", "NETWORK_ERROR": "NETWORK_ERROR", "TIMEOUT": "NETWORK_ERROR"}.get(
                err.outcome, "PROVIDER_ERROR"
            )
            return ConnectionCheckResult(provider="anthropic", result=result)
        return ConnectionCheckResult(provider="anthropic", result="OK")

    async def retrieve_model(self, model_id: str) -> dict[str, Any] | None:
        """Thông tin model từ Models API (không tính phí) – dùng để xác minh model ID/khả năng (FR-019c)."""
        try:
            info = await self.client.models.retrieve(model_id)
        except anthropic.NotFoundError:
            return None
        except Exception as exc:
            raise map_anthropic_error(exc) from exc
        return info.model_dump()
