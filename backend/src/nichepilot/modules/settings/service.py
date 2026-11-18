"""Cấu hình không bí mật trong bảng `settings` và project mặc định (FR-055, FR-057, BR-10)."""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from decimal import Decimal, InvalidOperation
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from nichepilot.modules.settings.models import SECRET_LIKE_KEY_REGEX, Project, Setting


async def get_setting_values(session: AsyncSession, keys: list[str]) -> dict[str, Any]:
    rows = (await session.execute(select(Setting.key, Setting.value).where(Setting.key.in_(keys)))).all()
    values = {k: v for k, v in rows}
    missing = [k for k in keys if k not in values]
    if missing:
        raise RuntimeError(f"Thiếu cấu hình: {missing}")
    return values


async def get_default_project(session: AsyncSession) -> Project:
    return (await session.execute(select(Project).where(Project.is_default))).scalar_one()


# ---------------------------------------------------------------------------------------------------------------
# Registry khóa cấu hình (T112 – FR-055, FR-057): mỗi khóa có bộ kiểm tra riêng; khóa lạ hoặc giống secret bị từ chối.
# Giá trị đọc trực tiếp từ DB ở mỗi lần dùng (auth/budget/logging) → thay đổi có hiệu lực ngay, không cần khởi động lại.
# ---------------------------------------------------------------------------------------------------------------

SECRET_LIKE = re.compile(SECRET_LIKE_KEY_REGEX, re.IGNORECASE)
MIN_LOG_RETENTION_DAYS = 90


class SettingValidationError(ValueError):
    def __init__(self, key: str, code: str) -> None:
        super().__init__(f"{key}: {code}")
        self.key = key
        self.code = code


def _int(lo: int, hi: int) -> Callable[[Any], Any]:
    def check(v: Any) -> Any:
        if isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi:
            raise ValueError(f"integer_{lo}_{hi}")
        return v

    return check


def _number(lo: float, hi: float, *, lo_inclusive: bool = True) -> Callable[[Any], Any]:
    def check(v: Any) -> Any:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError("number")
        if not (lo <= v if lo_inclusive else lo < v) or v > hi:
            raise ValueError("out_of_range")
        return v

    return check


def _money(v: Any) -> Any:
    if not isinstance(v, str):
        raise ValueError("money_string")
    try:
        d = Decimal(v)
    except InvalidOperation:
        raise ValueError("money_string") from None
    if not d.is_finite() or d < 0 or d.as_tuple().exponent < -6:  # type: ignore[operator]
        raise ValueError("money_non_negative")
    return v


def _enum(*values: str) -> Callable[[Any], Any]:
    def check(v: Any) -> Any:
        if v not in values:
            raise ValueError("enum")
        return v

    return check


def _timezone(v: Any) -> Any:
    try:
        ZoneInfo(str(v))
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("timezone") from None
    if not isinstance(v, str):
        raise ValueError("timezone")
    return v


def _billing_policy(v: Any) -> Any:
    if not isinstance(v, dict) or not all(
        k in ("anthropic", "openai", "mock") and isinstance(b, bool) for k, b in v.items()
    ):
        raise ValueError("provider_bool_map")
    return v


SETTING_VALIDATORS: dict[str, Callable[[Any], Any]] = {
    "budget.daily_usd": _money,
    "budget.monthly_usd": _money,
    "budget.per_job_default_usd": _money,
    "budget.warning_threshold": _number(0, 1, lo_inclusive=False),
    "budget.reservation_margin_s": _int(0, 3600),
    "budget.max_uncertain_per_job": _int(1, 20),
    "system.timezone": _timezone,
    "agent.default_max_steps": _int(1, 200),
    "agent.default_max_ai_calls": _int(1, 500),
    "agent.default_job_timeout_s": _int(30, 86400),
    "worker.max_concurrent_jobs": _int(1, 32),
    "schedule.misfire_policy_default": _enum("SKIP", "RUN_ONCE"),
    "ui.default_locale": _enum("vi", "en"),
    "auth.session_idle_timeout_hours": _int(1, 720),
    "auth.lockout_threshold": _int(1, 100),
    "auth.lockout_minutes": _int(1, 1440),
    "logging.retention_days": _int(MIN_LOG_RETENTION_DAYS, 3650),  # FR-057: không thấp hơn 90 ngày
    "logging.disk_warn_gb": _number(0, 10_000, lo_inclusive=False),
    "billing.error_responses_not_billed_verified": _billing_policy,
}


def validate_setting(key: str, value: Any) -> Any:
    if SECRET_LIKE.search(key):
        raise SettingValidationError(key, "secret_key_not_allowed")
    validator = SETTING_VALIDATORS.get(key)
    if validator is None:
        raise SettingValidationError(key, "unknown_key")
    try:
        return validator(value)
    except ValueError as exc:
        raise SettingValidationError(key, str(exc)) from None


def validate_cross(values: dict[str, Any]) -> None:
    """Ràng buộc chéo trên tập giá trị sau khi áp dụng thay đổi."""
    daily = Decimal(str(values["budget.daily_usd"]))
    monthly = Decimal(str(values["budget.monthly_usd"]))
    per_job = Decimal(str(values["budget.per_job_default_usd"]))
    if daily > monthly:
        raise SettingValidationError("budget.daily_usd", "daily_exceeds_monthly")
    if per_job > daily:
        raise SettingValidationError("budget.per_job_default_usd", "per_job_exceeds_daily")


class VersionConflictError(Exception):
    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


async def list_settings(session: AsyncSession) -> list[Setting]:
    return list((await session.execute(select(Setting).order_by(Setting.key))).scalars().all())


async def update_settings(
    session: AsyncSession, items: list[tuple[str, Any, int]], *, user_id: uuid.UUID | None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Cập nhật nguyên tử nhiều khóa với optimistic locking. Trả về (before, after) cho audit."""
    validated = [(key, validate_setting(key, value), version) for key, value, version in items]
    rows = {s.key: s for s in await list_settings(session)}
    merged = {k: s.value for k, s in rows.items()}
    original = dict(merged)  # giá trị trước khi cập nhật (identity map sẽ được đồng bộ sau UPDATE)
    for key, value, _ in validated:
        if key not in rows:
            raise SettingValidationError(key, "unknown_key")
        merged[key] = value
    validate_cross(merged)
    before: dict[str, Any] = {}
    after: dict[str, Any] = {}
    for key, value, version in validated:
        updated = (
            await session.execute(
                update(Setting)
                .where(Setting.key == key, Setting.version == version)
                .values(value=value, version=Setting.version + 1, updated_by=user_id, updated_at=func.now())
                .returning(Setting.id)
            )
        ).scalar_one_or_none()
        if updated is None:
            raise VersionConflictError(key)
        before[key] = original[key]
        after[key] = value
    return before, after
