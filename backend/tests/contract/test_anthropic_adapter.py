"""T059 – Adapter Anthropic kiểm thử bằng transport HTTP giả lập (httpx2.MockTransport). KHÔNG gọi API thật.

Payload mẫu dựng theo định dạng Messages API; đây KHÔNG phải kiểm thử tích hợp với API thật (chỉ ở tests/live).
"""

from __future__ import annotations

import httpx2
import pytest

from nichepilot.ai.providers.anthropic_api import ANTHROPIC_BASE_URL, AnthropicAPIProvider
from nichepilot.ai.providers.base import (
    LLMMessage,
    LLMRequest,
    ProviderAuthError,
    ProviderBadRequestError,
    ProviderNetworkError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ToolSpec,
)
from tests.fakes.http import Handler, json_response, mock_client

pytestmark = pytest.mark.mock
KEY = "sk-ant-test-key-not-real-0000"


def _req(**kw: object) -> LLMRequest:
    base: dict[str, object] = {
        "task_type": "system.diagnostic",
        "model": "claude-haiku-5-5",
        "system": "sys",
        "messages": [LLMMessage(role="user", content="hi")],
        "max_output_tokens": 256,
        "timeout_s": 5,
        "effort": "low",
    }
    base.update(kw)
    return LLMRequest(**base)  # type: ignore[arg-type]


def _msg(content: list[dict[str, object]], stop: str = "end_turn", **extra: object) -> Handler:
    return json_response(
        200,
        {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": "claude-haiku-5-5",
            "content": content,
            "stop_reason": stop,
            "stop_sequence": None,
            "usage": {
                "input_tokens": 120,
                "output_tokens": 30,
                "cache_read_input_tokens": 10,
                "cache_creation_input_tokens": 5,
            },
            **extra,
        },
    )


def _err(status: int, kind: str) -> Handler:
    return json_response(status, {"type": "error", "error": {"type": kind, "message": "x"}}, {"retry-after": "2"})


def _provider(responder: Handler | Exception) -> tuple[AnthropicAPIProvider, object]:
    client, rec = mock_client(responder)
    return AnthropicAPIProvider(KEY, http_client=client), rec


async def test_TC_FR010_01_structured_output_request_and_parse() -> None:
    schema = {"type": "object", "properties": {"status": {"type": "string"}}, "required": ["status"]}
    p, rec = _provider(_msg([{"type": "text", "text": '{"status":"ok"}'}]))
    r = await p.generate(_req(output_schema=schema))
    assert r.outcome == "SUCCESS" and r.parsed_output == {"status": "ok"} and r.data_origin == "REAL"
    assert r.usage.input_tokens == 120 and r.usage.cache_read_tokens == 10 and r.usage.cache_write_tokens == 5
    sent = rec.last_json  # type: ignore[attr-defined]
    req = rec.calls[-1]  # type: ignore[attr-defined]
    assert str(req.url) == f"{ANTHROPIC_BASE_URL}/v1/messages"
    assert sent["output_config"] == {"effort": "low", "format": {"type": "json_schema", "schema": schema}}
    assert "temperature" not in sent and "top_p" not in sent
    assert sent["messages"][-1]["role"] == "user"  # không prefill assistant
    # SDK 2.x gửi API key chính thức qua Authorization: Bearer <api_key> – đúng key đã cấu hình, không phải OAuth.
    assert req.headers["authorization"] == f"Bearer {KEY}"
    assert "oauth" not in req.headers.get("anthropic-beta", "")


async def test_TC_FR010_02_tool_use_parsed_and_tools_strict() -> None:
    p, rec = _provider(
        _msg([{"type": "tool_use", "id": "tu_1", "name": "system_runtime_info", "input": {}}], "tool_use")
    )
    tool = ToolSpec(name="system.runtime_info", description="d", input_schema={"type": "object", "properties": {}})
    r = await p.generate(_req(tools=[tool]))
    assert r.tool_calls[0].name == "system.runtime_info" and r.tool_calls[0].id == "tu_1"
    sent = rec.last_json  # type: ignore[attr-defined]
    assert sent["tools"][0]["name"] == "system_runtime_info"
    assert sent["tools"][0]["strict"] is True and sent["tool_choice"] == {"type": "auto"}


