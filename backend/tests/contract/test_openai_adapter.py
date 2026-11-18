"""T060 – Adapter OpenAI (dự phòng) kiểm thử bằng transport HTTP giả lập. KHÔNG gọi API thật."""

from __future__ import annotations

import pytest

from nichepilot.ai.providers.base import LLMMessage, LLMRequest, ProviderAuthError, ProviderRateLimitedError
from nichepilot.ai.providers.openai_api import OpenAIAPIProvider
from tests.fakes.http import Handler, json_response, mock_client

pytestmark = pytest.mark.mock
KEY = "sk-proj-test-key-not-real-000000"


def _req(**kw: object) -> LLMRequest:
    base: dict[str, object] = {
        "task_type": "system.diagnostic",
        "model": "gpt-test",
        "system": "sys",
        "messages": [LLMMessage(role="user", content="hi")],
        "max_output_tokens": 128,
        "timeout_s": 5,
    }
    base.update(kw)
    return LLMRequest(**base)  # type: ignore[arg-type]


def _completion(content: str | None, finish: str = "stop", refusal: str | None = None) -> Handler:
    return json_response(
        200,
        {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "created": 0,
            "model": "gpt-test",
            "choices": [
                {
                    "index": 0,
                    "finish_reason": finish,
                    "message": {"role": "assistant", "content": content, "refusal": refusal},
                }
            ],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 10,
                "total_tokens": 60,
                "prompt_tokens_details": {"cached_tokens": 4},
            },
        },
    )


def _provider(responder: Handler) -> tuple[OpenAIAPIProvider, object]:
    client, rec = mock_client(responder)
    return OpenAIAPIProvider(KEY, http_client=client), rec


async def test_TC_FR011_01_structured_output_usage_and_mapping() -> None:
    schema = {"type": "object", "properties": {"status": {"type": "string"}}, "required": ["status"]}
    p, rec = _provider(_completion('{"status":"ok"}'))
    r = await p.generate(_req(output_schema=schema))
    assert r.outcome == "SUCCESS" and r.parsed_output == {"status": "ok"}
    assert r.usage.input_tokens == 50 and r.usage.output_tokens == 10 and r.usage.cache_read_tokens == 4
    assert rec.last_json["response_format"]["type"] == "json_schema"  # type: ignore[attr-defined]
    assert rec.calls[-1].headers["authorization"] == f"Bearer {KEY}"  # type: ignore[attr-defined]


async def test_TC_FR011_02_refusal_truncation_errors() -> None:
    p, _ = _provider(_completion(None, refusal="no"))
    assert (await p.generate(_req())).outcome == "REFUSED"
    p, _ = _provider(_completion("{", finish="length"))
    assert (await p.generate(_req())).outcome == "TRUNCATED"
    p, _ = _provider(json_response(401, {"error": {"message": "bad key"}}))
    with pytest.raises(ProviderAuthError):
        await p.generate(_req())
    p, _ = _provider(json_response(429, {"error": {"message": "slow"}}))
    with pytest.raises(ProviderRateLimitedError):
        await p.generate(_req())
