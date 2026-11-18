"""Hàng đợi job (T080 – R-01, FR-037): Procrastinate trên PostgreSQL sau interface `JobQueue`.

`agent_jobs` là nguồn sự thật về trạng thái nghiệp vụ; Procrastinate chỉ giữ "lượt thực thi".
`queueing_lock` + `lock` theo job_id: không xếp hàng trùng, không chạy song song cùng một job.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Protocol

import procrastinate

TASK_NAME = "run_agent_job"
JOB_QUEUE_NAME = "agent_jobs"


class JobQueue(Protocol):
    async def enqueue_run(self, job_id: uuid.UUID) -> int | None: ...


def conninfo_from_url(url: str) -> str:
    """`postgresql+psycopg://…` (SQLAlchemy) → `postgresql://…` (libpq)."""
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def build_procrastinate_app(
    db_url: str, runner: Callable[[uuid.UUID], Awaitable[object]] | None = None
) -> procrastinate.App:
    app = procrastinate.App(connector=procrastinate.PsycopgConnector(conninfo=conninfo_from_url(db_url)))

    @app.task(name=TASK_NAME, queue=JOB_QUEUE_NAME, pass_context=False)
    async def run_agent_job(job_id: str) -> None:
        if runner is None:
            raise RuntimeError("Worker chưa được cấu hình runner")
        await runner(uuid.UUID(job_id))

    return app


class ProcrastinateJobQueue:
    def __init__(self, app: procrastinate.App) -> None:
        self.app = app

    async def enqueue_run(self, job_id: uuid.UUID) -> int | None:
        lock = f"agent_job:{job_id}"
        task = self.app.tasks[TASK_NAME]
        try:
            return await task.configure(queueing_lock=lock, lock=lock).defer_async(job_id=str(job_id))
        except procrastinate.exceptions.AlreadyEnqueued:
            return None  # đã có lượt chờ chạy cho job này – không tạo trùng
