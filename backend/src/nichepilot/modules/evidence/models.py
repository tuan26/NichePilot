"""Kho bằng chứng dùng chung (data-model.md §14 – FR-007). E0 chỉ tạo cấu trúc, không có dữ liệu nghiên cứu."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from nichepilot.core.models_base import Base, TimestampMixin, UUIDPkMixin, data_origin_check, in_list

SOURCE_TYPES = ("WEB_PAGE", "FORUM", "REVIEW_SITE", "VIDEO", "API", "DOCUMENT", "OTHER")
VERIFICATION_STATUSES = ("VERIFIED", "INFERRED", "UNKNOWN", "CONFLICTING")
MAX_EXCERPT_CHARS = 1000


class ResearchSource(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "research_sources"
    __table_args__ = (
        UniqueConstraint("project_id", "canonical_url", "content_hash"),
        CheckConstraint(in_list("source_type", SOURCE_TYPES), name="source_type"),
        data_origin_check(),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    source_type: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    canonical_url: Mapped[str] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(Text)
    publisher: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str] = mapped_column(Text)
    data_origin: Mapped[str] = mapped_column(Text)


class ResearchEvidence(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "research_evidence"
    __table_args__ = (
        CheckConstraint(in_list("verification_status", VERIFICATION_STATUSES), name="verification_status"),
        CheckConstraint("verification_status <> 'VERIFIED' OR source_id IS NOT NULL", name="verified_has_source"),
        CheckConstraint("verification_status <> 'UNKNOWN' OR value IS NULL", name="unknown_has_no_value"),
        CheckConstraint(f"excerpt IS NULL OR length(excerpt) <= {MAX_EXCERPT_CHARS}", name="excerpt_length"),
        data_origin_check(),
        Index("ix_research_evidence_project_claim", "project_id", "claim_key"),
        Index("ix_research_evidence_subject", "subject_type", "subject_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("research_sources.id"))
    subject_type: Mapped[str | None] = mapped_column(Text)
    subject_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    claim_key: Mapped[str] = mapped_column(Text)
    value: Mapped[Any | None] = mapped_column(JSONB(none_as_null=True))  # UNKNOWN ⇒ SQL NULL, không phải JSON null
    excerpt: Mapped[str | None] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(Text)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collected_by_job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_jobs.id"))
    data_origin: Mapped[str] = mapped_column(Text)
