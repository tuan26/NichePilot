"""Tác vụ bảo trì định kỳ chạy trong worker (T089, T100 – FR-036, FR-048, SC-006).

Retention log ứng dụng được thêm ở US7.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

import procrastinate
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nichepilot.ai.budget import BudgetService
from nichepilot.core.logging import get_logger
from nichepilot.jobs.queue import TASK_NAME, JobQueue

MAINTENANCE_QUEUE = "maintenance"
log = get_logger(__name__)


async def release_stalled_queue_jobs(app: procrastinate.App, *, stalled_after_s: int) -> int:
    """Lượt thực thi Procrastinate của worker đã chết vẫn giữ `lock` → đánh dấu failed để giải phóng lock."""
    stalled = list(await app.job_manager.get_stalled_jobs(task_name=TASK_NAME, seconds_since_heartbeat=stalled_after_s))
    for job in stalled:
        assert job.id is not None
        await app.job_manager.finish_job_by_id_async(job.id, status=procrastinate.jobs.Status.FAILED, delete_job=False)
    if stalled:
        log.warning("queue.stalled_released", count=len(stalled))
    return len(stalled)


async def recover_stalled_jobs(
    sessionmaker: async_sessionmaker[AsyncSession],
    requeue: Callable[[uuid.UUID], Awaitable[object]],
    *,
    stalled_after_s: int,
) -> dict[str, int]:
    """Job RUNNING mất heartbeat (worker chết) và không còn reservation ACTIVE:
    - còn reservation UNCERTAIN → PAUSED_BUDGET (UNCERTAIN_RESERVATIONS_UNRESOLVED): KHÔNG gọi lại API có phí;
    - ngược lại → RETRY_SCHEDULED và xếp hàng lại; runtime tiếp tục từ checkpoint.
    """
    async with sessionmaker() as s, s.begin():
        rows = (
            await s.execute(
                text(
                    "SELECT j.id, (SELECT COUNT(*) FROM budget_reservations r WHERE r.job_id = j.id"
                    " AND r.status = 'UNCERTAIN') AS uncertain FROM agent_jobs j"
                    " WHERE j.status = 'RUNNING' AND j.heartbeat_at < now() - make_interval(secs => :s)"
                    " AND NOT EXISTS (SELECT 1 FROM budget_reservations r"
                    " WHERE r.job_id = j.id AND r.status = 'ACTIVE')"
                    " FOR UPDATE OF j SKIP LOCKED"
                ),
                {"s": stalled_after_s},
            )
        ).all()
        requeue_ids: list[uuid.UUID] = []
        paused = 0
        for job_id, uncertain in rows:
            if uncertain:
                await s.execute(
                    text(
                        "UPDATE agent_jobs SET status = 'PAUSED_BUDGET',"
                        " status_reason_code = 'UNCERTAIN_RESERVATIONS_UNRESOLVED', updated_at = now() WHERE id = :j"
                    ),
                    {"j": job_id},
                )
                paused += 1
            else:
                await s.execute(
                    text(
                        "UPDATE agent_jobs SET status = 'RETRY_SCHEDULED', status_reason_code = 'WORKER_LOST',"
                        " updated_at = now() WHERE id = :j"
                    ),
                    {"j": job_id},
                )
                requeue_ids.append(job_id)
    for job_id in requeue_ids:
        await requeue(job_id)
    if rows:
        log.warning("jobs.stalled_recovered", requeued=len(requeue_ids), paused_uncertain=paused)
    return {"requeued": len(requeue_ids), "paused_uncertain": paused}


def register_maintenance(
    app: procrastinate.App,
    budget: BudgetService,
    sessionmaker: async_sessionmaker[AsyncSession],
    queue: JobQueue,
    stalled_after_s: int,
) -> None:
    @app.periodic(cron="* * * * *", periodic_id="budget_sweep_stale")
    @app.task(name="budget_sweep_stale", queue=MAINTENANCE_QUEUE, pass_context=False)
    async def budget_sweep_stale(timestamp: int) -> None:
        # ACTIVE quá hạn → RELEASED (chưa gửi) hoặc UNCERTAIN (đã gửi); không bao giờ tự giải phóng UNCERTAIN.
        await budget.sweep_stale()

    @app.periodic(cron="* * * * *", periodic_id="jobs_recover_stalled")
    @app.task(name="jobs_recover_stalled", queue=MAINTENANCE_QUEUE, pass_context=False)
    async def jobs_recover_stalled(timestamp: int) -> None:
        await release_stalled_queue_jobs(app, stalled_after_s=stalled_after_s)
        await budget.sweep_stale()
        await recover_stalled_jobs(sessionmaker, queue.enqueue_run, stalled_after_s=stalled_after_s)
