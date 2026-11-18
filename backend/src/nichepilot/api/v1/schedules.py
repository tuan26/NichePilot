"""Router lịch chạy job (T107 – FR-033, FR-034, FR-051; contracts/openapi.yaml tag schedules)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from nichepilot.api.deps import MetaDep, SessionDep, UserDep
from nichepilot.api.v1.jobs import money, services
from nichepilot.core.errors import AppError
from nichepilot.jobs.scheduler import budget_configured, next_after, validate_cron
from nichepilot.modules.audit.service import record_audit
from nichepilot.modules.settings.service import get_default_project, get_setting_values

router = APIRouter(tags=["schedules"])


class ScheduleInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    job_type: str
    params: dict[str, Any] = Field(default_factory=dict)
    cron_expr: str
    timezone: str | None = None
    enabled: bool
    misfire_policy: Literal["SKIP", "RUN_ONCE"] = "RUN_ONCE"
    budget_limit_usd: Decimal | None = Field(default=None, gt=0)


def schedule_dict(row: Any) -> dict[str, Any]:
    r = dict(row)
    return {
        "id": str(r["id"]),
        "name": r["name"],
        "job_type": r["job_type"],
        "params": r["params"],
        "cron_expr": r["cron_expr"],
        "timezone": r["timezone"],
        "enabled": r["enabled"],
        "misfire_policy": r["misfire_policy"],
        "budget_limit_usd": money(r["budget_limit_usd"]) if r["budget_limit_usd"] is not None else None,
        "last_run_at": r["last_run_at"].isoformat() if r["last_run_at"] else None,
        "next_run_at": r["next_run_at"].isoformat() if r["next_run_at"] else None,
    }


def _audit_view(values: dict[str, Any]) -> dict[str, Any]:
    keys = ("name", "job_type", "params", "cron_expr", "timezone", "enabled", "misfire_policy", "budget_limit_usd")
    return {k: (str(values[k]) if isinstance(values[k], Decimal) else values[k]) for k in keys}


async def _validated(body: ScheduleInput, request: Request, session: Any) -> dict[str, Any]:
    agent = services(request).agents.get(body.job_type)
    if agent is None:
        raise AppError("VALIDATION_ERROR", errors=[{"field": "job_type", "code": "unknown"}])
    try:
        params = agent.definition.input_model.model_validate(body.params).model_dump(exclude_none=True)
    except ValidationError as exc:
        errs = [{"field": "params." + ".".join(str(p) for p in e["loc"]), "code": e["type"]} for e in exc.errors()]
        raise AppError("VALIDATION_ERROR", errors=errs) from None
    if params.get("mock_scenario"):  # kịch bản mock không được lên lịch (chỉ dùng thủ công khi dev/test)
        raise AppError("VALIDATION_ERROR", errors=[{"field": "params.mock_scenario", "code": "not_allowed"}])
    tz = body.timezone or str((await get_setting_values(session, ["system.timezone"]))["system.timezone"])
    try:
        validate_cron(body.cron_expr, tz)
    except ValueError as exc:
        raise AppError("VALIDATION_ERROR", errors=[{"field": "cron_expr", "code": str(exc)}]) from None
    if body.enabled and agent.definition.paid and not await budget_configured(session):
        raise AppError("BUDGET_NOT_CONFIGURED")  # FR-034
    return {
        **body.model_dump(),
        "params": params,
        "timezone": tz,
        "next_run_at": next_after(body.cron_expr, tz, datetime.now(UTC)) if body.enabled else None,
    }


async def _get(session: Any, schedule_id: uuid.UUID) -> Any:
    row = (
        (await session.execute(text("SELECT * FROM job_schedules WHERE id = :s"), {"s": schedule_id}))
        .mappings()
        .first()
    )
    if row is None:
        raise AppError("NOT_FOUND")
    return row


async def _write(session: Any, sql: str, values: dict[str, Any]) -> Any:
    try:
        async with session.begin_nested():
            return (
                (await session.execute(text(sql), {**values, "params": json.dumps(values["params"])})).mappings().one()
            )
    except IntegrityError:
        raise AppError("SCHEDULE_NAME_EXISTS") from None


@router.get("/schedules")
async def list_schedules(_user: UserDep, session: SessionDep) -> list[dict[str, Any]]:
    rows = (await session.execute(text("SELECT * FROM job_schedules ORDER BY name"))).mappings().all()
    return [schedule_dict(r) for r in rows]


@router.get("/schedules/{schedule_id}")
async def get_schedule(schedule_id: uuid.UUID, _user: UserDep, session: SessionDep) -> dict[str, Any]:
    return schedule_dict(await _get(session, schedule_id))


@router.post("/schedules", status_code=status.HTTP_201_CREATED)
async def create_schedule(
    body: ScheduleInput, request: Request, user: UserDep, session: SessionDep, meta: MetaDep
) -> dict[str, Any]:
    values = await _validated(body, request, session)
    project = await get_default_project(session)
    row = await _write(
        session,
        "INSERT INTO job_schedules (project_id, name, job_type, params, cron_expr, timezone, enabled, misfire_policy,"
        " budget_limit_usd, next_run_at) VALUES (:p, :name, :job_type, CAST(:params AS jsonb), :cron_expr, :timezone,"
        " :enabled, :misfire_policy, :budget_limit_usd, :next_run_at) RETURNING *",
        {**values, "p": project.id},
    )
    await record_audit(
        session,
        action="schedule.created",
        actor_type="USER",
        actor_id=user.id,
        entity_type="job_schedule",
        entity_id=row["id"],
        after=_audit_view(values),
        request_id=meta.request_id,
    )
    return schedule_dict(row)


@router.patch("/schedules/{schedule_id}")
async def update_schedule(
    schedule_id: uuid.UUID, body: ScheduleInput, request: Request, user: UserDep, session: SessionDep, meta: MetaDep
) -> dict[str, Any]:
    before = await _get(session, schedule_id)
    values = await _validated(body, request, session)
    row = await _write(
        session,
        "UPDATE job_schedules SET name = :name, job_type = :job_type, params = CAST(:params AS jsonb),"
        " cron_expr = :cron_expr, timezone = :timezone, enabled = :enabled, misfire_policy = :misfire_policy,"
        " budget_limit_usd = :budget_limit_usd, next_run_at = :next_run_at, updated_at = now()"
        " WHERE id = :id RETURNING *",
        {**values, "id": schedule_id},
    )
    await record_audit(
        session,
        action="schedule.updated",
        actor_type="USER",
        actor_id=user.id,
        entity_type="job_schedule",
        entity_id=schedule_id,
        before=_audit_view(dict(before)),
        after=_audit_view(values),
        request_id=meta.request_id,
    )
    return schedule_dict(row)


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(schedule_id: uuid.UUID, user: UserDep, session: SessionDep, meta: MetaDep) -> Response:
    before = await _get(session, schedule_id)
    # Job đã tạo từ lịch được giữ lại (contract: "không xóa job đã tạo") – chỉ gỡ liên kết.
    await session.execute(text("UPDATE agent_jobs SET schedule_id = NULL WHERE schedule_id = :s"), {"s": schedule_id})
    await session.execute(text("DELETE FROM job_schedules WHERE id = :s"), {"s": schedule_id})
    await record_audit(
        session,
        action="schedule.deleted",
        actor_type="USER",
        actor_id=user.id,
        entity_type="job_schedule",
        entity_id=schedule_id,
        before=_audit_view(dict(before)),
        request_id=meta.request_id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
