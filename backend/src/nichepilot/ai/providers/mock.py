"""MockAIProvider (T070 – FR-018, R-14). CHỈ dùng ở development/test.

- Không có I/O mạng; kết quả xác định theo `seed`.
- Mọi chuỗi sinh ra có tiền tố `[MOCK]`; `data_origin = MOCK`. Không bao giờ sinh số liệu thị trường giả dạng thật.
- Kịch bản: success, timeout (trước khi gửi), timeout_after_send, rate_limit, schema_invalid, provider_error,
  auth_error, network_error, refusal, truncated, budget_heavy, fail_n_then_success:<kịch bản>:<n>.
"""

from __future__ import annotations

import json
from typing import Any

from nichepilot.ai.providers.base import (
    ConnectionCheckResult,
    DataOrigin,
    LLMRequest,
    LLMResponse,
    ProviderAuthError,
    ProviderName,
    ProviderNetworkError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    TokenUsage,
    ToolCall,
)

SCENARIOS = frozenset(
    {
        "success",
        "timeout",
        "timeout_after_send",
        "rate_limit",
        "schema_invalid",
        "provider_error",
        "auth_error",
        "network_error",
        "refusal",
        "truncated",
        "budget_heavy",
    }
)
MOCK_MODEL = "mock-model"
DEFAULT_USAGE = TokenUsage(input_tokens=2000, output_tokens=500)
HEAVY_INPUT_TOKENS = 2_000_000


def validate_scenario(scenario: str) -> None:
    if scenario.startswith("fail_n_then_success:"):
        parts = scenario.split(":")
        if len(parts) != 3 or parts[1] not in SCENARIOS or not parts[2].isdigit():
            raise ValueError(f"Kịch bản mock không hợp lệ: {scenario}")
        return
    if scenario not in SCENARIOS:
        raise ValueError(f"Kịch bản mock không hợp lệ: {scenario}")


def sample_from_schema(schema: dict[str, Any], name: str = "value") -> Any:
    """Giá trị tối thiểu hợp lệ theo JSON Schema; chuỗi luôn có tiền tố [MOCK]."""
    if "const" in schema:
        return schema["const"]
    if "enum" in schema:
        return schema["enum"][0]
    if "anyOf" in schema:
        return sample_from_schema(schema["anyOf"][0], name)
    kind = schema.get("type")
    if isinstance(kind, list):
        kind = next((k for k in kind if k != "null"), "null")
    if kind == "object":
        props: dict[str, Any] = schema.get("properties", {})
        return {k: sample_from_schema(v, k) for k, v in props.items()}
    if kind == "array":
        return []
    if kind == "integer":
        return int(schema.get("minimum", 0))
    if kind == "number":
        return float(schema.get("minimum", 0))
    if kind == "boolean":
        return False
    if kind == "null":
        return None
    return f"[MOCK] {name}"


def _has_tool_result(req: LLMRequest) -> bool:
    for m in req.messages:
        if isinstance(m.content, list) and any(b.get("type") == "tool_result" for b in m.content):
            return True
    return False


class MockAIProvider:
    name: ProviderName = "mock"
    data_origin: DataOrigin = "MOCK"
    paid = False

    def __init__(self, default_scenario: str = "success") -> None:
        validate_scenario(default_scenario)
        self.default_scenario = default_scenario
        self._attempts: dict[str, int] = {}

    def _resolve(self, req: LLMRequest) -> str:
        scenario = req.mock_scenario or self.default_scenario
        validate_scenario(scenario)
        if scenario.startswith("fail_n_then_success:"):
            _, failing, n = scenario.split(":")
            key = f"{req.seed}:{scenario}"
            count = self._attempts.get(key, 0)
            self._attempts[key] = count + 1
            return failing if count < int(n) else "success"
        return scenario

    async def count_input_tokens(self, req: LLMRequest) -> int:
        scenario = req.mock_scenario or self.default_scenario
        return HEAVY_INPUT_TOKENS if scenario == "budget_heavy" else DEFAULT_USAGE.input_tokens

    async def generate(self, req: LLMRequest) -> LLMResponse:
        scenario = self._resolve(req)
        base: dict[str, Any] = {
            "raw_model": MOCK_MODEL,
            "data_origin": "MOCK",
            "provider_request_id": f"mock-{req.seed}",
        }
        match scenario:
            case "timeout":
                raise ProviderTimeoutError("[MOCK] timeout trước khi gửi", sent=False)
            case "timeout_after_send":
                raise ProviderTimeoutError("[MOCK] timeout sau khi gửi", sent=True)
            case "rate_limit":
                raise ProviderRateLimitedError("[MOCK] rate limited", sent=True, retry_after_s=0.01)
            case "provider_error":
                raise ProviderUnavailableError("[MOCK] provider unavailable", sent=True)
            case "auth_error":
                raise ProviderAuthError("[MOCK] invalid key", sent=True)
            case "network_error":
                raise ProviderNetworkError("[MOCK] không có internet", sent=False)
            case "refusal":
                return LLMResponse(
                    outcome="REFUSED",
                    stop_reason="refusal",
                    refusal_category="mock_policy",
                    refusal_explanation="[MOCK] refusal",
                    usage=TokenUsage(input_tokens=DEFAULT_USAGE.input_tokens, output_tokens=5),
                    **base,
                )
            case "truncated":
                return LLMResponse(
                    outcome="TRUNCATED",
                    stop_reason="max_tokens",
                    content_text="[MOCK] {",
                    usage=TokenUsage(input_tokens=DEFAULT_USAGE.input_tokens, output_tokens=req.max_output_tokens),
                    **base,
                )
        usage = (
            TokenUsage(input_tokens=HEAVY_INPUT_TOKENS, output_tokens=DEFAULT_USAGE.output_tokens)
            if scenario == "budget_heavy"
            else DEFAULT_USAGE
        )
        if req.tools and not _has_tool_result(req):
            tool = req.tools[0]
            return LLMResponse(
                outcome="SUCCESS",
                stop_reason="tool_use",
                content_text="[MOCK] calling tool",
                tool_calls=[
                    ToolCall(id=f"mock-tool-{req.seed}", name=tool.name, input=sample_from_schema(tool.input_schema))
                ],
                usage=usage,
                **base,
            )
        parsed: dict[str, Any] | None = None
        if req.output_schema is not None:
            parsed = {"unexpected": "[MOCK]"} if scenario == "schema_invalid" else sample_from_schema(req.output_schema)
        return LLMResponse(
            outcome="SUCCESS",
            stop_reason="end_turn",
            content_text="[MOCK] " + json.dumps(parsed, ensure_ascii=False) if parsed is not None else "[MOCK] ok",
            parsed_output=parsed,
            usage=usage,
            **base,
        )

    async def check_connection(self) -> ConnectionCheckResult:
        return ConnectionCheckResult(provider="mock", result="MOCK")
