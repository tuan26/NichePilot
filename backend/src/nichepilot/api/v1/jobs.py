"""Router job & tool (T081 – FR-032, FR-037; contracts/openapi.yaml tag jobs, tools)."""

from __future__ import annotations

import json
import uuid
from decimal import Decimal
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, Request, Response, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import text

from nichepilot.ai.providers.mock import validate_scenario
from nichepilot.api.deps import MetaDep, SessionDep, SettingsDep, UserDep
from nichepilot.core.errors import AppError
from nichepilot.modules.audit.service import record_audit
from nichepilot.modules.settings.service import get_default_project, get_setting_values
from nichepilot.services import Services

router = APIRouter(tags=["jobs"])
JOB_STATUSES = Literal[
    "QUEUED", "RUNNING", "PAUSED", "PAUSED_BUDGET", "RETRY_SCHEDULED", "SUCCEEDED", "FAILED", "CANCELLED"
]


def services(request: Request) -> Services:
    svc: Services = request.app.state.services
    return svc


class CreateJobRequest(BaseModel):
    job_type: str
    params: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=200)
    budget_limit_usd: Decimal | None = Field(default=None, gt=0)


def money(v: Any) -> str:
    return str(Decimal(v).quantize(Decimal("0.000001"))) if v is not None else "0.000000"


def job_dict(row: Any) -> dict[str, Any]:
    r = dict(row)
    return {
        "id": str(r["id"]),
        "job_type": r["job_type"],
        "params": r["params"],
        "status": r["status"],
        "trigger": r["trigger"],
        "data_origin": r["data_origin"],
        "schedule_id": str(r["schedule_id"]) if r["schedule_id"] else None,
        "budget_limit_usd": money(r["budget_limit_usd"]),
        "cost_accumulated_usd": money(r["cost_accumulated_usd"]),
        "step_count": r["step_count"],
        "ai_call_count": r["ai_call_count"],
        "last_completed_seq": r["last_completed_seq"],
        "attempt": r["attempt"],
        "status_reason_code": r["status_reason_code"],
        "status_reason_detail": r["status_reason_detail"],
        "result": r["result"],
        "created_at": r["created_at"].isoformat(),
        "started_at": r["started_at"].isoformat() if r["started_at"] else None,
        "finished_at": r["finished_at"].isoformat() if r["finished_at"] else None,
    }


@router.get("/job-types")
async def job_types(request: Request, _user: UserDep) -> list[dict[str, Any]]:
    return [
        {
            "job_type": a.definition.job_type,
            "description": a.definition.description,
            "params_schema": a.definition.input_model.model_json_schema(),
            "paid": a.definition.paid,
        }
        for a in services(request).agents.values()
    ]


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
async def create_job(
    body: CreateJobRequest,
    request: Request,
    response: Response,
    user: UserDep,
    session: SessionDep,
    settings: SettingsDep,
    meta: MetaDep,
) -> dict[str, Any]:
    svc = services(request)
    agent = svc.agents.get(body.job_type)
    if agent is None:
        raise AppError("VALIDATION_ERROR", errors=[{"field": "job_type", "code": "unknown"}])
    try:
        params = agent.definition.input_model.model_validate(body.params).model_dump(exclude_none=True)
    except ValidationError as exc:
        errs = [{"field": "params." + ".".join(str(p) for p in e["loc"]), "code": e["type"]} for e in exc.errors()]
        raise AppError("VALIDATION_ERROR", errors=errs) from None
    origin = await svc.gateway.resolve_data_origin(agent.definition.task_type)  # MOCK_NOT_ALLOWED ở production
    if params.get("mock_scenario"):
        if origin != "MOCK" or settings.is_production:
            raise AppError("MOCK_NOT_ALLOWED")
        try:
            validate_scenario(params["mock_scenario"])
        except ValueError:
            raise AppError("VALIDATION_ERROR", errors=[{"field": "params.mock_scenario", "code": "invalid"}]) from None
    budget = await get_setting_values(session, ["budget.per_job_default_usd", "budget.daily_usd"])
    limit = body.budget_limit_usd or Decimal(str(budget["budget.per_job_default_usd"]))
    if limit > Decimal(str(budget["budget.daily_usd"])):
        raise AppError("VALIDATION_ERROR", errors=[{"field": "budget_limit_usd", "code": "exceeds_daily_budget"}])
    project = await get_default_project(session)
    key = body.idempotency_key or f"manual:{uuid.uuid4()}"
    d = agent.definition
    row = (
        (
            await session.execute(
                text(
                    "INSERT INTO agent_jobs (project_id, job_type, params, idempotency_key, status, trigger,"
                    " data_origin, budget_limit_usd, max_steps, max_ai_calls, timeout_s, max_attempts)"
                    " VALUES (:p, :t, CAST(:params AS jsonb), :k, 'QUEUED', 'MANUAL', :o, :b, :ms, :ma, :to, :att)"
                    " ON CONFLICT (idempotency_key) DO NOTHING RETURNING *"
                ),
                {
                    "p": project.id,
                    "t": d.job_type,
                    "params": json.dumps(params),
                    "k": key,
                    "o": origin,
                    "b": limit,
                    "ms": d.max_steps,
                    "ma": d.max_ai_calls,
                    "to": d.timeout_s,
                    "att": d.retry_max_attempts,
                },
            )
        )
        .mappings()
        .first()
    )
    if row is None:  # trùng idempotency_key → trả job hiện có
        existing = (
            (await session.execute(text("SELECT * FROM agent_jobs WHERE idempotency_key = :k"), {"k": key}))
            .mappings()
            .one()
        )
        response.status_code = status.HTTP_200_OK
        return job_dict(existing)
    await record_audit(
        session,
        action="job.created",
        actor_type="USER",
        actor_id=user.id,
        entity_type="agent_job",
        entity_id=row["id"],
        after={"job_type": d.job_type, "params": params, "data_origin": origin},
        request_id=meta.request_id,
    )
    await session.commit()  # commit TRƯỚC khi xếp hàng để worker luôn thấy job
    queue_id = await svc.job_queue.enqueue_run(row["id"])
    if queue_id is not None:
        await session.execute(
            text("UPDATE agent_jobs SET queue_job_id = :q WHERE id = :j"), {"q": queue_id, "j": row["id"]}
        )
    return job_dict(row)


