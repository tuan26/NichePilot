"""Adapter `http_json_api` với API kiểu MediaWiki (D2 – xác minh Wikipedia, 2026-11-22; FR-006, FR-030, FR-030a).

- `url_template`: kết quả `list=search` chỉ có tiêu đề → URL bài viết dựng từ mẫu (tiêu đề mã hóa, khoảng trắng → `_`).
- `error_key`: lỗi trả trong body với HTTP 200 (`maxlag`, `ratelimited`) → chờ theo `Retry-After`/backoff rồi thử lại có giới hạn
  (API:Etiquette); hết lượt → RATE_LIMITED; mã lỗi khác → UNAVAILABLE `API_ERROR`. Không coi lỗi là "không có kết quả".
- User-Agent cấu hình được gửi ở mọi request. Không mạng thật (httpx MockTransport).
"""

from __future__ import annotations

from datetime import date
from typing import Any

import httpx
import pytest

from nichepilot.tools.sources.base import PolicySnapshot, RateLimiter
from nichepilot.tools.sources.http_json_api import HttpJsonApiAdapter

pytestmark = pytest.mark.discovery
UA = "NichePilotResearchBot/0.1 (test contact) httpx"
CFG = {
    "base_url": "https://en.wikipedia.org/w/api.php",
    "query_template": "action=query&list=search&srsearch={query}&format=json&srlimit=10&maxlag=5",
    "result_mapping": {"items": "query.search", "title": "title", "snippet": "snippet"},
    "url_template": "https://en.wikipedia.org/wiki/{title}",
    "error_key": "error",
    "max_retries": 2,
}


def _policy(cfg: dict[str, Any] | None = None) -> PolicySnapshot:
    return PolicySnapshot(
        policy_id="00000000-0000-0000-0000-000000000001",
        source_key="api:wikipedia",
        adapter_type="http_json_api",
        config=cfg or CFG,
        compliance_status="ALLOWED",
        verified_at=date(2026, 11, 22),
    )


def _adapter(handler: Any, sleeps: list[float]) -> HttpJsonApiAdapter:
    async def sleep(s: float) -> None:
        sleeps.append(s)

    async def limiter_sleep(_s: float) -> None:  # chờ của rate limiter tách riêng khỏi backoff
        return None

    transport = httpx.MockTransport(handler)
    return HttpJsonApiAdapter(
        user_agent=UA,
        client_factory=lambda: httpx.AsyncClient(transport=transport),
        sleep=sleep,
        limiter=RateLimiter(sleep=limiter_sleep),
    )


async def test_TC_E1_FR006_04_mediawiki_search_builds_article_urls() -> None:
    seen: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(
            200,
            json={
                "query": {
                    "search": [
                        {"title": "Inventory management software", "snippet": "small <span>bakery</span> stock"},
                        {"title": "Bakery", "snippet": "x"},
                    ]
                }
            },
        )

    out = await _adapter(handler, []).query(_policy(), "bakery inventory", market="US", language="en", max_results=5)
    assert out.status == "OK"
    assert [h.url for h in out.hits] == [
        "https://en.wikipedia.org/wiki/Inventory_management_software",
        "https://en.wikipedia.org/wiki/Bakery",
    ]
    assert seen[0].headers["User-Agent"] == UA
    assert "maxlag=5" in str(seen[0].url) and "srsearch=bakery%20inventory" in str(seen[0].url)


async def test_TC_E1_FR030_03_in_body_maxlag_backs_off_then_succeeds() -> None:
    calls: list[int] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(200, headers={"Retry-After": "5"}, json={"error": {"code": "maxlag", "info": "lag"}})
        return httpx.Response(200, json={"query": {"search": [{"title": "Bakery"}]}})

    sleeps: list[float] = []
    out = await _adapter(handler, sleeps).query(_policy(), "bakery", market="US", language="en", max_results=5)
    assert out.status == "OK" and len(calls) == 2
    assert 5 in sleeps  # tôn trọng Retry-After


async def test_TC_E1_FR030_04_ratelimited_exhausts_retries_and_other_errors_are_not_no_results() -> None:
    def limited(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": {"code": "ratelimited", "info": "slow down"}})

    sleeps: list[float] = []
    out = await _adapter(limited, sleeps).query(_policy(), "q", market="US", language="en", max_results=5)
    assert out.status == "RATE_LIMITED" and out.reason == "API_RATELIMITED"
    assert len(sleeps) >= 2 and sleeps == sorted(sleeps)  # backoff tăng dần

    def bad(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"error": {"code": "badvalue", "info": "x"}})

    out2 = await _adapter(bad, []).query(_policy(), "q", market="US", language="en", max_results=5)
    assert out2.status == "UNAVAILABLE" and out2.reason == "API_ERROR"


def test_TC_E1_FR006g_04_config_requires_url_or_url_template() -> None:
    from nichepilot.core.source_config import SourceConfigError, validate_source_config

    validate_source_config("http_json_api", CFG)
    with pytest.raises(SourceConfigError):
        validate_source_config("http_json_api", {**CFG, "url_template": None, "result_mapping": {"items": "x"}})
    with pytest.raises(SourceConfigError):
        validate_source_config("http_json_api", {**CFG, "url_template": "https://en.wikipedia.org/wiki/{nope}"})


async def test_TC_E1_FR030_05_slow_response_triggers_cooldown_before_next_request() -> None:
    """Robot Policy (Action API rules): "if your request takes more than 1 second to serve, please wait 5 seconds before making
    another request" – cấu hình qua `slow_response_s` / `slow_cooldown_s` (mặc định tắt)."""
    import time

    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"query": {"search": [{"title": "Bakery"}]}})

    sleeps: list[float] = []
    adapter = _adapter(handler, sleeps)
    clock = {"t": 1000.0}
    adapter.clock = lambda: clock["t"]  # type: ignore[method-assign]
    cfg = {**CFG, "slow_response_s": 1.0, "slow_cooldown_s": 5.0}
    real_get = httpx.AsyncClient.get

    async def slow_get(self: httpx.AsyncClient, *a: Any, **k: Any) -> httpx.Response:
        resp = await real_get(self, *a, **k)
        clock["t"] += 1.5  # phản hồi mất 1,5 s
        return resp

    httpx.AsyncClient.get = slow_get  # type: ignore[method-assign]
    try:
        await adapter.query(_policy(cfg), "a", market="US", language="en", max_results=5)
        await adapter.query(_policy(cfg), "b", market="US", language="en", max_results=5)
    finally:
        httpx.AsyncClient.get = real_get  # type: ignore[method-assign]
    assert any(abs(s - 5.0) < 0.01 for s in sleeps), sleeps  # chờ 5 s trước request kế tiếp
    fast: list[float] = []
    plain = _adapter(handler, fast)
    await plain.query(_policy(), "a", market="US", language="en", max_results=5)
    await plain.query(_policy(), "b", market="US", language="en", max_results=5)
    assert fast == []  # không cấu hình → không chờ thêm
    del time
