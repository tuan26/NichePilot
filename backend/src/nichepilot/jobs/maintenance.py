"""Tác vụ bảo trì định kỳ chạy trong worker (T089, T100 – FR-036, FR-048, SC-006).

Gồm: quét reservation treo, khôi phục job mất heartbeat, scheduler tick (US5). Retention log ứng dụng ở US7.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import procrastinate
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nichepilot.ai.budget import BudgetService
from nichepilot.core.logging import get_logger
from nichepilot.jobs.queue import TASK_NAME, JobQueue
from nichepilot.jobs.scheduler import scheduler_tick

MAINTENANCE_QUEUE = "maintenance"
MIN_LOG_RETENTION_DAYS = 90
LOG_FILE_RE = re.compile(r"^app-(\d{4}-\d{2}-\d{2})\.jsonl$")
GB = 1_000_000_000
log = get_logger(__name__)


@dataclass
class LogStorageReport:
    retention_days: int
    warn_gb: float
    used_bytes: int
    warning: bool
    deleted: list[str] = field(default_factory=list)

    @property
    def used_gb(self) -> float:
        return round(self.used_bytes / GB, 6)


LOG_POLICY_SQL = "SELECT key, value FROM settings WHERE key IN ('logging.retention_days', 'logging.disk_warn_gb')"


async def log_policy(session: AsyncSession) -> tuple[int, float]:
    rows: dict[str, object] = dict((await session.execute(text(LOG_POLICY_SQL))).tuples().all())
    # Phòng thủ: không bao giờ giữ ít hơn 90 ngày kể cả khi DB bị sửa tay (FR-057).
    retention = max(MIN_LOG_RETENTION_DAYS, int(str(rows.get("logging.retention_days", MIN_LOG_RETENTION_DAYS))))
    return retention, float(str(rows.get("logging.disk_warn_gb", 2)))


async def read_log_policy(sessionmaker: async_sessionmaker[AsyncSession]) -> tuple[int, float]:
    async with sessionmaker() as s:
        return await log_policy(s)


def measure_log_dir(log_dir: Path) -> int:
    if not log_dir.is_dir():
        return 0
    return sum(p.stat().st_size for p in log_dir.rglob("*") if p.is_file())


def _expired_files(log_dir: Path, retention_days: int, today: date) -> list[Path]:
    """Chỉ file log ứng dụng theo ngày (`app-YYYY-MM-DD.jsonl`) có ngày < hôm nay − retention mới bị xóa."""
    cutoff = today - timedelta(days=retention_days)
    expired: list[Path] = []
    if not log_dir.is_dir():
        return expired
    for p in log_dir.iterdir():
        m = LOG_FILE_RE.match(p.name)
        if not m or not p.is_file():
            continue
        try:
            file_date = date.fromisoformat(m.group(1))
        except ValueError:
            continue
        if file_date < cutoff:
            expired.append(p)
    return sorted(expired)


async def run_log_maintenance(
    sessionmaker: async_sessionmaker[AsyncSession], log_dir: Path, *, today: date | None = None
) -> LogStorageReport:
    """Xóa log quá hạn lưu; đo dung lượng; vượt ngưỡng chỉ CẢNH BÁO – không bao giờ xóa log chưa đủ hạn (FR-057).

    Không đụng tới audit log (nằm trong database).
    """
    retention, warn_gb = await read_log_policy(sessionmaker)
    today = today or datetime.now(UTC).date()
    deleted: list[str] = []
    for p in await asyncio.to_thread(_expired_files, log_dir, retention, today):
        await asyncio.to_thread(p.unlink, missing_ok=True)
        deleted.append(p.name)
    if deleted:
        log.info("logs.retention_deleted", count=len(deleted), files=deleted, retention_days=retention)
    used = await asyncio.to_thread(measure_log_dir, log_dir)
    warning = used > warn_gb * GB
    if warning:
        log.warning(
            "logs.disk_warning",
            used_gb=round(used / GB, 3),
            warn_gb=warn_gb,
            retention_days=retention,
            note="log chưa đủ hạn lưu không bị xóa vì dung lượng",
        )
    return LogStorageReport(retention, warn_gb, used, warning, deleted)


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
    provider_override: str | None = None,
    log_dir: Path | None = None,
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

    @app.periodic(cron="* * * * *", periodic_id="jobs_scheduler_tick")
    @app.task(name="jobs_scheduler_tick", queue=MAINTENANCE_QUEUE, pass_context=False)
    async def jobs_scheduler_tick(timestamp: int) -> None:
        # Periodic Procrastinate đảm bảo mỗi phút chỉ defer 1 lần; tick vẫn an toàn khi chạy song song (SKIP LOCKED +
        # idempotency_key) và tự chạy bù theo misfire_policy sau khi worker khởi động lại.
        await scheduler_tick(sessionmaker, queue.enqueue_run, override=provider_override)

    @app.periodic(cron="41 2 * * *", periodic_id="logs_retention")
    @app.task(name="logs_retention", queue=MAINTENANCE_QUEUE, pass_context=False)
    async def logs_retention(timestamp: int) -> None:
        if log_dir is not None:
            await run_log_maintenance(sessionmaker, log_dir)
