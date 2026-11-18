"""T103 – Tính thời điểm đến hạn của lịch (FR-033): múi giờ, chính sách chạy bù, khoảng cách tối thiểu."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from nichepilot.jobs.scheduler import ON_TIME_TOLERANCE, due_runs, next_after, validate_cron

T0 = datetime(2026, 11, 18, 0, 0, tzinfo=UTC)


def test_TC_FR033_01_timezone_asia_ho_chi_minh() -> None:
    # 02:00 tại Asia/Ho_Chi_Minh (UTC+7) = 19:00 UTC ngày hôm trước
    assert next_after("0 2 * * *", "Asia/Ho_Chi_Minh", T0) == datetime(2026, 11, 18, 19, 0, tzinfo=UTC)
    assert next_after("0 2 * * *", "UTC", T0) == datetime(2026, 11, 18, 2, 0, tzinfo=UTC)


def test_TC_FR033_02_on_time_run() -> None:
    due = datetime(2026, 11, 18, 19, 0, tzinfo=UTC)
    now = due + timedelta(seconds=30)
    for policy in ("SKIP", "RUN_ONCE"):
        assert due_runs("0 2 * * *", "Asia/Ho_Chi_Minh", next_run_at=due, now=now, misfire_policy=policy) == [due]


def test_TC_FR033_03_missed_runs_policy() -> None:
    first_due = datetime(2026, 11, 18, 0, 0, tzinfo=UTC)
    now = first_due + timedelta(hours=1, minutes=3)  # hệ thống tắt 1 giờ → lỡ 13 lần chạy (*/5)
    run_once = due_runs("*/5 * * * *", "UTC", next_run_at=first_due, now=now, misfire_policy="RUN_ONCE")
    assert run_once == [datetime(2026, 11, 18, 1, 0, tzinfo=UTC)]  # chạy bù tối đa 1 lần (lần gần nhất)
    assert due_runs("*/5 * * * *", "UTC", next_run_at=first_due, now=now, misfire_policy="SKIP") == []
    assert ON_TIME_TOLERANCE == timedelta(seconds=90)


def test_TC_FR033_04_not_due_yet() -> None:
    due = T0 + timedelta(minutes=10)
    assert due_runs("*/5 * * * *", "UTC", next_run_at=due, now=T0, misfire_policy="RUN_ONCE") == []


@pytest.mark.parametrize(
    ("expr", "tz", "ok"),
    [
        ("*/5 * * * *", "UTC", True),
        ("0 2 * * *", "Asia/Ho_Chi_Minh", True),
        ("* * * * *", "UTC", False),  # mỗi phút < 5 phút tối thiểu
        ("*/2 * * * *", "UTC", False),
        ("0 2 * * * *", "UTC", False),  # 6 trường
        ("not a cron", "UTC", False),
        ("0 2 * * *", "Mars/Olympus", False),
    ],
)
def test_TC_FR033_05_validate_cron(expr: str, tz: str, ok: bool) -> None:
    if ok:
        validate_cron(expr, tz)
    else:
        with pytest.raises(ValueError):
            validate_cron(expr, tz)
