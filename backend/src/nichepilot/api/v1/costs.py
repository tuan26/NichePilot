"""Router ngân sách & tổng hợp chi phí (T091 – FR-042, FR-044, FR-047, FR-049, FR-018g).

Chi phí giả lập (MOCK) luôn tách khỏi chi phí thật; tổng hợp mặc định chỉ lấy REAL.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text

from nichepilot.ai.budget import BudgetService, LedgerStatus, ReservationStateError, period_windows
from nichepilot.api.deps import MetaDep, SessionDep, UserDep
from nichepilot.core.errors import AppError
from nichepilot.modules.audit.service import record_audit

router = APIRouter(tags=["costs"])
Q = Decimal("0.000001")


def _m(v: Decimal) -> str:
    return str(Decimal(v).quantize(Q))


def _budget(request: Request) -> BudgetService:
    svc: BudgetService = request.app.state.services.gateway.budget
    return svc


class BudgetLimitsIn(BaseModel):
    daily_usd: Decimal = Field(gt=0)
    monthly_usd: Decimal = Field(gt=0)
    per_job_default_usd: Decimal = Field(gt=0)
    warning_threshold: Decimal = Field(default=Decimal("0.8"), ge=Decimal("0.1"), le=Decimal("1.0"))
    max_uncertain_per_job: int = Field(default=3, ge=1)


class ResolveIn(BaseModel):
    actual_usd: Decimal = Field(ge=0)
    resolution_note: str = Field(min_length=5, max_length=1000)


def _ledger(s: LedgerStatus) -> dict[str, Any]:
    lim = s.limits

    def scope(prefix: str, usage: Any, uncertain: Decimal, limit: Decimal) -> dict[str, str]:
        return {
            f"spent_{prefix}_usd": _m(usage.spent),
            f"reserved_{prefix}_usd": _m(usage.held - uncertain),
            f"uncertain_{prefix}_usd": _m(uncertain),
            f"remaining_{prefix}_usd": _m(max(usage.remaining(limit), Decimal(0))),
        }

    warnings = []
    for name, usage, limit in (("DAILY", s.day, lim.daily), ("MONTHLY", s.month, lim.monthly)):
        used = usage.spent + usage.held
        if usage.remaining(limit) <= 0:
            warnings.append(f"{name}_EXHAUSTED")
        elif used >= limit * lim.warning_threshold:
            warnings.append(f"{name}_80")
    if s.uncertain_count:
        warnings.append("UNCERTAIN_RESERVATIONS")
    return {
        **scope("today", s.day, s.uncertain_day_usd, lim.daily),
        **scope("month", s.month, s.uncertain_month_usd, lim.monthly),
        "uncertain_count": s.uncertain_count,
        "warnings": warnings,
    }


async def _status(budget: BudgetService) -> dict[str, Any]:
    real, mock = await budget.status("REAL"), await budget.status("MOCK")
    lim = real.limits
    return {
        "limits": {
            "daily_usd": _m(lim.daily),
            "monthly_usd": _m(lim.monthly),
            "per_job_default_usd": _m(lim.per_job_default),
            "warning_threshold": float(lim.warning_threshold),
            "max_uncertain_per_job": lim.max_uncertain_per_job,
        },
        "timezone": lim.timezone,
        "real": _ledger(real),
        "mock": _ledger(mock),
    }


@router.get("/budget")
async def get_budget(request: Request, _user: UserDep) -> dict[str, Any]:
    return await _status(_budget(request))


@router.put("/budget")
async def put_budget(
    body: BudgetLimitsIn, request: Request, user: UserDep, session: SessionDep, meta: MetaDep
) -> dict[str, Any]:
    if not (body.per_job_default_usd <= body.daily_usd <= body.monthly_usd):
        raise AppError(
            "VALIDATION_ERROR", errors=[{"field": "per_job_default_usd", "code": "per_job_le_daily_le_monthly"}]
        )
    new = {
        "budget.daily_usd": str(body.daily_usd),
        "budget.monthly_usd": str(body.monthly_usd),
        "budget.per_job_default_usd": str(body.per_job_default_usd),
        "budget.warning_threshold": float(body.warning_threshold),
        "budget.max_uncertain_per_job": body.max_uncertain_per_job,
    }
    before: dict[str, Any] = dict(
        (await session.execute(text("SELECT key, value FROM settings WHERE key = ANY(:k)"), {"k": list(new)})).all()
    )
    for key, value in new.items():
        await session.execute(
            text(
                "UPDATE settings SET value = CAST(:v AS jsonb), version = version + 1, updated_by = :u,"
                " updated_at = now()"
                " WHERE key = :k"
            ),
            {"k": key, "v": json.dumps(value), "u": user.id},
        )
    await record_audit(
        session,
        action="budget.limits_updated",
        actor_type="USER",
        actor_id=user.id,
        entity_type="settings",
        before=before,
        after=new,
        request_id=meta.request_id,
    )
    await session.commit()
    return await _status(_budget(request))


def _reservation(r: Any) -> dict[str, Any]:
    return {
        "id": str(r["id"]),
        "job_id": str(r["job_id"]),
        "step_id": str(r["step_id"]) if r["step_id"] else None,
        "data_origin": r["data_origin"],
        "amount_usd": _m(r["amount_usd"]),
        "actual_usd": _m(r["actual_usd"]) if r["actual_usd"] is not None else None,
        "status": r["status"],
        "sent_at": r["sent_at"].isoformat() if r["sent_at"] else None,
        "release_reason": r["release_reason"],
        "uncertain_reason": r["uncertain_reason"],
        "resolution_note": r["resolution_note"],
        "resolved_at": r["resolved_at"].isoformat() if r["resolved_at"] else None,
        "created_at": r["created_at"].isoformat(),
    }


@router.get("/budget/reservations")
async def list_reservations(
    _user: UserDep,
    session: SessionDep,
    status: Literal["ACTIVE", "SETTLED", "RELEASED", "UNCERTAIN", "RESOLVED"] | None = None,
    data_origin: Literal["REAL", "MOCK"] | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    where = "WHERE (CAST(:s AS text) IS NULL OR status = :s) AND (CAST(:o AS text) IS NULL OR data_origin = :o)"
    params = {"s": status, "o": data_origin}
    total = (await session.execute(text(f"SELECT COUNT(*) FROM budget_reservations {where}"), params)).scalar_one()  # noqa: S608
    rows = (
        (
            await session.execute(
                text(f"SELECT * FROM budget_reservations {where} ORDER BY created_at DESC LIMIT :l OFFSET :off"),  # noqa: S608
                {**params, "l": page_size, "off": (page - 1) * page_size},
            )
        )
        .mappings()
        .all()
    )
    return {"page": page, "page_size": page_size, "total": total, "items": [_reservation(r) for r in rows]}


@router.post("/budget/reservations/{reservation_id}/resolve")
async def resolve_reservation(
    reservation_id: uuid.UUID, body: ResolveIn, request: Request, user: UserDep, session: SessionDep, meta: MetaDep
) -> dict[str, Any]:
    try:
        await _budget(request).resolve(reservation_id, body.actual_usd, body.resolution_note, user.id, meta.request_id)
    except ReservationStateError:
        raise AppError("RESERVATION_NOT_UNCERTAIN") from None
    row = (
        (await session.execute(text("SELECT * FROM budget_reservations WHERE id = :i"), {"i": reservation_id}))
        .mappings()
        .one()
    )
    return _reservation(row)


@router.get("/costs/summary")
async def cost_summary(
    request: Request,
    _user: UserDep,
    session: SessionDep,
    period: Literal["day", "month"],
    on: Annotated[date | None, Query(alias="date")] = None,
    data_origin: Literal["REAL", "MOCK"] = "REAL",
) -> dict[str, Any]:
    tz = (await _budget(request).status(data_origin)).limits.timezone
    ref = datetime.now(UTC) if on is None else datetime(on.year, on.month, on.day, 12, tzinfo=ZoneInfo(tz))
    w = period_windows(ref, tz)
    start, end = (w.day_start, w.day_end) if period == "day" else (w.month_start, w.month_end)
    base = (
        "FROM ai_usage_logs u WHERE u.data_origin = :o AND u.billing_status = 'BILLED'"
        " AND u.created_at >= :s AND u.created_at < :e"
    )
    p = {"o": data_origin, "s": start, "e": end}
    total = (await session.execute(text(f"SELECT COALESCE(SUM(cost_usd),0), COUNT(*) {base}"), p)).one()
    by_model = (
        await session.execute(
            text(
                "SELECT provider, model, SUM(cost_usd) c, SUM(input_tokens) i, SUM(output_tokens) o "
                f"{base} GROUP BY 1, 2 ORDER BY 3 DESC"
            ),
            p,
        )
    ).all()
    by_job_type = (
        await session.execute(
            text(
                f"SELECT j.job_type, SUM(u.cost_usd) c, COUNT(DISTINCT j.id) n {base.replace('FROM ai_usage_logs u', 'FROM ai_usage_logs u JOIN agent_jobs j ON j.id = u.job_id')} GROUP BY 1"  # noqa: E501
            ),
            p,
        )
    ).all()
    by_day = (
        await session.execute(
            text(f"SELECT (u.created_at AT TIME ZONE :tz)::date d, SUM(u.cost_usd) c {base} GROUP BY 1 ORDER BY 1"),
            {**p, "tz": tz},
        )
    ).all()
    return {
        "period": period,
        "from": start.isoformat(),
        "to": end.isoformat(),
        "data_origin": data_origin,
        "total_usd": _m(total[0]),
        "call_count": total[1],
        "by_model": [
            {
                "provider": r[0],
                "model": r[1],
                "cost_usd": _m(r[2]),
                "input_tokens": int(r[3]),
                "output_tokens": int(r[4]),
            }
            for r in by_model
        ],
        "by_job_type": [{"job_type": r[0], "cost_usd": _m(r[1]), "job_count": r[2]} for r in by_job_type],
        "by_day": [{"date": r[0].isoformat(), "cost_usd": _m(r[1])} for r in by_day],
    }