async def test_TC_FR017_01_refusal_and_truncation() -> None:
    p, _ = _provider(
        _msg([], "refusal", stop_details={"type": "refusal", "category": "cyber", "explanation": "policy"})
    )
    r = await p.generate(_req())
    assert r.outcome == "REFUSED" and r.refusal_category == "cyber" and r.refusal_explanation == "policy"
    p, _ = _provider(_msg([{"type": "text", "text": "{"}], "max_tokens"))
    assert (await p.generate(_req())).outcome == "TRUNCATED"


@pytest.mark.parametrize(
    ("status", "kind", "exc"),
    [
        (401, "authentication_error", ProviderAuthError),
        (403, "permission_error", ProviderAuthError),
        (400, "invalid_request_error", ProviderBadRequestError),
        (404, "not_found_error", ProviderBadRequestError),
        (429, "rate_limit_error", ProviderRateLimitedError),
        (500, "api_error", ProviderUnavailableError),
        (529, "overloaded_error", ProviderUnavailableError),
    ],
)
async def test_TC_FR014_01_http_errors_mapped(status: int, kind: str, exc: type[Exception]) -> None:
    p, _ = _provider(_err(status, kind))
    with pytest.raises(exc) as info:
        await p.generate(_req())
    assert info.value.sent is True  # type: ignore[attr-defined]
    if status == 429:
        assert info.value.retry_after_s == 2.0  # type: ignore[attr-defined]


async def test_TC_FR014_02_connection_errors_distinguish_sent() -> None:
    p, _ = _provider(httpx2.ConnectError("refused"))
    with pytest.raises(ProviderNetworkError) as net:
        await p.generate(_req())
    assert net.value.sent is False
    p, _ = _provider(httpx2.ReadTimeout("slow"))
    with pytest.raises(ProviderTimeoutError) as t:
        await p.generate(_req())
    assert t.value.sent is True
    p, _ = _provider(httpx2.ConnectTimeout("slow connect"))
    with pytest.raises(ProviderTimeoutError) as t2:
        await p.generate(_req())
    assert t2.value.sent is False
    p, _ = _provider(httpx2.RemoteProtocolError("dropped"))
    with pytest.raises(ProviderNetworkError) as dropped:
        await p.generate(_req())
    assert dropped.value.sent is True


def test_TC_FR019b_02_client_uses_explicit_key_and_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "oauth-should-not-be-used")
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://evil.example.com")
    p = AnthropicAPIProvider(KEY)
    assert p.client.api_key == KEY and p.client.auth_token is None
    assert str(p.client.base_url).rstrip("/") == ANTHROPIC_BASE_URL
    assert p.client.max_retries == 0
    with pytest.raises(ValueError):
        AnthropicAPIProvider("")


async def test_TC_FR018f_03_real_provider_rejects_mock_scenario() -> None:
    p, rec = _provider(_msg([]))
    with pytest.raises(ValueError):
        await p.generate(_req(mock_scenario="success"))
    assert rec.calls == []  # type: ignore[attr-defined]


async def test_TC_FR056_01_check_connection_uses_free_models_endpoint() -> None:
    p, rec = _provider(json_response(200, {"data": [], "has_more": False, "first_id": None, "last_id": None}))
    assert (await p.check_connection()).result == "OK"
    assert rec.calls[-1].method == "GET" and rec.calls[-1].url.path == "/v1/models"  # type: ignore[attr-defined]
    p, _ = _provider(_err(401, "authentication_error"))
    assert (await p.check_connection()).result == "INVALID_KEY"
