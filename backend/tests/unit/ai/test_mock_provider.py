"""T057 – MockAIProvider (FR-018). Mọi dữ liệu do mock sinh ra mang nhãn MOCK, không gọi mạng."""

from __future__ import annotations

import pytest

from nichepilot.ai.providers.base import (
    LLMMessage,
    LLMRequest,
    ProviderAuthError,
    ProviderNetworkError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ToolSpec,
)
from nichepilot.ai.providers.mock import MockAIProvider

pytestmark = pytest.mark.mock

SCHEMA = {
    "type": "object",
    "properties": {"status": {"type": "string", "enum": ["ok"]}, "note": {"type": "string"}, "n": {"type": "integer"}},
    "required": ["status", "note", "n"],
    "additionalProperties": False,
}


def _req(scenario: str | None = None, *, tools: bool = False, schema: bool = True, seed: str = "job-1") -> LLMRequest:
    return LLMRequest(
        task_type="system.diagnostic",
        model="mock-model",
        system="s",
        messages=[LLMMessage(role="user", content="hi")],
        tools=[ToolSpec(name="system.runtime_info", description="d", input_schema={"type": "object"})] if tools else [],
        output_schema=SCHEMA if schema else None,
        max_output_tokens=100,
        timeout_s=5,
        mock_scenario=scenario,
        seed=seed,
    )


async def test_TC_FR018_02_success_is_labelled_mock_and_matches_schema() -> None:
    p = MockAIProvider()
    assert p.data_origin == "MOCK" and p.paid is False
    r = await p.generate(_req("success"))
    assert r.outcome == "SUCCESS" and r.data_origin == "MOCK"
    assert r.parsed_output == {"status": "ok", "note": "[MOCK] note", "n": 0}
    assert r.content_text is not None and r.content_text.startswith("[MOCK]")
    assert r.usage.input_tokens == 2000 and r.usage.output_tokens == 500


async def test_TC_FR018_03_tool_call_first_then_final() -> None:
    p = MockAIProvider()
    r = await p.generate(_req("success", tools=True, schema=False))
    assert r.outcome == "SUCCESS" and r.stop_reason == "tool_use"
    assert r.tool_calls[0].name == "system.runtime_info"


async def test_TC_FR018_04_deterministic() -> None:
    a = await MockAIProvider().generate(_req("success", seed="x"))
    b = await MockAIProvider().generate(_req("success", seed="x"))
    assert a.model_dump(exclude={"latency_ms"}) == b.model_dump(exclude={"latency_ms"})


@pytest.mark.parametrize(
    ("scenario", "exc", "sent"),
    [
        ("timeout", ProviderTimeoutError, False),
        ("timeout_after_send", ProviderTimeoutError, True),
        ("rate_limit", ProviderRateLimitedError, True),
        ("provider_error", ProviderUnavailableError, True),
        ("auth_error", ProviderAuthError, True),
        ("network_error", ProviderNetworkError, False),
    ],
)
async def test_TC_FR018_05_error_scenarios(scenario: str, exc: type[Exception], sent: bool) -> None:
    with pytest.raises(exc) as info:
        await MockAIProvider().generate(_req(scenario))
    assert info.value.sent is sent  # type: ignore[attr-defined]


async def test_TC_FR018_06_refusal_truncated_schema_invalid_budget_heavy() -> None:
    p = MockAIProvider()
    refused = await p.generate(_req("refusal"))
    assert refused.outcome == "REFUSED" and refused.refusal_category and refused.usage.output_tokens > 0
    truncated = await p.generate(_req("truncated"))
    assert truncated.outcome == "TRUNCATED" and truncated.stop_reason == "max_tokens"
    invalid = await p.generate(_req("schema_invalid"))
    assert invalid.outcome == "SUCCESS" and invalid.parsed_output == {"unexpected": "[MOCK]"}
    heavy = await p.generate(_req("budget_heavy"))
    assert heavy.usage.input_tokens == 2_000_000
    assert await p.count_input_tokens(_req("budget_heavy")) == 2_000_000


async def test_TC_FR018_07_fail_n_then_success_counts_per_seed() -> None:
    p = MockAIProvider()
    for _ in range(2):
        with pytest.raises(ProviderTimeoutError):
            await p.generate(_req("fail_n_then_success:timeout:2", seed="s1"))
    assert (await p.generate(_req("fail_n_then_success:timeout:2", seed="s1"))).outcome == "SUCCESS"


async def test_TC_FR018_08_unknown_scenario_rejected_and_connection_check() -> None:
    p = MockAIProvider()
    with pytest.raises(ValueError):
        await p.generate(_req("not-a-scenario"))
    assert (await p.check_connection()).result == "MOCK"
