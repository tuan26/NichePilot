"""Tiện ích tạo dữ liệu kiểm thử cho sổ ngân sách. Chỉ dùng trong test; dữ liệu mang data_origin=MOCK."""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def insert_job(engine: AsyncEngine, *, budget_limit: str = "2.00", origin: str = "MOCK") -> uuid.UUID:
    async with engine.begin() as conn:
        project_id = (await conn.execute(text("SELECT id FROM projects WHERE is_default"))).scalar_one()
        job_id = uuid.uuid4()
        await conn.execute(
            text(
                """INSERT INTO agent_jobs (id, project_id, job_type, params, idempotency_key, status, trigger,
                       data_origin, budget_limit_usd, max_steps, max_ai_calls, timeout_s, max_attempts)
                   VALUES (:id, :p, 'system.diagnostic', '{}', :k, 'RUNNING', 'MANUAL', :o, :b, 20, 30, 1800, 3)"""
            ),
            {"id": job_id, "p": project_id, "k": f"test:{job_id}", "o": origin, "b": Decimal(budget_limit)},
        )
    return job_id


async def set_setting(engine: AsyncEngine, key: str, value_json: str) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE settings SET value = CAST(:v AS jsonb), version = version + 1 WHERE key = :k"),
            {"k": key, "v": value_json},
        )


async def insert_usage(engine: AsyncEngine, job_id: uuid.UUID, cost: str, origin: str = "MOCK") -> uuid.UUID:
    async with engine.begin() as conn:
        usage_id = uuid.uuid4()
        await conn.execute(
            text(
                """INSERT INTO ai_usage_logs (id, job_id, provider, model, task_type, data_origin, outcome,
                       billing_status, sent, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
                       cost_usd, latency_ms)
                   VALUES (:id, :j, 'mock', 'mock-model', 'system.diagnostic', :o, 'SUCCESS', 'BILLED', true,
                       10, 10, 0, 0, :c, 1)"""
            ),
            {"id": usage_id, "j": job_id, "o": origin, "c": Decimal(cost)},
        )
    return usage_id


DEFAULT_BUDGET = {
    "budget.daily_usd": '"3.00"',
    "budget.monthly_usd": '"30.00"',
    "budget.per_job_default_usd": '"2.00"',
    "budget.max_uncertain_per_job": "3",
}


async def restore_budget_defaults(engine: AsyncEngine) -> None:
    for k, v in DEFAULT_BUDGET.items():
        await set_setting(engine, k, v)