@router.get("/jobs")
async def list_jobs(
    _user: UserDep,
    session: SessionDep,
    status_: Annotated[JOB_STATUSES | None, Query(alias="status")] = None,
    job_type: str | None = None,
    data_origin: Literal["REAL", "MOCK"] | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    where = (
        "WHERE (CAST(:s AS text) IS NULL OR status = :s) AND (CAST(:t AS text) IS NULL OR job_type = :t)"
        " AND (CAST(:o AS text) IS NULL OR data_origin = :o)"
    )
    params = {"s": status_, "t": job_type, "o": data_origin}
    total = (await session.execute(text(f"SELECT COUNT(*) FROM agent_jobs {where}"), params)).scalar_one()  # noqa: S608
    rows = (
        (
            await session.execute(
                text(f"SELECT * FROM agent_jobs {where} ORDER BY created_at DESC LIMIT :l OFFSET :off"),  # noqa: S608
                {**params, "l": page_size, "off": (page - 1) * page_size},
            )
        )
        .mappings()
        .all()
    )
    return {"page": page, "page_size": page_size, "total": total, "items": [job_dict(r) for r in rows]}


async def _get_job(session: Any, job_id: uuid.UUID) -> Any:
    row = (await session.execute(text("SELECT * FROM agent_jobs WHERE id = :j"), {"j": job_id})).mappings().first()
    if row is None:
        raise AppError("NOT_FOUND")
    return row


@router.get("/jobs/{job_id}")
async def get_job(job_id: uuid.UUID, _user: UserDep, session: SessionDep) -> dict[str, Any]:
    return job_dict(await _get_job(session, job_id))


@router.get("/jobs/{job_id}/steps")
async def job_steps(job_id: uuid.UUID, _user: UserDep, session: SessionDep) -> list[dict[str, Any]]:
    await _get_job(session, job_id)
    steps = (
        (await session.execute(text("SELECT * FROM job_steps WHERE job_id = :j ORDER BY seq"), {"j": job_id}))
        .mappings()
        .all()
    )
    tools = (
        (
            await session.execute(
                text("SELECT * FROM tool_executions WHERE job_id = :j ORDER BY created_at"), {"j": job_id}
            )
        )
        .mappings()
        .all()
    )
    usage = (
        (
            await session.execute(
                text("SELECT * FROM ai_usage_logs WHERE job_id = :j ORDER BY created_at"), {"j": job_id}
            )
        )
        .mappings()
        .all()
    )
    out = []
    for s in steps:
        out.append(
            {
                "id": str(s["id"]),
                "seq": s["seq"],
                "step_type": s["step_type"],
                "name": s["name"],
                "status": s["status"],
                "attempt": s["attempt"],
                "data_origin": s["data_origin"],
                "output": s["output"],
                "error_code": s["error_code"],
                "error_message": s["error_message"],
                "cost_usd": money(s["cost_usd"]),
                "started_at": s["started_at"].isoformat() if s["started_at"] else None,
                "finished_at": s["finished_at"].isoformat() if s["finished_at"] else None,
                "tool_executions": [
                    {
                        "tool_name": t["tool_name"],
                        "status": t["status"],
                        "denial_reason": t["denial_reason"],
                        "duration_ms": t["duration_ms"],
                    }
                    for t in tools
                    if t["step_id"] == s["id"]
                ],
                "ai_usage": [usage_dict(u) for u in usage if u["step_id"] == s["id"]],
            }
        )
    return out


def usage_dict(u: Any) -> dict[str, Any]:
    return {
        "id": str(u["id"]),
        "job_id": str(u["job_id"]) if u["job_id"] else None,
        "provider": u["provider"],
        "model": u["model"],
        "task_type": u["task_type"],
        "outcome": u["outcome"],
        "data_origin": u["data_origin"],
        "is_fallback": u["is_fallback"],
        "billing_status": u["billing_status"],
        "refusal_category": u["refusal_category"],
        "refusal_explanation": u["refusal_explanation"],
        "input_tokens": u["input_tokens"],
        "output_tokens": u["output_tokens"],
        "cache_read_tokens": u["cache_read_tokens"],
        "cache_write_tokens": u["cache_write_tokens"],
        "cost_usd": money(u["cost_usd"]),
        "latency_ms": u["latency_ms"] or 0,
        "created_at": u["created_at"].isoformat(),
    }


@router.get("/tools", tags=["tools"])
async def list_tools(request: Request, _user: UserDep) -> list[dict[str, Any]]:
    return services(request).tools.list_info()


@router.get("/costs/usage", tags=["costs"])
async def cost_usage(
    _user: UserDep,
    session: SessionDep,
    job_id: uuid.UUID | None = None,
    outcome: str | None = None,
    data_origin: Literal["REAL", "MOCK"] = "REAL",  # FR-018g: mặc định chỉ chi phí thật
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    where = (
        "WHERE data_origin = :o AND (CAST(:j AS uuid) IS NULL OR job_id = :j)"
        " AND (CAST(:oc AS text) IS NULL OR outcome = :oc)"
    )
    params = {"o": data_origin, "j": job_id, "oc": outcome}
    total = (await session.execute(text(f"SELECT COUNT(*) FROM ai_usage_logs {where}"), params)).scalar_one()  # noqa: S608
    rows = (
        (
            await session.execute(
                text(f"SELECT * FROM ai_usage_logs {where} ORDER BY created_at DESC LIMIT :l OFFSET :off"),  # noqa: S608
                {**params, "l": page_size, "off": (page - 1) * page_size},
            )
        )
        .mappings()
        .all()
    )
    return {"page": page, "page_size": page_size, "total": total, "items": [usage_dict(u) for u in rows]}


@router.post("/jobs/{job_id}/resume", status_code=status.HTTP_202_ACCEPTED)
async def resume_job(
    job_id: uuid.UUID, request: Request, user: UserDep, session: SessionDep, meta: MetaDep
) -> dict[str, Any]:
    """Tiếp tục job PAUSED / PAUSED_BUDGET từ checkpoint (FR-045, FR-049). Không bao giờ tự resume."""
    svc = services(request)
    job = await _get_job(session, job_id)
    if job["status"] not in ("PAUSED", "PAUSED_BUDGET"):
        raise AppError("INVALID_JOB_TRANSITION", params={"from": job["status"], "action": "resume"})
    if job["status"] == "PAUSED_BUDGET":
        check = await svc.gateway.budget.can_resume(job_id)
        if check != "OK":
            raise AppError(check)
    row = (
        (
            await session.execute(
                text(
                    "UPDATE agent_jobs SET status = 'QUEUED', pause_requested = false, status_reason_code = NULL,"
                    " status_reason_detail = NULL, updated_at = now() WHERE id = :j AND status = :st RETURNING *"
                ),
                {"j": job_id, "st": job["status"]},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise AppError("INVALID_JOB_TRANSITION", params={"action": "resume"})
    await record_audit(
        session,
        action="job.resumed",
        actor_type="USER",
        actor_id=user.id,
        entity_type="agent_job",
        entity_id=job_id,
        before={"status": job["status"]},
        after={"status": "QUEUED"},
        request_id=meta.request_id,
    )
    await session.commit()
    await svc.job_queue.enqueue_run(job_id)
    return job_dict(row)
