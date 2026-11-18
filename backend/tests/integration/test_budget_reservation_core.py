"""T022 – Vòng đời reservation lõi (FR-047, FR-049, SC-004b)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from nichepilot.ai.budget import BudgetService, ReservationStateError, UncertainLimitReachedError
from tests.integration.budget_helpers import insert_job, insert_usage, restore_budget_defaults, set_setting

pytestmark = pytest.mark.integration
D = Decimal


@pytest.fixture
async def svc(clean_db: AsyncEngine) -> AsyncIterator[BudgetService]:
    yield BudgetService(async_sessionmaker(clean_db, expire_on_commit=False))
    await restore_budget_defaults(clean_db)


async def _row(engine: AsyncEngine, rid: object) -> dict[str, object]:
    async with engine.connect() as conn:
        r = (await conn.execute(text("SELECT * FROM budget_reservations WHERE id=:i"), {"i": rid})).mappings().one()
    return dict(r)


async def test_TC_FR047_01_mark_sent_then_settle_with_actual(svc: BudgetService, clean_db: AsyncEngine) -> None:
    job = await insert_job(clean_db)
    res = await svc.reserve(job, D("0.50"), "MOCK", call_timeout_s=30)
    row = await _row(clean_db, res.id)
    assert row["status"] == "ACTIVE" and row["sent_at"] is None
    assert row["expires_at"] > row["created_at"]  # type: ignore[operator]

    await svc.mark_sent(res.id)
    assert (await _row(clean_db, res.id))["sent_at"] is not None

    usage = await insert_usage(clean_db, job, "0.12")
    diff = await svc.settle(res.id, usage, D("0.12"))
    assert diff == D("-0.38")
    row = await _row(clean_db, res.id)
    assert row["status"] == "SETTLED" and row["actual_usd"] == D("0.12") and row["usage_log_id"] == usage
    status = await svc.status("MOCK")
    assert status.day.spent == D("0.12") and status.day.held == D("0")


async def test_TC_FR047_02_release_only_when_active(svc: BudgetService, clean_db: AsyncEngine) -> None:
    job = await insert_job(clean_db)
    res = await svc.reserve(job, D("0.50"), "MOCK", call_timeout_s=30)
    await svc.release(res.id, "NOT_SENT")
    row = await _row(clean_db, res.id)
    assert row["status"] == "RELEASED" and row["release_reason"] == "NOT_SENT"
    with pytest.raises(ReservationStateError):
        await svc.release(res.id, "NOT_SENT")


async def test_TC_FR047_03_uncertain_keeps_hold_and_cannot_be_released(
    svc: BudgetService, clean_db: AsyncEngine
) -> None:
    job = await insert_job(clean_db)
    res = await svc.reserve(job, D("0.40"), "MOCK", call_timeout_s=30)
    await svc.mark_sent(res.id)
    count = await svc.mark_uncertain(res.id, "TIMEOUT_AFTER_SEND")
    assert count == 1
    row = await _row(clean_db, res.id)
    assert row["status"] == "UNCERTAIN" and row["uncertain_reason"] == "TIMEOUT_AFTER_SEND"
    status = await svc.status("MOCK")
    assert status.day.held == D("0.40")  # vẫn bị trừ ngân sách
    assert status.uncertain_count == 1
    with pytest.raises(ReservationStateError):
        await svc.release(res.id, "NOT_SENT")  # không bao giờ tự giải phóng UNCERTAIN


async def test_TC_FR049_02_reserve_refused_when_job_reaches_uncertain_limit(
    svc: BudgetService, clean_db: AsyncEngine
) -> None:
    await set_setting(clean_db, "budget.max_uncertain_per_job", "2")
    job = await insert_job(clean_db)
    for expected in (1, 2):
        r = await svc.reserve(job, D("0.10"), "MOCK", call_timeout_s=30)
        await svc.mark_sent(r.id)
        assert await svc.mark_uncertain(r.id, "TIMEOUT_AFTER_SEND") == expected
    with pytest.raises(UncertainLimitReachedError) as exc:
        await svc.reserve(job, D("0.10"), "MOCK", call_timeout_s=30)
    assert exc.value.code == "UNCERTAIN_RESERVATION_LIMIT"
    assert exc.value.detail() == {"job_id": str(job), "uncertain_count": 2, "limit": 2}
    # Job khác không bị ảnh hưởng
    other = await insert_job(clean_db)
    await svc.reserve(other, D("0.10"), "MOCK", call_timeout_s=30)


async def test_TC_FR018_01_real_and_mock_ledgers_are_separate(svc: BudgetService, clean_db: AsyncEngine) -> None:
    job = await insert_job(clean_db)
    await svc.reserve(job, D("1.00"), "MOCK", call_timeout_s=30)
    real = await svc.status("REAL")
    mock = await svc.status("MOCK")
    assert real.day.held == D("0") and mock.day.held == D("1.00")
