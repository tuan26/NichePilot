"""T104 – Scheduler tick (FR-033, FR-034, FR-037, SC-007). Chạy với MockAIProvider."""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from nichepilot.jobs.scheduler import scheduler_tick
from tests.integration.budget_helpers import restore_budget_defaults, set_setting

pytestmark = [pytest.mark.integration, pytest.mark.mock]


async def _schedule(
    engine: AsyncEngine,
    *,
    cron: str = "*/5 * * * *",
    next_run_at: datetime,
    enabled: bool = True,
    policy: str = "RUN_ONCE",
    tz: str = "UTC",
) -> uuid.UUID:
    async with engine.begin() as conn:
        pid = (await conn.execute(text("SELECT id FROM projects WHERE is_default"))).scalar_one()
        sid = uuid.uuid4()
        await conn.execute(
            text(
                "INSERT INTO job_schedules (id, project_id, name, job_type, params, cron_expr, timezone, enabled, misfire_policy,"
                " next_run_at) VALUES (:id, :p, :n, 'system.diagnostic', '{}', :c, :tz, :e, :m, :nr)"
            ),
            {"id": sid, "p": pid, "n": f"s-{sid}", "c": cron, "tz": tz, "e": enabled, "m": policy, "nr": next_run_at},
        )
    return sid


async def _jobs(engine: AsyncEngine, sid: uuid.UUID) -> list[tuple[Any, ...]]:
    async with engine.connect() as conn:
        return [
            tuple(r)
            for r in (
                await conn.execute(
                    text(
                        "SELECT trigger, scheduled_for, data_origin FROM agent_jobs WHERE schedule_id = :s ORDER BY scheduled_for"
                    ),
                    {"s": sid},
                )
            ).all()
        ]


class Recorder:
    def __init__(self) -> None:
        self.ids: list[uuid.UUID] = []

    async def __call__(self, job_id: uuid.UUID, delay_s: int = 0) -> None:
        self.ids.append(job_id)


async def test_TC_SC007_01_concurrent_ticks_create_exactly_one_job(clean_db: AsyncEngine, migrated_db: str) -> None:
    due = datetime(2026, 11, 18, 0, 5, tzinfo=UTC)
    sid = await _schedule(clean_db, next_run_at=due)
    sm = async_sessionmaker(clean_db, expire_on_commit=False)
    rec = Recorder()
    now = due + timedelta(seconds=20)
    await asyncio.gather(*(scheduler_tick(sm, rec, now=now, override="mock") for _ in range(4)))  # 4 worker cùng tick
    jobs = await _jobs(clean_db, sid)
    assert jobs == [("SCHEDULE", due, "MOCK")]
    assert len(rec.ids) == 1
    await scheduler_tick(sm, rec, now=now, override="mock")  # tick lại (khởi động lại worker) không tạo trùng
    assert len(await _jobs(clean_db, sid)) == 1
    async with clean_db.connect() as conn:
        nxt, last = (
            await conn.execute(text("SELECT next_run_at, last_run_at FROM job_schedules WHERE id=:s"), {"s": sid})
        ).one()
    assert nxt == datetime(2026, 11, 18, 0, 10, tzinfo=UTC) and last == due


async def test_TC_FR033_06_disabled_schedule_creates_nothing(clean_db: AsyncEngine) -> None:
    due = datetime(2026, 11, 18, 0, 5, tzinfo=UTC)
    sid = await _schedule(clean_db, next_run_at=due, enabled=False)
    await scheduler_tick(async_sessionmaker(clean_db), Recorder(), now=due + timedelta(seconds=10), override="mock")
    assert await _jobs(clean_db, sid) == []


async def test_TC_FR033_07_restart_after_missed_runs(clean_db: AsyncEngine) -> None:
    first_due = datetime(2026, 11, 18, 0, 0, tzinfo=UTC)
    now = first_due + timedelta(hours=1, minutes=3)
    sm = async_sessionmaker(clean_db, expire_on_commit=False)
    once = await _schedule(clean_db, next_run_at=first_due, policy="RUN_ONCE")
    skip = await _schedule(clean_db, next_run_at=first_due, policy="SKIP")
    await scheduler_tick(sm, Recorder(), now=now, override="mock")
    assert [j[1] for j in await _jobs(clean_db, once)] == [datetime(2026, 11, 18, 1, 0, tzinfo=UTC)]
    assert await _jobs(clean_db, skip) == []
    async with clean_db.connect() as conn:
        rows = (
            await conn.execute(
                text("SELECT next_run_at FROM job_schedules WHERE id IN (:a, :b)"), {"a": once, "b": skip}
            )
        ).all()
    assert {r[0] for r in rows} == {datetime(2026, 11, 18, 1, 5, tzinfo=UTC)}


async def test_TC_FR034_01_tick_skips_paid_jobs_without_budget(clean_db: AsyncEngine) -> None:
    due = datetime(2026, 11, 18, 0, 5, tzinfo=UTC)
    sid = await _schedule(clean_db, next_run_at=due)
    await set_setting(clean_db, "budget.daily_usd", '"0"')
    try:
        await scheduler_tick(async_sessionmaker(clean_db), Recorder(), now=due + timedelta(seconds=5), override="mock")
        assert await _jobs(clean_db, sid) == []
    finally:
        await restore_budget_defaults(clean_db)


async def test_TC_SC007_02_scheduled_job_runs_through_worker(clean_db: AsyncEngine, migrated_db: str) -> None:
    from tests.api_helpers import api_client, run_worker_once, setup_owner

    now = datetime.now(UTC)
    due = now.replace(minute=now.minute - now.minute % 5, second=0, microsecond=0)  # khớp lưới */5
    sid = await _schedule(clean_db, next_run_at=due)
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        svc = client.services  # type: ignore[attr-defined]
        created = await scheduler_tick(
            async_sessionmaker(clean_db), svc.job_queue.enqueue_run, now=due + timedelta(seconds=5), override="mock"
        )
        assert len(created) == 1
        await run_worker_once(client)
        job = (await client.get(f"/api/v1/jobs/{created[0]}")).json()
    assert job["status"] == "SUCCEEDED" and job["trigger"] == "SCHEDULE" and job["data_origin"] == "MOCK"
    assert job["schedule_id"] == str(sid)
