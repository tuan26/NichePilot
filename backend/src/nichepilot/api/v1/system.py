"""Router trạng thái hệ thống (T051 – FR-002, FR-054). Không bao giờ trả giá trị API key."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from nichepilot.api.deps import SessionDep, SettingsDep, UserDep
from nichepilot.api.v1.providers import ProviderStatus, provider_statuses
from nichepilot.core.logging import get_logger

router = APIRouter(prefix="/system", tags=["system"])
log = get_logger(__name__)
WORKER_FRESH_SECONDS = 60


class LogStorage(BaseModel):
    retention_days: int
    used_gb: float | None = None
    warn_gb: float | None = None
    warning: bool = False


class SystemStatus(BaseModel):
    version: str
    app_env: Literal["development", "test", "production"]
    database: Literal["OK", "UNAVAILABLE"]
    worker: Literal["OK", "STALE", "NOT_RUNNING"]
    schema_revision: str | None
    paid_calls_enabled: bool
    provider_override: str | None
    providers: list[ProviderStatus]
    log_storage: LogStorage | None = None


@router.get("/status", response_model=SystemStatus)
async def status(_user: UserDep, session: SessionDep, settings: SettingsDep) -> SystemStatus:
    database: Literal["OK", "UNAVAILABLE"] = "OK"
    worker: Literal["OK", "STALE", "NOT_RUNNING"] = "NOT_RUNNING"
    revision: str | None = None
    try:
        revision = (await session.execute(text("SELECT version_num FROM alembic_version"))).scalar_one_or_none()
        row = (
            await session.execute(
                text(
                    "SELECT COUNT(*) AS n, COALESCE(MAX(EXTRACT(EPOCH FROM (now() - last_heartbeat))), 1e9) AS age "
                    "FROM procrastinate_workers"
                )
            )
        ).one()
        if row.n:
            worker = "OK" if float(row.age) <= WORKER_FRESH_SECONDS else "STALE"
    except Exception as exc:  # DB không khả dụng → báo trạng thái, không ném lỗi chi tiết
        log.warning("status database check failed", error_type=type(exc).__name__)
        database = "UNAVAILABLE"

    providers = await provider_statuses(session, settings) if database == "OK" else []
    return SystemStatus(
        version=settings.app_version,
        app_env=settings.app_env,
        database=database,
        worker=worker,
        schema_revision=revision,
        paid_calls_enabled=settings.ai_paid_calls_enabled,
        provider_override=settings.ai_provider_override,
        providers=providers,
    )
