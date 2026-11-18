"""T020 – Công thức sổ ngân sách (FR-042, FR-043, FR-018, FR-049)."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from nichepilot.ai.budget import (
    BudgetExceededError,
    ScopeUsage,
    UncertainLimitReachedError,
    evaluate_reservation,
    period_windows,
)

D = Decimal


def test_TC_FR042_01_windows_follow_configured_timezone() -> None:
    # 2026-11-30 18:30 UTC = 2026-12-01 01:30 tại Asia/Ho_Chi_Minh (UTC+7) → đã sang ngày/tháng mới
    now = datetime(2026, 11, 30, 18, 30, tzinfo=UTC)
    w = period_windows(now, "Asia/Ho_Chi_Minh")
    assert w.day_start == datetime(2026, 11, 30, 17, 0, tzinfo=UTC)
    assert w.day_end == datetime(2026, 12, 1, 17, 0, tzinfo=UTC)
    assert w.month_start == datetime(2026, 11, 30, 17, 0, tzinfo=UTC)
    assert w.month_end == datetime(2026, 12, 31, 17, 0, tzinfo=UTC)


def test_TC_FR043_01_remaining_counts_spent_and_held() -> None:
    usage = ScopeUsage(spent=D("1.20"), held=D("0.50"))
    assert usage.remaining(D("3.00")) == D("1.30")


def _ok(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "amount": D("0.10"),
        "daily_limit": D("3.00"),
        "monthly_limit": D("30.00"),
        "job_limit": D("2.00"),
        "day": ScopeUsage(D("0"), D("0")),
        "month": ScopeUsage(D("0"), D("0")),
        "job": ScopeUsage(D("0"), D("0")),
        "job_uncertain_count": 0,
        "max_uncertain_per_job": 3,
    }
    base.update(overrides)
    return base


def test_TC_FR043_02_accepts_within_all_limits() -> None:
    evaluate_reservation(**_ok())  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("override", "scope"),
    [
        ({"day": ScopeUsage(D("2.95"), D("0"))}, "DAILY"),
        ({"month": ScopeUsage(D("29.00"), D("0.95"))}, "MONTHLY"),
        ({"job": ScopeUsage(D("1.50"), D("0.45"))}, "JOB"),
    ],
)
def test_TC_FR043_03_rejects_when_any_scope_insufficient(override: dict[str, object], scope: str) -> None:
    with pytest.raises(BudgetExceededError) as exc:
        evaluate_reservation(**_ok(**override))  # type: ignore[arg-type]
    assert exc.value.scope == scope
    assert exc.value.code == f"BUDGET_{scope}_EXCEEDED"
    detail = exc.value.detail()
    assert {"scope", "limit_usd", "spent_usd", "held_usd", "requested_usd"} <= detail.keys()


def test_TC_FR043_04_exact_fit_is_allowed() -> None:
    evaluate_reservation(**_ok(amount=D("1.00"), day=ScopeUsage(D("2.00"), D("0"))))  # type: ignore[arg-type]


def test_TC_FR049_01_uncertain_limit_checked_before_budget() -> None:
    with pytest.raises(UncertainLimitReachedError) as exc:
        evaluate_reservation(**_ok(job_uncertain_count=3))  # type: ignore[arg-type]
    assert exc.value.code == "UNCERTAIN_RESERVATION_LIMIT"
    evaluate_reservation(**_ok(job_uncertain_count=2))  # type: ignore[arg-type]


def test_TC_FR043_05_non_positive_amount_rejected() -> None:
    with pytest.raises(ValueError):
        evaluate_reservation(**_ok(amount=D("0")))  # type: ignore[arg-type]
