"""T066 – Job Runtime: giới hạn bước/lời gọi/token/timeout, acceptance, ghi job_steps (FR-021, FR-024, FR-025, FR-031).

Agent trong file này là TEST DOUBLE; provider là MockAIProvider (dữ liệu MOCK).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from nichepilot.ai.gateway import AIGateway
from nichepilot.ai.providers.base import LLMMessage
from nichepilot.ai.providers.mock import MockAIProvider
from nichepilot.jobs.runtime import AgentDefinition, JobContext, JobRuntime, StepOutcome
from nichepilot.tools.registry import ToolRegistry
from tests.api_helpers import make_settings
from tests.integration.budget_helpers import insert_job

pytestmark = [pytest.mark.integration, pytest.mark.mock]


class NoInput(BaseModel):
    mock_scenario: str | None = None


def _definition(**kw: Any) -> AgentDefinition:
    base: dict[str, Any] = {
        "job_type": "system.diagnostic",
        "description": "test",
        "task_type": "system.diagnostic",
        "input_model": NoInput,
        "output_model": NoInput,
        "allowed_tools": [],
        "max_steps": 3,
        "max_ai_calls": 2,
        "timeout_s": 30,
        "token_budget": 1_000_000,
        "paid": True,
        "acceptance": lambda result: [],
    }
    base.update(kw)
    return AgentDefinition(**base)


class LoopAgent:
    def __init__(
        self,
        definition: AgentDefinition,
        *,
        ai: bool = False,
        sleep: float = 0,
        done_at: int | None = None,
        result: dict[str, Any] | None = None,
    ) -> None:
        self.definition = definition
        self.ai, self.sleep, self.done_at, self.result = ai, sleep, done_at, result

    async def run_step(self, seq: int, state: dict[str, Any], ctx: JobContext) -> StepOutcome:
        if self.sleep:
            await asyncio.sleep(self.sleep)
        if self.ai:
            await ctx.call_ai(system="s", messages=[LLMMessage(role="user", content="x")])
        done = self.done_at is not None and seq >= self.done_at
        return StepOutcome(
            name=f"step{seq}",
            step_type="AI_CALL" if self.ai else "LOGIC",
            output={"seq": seq},
            state={**state, "last": seq},
            done=done,
            result=self.result if done else None,
        )


def _runtime(engine: AsyncEngine, url: str, agent: LoopAgent) -> JobRuntime:
    sm = async_sessionmaker(engine, expire_on_commit=False)
    settings = make_settings(url)
    gw = AIGateway(settings, sm, {"mock": MockAIProvider()}, backoff_base_s=0)
    return JobRuntime(sm, gw, ToolRegistry(), {agent.definition.job_type: agent}, settings)


async def _job(engine: AsyncEngine) -> Any:
    job = await insert_job(engine)
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE agent_jobs SET status='QUEUED', max_steps=3, max_ai_calls=2, timeout_s=30 WHERE id=:j"),
            {"j": job},
        )
    return job


async def _status(engine: AsyncEngine, job: Any) -> tuple[Any, ...]:
    async with engine.connect() as conn:
        return tuple(
            (
                await conn.execute(
                    text(
                        "SELECT status, status_reason_code, last_completed_seq, step_count FROM agent_jobs WHERE id=:j"
                    ),
                    {"j": job},
                )
            ).one()
        )


async def test_TC_FR024_01_max_steps(clean_db: AsyncEngine, migrated_db: str) -> None:
    job = await _job(clean_db)
    await _runtime(clean_db, migrated_db, LoopAgent(_definition())).run(job)
    assert await _status(clean_db, job) == ("FAILED", "MAX_STEPS_EXCEEDED", 3, 3)


async def test_TC_FR024_02_max_ai_calls(clean_db: AsyncEngine, migrated_db: str) -> None:
    job = await _job(clean_db)
    await _runtime(clean_db, migrated_db, LoopAgent(_definition(), ai=True)).run(job)
    status = await _status(clean_db, job)
    assert status[:2] == ("FAILED", "MAX_AI_CALLS_EXCEEDED")
    async with clean_db.connect() as conn:
        assert (
            await conn.execute(text("SELECT COUNT(*) FROM ai_usage_logs WHERE job_id=:j"), {"j": job})
        ).scalar() == 2


async def test_TC_FR024_03_job_timeout(clean_db: AsyncEngine, migrated_db: str) -> None:
    job = await _job(clean_db)
    async with clean_db.begin() as conn:
        await conn.execute(text("UPDATE agent_jobs SET timeout_s=1 WHERE id=:j"), {"j": job})
    await _runtime(clean_db, migrated_db, LoopAgent(_definition(), sleep=2)).run(job)
    assert (await _status(clean_db, job))[:2] == ("FAILED", "JOB_TIMEOUT")


async def test_TC_FR021_01_acceptance_checked_and_steps_recorded(clean_db: AsyncEngine, migrated_db: str) -> None:
    job = await _job(clean_db)
    bad = _definition(acceptance=lambda r: [] if r.get("ok") else ["ok must be true"])
    await _runtime(clean_db, migrated_db, LoopAgent(bad, done_at=2, result={"ok": False})).run(job)
    assert (await _status(clean_db, job))[:2] == ("FAILED", "VALIDATION_ERROR")
    job2 = await _job(clean_db)
    await _runtime(clean_db, migrated_db, LoopAgent(bad, done_at=2, result={"ok": True})).run(job2)
    assert await _status(clean_db, job2) == ("SUCCEEDED", None, 2, 2)
    async with clean_db.connect() as conn:
        rows = (
            await conn.execute(
                text("SELECT seq, status, step_type, data_origin FROM job_steps WHERE job_id=:j ORDER BY seq"),
                {"j": job2},
            )
        ).all()
    assert [tuple(r) for r in rows] == [(1, "SUCCEEDED", "LOGIC", "MOCK"), (2, "SUCCEEDED", "LOGIC", "MOCK")]


async def test_TC_FR031_01_run_is_idempotent_for_finished_jobs(clean_db: AsyncEngine, migrated_db: str) -> None:
    job = await _job(clean_db)
    rt = _runtime(clean_db, migrated_db, LoopAgent(_definition(), done_at=1, result={}))
    await rt.run(job)
    await rt.run(job)  # chạy lại job đã xong: không làm gì, không tạo bước trùng
    async with clean_db.connect() as conn:
        assert (await conn.execute(text("SELECT COUNT(*) FROM job_steps WHERE job_id=:j"), {"j": job})).scalar() == 1
