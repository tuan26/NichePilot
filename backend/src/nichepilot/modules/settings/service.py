"""Đọc cấu hình không bí mật từ bảng `settings` (FR-055). Phần cập nhật qua API được bổ sung ở US6 (T112)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nichepilot.modules.settings.models import Project, Setting


async def get_setting_values(session: AsyncSession, keys: list[str]) -> dict[str, Any]:
    rows = (await session.execute(select(Setting.key, Setting.value).where(Setting.key.in_(keys)))).all()
    values = {k: v for k, v in rows}
    missing = [k for k in keys if k not in values]
    if missing:
        raise RuntimeError(f"Thiếu cấu hình: {missing}")
    return values


async def get_default_project(session: AsyncSession) -> Project:
    return (await session.execute(select(Project).where(Project.is_default))).scalar_one()
