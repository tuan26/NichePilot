"""US4 – Vòng đời Agent Job (T093–T097; FR-030…FR-038, SC-006, QA-09, QA-10).

Agent `GatedAgent` là TEST DOUBLE: mỗi bước chờ một asyncio.Event để test điều khiển thời điểm pause/cancel/crash.
Provider là MockAIProvider (dữ liệu MOCK) – không gọi API có phí.
"""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from nichepilot.ai.providers.base import LLMMessage
from nichepilot.jobs.maintenance import recover_stalled_jobs
from nichepilot.jobs.runtime import AgentDefinition, JobContext, JobRuntime, StepOutcome
from nichepilot.worker import effective_concurrency
from tests.api_helpers import api_client, csrf_headers, make_settings, run_worker_once, setup_owner
from tests.integration.budget_helpers import insert_job, restore_budget_defaults

pytestmark = [pytest.mark.integration, pytest.mark.mock]


class NoInput(BaseModel):
    mock_scenario: str | None = None


class GatedAgent:
    """3 bước; bước `ai_step` gọi AI qua gateway dùng chung. Mỗi bước chờ gate[seq] nếu có."""

    def __init__(self, gates: dict[int, asyncio.Event] | None = None, ai_step: int | None = None) -> None:
        self.gates = gates or {}
        self.ai_step = ai_step
        self.entered: dict[int, asyncio.Event] = {i: asyncio.Event() for i in (1, 2, 3)}
        self.definition = AgentDefinition(
            job_type="system.diagnostic",
            description="gated",
            task_type="system.diagnostic",
            input_model=NoInput,
            output_model=NoInput,
            allowed_tools=[],
            max_steps=5,
            max_ai_calls=5,
            timeout_s=60,
            token_budget=10**7,
            paid=True,
            acceptance=lambda r: [],
        )

    async def run_step(self, seq: int, state: dict[str, Any], ctx: JobContext) -> StepOutcome:
        self.entered[seq].set()
        if seq in self.gates:
            await self.gates[seq].wait()
        if seq == self.ai_step:
            await ctx.call_ai(system="s", messages=[LLMMessage(role="user", content="x")])
        return StepOutcome(
            name=f"s{seq}",
            step_type="LOGIC",
            output={"seq": seq},
            state={**state, f"s{seq}": True},
            done=seq == 3,
            result={"ok": True} if seq == 3 else None,
        )


def _runtime(engine: AsyncEngine, url: str, agent: GatedAgent) -> JobRuntime:
    from nichepilot.ai.gateway import AIGateway
    from nichepilot.ai.providers.mock import MockAIProvider
    from nichepilot.tools.registry import ToolRegistry

    sm = async_sessionmaker(engine, expire_on_commit=False)
    settings = make_settings(url)
    gw = AIGateway(settings, sm, {"mock": MockAIProvider()}, backoff_base_s=0)
    return JobRuntime(sm, gw, ToolRegistry(), {"system.diagnostic": agent}, settings, heartbeat_interval_s=0.2)


async def _queued_job(engine: AsyncEngine) -> uuid.UUID:
    job = await insert_job(engine)
    async with engine.begin() as conn:
        await conn.execute(text("UPDATE agent_jobs SET status='QUEUED' WHERE id=:j"), {"j": job})
    return job


async def _row(engine: AsyncEngine, job: uuid.UUID) -> dict[str, Any]:
    async with engine.connect() as conn:
        return dict((await conn.execute(text("SELECT * FROM agent_jobs WHERE id=:j"), {"j": job})).mappings().one())


async def _count(engine: AsyncEngine, sql: str, **p: Any) -> int:
    async with engine.connect() as conn:
        return int((await conn.execute(text(sql), p)).scalar_one())


async def _flag(engine: AsyncEngine, job: uuid.UUID, column: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(f"UPDATE agent_jobs SET {column} = true WHERE id = :j"), {"j": job})  # noqa: S608


