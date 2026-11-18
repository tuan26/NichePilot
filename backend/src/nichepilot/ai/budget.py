"""Sổ ngân sách AI – giữ chỗ nguyên tử (T038 – FR-042, FR-043, FR-047, FR-049; data-model.md §11).

Công thức (theo `data_origin`, kỳ theo múi giờ cấu hình):
    spent = Σ ai_usage_logs.cost_usd (billing_status = BILLED) + Σ reservations.actual_usd (RESOLVED)
    held  = Σ reservations.amount_usd (status ∈ {ACTIVE, UNCERTAIN})
    remaining = limit − spent − held
Một reservation chỉ được tạo khi đủ cho CẢ BA giới hạn ngày/tháng/job và job chưa chạm giới hạn UNCERTAIN.
Mọi `reserve()` cùng sổ được tuần tự hóa bằng `pg_advisory_xact_lock` → không vượt giới hạn do race condition.
Không có đường nào tự động chuyển UNCERTAIN → RELEASED.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nichepilot.core.logging import get_logger

Origin = Literal["REAL", "MOCK"]
Scope = Literal["DAILY", "MONTHLY", "JOB"]
ZERO = Decimal("0")
log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Hàm thuần (unit-testable)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Windows:
    day_start: datetime
    day_end: datetime
    month_start: datetime
    month_end: datetime


def period_windows(now: datetime, tz: str) -> Windows:
    """Khung ngày/tháng hiện tại theo múi giờ cấu hình, trả về mốc UTC."""
    zone = ZoneInfo(tz)
    local = now.astimezone(zone)
    day_start = datetime(local.year, local.month, local.day, tzinfo=zone)
    next_day = (day_start + timedelta(days=1)).date()
    day_end = datetime(next_day.year, next_day.month, next_day.day, tzinfo=zone)
    month_start = datetime(local.year, local.month, 1, tzinfo=zone)
    ny, nm = (local.year + 1, 1) if local.month == 12 else (local.year, local.month + 1)
    month_end = datetime(ny, nm, 1, tzinfo=zone)
    return Windows(
        day_start.astimezone(UTC), day_end.astimezone(UTC), month_start.astimezone(UTC), month_end.astimezone(UTC)
    )


@dataclass(frozen=True)
class ScopeUsage:
    spent: Decimal
    held: Decimal

    def remaining(self, limit: Decimal) -> Decimal:
        return limit - self.spent - self.held


class BudgetExceededError(Exception):
    def __init__(self, scope: Scope, limit: Decimal, usage: ScopeUsage, requested: Decimal) -> None:
        super().__init__(f"BUDGET_{scope}_EXCEEDED")
        self.scope = scope
        self.limit = limit
        self.usage = usage
        self.requested = requested

    @property
    def code(self) -> str:
        return f"BUDGET_{self.scope}_EXCEEDED"

    def detail(self) -> dict[str, str]:
        return {
            "scope": self.scope,
            "limit_usd": str(self.limit),
            "spent_usd": str(self.usage.spent),
            "held_usd": str(self.usage.held),
            "remaining_usd": str(self.usage.remaining(self.limit)),
            "requested_usd": str(self.requested),
        }


class UncertainLimitReachedError(Exception):
    code = "UNCERTAIN_RESERVATION_LIMIT"

    def __init__(self, job_id: uuid.UUID | None, count: int, limit: int) -> None:
        super().__init__(self.code)
        self.job_id = job_id
        self.count = count
        self.limit = limit

    def detail(self) -> dict[str, Any]:
        return {"job_id": str(self.job_id), "uncertain_count": self.count, "limit": self.limit}


class ReservationStateError(Exception):
    """Chuyển trạng thái reservation không hợp lệ (ví dụ giải phóng reservation không còn ACTIVE)."""


def evaluate_reservation(
    *,
    amount: Decimal,
    daily_limit: Decimal,
    monthly_limit: Decimal,
    job_limit: Decimal,
    day: ScopeUsage,
    month: ScopeUsage,
    job: ScopeUsage,
    job_uncertain_count: int,
    max_uncertain_per_job: int,
    job_id: uuid.UUID | None = None,
) -> None:
    """Ném lỗi nếu không được phép giữ chỗ `amount`. Thứ tự: giới hạn UNCERTAIN → ngày → tháng → job."""
    if amount <= ZERO:
        raise ValueError("amount phải > 0")
    if job_uncertain_count >= max_uncertain_per_job:
        raise UncertainLimitReachedError(job_id, job_uncertain_count, max_uncertain_per_job)
    checks: list[tuple[Scope, Decimal, ScopeUsage]] = [
        ("DAILY", daily_limit, day),
        ("MONTHLY", monthly_limit, month),
        ("JOB", job_limit, job),
    ]
    for scope, limit, usage in checks:
        if amount > usage.remaining(limit):
            raise BudgetExceededError(scope, limit, usage, amount)


# ---------------------------------------------------------------------------
# Dịch vụ dùng PostgreSQL
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BudgetLimits:
    daily: Decimal
    monthly: Decimal
    per_job_default: Decimal
    warning_threshold: Decimal
    max_uncertain_per_job: int
    margin_s: int
    timezone: str


@dataclass(frozen=True)
class Reservation:
    id: uuid.UUID
    job_id: uuid.UUID
    amount_usd: Decimal
    data_origin: Origin
    expires_at: datetime


@dataclass(frozen=True)
class LedgerStatus:
    data_origin: Origin
    limits: BudgetLimits
    day: ScopeUsage
    month: ScopeUsage
    uncertain_count: int
    uncertain_day_usd: Decimal
    uncertain_month_usd: Decimal


_BUDGET_KEYS = (
    "budget.daily_usd",
    "budget.monthly_usd",
    "budget.per_job_default_usd",
    "budget.warning_threshold",
    "budget.max_uncertain_per_job",
    "budget.reservation_margin_s",
    "system.timezone",
)

_SPENT_SQL = text(
    """
    SELECT
      COALESCE((SELECT SUM(cost_usd) FROM ai_usage_logs
                WHERE data_origin = :o AND billing_status = 'BILLED'
                  AND created_at >= :s AND created_at < :e), 0)
    + COALESCE((SELECT SUM(actual_usd) FROM budget_reservations
                WHERE data_origin = :o AND status = 'RESOLVED'
                  AND created_at >= :s AND created_at < :e), 0) AS spent,
      COALESCE((SELECT SUM(amount_usd) FROM budget_reservations
                WHERE data_origin = :o AND status IN ('ACTIVE','UNCERTAIN')
                  AND created_at >= :s AND created_at < :e), 0) AS held,
      COALESCE((SELECT SUM(amount_usd) FROM budget_reservations
                WHERE data_origin = :o AND status = 'UNCERTAIN'
                  AND created_at >= :s AND created_at < :e), 0) AS uncertain
    """
)

_JOB_SQL = text(
    """
    SELECT
      COALESCE((SELECT SUM(cost_usd) FROM ai_usage_logs WHERE job_id = :j AND billing_status = 'BILLED'), 0)
    + COALESCE((SELECT SUM(actual_usd) FROM budget_reservations WHERE job_id = :j AND status = 'RESOLVED'), 0)
        AS spent,
      COALESCE((SELECT SUM(amount_usd) FROM budget_reservations
                WHERE job_id = :j AND status IN ('ACTIVE','UNCERTAIN')), 0) AS held,
      (SELECT COUNT(*) FROM budget_reservations WHERE job_id = :j AND status = 'UNCERTAIN') AS uncertain_count,
      (SELECT budget_limit_usd FROM agent_jobs WHERE id = :j) AS job_limit
    """
)


def _now() -> datetime:
    return datetime.now(UTC)


class BudgetService:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        clock: Callable[[], datetime] = _now,
    ) -> None:
        self._sessionmaker = sessionmaker
        self._clock = clock

    # -- đọc cấu hình -------------------------------------------------------
    @staticmethod
    async def load_limits(session: AsyncSession) -> BudgetLimits:
        rows = (
            await session.execute(
                text("SELECT key, value FROM settings WHERE key = ANY(:k)"), {"k": list(_BUDGET_KEYS)}
            )
        ).all()
        v = {k: val for k, val in rows}
        missing = [k for k in _BUDGET_KEYS if k not in v]
        if missing:
            raise RuntimeError(f"Thiếu cấu hình ngân sách: {missing}")
        return BudgetLimits(
            daily=Decimal(str(v["budget.daily_usd"])),
            monthly=Decimal(str(v["budget.monthly_usd"])),
            per_job_default=Decimal(str(v["budget.per_job_default_usd"])),
            warning_threshold=Decimal(str(v["budget.warning_threshold"])),
            max_uncertain_per_job=int(v["budget.max_uncertain_per_job"]),
            margin_s=int(v["budget.reservation_margin_s"]),
            timezone=str(v["system.timezone"]),
        )

    @staticmethod
    async def _scope(
        session: AsyncSession, origin: Origin, start: datetime, end: datetime
    ) -> tuple[ScopeUsage, Decimal]:
        row = (await session.execute(_SPENT_SQL, {"o": origin, "s": start, "e": end})).one()
        return ScopeUsage(Decimal(row.spent), Decimal(row.held)), Decimal(row.uncertain)

    # -- thao tác ------------------------------------------------------------
    async def reserve(
        self,
        job_id: uuid.UUID,
        amount: Decimal,
        origin: Origin,
        *,
        call_timeout_s: int,
        step_id: uuid.UUID | None = None,
    ) -> Reservation:
        async with self._sessionmaker() as session, session.begin():
            await session.execute(
                text("SELECT pg_advisory_xact_lock(hashtext('nichepilot.budget:' || :o))"), {"o": origin}
            )
            limits = await self.load_limits(session)
            now = self._clock()
            w = period_windows(now, limits.timezone)
            day, _ = await self._scope(session, origin, w.day_start, w.day_end)
            month, _ = await self._scope(session, origin, w.month_start, w.month_end)
            jrow = (await session.execute(_JOB_SQL, {"j": job_id})).one()
            if jrow.job_limit is None:
                raise ValueError(f"Không tìm thấy job {job_id}")
            evaluate_reservation(
                amount=amount,
                daily_limit=limits.daily,
                monthly_limit=limits.monthly,
                job_limit=Decimal(jrow.job_limit),
                day=day,
                month=month,
                job=ScopeUsage(Decimal(jrow.spent), Decimal(jrow.held)),
                job_uncertain_count=int(jrow.uncertain_count),
                max_uncertain_per_job=limits.max_uncertain_per_job,
                job_id=job_id,
            )
            rid = uuid.uuid4()
            expires_at = now + timedelta(seconds=call_timeout_s + limits.margin_s)
            await session.execute(
                text(
                    "INSERT INTO budget_reservations (id, job_id, step_id, data_origin, amount_usd, status, expires_at,"
                    " created_at, updated_at) VALUES (:id, :j, :st, :o, :a, 'ACTIVE', :x, :now, :now)"
                ),
                {"id": rid, "j": job_id, "st": step_id, "o": origin, "a": amount, "x": expires_at, "now": now},
            )
        log.info("budget.reserved", reservation_id=str(rid), job_id=str(job_id), amount_usd=str(amount), origin=origin)
        return Reservation(rid, job_id, amount, origin, expires_at)

    async def _transition(self, sql: str, params: dict[str, Any]) -> Any:
        async with self._sessionmaker() as session, session.begin():
            row = (await session.execute(text(sql), params)).first()
        if row is None:
            raise ReservationStateError(f"Reservation {params.get('id')} không ở trạng thái ACTIVE")
        return row

    async def mark_sent(self, reservation_id: uuid.UUID) -> None:
        """Ghi mốc đã gửi (commit riêng) ngay trước khi gửi yêu cầu tới provider."""
        await self._transition(
            "UPDATE budget_reservations SET sent_at = now(), updated_at = now() "
            "WHERE id = :id AND status = 'ACTIVE' AND sent_at IS NULL RETURNING id",
            {"id": reservation_id},
        )

    async def settle(self, reservation_id: uuid.UUID, usage_log_id: uuid.UUID, actual_usd: Decimal) -> Decimal:
        """Đối soát theo chi phí thực; trả về chênh lệch actual − amount (dương = vượt ước tính)."""
        row = await self._transition(
            "UPDATE budget_reservations SET status = 'SETTLED', usage_log_id = :u, actual_usd = :a, "
            "updated_at = now() WHERE id = :id AND status = 'ACTIVE' RETURNING amount_usd, job_id",
            {"id": reservation_id, "u": usage_log_id, "a": actual_usd},
        )
        diff = actual_usd - Decimal(row.amount_usd)
        if diff > ZERO:
            log.warning(
                "BUDGET_RESERVATION_OVERRUN",
                reservation_id=str(reservation_id),
                job_id=str(row.job_id),
                reserved_usd=str(row.amount_usd),
                actual_usd=str(actual_usd),
            )
        return diff

    async def release(self, reservation_id: uuid.UUID, reason: str) -> None:
        """Chỉ dùng khi CHẮC CHẮN chưa phát sinh phí."""
        await self._transition(
            "UPDATE budget_reservations SET status = 'RELEASED', release_reason = :r, updated_at = now() "
            "WHERE id = :id AND status = 'ACTIVE' RETURNING id",
            {"id": reservation_id, "r": reason},
        )

    async def mark_uncertain(self, reservation_id: uuid.UUID, reason: str) -> int:
        """Chi phí chưa xác định: giữ nguyên phần giữ chỗ. Trả về số UNCERTAIN hiện tại của job."""
        row = await self._transition(
            "UPDATE budget_reservations SET status = 'UNCERTAIN', uncertain_reason = :r, updated_at = now() "
            "WHERE id = :id AND status = 'ACTIVE' RETURNING job_id",
            {"id": reservation_id, "r": reason},
        )
        async with self._sessionmaker() as session:
            count = (
                await session.execute(
                    text("SELECT COUNT(*) FROM budget_reservations WHERE job_id = :j AND status = 'UNCERTAIN'"),
                    {"j": row.job_id},
                )
            ).scalar_one()
        log.warning("budget.uncertain", reservation_id=str(reservation_id), job_id=str(row.job_id), reason=reason)
        return int(count)

    async def status(self, origin: Origin) -> LedgerStatus:
        async with self._sessionmaker() as session:
            limits = await self.load_limits(session)
            w = period_windows(self._clock(), limits.timezone)
            day, unc_day = await self._scope(session, origin, w.day_start, w.day_end)
            month, unc_month = await self._scope(session, origin, w.month_start, w.month_end)
            count = (
                await session.execute(
                    text("SELECT COUNT(*) FROM budget_reservations WHERE data_origin = :o AND status = 'UNCERTAIN'"),
                    {"o": origin},
                )
            ).scalar_one()
        return LedgerStatus(origin, limits, day, month, int(count), unc_day, unc_month)

    # ------------------------------------------------------------------ US3: đối soát, tiếp tục, reservation treo
    async def resolve(
        self,
        reservation_id: uuid.UUID,
        actual_usd: Decimal,
        note: str,
        user_id: uuid.UUID,
        request_id: str | None = None,
    ) -> None:
        """Chủ sở hữu đối soát reservation UNCERTAIN bằng chi phí thực tế (FR-047) – ghi audit cùng transaction."""
        if actual_usd < ZERO:
            raise ValueError("actual_usd phải >= 0")
        from nichepilot.modules.audit.service import record_audit

        async with self._sessionmaker() as session, session.begin():
            row = (
                await session.execute(
                    text(
                        "UPDATE budget_reservations SET status = 'RESOLVED', actual_usd = :a, resolution_note = :n,"
                        " resolved_by = :u, resolved_at = now(), updated_at = now()"
                        " WHERE id = :id AND status = 'UNCERTAIN' RETURNING job_id, amount_usd, uncertain_reason"
                    ),
                    {"id": reservation_id, "a": actual_usd, "n": note, "u": user_id},
                )
            ).first()
            if row is None:
                raise ReservationStateError(f"Reservation {reservation_id} không ở trạng thái UNCERTAIN")
            await record_audit(
                session,
                action="budget.reservation_resolved",
                actor_type="USER",
                actor_id=user_id,
                entity_type="budget_reservation",
                entity_id=reservation_id,
                before={"status": "UNCERTAIN", "amount_usd": str(row.amount_usd), "reason": row.uncertain_reason},
                after={"status": "RESOLVED", "actual_usd": str(actual_usd), "note": note},
                request_id=request_id,
            )

    async def can_resume(self, job_id: uuid.UUID, next_call_estimate: Decimal = Decimal("0.000001")) -> str:
        """OK | UNCERTAIN_RESERVATIONS_UNRESOLVED | BUDGET_STILL_INSUFFICIENT (FR-045, FR-049)."""
        async with self._sessionmaker() as session:
            jrow = (
                await session.execute(
                    text("SELECT data_origin, status_reason_code, status_reason_detail FROM agent_jobs WHERE id = :j"),
                    {"j": job_id},
                )
            ).one()
            uncertain = (
                await session.execute(
                    text("SELECT COUNT(*) FROM budget_reservations WHERE job_id = :j AND status = 'UNCERTAIN'"),
                    {"j": job_id},
                )
            ).scalar_one()
        if jrow.status_reason_code == "UNCERTAIN_RESERVATION_LIMIT" and int(uncertain) > 0:
            return "UNCERTAIN_RESERVATIONS_UNRESOLVED"
        detail = jrow.status_reason_detail or {}
        if detail.get("requested_usd"):
            # Phải đủ ngân sách cho đúng lời gọi đã bị chặn, không chỉ một khoản tối thiểu.
            next_call_estimate = max(next_call_estimate, Decimal(str(detail["requested_usd"])))
        try:
            async with self._sessionmaker() as session:
                limits = await self.load_limits(session)
                w = period_windows(self._clock(), limits.timezone)
                day, _ = await self._scope(session, jrow.data_origin, w.day_start, w.day_end)
                month, _ = await self._scope(session, jrow.data_origin, w.month_start, w.month_end)
                j = (await session.execute(_JOB_SQL, {"j": job_id})).one()
            evaluate_reservation(
                amount=next_call_estimate,
                daily_limit=limits.daily,
                monthly_limit=limits.monthly,
                job_limit=Decimal(j.job_limit),
                day=day,
                month=month,
                job=ScopeUsage(Decimal(j.spent), Decimal(j.held)),
                job_uncertain_count=int(j.uncertain_count),
                max_uncertain_per_job=limits.max_uncertain_per_job,
                job_id=job_id,
            )
        except BudgetExceededError:
            return "BUDGET_STILL_INSUFFICIENT"
        except UncertainLimitReachedError:
            return "UNCERTAIN_RESERVATIONS_UNRESOLVED"
        return "OK"

    async def sweep_stale(self) -> dict[str, int]:
        """Reservation ACTIVE quá hạn (ví dụ worker chết): chưa gửi → RELEASED; đã gửi → UNCERTAIN(WORKER_LOST).
        Không bao giờ chạm vào reservation UNCERTAIN (FR-048)."""
        async with self._sessionmaker() as session, session.begin():
            released = (
                await session.execute(
                    text(
                        "UPDATE budget_reservations SET status = 'RELEASED', release_reason = 'NOT_SENT',"
                        " updated_at = now()"
                        " WHERE status = 'ACTIVE' AND expires_at < now() AND sent_at IS NULL RETURNING id"
                    )
                )
            ).all()
            uncertain = (
                await session.execute(
                    text(
                        "UPDATE budget_reservations SET status = 'UNCERTAIN', uncertain_reason = 'WORKER_LOST',"
                        " updated_at = now() WHERE status = 'ACTIVE' AND expires_at < now() AND sent_at IS NOT NULL"
                        " RETURNING id"
                    )
                )
            ).all()
        if released or uncertain:
            log.warning("budget.sweep_stale", released=len(released), uncertain=len(uncertain))
        return {"released": len(released), "uncertain": len(uncertain)}
