"""Entrypoint tiến trình worker (T080): `python -m nichepilot.worker`.

Chạy Procrastinate worker xử lý lượt thực thi job; tác vụ bảo trì định kỳ (scheduler tick, quét reservation treo,
stalled job, retention log) được đăng ký ở các user story tương ứng.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from nichepilot.core.config import detect_ignored_credentials, get_settings
from nichepilot.core.db import dispose_db, init_db
from nichepilot.core.logging import configure_logging, get_logger
from nichepilot.jobs.maintenance import MAINTENANCE_QUEUE
from nichepilot.jobs.queue import JOB_QUEUE_NAME
from nichepilot.services import build_services

log = get_logger(__name__)


def effective_concurrency(*, env_cap: int, configured: int) -> int:
    """Số job đồng thời = min(WORKER_CONCURRENCY, setting worker.max_concurrent_jobs), tối thiểu 1 (FR-038)."""
    return max(1, min(env_cap, configured))


async def main() -> None:
    settings = get_settings()
    configure_logging(
        level=settings.log_level,
        fmt=settings.log_format,
        log_dir=settings.log_dir,
        secret_values=settings.secret_values(),
    )
    for name in detect_ignored_credentials():
        log.warning("ignored credential variable", variable=name)
    sessionmaker = init_db(settings.database_url.get_secret_value())
    services = build_services(settings, sessionmaker)
    async with sessionmaker() as session:
        configured = (
            await session.execute(text("SELECT value FROM settings WHERE key = 'worker.max_concurrent_jobs'"))
        ).scalar_one()
    concurrency = effective_concurrency(env_cap=settings.worker_concurrency, configured=int(configured))
    log.info("worker started", app_env=settings.app_env, concurrency=concurrency)
    try:
        async with services.procrastinate_app.open_async():
            await services.procrastinate_app.run_worker_async(
                queues=[JOB_QUEUE_NAME, MAINTENANCE_QUEUE],
                concurrency=concurrency,
                name="nichepilot-worker",
            )
    finally:
        await dispose_db()


if __name__ == "__main__":
    asyncio.run(main())
