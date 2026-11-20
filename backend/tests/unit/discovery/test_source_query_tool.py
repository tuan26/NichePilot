"""T020 – Tool `source.query` (FR-006, FR-006d, FR-006f, FR-012b; internal-interfaces §1)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

import httpx
import pytest

from nichepilot.core.discovery_config import DiscoverySettings
from nichepilot.tools.builtin.source_query import SourceQueryInput, build_source_query_tool
from nichepilot.tools.registry import ToolContext
from nichepilot.tools.sources.base import RateLimiter
from nichepilot.tools.sources.searxng_engine import SearxngEngineAdapter

pytestmark = pytest.mark.discovery


def _policy(status: str = "ALLOWED", **cfg: Any) -> dict[str, Any]:
    return {
        "policy_id": str(uuid.uuid4()),
        "source_key": "searxng:wikipedia",
        "adapter_type": "searxng_engine",
        "config": {"engine_name": "wikipedia", "max_retries": 1, "timeout_s": 5, **cfg},
        "compliance_status": status,
        "verified_at": str(date(2026, 11, 1)),
    }


def _ctx() -> ToolContext:
    async def _rec(_row: dict[str, Any]) -> None:
        return None

    return ToolContext(uuid.uuid4(), None, frozenset({"source.query"}), "REAL", _rec)


def _tool(handler: Any) -> Any:
    transport = httpx.MockTransport(handler)
    adapter = SearxngEngineAdapter(
        base_url="http://searxng:8080",
        user_agent="test",
        client_factory=lambda: httpx.AsyncClient(transport=transport),
        sleep=_nosleep,
        limiter=RateLimiter(sleep=_nosleep),
    )
    return build_source_query_tool(DiscoverySettings(), adapters={"searxng_engine": adapter}, sleep=lambda _s: _noop())


async def _noop() -> None:
    return None


async def _nosleep(_s: float) -> None:
    return None


async def _run(tool: Any, policy: dict[str, Any]) -> dict[str, Any]:
    inp = SourceQueryInput(policy=policy, query="bakery inventory", market="US", language="en", max_results=5)
    out = await tool.handler(inp, _ctx())
    return out.model_dump(mode="json")  # type: ignore[no-any-return]


async def test_TC_E1_FR006_01_allowed_source_queried_and_snippets_redacted() -> None:
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://forum.example/t/1",
                        "title": "Flour stock",
                        "content": "Mail me at a.b@example.com",
                    },
                    {"url": "https://forum.example/t/2", "title": "Waste", "content": "Last week Priya Raman told me"},
                ]
            },
        )

    out = await _run(_tool(handler), _policy())
    assert out["status"] == "OK" and len(out["hits"]) == 2
    req = seen[0]
    assert req.url.params["engines"] == "wikipedia" and req.url.params["format"] == "json"
    assert "X-Real-IP" in req.headers  # tránh botdetection của SearXNG
    first, second = out["hits"]
    assert "a.b@example.com" not in str(out) and first["redaction_status"] == "REDACTED"
    assert second["redaction_status"] == "NEEDS_REVIEW" and second["snippet"] is None  # không lưu/không gửi AI
    assert "Priya" not in str(out)


@pytest.mark.parametrize("status", ["UNVERIFIED", "PROHIBITED"])
async def test_TC_E1_FR006_02_non_allowed_policy_rejected_without_request(status: str) -> None:
    calls: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        return httpx.Response(200, json={"results": []})

    with pytest.raises(PermissionError):
        await _run(_tool(handler), _policy(status))
    assert calls == []  # không có truy vấn nào ra nguồn chưa ALLOWED


async def test_TC_E1_FR006f_01_rate_limit_and_captcha_not_bypassed() -> None:
    attempts: list[int] = []

    def limited(req: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(429, headers={"Retry-After": "1"})

    out = await _run(_tool(limited), _policy(max_retries=1))
    assert out["status"] == "RATE_LIMITED" and len(attempts) == 2  # 1 lần + 1 lần thử lại, rồi dừng

    def captcha(req: httpx.Request) -> httpx.Response:
        return httpx.Response(403, text="<html>Please complete the CAPTCHA</html>")

    out2 = await _run(_tool(captcha), _policy())
    assert out2["status"] == "ACCESS_RESTRICTED" and out2["hits"] == []


async def test_TC_E1_FR012b_01_network_error_and_auth_failure_statuses() -> None:
    def down(req: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    out = await _run(_tool(down), _policy(max_retries=0))
    assert out["status"] == "UNAVAILABLE" and out["reason"] == "NETWORK_ERROR"
