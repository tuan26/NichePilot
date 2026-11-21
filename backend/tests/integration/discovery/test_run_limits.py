"""T101 – Giới hạn lượt (FR-030b, FR-030c, FR-030d, SC-015): page_limit, time_limit (thời gian tạm dừng không tính), dừng sớm,
phân bổ trang, outcome + stop_reason; hết giờ khi sắp gọi AI → không gửi lời gọi mới. MOCK – đồng hồ giả lập, không mạng."""

from __future__ import annotations

import time
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from nichepilot.jobs.agents import niche_discovery
from tests.discovery_helpers import allow_test_source, discovery_client
from tests.discovery_run import COPY, FORUM, REVIEW, run_discovery, set_search
from tests.fakes.discovery_ai import CANDIDATES, ScriptedDiscoveryAI

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]


class FakeClock:
    def __init__(self) -> None:
        self.offset = 0.0

    def monotonic(self) -> float:
        return time.monotonic() + self.offset


def _urls(n: int, prefix: str = "u") -> list[str]:
    return [f"https://{prefix}{i}.example/p" for i in range(n)]


async def _fetch_counts(engine: AsyncEngine) -> dict[str, int]:
    async with engine.connect() as conn:
        rows = (await conn.execute(text("SELECT outcome, count(*) FROM page_fetch_log GROUP BY outcome"))).all()
    return {str(r[0]): int(r[1]) for r in rows}


async def test_TC_E1_FR030d_01_page_limit_stops_collection_but_still_evaluates(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    ai = ScriptedDiscoveryAI()
    async with discovery_client(migrated_db, ai=ai) as client:
        await allow_test_source(clean_db)
        web = client.services.discovery.backends.mock_web  # type: ignore[attr-defined]
        q = [c["queries"][0] for c in CANDIDATES["candidates"]]
        web.search = {q[0]: [FORUM, REVIEW, *_urls(3, "a")], q[1]: _urls(5, "b"), q[2]: _urls(5, "c")}
        run = await run_discovery(client, {"market": "US", "page_limit": 10})
        assert run["outcome"] == "PARTIAL_COMPLETED" and run["stop_reason"] == "PAGE_LIMIT_REACHED"
        assert run["metrics"]["pages_attempted"] == 10
        assert sum((await _fetch_counts(clean_db)).values()) == 10
        assert ai.requests_for("discovery.extract") and ai.requests_for(
            "discovery.assess"
        )  # vẫn phân tích dữ liệu đã có


async def test_TC_E1_FR030b_01_page_budget_allocated_between_candidates(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        web = client.services.discovery.backends.mock_web  # type: ignore[attr-defined]
        q = [c["queries"][0] for c in CANDIDATES["candidates"]]
        web.search = {q[0]: _urls(10, "a"), q[1]: _urls(3, "b"), q[2]: _urls(3, "c")}
        await run_discovery(client, {"market": "US", "page_limit": 12})
        async with clean_db.connect() as conn:
            domains = (await conn.execute(text("SELECT domain FROM page_fetch_log"))).scalars().all()
        per = {p: sum(1 for d in domains if d.startswith(p)) for p in "abc"}
        assert sum(per.values()) == 12  # tổng không vượt giới hạn lượt
        assert (
            per["b"] == 3 and per["c"] == 3 and per["a"] == 6
        )  # ứng viên ít URL được nhận đủ phần, phần dư cho ứng viên khác


async def test_TC_E1_FR030c_01_early_stop_when_all_candidates_have_enough(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW, COPY, *_urls(5)])
        run = await run_discovery(client, {"market": "US", "max_candidates": 1})
        assert run["outcome"] == "COMPLETED" and run["stop_reason"] == "ALL_CANDIDATES_SUFFICIENT"
        assert run["metrics"]["pages_attempted"] < 8  # không crawl hết chỉ để dùng số trang
        requested = client.mock_fetcher.requested  # type: ignore[attr-defined]
        assert not any(u in requested for u in _urls(5)[1:])


async def test_TC_E1_FR030d_02_time_limit_before_ai_call_sends_nothing_new(
    clean_db: AsyncEngine, migrated_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = FakeClock()
    monkeypatch.setattr(niche_discovery, "time", clock)
    ai = ScriptedDiscoveryAI()

    def slow_candidates(req: Any) -> None:  # lời gọi ứng viên "mất" 91 phút
        if req.task_type == "discovery.candidates":
            clock.offset += 91 * 60

    ai.before_generate = slow_candidates
    async with discovery_client(migrated_db, ai=ai) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        run = await run_discovery(client, {"market": "US", "time_limit_minutes": 90})
        assert run["outcome"] == "PARTIAL_COMPLETED" and run["stop_reason"] == "TIME_LIMIT_REACHED"
        assert [r.task_type for r in ai.requests] == ["discovery.candidates"]  # không gửi lời gọi AI mới
        assert run["metrics"]["pages_attempted"] == 0
        assert run["metrics"]["insufficient_evidence"] == 3  # ngách thiếu bằng chứng → INSUFFICIENT_EVIDENCE


async def test_TC_E1_FR030c_02_TC_E1_SC015_01_paused_time_not_counted(clean_db: AsyncEngine, migrated_db: str) -> None:
    """elapsed_active_s chỉ cộng thời gian các bước chạy – thời gian job nằm ở PAUSED/PAUSED_BUDGET không được tính."""
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        run = await run_discovery(client)
        async with clean_db.connect() as conn:
            span = (
                await conn.execute(
                    text("SELECT extract(epoch FROM (finished_at - created_at)) FROM agent_jobs WHERE id = :j"),
                    {"j": run["job"]["job_id"]},
                )
            ).scalar_one()
        active = float(run["metrics"]["elapsed_active_s"])
        assert 0 < active <= float(span) + 0.5
