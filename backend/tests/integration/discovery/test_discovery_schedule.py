"""T120 – Lượt khám phá theo lịch E0 (FR-033, SC-017): đúng 1 lượt/mốc; `ensure_run` tạo đúng một `discovery_runs` (idempotent);
`trigger = SCHEDULE` lấy từ `agent_jobs`; chỉ nguồn ALLOWED; không nguồn → NO_COMPLIANT_SEARCH_SOURCE, 0 lời gọi AI; ngân sách chưa cấu
hình → scheduler E0 không tạo job. Không sửa Scheduler E0. MOCK."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from nichepilot.jobs.scheduler import scheduler_tick
from tests.api_helpers import run_worker_once
from tests.discovery_helpers import allow_test_source, discovery_client
from tests.discovery_run import FORUM, REVIEW, set_search
from tests.fakes.discovery_ai import ScriptedDiscoveryAI
from tests.integration.budget_helpers import restore_budget_defaults, set_setting

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]


async def _schedule(engine: AsyncEngine, due: datetime) -> uuid.UUID:
    async with engine.begin() as conn:
        pid = (await conn.execute(text("SELECT id FROM projects WHERE is_default"))).scalar_one()
        sid = uuid.uuid4()
        await conn.execute(
            text(
                "INSERT INTO job_schedules (id, project_id, name, job_type, params, cron_expr, timezone, enabled,"
                " misfire_policy, next_run_at) VALUES (:id, :p, :n, 'discovery.run', CAST(:params AS jsonb), '*/5 * * * *',"
                " 'UTC', true, 'RUN_ONCE', :nr)"
            ),
            {"id": sid, "p": pid, "n": f"discovery-{sid}", "params": json.dumps({"market": "US"}), "nr": due},
        )
    return sid


def _due() -> datetime:
    now = datetime.now(UTC)
    return now.replace(minute=now.minute - now.minute % 5, second=0, microsecond=0)


async def test_TC_E1_FR033_01_one_run_per_slot_with_schedule_trigger(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        due = _due()
        sid = await _schedule(clean_db, due)
        sm = async_sessionmaker(clean_db)
        enqueue = client.services.job_queue.enqueue_run  # type: ignore[attr-defined]
        created = await scheduler_tick(sm, enqueue, now=due + timedelta(seconds=5), override="mock")
        again = await scheduler_tick(sm, enqueue, now=due + timedelta(seconds=30), override="mock")
        assert len(created) == 1 and again == []
        await run_worker_once(client)
        await run_worker_once(client)  # job giao lại / chạy lại worker không tạo lượt thứ hai
        async with clean_db.connect() as conn:
            runs = (
                await conn.execute(
                    text(
                        "SELECT r.trigger, r.outcome, j.schedule_id FROM discovery_runs r JOIN agent_jobs j ON j.id = r.job_id"
                    )
                )
            ).all()
        assert len(runs) == 1 and runs[0].trigger == "SCHEDULE" and runs[0].schedule_id == sid
        assert runs[0].outcome == "COMPLETED"


async def test_TC_E1_SC017_04_scheduled_run_without_allowed_source_makes_no_ai_call(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    ai = ScriptedDiscoveryAI()
    async with discovery_client(migrated_db, ai=ai) as client:  # không có nguồn ALLOWED nào (seed UNVERIFIED)
        due = _due()
        await _schedule(clean_db, due)
        enqueue = client.services.job_queue.enqueue_run  # type: ignore[attr-defined]
        assert (
            len(
                await scheduler_tick(
                    async_sessionmaker(clean_db), enqueue, now=due + timedelta(seconds=5), override="mock"
                )
            )
            == 1
        )
        await run_worker_once(client)
        async with clean_db.connect() as conn:
            run = (await conn.execute(text("SELECT outcome, stop_reason, source_policy_ids FROM discovery_runs"))).one()
        assert run.outcome == "PARTIAL_COMPLETED" and run.stop_reason == "NO_COMPLIANT_SEARCH_SOURCE"
        assert run.source_policy_ids == [] and ai.requests == []


async def test_TC_E1_FR033_02_no_budget_no_scheduled_job(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        due = _due()
        await _schedule(clean_db, due)
        await set_setting(clean_db, "budget.daily_usd", '"0"')
        try:
            enqueue = client.services.job_queue.enqueue_run  # type: ignore[attr-defined]
            created = await scheduler_tick(
                async_sessionmaker(clean_db), enqueue, now=due + timedelta(seconds=5), override="mock"
            )
            assert created == []
        finally:
            await restore_budget_defaults(clean_db)
