"""Lớp model cơ sở (T028 – FR-005, data-model.md "Quy ước chung")."""

from __future__ import annotations

import os
import time
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, MetaData, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}
DATA_ORIGINS = ("REAL", "MOCK")


def uuid7() -> uuid.UUID:
    """UUIDv7 (RFC 9562) – có thứ tự thời gian, sinh phía ứng dụng."""
    ms = int(time.time() * 1000)
    rand = int.from_bytes(os.urandom(10), "big")
    value = (ms & ((1 << 48) - 1)) << 80
    value |= 0x7 << 76
    value |= ((rand >> 62) & 0xFFF) << 64
    value |= 0b10 << 62
    value |= rand & ((1 << 62) - 1)
    return uuid.UUID(int=value)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class UUIDPkMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7, server_default=text("gen_random_uuid()")
    )


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TimestampMixin(CreatedAtMixin):
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


def data_origin_check() -> CheckConstraint:
    """CHECK data_origin ∈ {REAL, MOCK} – mỗi bảng chứa kết quả AI/tool/nghiên cứu phải có (R-14)."""
    return CheckConstraint("data_origin IN ('REAL','MOCK')", name="data_origin")


def in_list(column: str, values: tuple[str, ...] | list[str]) -> str:
    """Tạo biểu thức CHECK `col IN (...)` dùng chung cho model và migration."""
    quoted = ",".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"
