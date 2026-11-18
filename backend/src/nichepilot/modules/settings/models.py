"""Model cấu hình (data-model.md §3 projects, §4 settings)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from nichepilot.core.models_base import Base, TimestampMixin, UUIDPkMixin

# Khóa cấu hình không được giống secret (R-08): secret chỉ nằm trong .env/Docker secrets.
SECRET_LIKE_KEY_REGEX = "(api[_-]?key|secret|token|password)"  # noqa: S105 – mẫu regex, không phải secret


class Project(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("target_market ~ '^[A-Z]{2}$'", name="target_market"),
        Index("uq_projects_single_default", "is_default", unique=True, postgresql_where=text("is_default")),
    )

    slug: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    target_market: Mapped[str] = mapped_column(Text, server_default=text("'US'"))
    research_language: Mapped[str] = mapped_column(Text, server_default=text("'auto'"))
    content_language: Mapped[str] = mapped_column(Text, server_default=text("'en'"))


class Setting(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "settings"
    __table_args__ = (
        CheckConstraint(f"key !~* '{SECRET_LIKE_KEY_REGEX}'", name="key_not_secret"),
        CheckConstraint("version >= 1", name="version"),
    )

    key: Mapped[str] = mapped_column(Text, unique=True)
    value: Mapped[Any] = mapped_column(JSONB)
    version: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
