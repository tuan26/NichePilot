"""T102 – Tốc độ và lỗi (FR-030, FR-030a, FR-031, SC-015, QA-06, QA-07): khoảng cách cùng tên miền ≥ mức trần; 429/503 thử lại ≤ 2 lần
theo Retry-After rồi RATE_LIMITED; Retry-After dài hơn thời gian còn lại → bỏ tên miền ngay; trang lỗi bị bỏ qua, lượt vẫn hoàn tất."""

from __future__ import annotations

import itertools
import time
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from nichepilot.tools.fetchers.http_fetcher import RawPage
from tests.discovery_helpers import allow_test_source, discovery_client
from tests.discovery_run import FORUM, REVIEW, run_discovery, set_search

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]


def _wrap(client: Any, rule: Any) -> list[tuple[str, float]]:
    fetcher = client.mock_fetcher
    real = fetcher.fetch
    calls: list[tuple[str, float]] = []

    async def fetch(url: str, *, timeout_s: float) -> RawPage:
        calls.append((url, time.monotonic()))
        override = rule(url, sum(1 for u, _ in calls if u == url))
        return override if override is not None else await real(url, timeout_s=timeout_s)

    fetcher.fetch = fetch
    return calls


async def _reasons(engine: AsyncEngine) -> dict[str, str | None]:
    async with engine.connect() as conn:
        rows = (await conn.execute(text("SELECT domain, reason FROM page_fetch_log"))).all()
    return {r[0]: r[1] for r in rows}


async def test_TC_E1_FR030_01_rate_limited_retried_then_succeeds(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        calls = _wrap(client, lambda u, n: RawPage(429, "text/html", "", u, 1.0) if u == REVIEW and n <= 2 else None)
        run = await run_discovery(client, {"market": "US", "per_domain_interval_s": 1})
        review_calls = [t for u, t in calls if u == REVIEW]
        assert len(review_calls) == 3  # 2 lần thử lại theo Retry-After rồi thành công
        assert review_calls[1] - review_calls[0] >= 0.9  # tôn trọng Retry-After
        assert (await _reasons(clean_db))["reviews.example"] is None and run["outcome"] == "COMPLETED"


async def test_TC_E1_FR030_02_gives_up_after_two_retries(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        calls = _wrap(client, lambda u, n: RawPage(503, "text/html", "", u, 1.0) if u == REVIEW else None)
        run = await run_discovery(client, {"market": "US", "per_domain_interval_s": 1})
        assert sum(1 for u, _ in calls if u == REVIEW) == 3  # 1 lần + tối đa 2 lần thử lại
        assert (await _reasons(clean_db))["reviews.example"] == "RATE_LIMITED"
        assert run["outcome"] == "COMPLETED" and run["metrics"]["skipped_by_reason"]["RATE_LIMITED"] == 1


async def test_TC_E1_FR030a_04_long_retry_after_drops_domain_immediately(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        second = "https://reviews.example/another-thread"
        set_search(client, [REVIEW, second, FORUM])
        calls = _wrap(
            client, lambda u, n: RawPage(429, "text/html", "", u, 99999.0) if "reviews.example" in u else None
        )
        run = await run_discovery(client)
        assert [u for u, _ in calls if "reviews.example" in u] == [
            REVIEW
        ]  # không thử lại, không chạm URL khác cùng miền
        assert run["metrics"]["skipped_by_reason"]["RATE_LIMITED"] == 2
        async with clean_db.connect() as conn:
            blocked = (
                await conn.execute(
                    text("SELECT block_reason FROM domain_access_state WHERE domain = 'reviews.example'")
                )
            ).scalar_one()
        assert blocked == "RATE_LIMITED"


async def test_TC_E1_FR031_02_TC_E1_SC015_02_errors_skipped_and_same_domain_spaced(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        same = ["https://reviews.example/a", "https://reviews.example/b", "https://reviews.example/c"]
        set_search(client, [*same, "https://broken.example/page", FORUM])
        calls = _wrap(client, lambda u, n: None)
        run = await run_discovery(client, {"market": "US", "per_domain_interval_s": 1})
        stamps = [t for u, t in calls if "reviews.example" in u]
        assert len(stamps) == 3 and all(b - a >= 0.95 for a, b in itertools.pairwise(stamps))
        assert run["outcome"] == "COMPLETED"  # trang lỗi không làm hỏng cả lượt
        assert run["metrics"]["skipped_by_reason"].get("HTTP_ERROR", 0) >= 1
