"""Audit log append-only (data-model.md §13). Không có updated_at; trigger DB chặn UPDATE/DELETE/TRUNCATE."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import CheckConstraint, Index, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from nichepilot.core.models_base import Base, CreatedAtMixin, UUIDPkMixin, in_list

ACTOR_TYPES = ("USER", "SYSTEM")


class AuditLog(UUIDPkMixin, CreatedAtMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint(in_list("actor_type", ACTOR_TYPES), name="actor_type"),
        Index("ix_audit_logs_created_at", "created_at"),
        Index("ix_audit_logs_action", "action"),
    )

    actor_type: Mapped[str] = mapped_column(Text)
    # Không FK: bản ghi audit bất biến, không được thay đổi khi user bị xóa.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    action: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str | None] = mapped_column(Text)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    before: Mapped[Any | None] = mapped_column(JSONB)
    after: Mapped[Any | None] = mapped_column(JSONB)
    request_id: Mapped[str | None] = mapped_column(Text)
    ip: Mapped[str | None] = mapped_column(Text)
    user_agent: Mapped[str | None] = mapped_column(Text)
