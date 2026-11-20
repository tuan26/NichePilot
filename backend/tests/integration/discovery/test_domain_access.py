"""T026 – DomainAccessService (FR-030a; research R-04): robots (protego, RFC 9309), khoảng cách theo tên miền, bền qua restart."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from nichepilot.modules.discovery.access import DomainAccessService

pytestmark = [pytest.mark.integration, pytest.mark.discovery]
FIX = Path(__file__).resolve().parents[2] / "fixtures" / "discovery"


class Clock:
    def __init__(self) -> None:
        self.now = datetime(2026, 11, 20, 8, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


async def test_TC_E1_FR030a_01_robots_rules_and_wildcards(clean_db: AsyncEngine) -> None:
    svc = DomainAccessService(async_sessionmaker(clean_db), clock=Clock())
    await svc.record_robots("reviews.example", "OK", (FIX / "robots_wildcard.txt").read_text())
    assert (await svc.permit("https://reviews.example/a-review", interval_ceiling_s=2)).allowed
    blocked = await svc.permit("https://reviews.example/files/report.pdf", interval_ceiling_s=2)
    assert not blocked.allowed and blocked.reason == "ROBOTS_DISALLOWED"  # wildcard /*.pdf$ (RFC 9309)
    await svc.record_robots("private.example", "OK", (FIX / "robots_disallow_all.txt").read_text())
    assert (await svc.permit("https://private.example/x", interval_ceiling_s=2)).reason == "ROBOTS_DISALLOWED"
    needs = await svc.permit("https://new.example/x", interval_ceiling_s=2)
    assert not needs.allowed and needs.reason == "ROBOTS_PENDING"  # agent phải gọi robots.fetch trước


async def test_TC_E1_FR030a_02_interval_is_max_of_ceiling_crawl_delay_retry_after(clean_db: AsyncEngine) -> None:
    clock = Clock()
    svc = DomainAccessService(async_sessionmaker(clean_db), clock=clock)
    await svc.record_robots("forum.example", "OK", (FIX / "robots_crawl_delay.txt").read_text())  # Crawl-delay: 5
    assert (await svc.permit("https://forum.example/t/1", interval_ceiling_s=2)).allowed
    await svc.record_request("forum.example")
    clock.now += timedelta(seconds=3)
    wait = await svc.permit("https://forum.example/t/2", interval_ceiling_s=2)
    assert not wait.allowed and wait.reason == "WAIT" and wait.wait_s == pytest.approx(2.0)
    clock.now += timedelta(seconds=2)
    assert (await svc.permit("https://forum.example/t/2", interval_ceiling_s=2)).allowed
    await svc.record_retry_after("forum.example", 30)
    later = await svc.permit("https://forum.example/t/3", interval_ceiling_s=2)
    assert later.reason == "WAIT" and later.wait_s == pytest.approx(30.0)
    # trạng thái bền qua "khởi động lại" (service mới, cùng DB)
    svc2 = DomainAccessService(async_sessionmaker(clean_db), clock=clock)
    assert (await svc2.permit("https://forum.example/t/3", interval_ceiling_s=2)).reason == "WAIT"


async def test_TC_E1_FR030a_03_robots_4xx_allows_5xx_blocks_domain(clean_db: AsyncEngine) -> None:
    svc = DomainAccessService(async_sessionmaker(clean_db), clock=Clock())
    await svc.record_robots("nofile.example", "NOT_FOUND", "")
    assert (await svc.permit("https://nofile.example/x", interval_ceiling_s=2)).allowed
    await svc.record_robots("down.example", "UNREACHABLE", "")
    d = await svc.permit("https://down.example/x", interval_ceiling_s=2)
    assert not d.allowed and d.reason == "ROBOTS_UNREACHABLE"
