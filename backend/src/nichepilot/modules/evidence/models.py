"""Kho bằng chứng dùng chung (data-model.md §14 – FR-007). E0 chỉ tạo cấu trúc, không có dữ liệu nghiên cứu."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import BigInteger, CheckConstraint, Date, DateTime, ForeignKey, Index, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from nichepilot.core.models_base import Base, TimestampMixin, UUIDPkMixin, data_origin_check, in_list

SOURCE_TYPES = ("WEB_PAGE", "FORUM", "REVIEW_SITE", "VIDEO", "API", "DOCUMENT", "OTHER")
LIFECYCLE_STATUSES = ("ACTIVE", "ERASED")  # E1 (X2) – FR-013e
REDACTION_STATUSES = ("REDACTED", "NEEDS_REVIEW")  # E1 (X2) – FR-012a
VERIFICATION_STATUSES = ("VERIFIED", "INFERRED", "UNKNOWN", "CONFLICTING")
MAX_EXCERPT_CHARS = 1000


class ResearchSource(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "research_sources"
    __table_args__ = (
        UniqueConstraint("project_id", "canonical_url", "content_hash"),
        CheckConstraint(in_list("source_type", SOURCE_TYPES), name="source_type"),
        data_origin_check(),
        # E1 (X2, specs/002-niche-discovery/data-model.md §1)
        CheckConstraint(in_list("lifecycle_status", LIFECYCLE_STATUSES), name="lifecycle_status"),
        CheckConstraint("(lifecycle_status = 'ERASED') = (erased_at IS NOT NULL)", name="erased_at"),
        CheckConstraint("registered_domain IS NULL OR registered_domain = lower(registered_domain)", name="reg_domain"),
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
    # E1 (X2) – NULL được cho nguồn E0 cũ
    registered_domain: Mapped[str | None] = mapped_column(Text)
    simhash: Mapped[int | None] = mapped_column(BigInteger)
    lifecycle_status: Mapped[str] = mapped_column(Text, server_default=text("'ACTIVE'"))
    erased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("source_policies.id"))
    policy_verified_at: Mapped[date | None] = mapped_column(Date)


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
        # E1 (X2, specs/002-niche-discovery/data-model.md §1)
        CheckConstraint(
            "redaction_status IS NULL OR " + in_list("redaction_status", REDACTION_STATUSES), name="redaction_status"
        ),
        CheckConstraint(
            "redaction_counts IS NULL OR (jsonb_typeof(redaction_counts) = 'object' AND"
            " redaction_counts - ARRAY['EMAIL','PHONE','USER','PERSON'] = '{}'::jsonb)",
            name="redaction_counts",
        ),
        CheckConstraint(in_list("lifecycle_status", LIFECYCLE_STATUSES), name="lifecycle_status"),
        CheckConstraint(
            "lifecycle_status <> 'ERASED' OR (excerpt IS NULL AND value IS NULL)", name="erased_no_content"
        ),
        CheckConstraint("(lifecycle_status = 'ERASED') = (erased_at IS NOT NULL)", name="erased_at"),
        CheckConstraint("content_hash IS NULL OR content_hash ~ '^[0-9a-f]{64}$'", name="content_hash"),
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
    # E1 (X2) – NULL được cho bằng chứng E0 cũ; E1 không bao giờ lưu nội dung chưa che PII
    redaction_status: Mapped[str | None] = mapped_column(Text)
    redaction_counts: Mapped[dict[str, int] | None] = mapped_column(JSONB)
    pii_engine: Mapped[str | None] = mapped_column(Text)
    lifecycle_status: Mapped[str] = mapped_column(Text, server_default=text("'ACTIVE'"))
    erased_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    content_hash: Mapped[str | None] = mapped_column(Text)
