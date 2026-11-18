"""Scheduler – tạo job theo lịch cron (T106 – FR-033, FR-034, FR-037, SC-007).

- Thời điểm đến hạn tính theo múi giờ của lịch (mặc định `Asia/Ho_Chi_Minh`), lưu `next_run_at` ở UTC.
- Tick chạy mỗi phút trong worker (periodic Procrastinate). Nhiều worker cùng tick vẫn chỉ tạo 1 job/thời điểm nhờ
  `SELECT … FOR UPDATE SKIP LOCKED` và `idempotency_key = schedule:{id}:{scheduled_for}` (UNIQUE).
- Lịch bị lỡ (hệ thống tắt): `RUN_ONCE` chạy bù tối đa 1 lần (thời điểm gần nhất), `SKIP` bỏ qua.
- Job tốn phí không được tạo khi ngân sách chưa cấu hình (> 0).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import croniter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nichepilot.core.logging import get_logger
from nichepilot.jobs.agents import build_agents
from nichepilot.jobs.runtime import Agent

ON_TIME_TOLERANCE = timedelta(seconds=90)  # trễ ≤ 90 giây coi là đúng giờ (tick mỗi phút)
MIN_INTERVAL = timedelta(minutes=5)
DEFAULT_TIMEZONE = "Asia/Ho_Chi_Minh"
MISFIRE_POLICIES = ("SKIP", "RUN_ONCE")
_SAMPLE_RUNS = 400

log = get_logger(__name__)


def _zone(tz: str) -> ZoneInfo:
    try:
        return ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"unknown timezone: {tz}") from None


def validate_cron(expr: str, tz: str) -> None:
    """Cron 5 trường hợp lệ, múi giờ IANA hợp lệ, khoảng cách giữa hai lần chạy ≥ 5 phút."""
    if len(expr.split()) != 5 or not croniter.is_valid(expr):
        raise ValueError("invalid cron expression (5 fields required)")
    zone = _zone(tz)
    it = croniter(expr, datetime(2026, 1, 1, tzinfo=zone))
    prev: datetime = it.get_next(datetime)
    for _ in range(_SAMPLE_RUNS):
        cur: datetime = it.get_next(datetime)
        if cur - prev < MIN_INTERVAL:
            raise ValueError("schedule interval must be at least 5 minutes")
        prev = cur


def next_after(expr: str, tz: str, after: datetime) -> datetime:
    """Lần chạy kế tiếp sau `after` (không bao gồm), trả về UTC."""
    nxt: datetime = croniter(expr, after.astimezone(_zone(tz))).get_next(datetime)
    return nxt.astimezone(UTC)


def _latest_at_or_before(expr: str, tz: str, now: datetime) -> datetime:
    prev: datetime = croniter(expr, (now + timedelta(seconds=1)).astimezone(_zone(tz))).get_prev(datetime)
    return prev.astimezone(UTC)


def due_runs(expr: str, tz: str, *, next_run_at: datetime, now: datetime, misfire_policy: str) -> list[datetime]:
    """Các thời điểm cần tạo job ở tick này (tối đa 1)."""
    if next_run_at > now:
        return []
    latest = _latest_at_or_before(expr, tz, now)
    if latest < next_run_at:
        return []
    if now - latest <= ON_TIME_TOLERANCE or misfire_policy == "RUN_ONCE":
        return [latest]
    return []  # SKIP: bỏ qua lần đã lỡ


async def _resolve_origin(session: AsyncSession, task_type: str, override: str | None) -> str | None:
    provider = (
        await session.execute(
            text("SELECT provider FROM model_task_profiles WHERE task_type = :t AND enabled"), {"t": task_type}
        )
    ).scalar_one_or_none()
    if provider is None:
        return None
    return "MOCK" if (override or provider) == "mock" else "REAL"


async def budget_configured(session: AsyncSession) -> bool:
    rows: dict[str, Any] = dict(
        (
            await session.execute(
                text("SELECT key, value FROM settings WHERE key IN ('budget.daily_usd', 'budget.monthly_usd')")
            )
        ).all()
    )
    return all(Decimal(str(rows.get(k, 0))) > 0 for k in ("budget.daily_usd", "budget.monthly_usd"))


async def _create_job(
    session: AsyncSession, sched: Any, agent: Agent, scheduled_for: datetime, origin: str
) -> uuid.UUID | None:
    defaults: dict[str, Any] = dict(
        (
            await session.execute(
                text("SELECT key, value FROM settings WHERE key IN ('budget.per_job_default_usd', 'budget.daily_usd')")
            )
        ).all()
    )
    limit = sched["budget_limit_usd"] or Decimal(str(defaults["budget.per_job_default_usd"]))
    limit = min(Decimal(str(limit)), Decimal(str(defaults["budget.daily_usd"])))
    d = agent.definition
    params = agent.definition.input_model.model_validate(sched["params"] or {}).model_dump(exclude_none=True)
    return (
        await session.execute(
            text(
                "INSERT INTO agent_jobs (project_id, job_type, params, idempotency_key, status, trigger, schedule_id,"
                " scheduled_for, data_origin, budget_limit_usd, max_steps, max_ai_calls, timeout_s, max_attempts)"
                " VALUES (:p, :t, CAST(:params AS jsonb), :k, 'QUEUED', 'SCHEDULE', :sid, :sf, :o, :b, :ms, :ma,"
                " :to, :att) ON CONFLICT (idempotency_key) DO NOTHING RETURNING id"
            ),
            {
                "p": sched["project_id"],
                "t": d.job_type,
                "params": json.dumps(params),
                "k": f"schedule:{sched['id']}:{scheduled_for.isoformat()}",
                "sid": sched["id"],
                "sf": scheduled_for,
                "o": origin,
                "b": limit,
                "ms": d.max_steps,
                "ma": d.max_ai_calls,
                "to": d.timeout_s,
                "att": d.retry_max_attempts,
            },
        )
    ).scalar_one_or_none()


async def scheduler_tick(
    sessionmaker: async_sessionmaker[AsyncSession],
    enqueue: Callable[[uuid.UUID], Awaitable[object]],
    *,
    now: datetime | None = None,
    override: str | None = None,
    agents: Mapping[str, Agent] | None = None,
) -> list[uuid.UUID]:
    """Một lượt quét lịch đến hạn; trả về id các job vừa tạo (đã commit trước khi xếp hàng)."""
    now = now or datetime.now(UTC)
    agents = agents if agents is not None else build_agents()
    created: list[uuid.UUID] = []
    async with sessionmaker() as s, s.begin():
        schedules = (
            (
                await s.execute(
                    text(
                        "SELECT * FROM job_schedules WHERE enabled AND next_run_at IS NOT NULL AND next_run_at <= :now"
                        " ORDER BY next_run_at FOR UPDATE SKIP LOCKED"
                    ),
                    {"now": now},
                )
            )
            .mappings()
            .all()
        )
        has_budget = await budget_configured(s) if schedules else True
        for sched in schedules:
            runs = due_runs(
                sched["cron_expr"],
                sched["timezone"],
                next_run_at=sched["next_run_at"],
                now=now,
                misfire_policy=sched["misfire_policy"],
            )
            agent = agents.get(sched["job_type"])
            last_created: datetime | None = None
            for scheduled_for in runs:
                if agent is None:
                    log.warning("scheduler.unknown_job_type", schedule_id=str(sched["id"]), job_type=sched["job_type"])
                    continue
                if agent.definition.paid and not has_budget:
                    log.warning("scheduler.budget_not_configured", schedule_id=str(sched["id"]))
                    continue
                origin = await _resolve_origin(s, agent.definition.task_type, override)
                if origin is None:
                    log.warning("scheduler.provider_not_configured", schedule_id=str(sched["id"]))
                    continue
                job_id = await _create_job(s, sched, agent, scheduled_for, origin)
                if job_id is not None:
                    created.append(job_id)
                    log.info(
                        "job.created",
                        job_id=str(job_id),
                        job_type=sched["job_type"],
                        trigger="SCHEDULE",
                        schedule_id=str(sched["id"]),
                        scheduled_for=scheduled_for.isoformat(),
                        data_origin=origin,
                    )
                last_created = scheduled_for  # job đã tồn tại (tick song song/khởi động lại) vẫn tính là đã chạy
            if not runs and sched["misfire_policy"] == "SKIP" and sched["next_run_at"] <= now:
                log.info("scheduler.misfire_skipped", schedule_id=str(sched["id"]))
            await s.execute(
                text(
                    "UPDATE job_schedules SET next_run_at = :n, last_run_at = COALESCE(:l, last_run_at),"
                    " updated_at = now() WHERE id = :id"
                ),
                {"n": next_after(sched["cron_expr"], sched["timezone"], now), "l": last_created, "id": sched["id"]},
            )
    for job_id in created:
        await enqueue(job_id)
    if created:
        log.info("scheduler.jobs_created", count=len(created))
    return created