# --------------------------------------------------------------------------- T093 cancel / pause
async def test_TC_QA09_01_cancel_before_ai_call_sends_nothing(clean_db: AsyncEngine, migrated_db: str) -> None:
    job = await _queued_job(clean_db)
    gate = asyncio.Event()
    agent = GatedAgent({1: gate}, ai_step=1)
    task = asyncio.create_task(_runtime(clean_db, migrated_db, agent).run(job))
    await agent.entered[1].wait()
    await _flag(clean_db, job, "cancel_requested")  # hủy trong lúc bước đang chạy, trước lời gọi AI
    gate.set()
    assert await task == "CANCELLED"
    row = await _row(clean_db, job)
    assert row["status"] == "CANCELLED" and row["status_reason_code"] == "JOB_CANCELLED"
    assert await _count(clean_db, "SELECT COUNT(*) FROM ai_usage_logs WHERE job_id=:j", j=job) == 0
    assert (
        await _count(clean_db, "SELECT COUNT(*) FROM budget_reservations WHERE job_id=:j AND status='RELEASED'", j=job)
        == 1
    )


async def test_TC_FR032_01_pause_after_current_step_then_resume_next_step(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    job = await _queued_job(clean_db)
    gate = asyncio.Event()
    agent = GatedAgent({2: gate})
    task = asyncio.create_task(_runtime(clean_db, migrated_db, agent).run(job))
    await agent.entered[2].wait()
    await _flag(clean_db, job, "pause_requested")
    gate.set()
    assert await task == "PAUSED"
    row = await _row(clean_db, job)
    assert row["status"] == "PAUSED" and row["last_completed_seq"] == 2  # bước hiện tại vẫn hoàn tất
    async with clean_db.begin() as conn:
        await conn.execute(text("UPDATE agent_jobs SET status='QUEUED', pause_requested=false WHERE id=:j"), {"j": job})
    assert await _runtime(clean_db, migrated_db, GatedAgent()).run(job) == "SUCCEEDED"
    async with clean_db.connect() as conn:
        seqs = [
            r[0]
            for r in (
                await conn.execute(text("SELECT seq FROM job_steps WHERE job_id=:j ORDER BY seq"), {"j": job})
            ).all()
        ]
    assert seqs == [1, 2, 3]


# --------------------------------------------------------------------------- T094 retry & checkpoint
async def test_TC_FR036_01_manual_retry_continues_from_checkpoint(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        r = await client.post(
            "/api/v1/jobs",
            json={"job_type": "system.diagnostic", "params": {"mock_scenario": "schema_invalid"}},
            headers=csrf_headers(client),
        )
        job_id = r.json()["id"]
        await run_worker_once(client)
        job = (await client.get(f"/api/v1/jobs/{job_id}")).json()
        assert (
            job["status"] == "FAILED"
            and job["status_reason_code"] == "AI_SCHEMA_INVALID"
            and job["last_completed_seq"] == 2
        )
        async with clean_db.begin() as conn:
            await conn.execute(text("UPDATE agent_jobs SET params='{}'::jsonb WHERE id=:j"), {"j": job_id})
        r = await client.post(f"/api/v1/jobs/{job_id}/retry", headers=csrf_headers(client))
        assert r.status_code == 202 and r.json()["status"] == "QUEUED"
        await run_worker_once(client)
        done = (await client.get(f"/api/v1/jobs/{job_id}")).json()
        assert done["status"] == "SUCCEEDED", done
        steps = (await client.get(f"/api/v1/jobs/{job_id}/steps")).json()
        assert [(s["seq"], s["attempt"]) for s in steps] == [(1, 1), (2, 1), (3, 2)]  # không chạy lại bước 1–2


async def test_TC_FR035_01_automatic_retry_for_transient_errors(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        # Gateway thử 3 lần/lời gọi; 3 lần đầu timeout → job tự retry (RETRY_SCHEDULED) → lần thứ 4 thành công.
        # Kịch bản đếm theo từng bước AI (bước 1 và bước 3) → 2 lần retry tự động → attempt = 3 (= max_attempts).
        r = await client.post(
            "/api/v1/jobs",
            json={"job_type": "system.diagnostic", "params": {"mock_scenario": "fail_n_then_success:timeout:3"}},
            headers=csrf_headers(client),
        )
        job_id = r.json()["id"]
        await run_worker_once(client)
        job = (await client.get(f"/api/v1/jobs/{job_id}")).json()
        assert job["status"] == "SUCCEEDED" and job["attempt"] == 3, job
    assert await _count(clean_db, "SELECT COUNT(*) FROM job_steps WHERE job_id=:j", j=job_id) == 3


async def test_TC_FR035_02_no_retry_when_cost_uncertain(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        job = await insert_job(clean_db)
        async with clean_db.begin() as conn:
            await conn.execute(
                text("UPDATE agent_jobs SET status='FAILED', status_reason_code='PROVIDER_TIMEOUT' WHERE id=:j"),
                {"j": job},
            )
            await conn.execute(
                text(
                    "INSERT INTO budget_reservations (job_id, data_origin, amount_usd, status, expires_at,"
                    " sent_at, uncertain_reason) VALUES (:j, 'MOCK', 0.1, 'UNCERTAIN', now(), now(), 'TIMEOUT_AFTER_SEND')"
                ),
                {"j": job},
            )
        r = await client.post(f"/api/v1/jobs/{job}/retry", headers=csrf_headers(client))
        assert r.status_code == 423 and r.json()["code"] == "UNCERTAIN_RESERVATIONS_UNRESOLVED"
        assert (await _row(clean_db, job))["status"] == "FAILED"


# --------------------------------------------------------------------------- T095 worker chết
async def _crash_mid_step(engine: AsyncEngine, url: str, job: uuid.UUID, *, at_step: int) -> None:
    gate = asyncio.Event()
    agent = GatedAgent({at_step: gate})
    task = asyncio.create_task(_runtime(engine, url, agent).run(job))
    await agent.entered[at_step].wait()
    task.cancel()  # mô phỏng tiến trình worker chết đột ngột
    with pytest.raises(asyncio.CancelledError):
        await task
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE agent_jobs SET heartbeat_at = now() - interval '10 minutes' WHERE id=:j"), {"j": job}
        )


async def test_TC_SC006_01_stalled_job_recovers_from_checkpoint(clean_db: AsyncEngine, migrated_db: str) -> None:
    job = await _queued_job(clean_db)
    await _crash_mid_step(clean_db, migrated_db, job, at_step=2)
    assert (await _row(clean_db, job))["status"] == "RUNNING"
    sm = async_sessionmaker(clean_db, expire_on_commit=False)
    requeued: list[uuid.UUID] = []

    async def requeue(job_id: uuid.UUID) -> None:
        requeued.append(job_id)

    result = await recover_stalled_jobs(sm, requeue, stalled_after_s=60)
    assert result == {"requeued": 1, "paused_uncertain": 0}
    assert requeued == [job] and (await _row(clean_db, job))["status"] == "RETRY_SCHEDULED"
    assert await _runtime(clean_db, migrated_db, GatedAgent()).run(job) == "SUCCEEDED"
    async with clean_db.connect() as conn:
        rows = (
            await conn.execute(text("SELECT seq, attempt FROM job_steps WHERE job_id=:j ORDER BY seq"), {"j": job})
        ).all()
    assert [tuple(r) for r in rows] == [(1, 1), (2, 2), (3, 1)]  # không có seq trùng


async def test_TC_SC006_02_stalled_job_with_uncertain_cost_is_not_rerun(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    job = await _queued_job(clean_db)
    await _crash_mid_step(clean_db, migrated_db, job, at_step=2)
    async with clean_db.begin() as conn:  # worker chết sau khi đã gửi lời gọi: reservation đã gửi, quá hạn
        await conn.execute(
            text(
                "INSERT INTO budget_reservations (job_id, data_origin, amount_usd, status, expires_at, sent_at)"
                " VALUES (:j, 'MOCK', 0.1, 'ACTIVE', now() - interval '1 minute', now() - interval '2 minutes')"
            ),
            {"j": job},
        )
    sm = async_sessionmaker(clean_db, expire_on_commit=False)
    from nichepilot.ai.budget import BudgetService

    await BudgetService(sm).sweep_stale()  # ACTIVE đã gửi + quá hạn → UNCERTAIN(WORKER_LOST)
    requeued: list[uuid.UUID] = []

    async def requeue(job_id: uuid.UUID) -> None:
        requeued.append(job_id)

    assert await recover_stalled_jobs(sm, requeue, stalled_after_s=60) == {"requeued": 0, "paused_uncertain": 1}
    row = await _row(clean_db, job)
    assert requeued == [] and row["status"] == "PAUSED_BUDGET"
    assert row["status_reason_code"] == "UNCERTAIN_RESERVATIONS_UNRESOLVED"


async def test_TC_SC006_03_stalled_procrastinate_lock_released(clean_db: AsyncEngine, migrated_db: str) -> None:
    from nichepilot.jobs.maintenance import release_stalled_queue_jobs
    from nichepilot.jobs.queue import build_procrastinate_app

    app = build_procrastinate_app(migrated_db)
    async with clean_db.begin() as conn:
        wid = (
            await conn.execute(
                text(
                    "INSERT INTO procrastinate_workers (last_heartbeat) VALUES (now() - interval '10 minutes') RETURNING id"
                )
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO procrastinate_jobs (queue_name, task_name, lock, args, status, worker_id)"
                " VALUES ('agent_jobs', 'run_agent_job', 'agent_job:x', '{}', 'doing', :w)"
            ),
            {"w": wid},
        )
    async with app.open_async():
        assert await release_stalled_queue_jobs(app, stalled_after_s=60) == 1
    async with clean_db.connect() as conn:
        assert (
            await conn.execute(text("SELECT status FROM procrastinate_jobs WHERE lock='agent_job:x'"))
        ).scalar() == "failed"


# --------------------------------------------------------------------------- T096 idempotency & concurrency
async def test_TC_FR037_03_single_executor_per_job(clean_db: AsyncEngine, migrated_db: str) -> None:
    job = await _queued_job(clean_db)
    rt1, rt2 = _runtime(clean_db, migrated_db, GatedAgent()), _runtime(clean_db, migrated_db, GatedAgent())
    results = await asyncio.gather(rt1.run(job), rt2.run(job))
    assert sorted(results, key=str) == sorted(["SUCCEEDED", None], key=str)
    assert await _count(clean_db, "SELECT COUNT(*) FROM job_steps WHERE job_id=:j", j=job) == 3


def test_TC_FR038_01_effective_concurrency() -> None:
    assert effective_concurrency(env_cap=1, configured=4) == 1
    assert effective_concurrency(env_cap=4, configured=2) == 2
    assert effective_concurrency(env_cap=2, configured=0) == 1


# --------------------------------------------------------------------------- T097 contract
async def test_TC_FR032_02_action_endpoints_and_invalid_transitions(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        h = csrf_headers(client)
        job = await insert_job(clean_db)  # RUNNING
        r = await client.post(f"/api/v1/jobs/{job}/pause", headers=h)
        assert r.status_code == 202 and (await _row(clean_db, job))["pause_requested"] is True
        r = await client.post(f"/api/v1/jobs/{job}/cancel", headers=h)
        assert r.status_code == 202 and (await _row(clean_db, job))["cancel_requested"] is True
        r = await client.post(f"/api/v1/jobs/{job}/retry", headers=h)
        assert r.status_code == 409 and r.json()["code"] == "INVALID_JOB_TRANSITION"

        queued = await _queued_job(clean_db)
        r = await client.post(f"/api/v1/jobs/{queued}/cancel", headers=h)
        assert r.status_code == 202 and r.json()["status"] == "CANCELLED"
        for action in ("pause", "resume", "cancel", "retry"):  # CANCELLED là trạng thái kết thúc
            r = await client.post(f"/api/v1/jobs/{queued}/{action}", headers=h)
            assert r.status_code == 409, action
        assert (await client.post(f"/api/v1/jobs/{uuid.uuid4()}/cancel", headers=h)).status_code == 404
        assert await _count(clean_db, "SELECT COUNT(*) FROM audit_logs WHERE action LIKE 'job.%'") >= 3
    await restore_budget_defaults(clean_db)
    _ = Decimal
