"""Entrypoint tiến trình worker (T080): `python -m nichepilot.worker`.

Chạy Procrastinate worker xử lý lượt thực thi job; tác vụ bảo trì định kỳ (scheduler tick, quét reservation treo,
stalled job, retention log) được đăng ký ở các user story tương ứng.
"""

from __future__ import annotations

import asyncio

from nichepilot.core.config import detect_ignored_credentials, get_settings
from nichepilot.core.db import dispose_db, init_db
from nichepilot.core.logging import configure_logging, get_logger
from nichepilot.jobs.queue import JOB_QUEUE_NAME
from nichepilot.services import build_services

log = get_logger(__name__)


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
    log.info("worker started", app_env=settings.app_env, concurrency=settings.worker_concurrency)
    try:
        async with services.procrastinate_app.open_async():
            await services.procrastinate_app.run_worker_async(
                queues=[JOB_QUEUE_NAME], concurrency=settings.worker_concurrency, name="nichepilot-worker"
            )
    finally:
        await dispose_db()


if __name__ == "__main__":
    asyncio.run(main())
