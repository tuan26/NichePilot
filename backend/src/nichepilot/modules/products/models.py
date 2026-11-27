"""Model E2 – Product & Affiliate Discovery (specs/003-product-affiliate-discovery/data-model.md §2).

Ràng buộc nghiệp vụ đặt ở CHECK của DB (fail-closed) và kiểm tra lại ở service. Thuộc tính sản phẩm/chương trình KHÔNG
có bảng riêng:
mỗi giá trị là một dòng `research_evidence` (research R-05).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from nichepilot.core.models_base import Base, CreatedAtMixin, TimestampMixin, UUIDPkMixin, data_origin_check, in_list

RUN_OUTCOMES = ("COMPLETED", "PARTIAL_COMPLETED", "FAILED")
CATEGORIES = ("PHYSICAL", "SOFTWARE", "DIGITAL", "UNKNOWN")
PRODUCT_RISK_FLAGS = ("COMPLIANCE_SENSITIVE",)
READINESS_STATUSES = (
    "READY_TO_PROMOTE",
    "ELIGIBILITY_UNVERIFIED",
    "NOT_ELIGIBLE",
    "AFFILIATE_UNVERIFIED",
    "NO_PROGRAM",
    "PROGRAM_CLOSED",
)
PAIR_RISK_FLAGS = ("MONETIZATION_RISK", "MARKET_NOT_ALLOWED", "MARKET_UNKNOWN", "COMPLIANCE_SENSITIVE")
PERSONA_MATCHES = ("MATCH", "PARTIAL", "NO_MATCH", "UNKNOWN")
AI_RECOMMENDATIONS = ("SELECT", "REJECT", "UNKNOWN")
DECISION_STATUSES = ("CANDIDATE", "SELECTED", "WATCH", "REJECTED")
LINK_STATUSES = ("VERIFIED", "INFERRED")
OPERATOR_TYPES = ("VENDOR", "NETWORK", "UNKNOWN")
PROGRAM_STATUSES = ("VERIFIED", "PARTIAL", "UNVERIFIED", "CLOSED")
SCORING_STATUSES = ("SCORED", "INSUFFICIENT_SCORING_DATA")


def _len(col: str, lo: int, hi: int) -> str:
    return f"char_length({col}) BETWEEN {lo} AND {hi}"


def _subset(col: str, values: tuple[str, ...]) -> str:
    quoted = ",".join(f"'{v}'" for v in values)
    return f"{col} <@ ARRAY[{quoted}]::text[]"


def _lower(col: str) -> str:
    return f"{col} IS NULL OR {col} = lower({col})"


def _score(col: str, nullable: bool = False) -> str:
    rule = f"{col} BETWEEN 0 AND 100"
    return f"{col} IS NULL OR ({rule})" if nullable else rule


class ProductRun(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "product_runs"
    __table_args__ = (
        data_origin_check(),
        CheckConstraint(f"outcome IS NULL OR {in_list('outcome', RUN_OUTCOMES)}", name="outcome"),
        CheckConstraint("jsonb_typeof(params) = 'object'", name="params"),
        CheckConstraint("jsonb_typeof(metrics) = 'object'", name="metrics"),
        Index("ix_product_runs_niche", "niche_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_jobs.id"), unique=True)
    niche_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("niches.id"))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    outcome: Mapped[str | None] = mapped_column(Text)
    stop_reason: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    data_origin: Mapped[str] = mapped_column(Text)


class Product(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        data_origin_check(),
        CheckConstraint(_len("name", 1, 200), name="name"),
        CheckConstraint(_lower("official_domain"), name="official_domain"),
        CheckConstraint(in_list("category", CATEGORIES), name="category"),
        CheckConstraint(_subset("risk_flags", PRODUCT_RISK_FLAGS), name="risk_flags"),
        CheckConstraint("merged_into_id IS NULL OR merged_into_id <> id", name="merged_into"),
        UniqueConstraint("project_id", "data_origin", "dedup_key"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(Text)
    normalized_name: Mapped[str] = mapped_column(Text)
    vendor: Mapped[str | None] = mapped_column(Text)
    official_domain: Mapped[str | None] = mapped_column(Text)
    official_url: Mapped[str | None] = mapped_column(Text)
    dedup_key: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(Text, server_default=text("'UNKNOWN'"))
    risk_flags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'::text[]"))
    merged_into_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"))
    data_origin: Mapped[str] = mapped_column(Text)


class ProductNiche(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "product_niches"
    __table_args__ = (
        data_origin_check(),
        UniqueConstraint("product_id", "niche_id"),
        CheckConstraint(in_list("readiness_status", READINESS_STATUSES), name="readiness_status"),
        CheckConstraint(_subset("risk_flags", PAIR_RISK_FLAGS), name="risk_flags"),
        CheckConstraint(in_list("persona_match", PERSONA_MATCHES), name="persona_match"),
        CheckConstraint(in_list("ai_recommendation", AI_RECOMMENDATIONS), name="ai_recommendation"),
        CheckConstraint(in_list("decision_status", DECISION_STATUSES), name="decision_status"),
        CheckConstraint(
            "decision_status = 'CANDIDATE' OR"
            " (decided_by IS NOT NULL AND char_length(decision_reason) BETWEEN 1 AND 1000)",
            name="decision_reason",
        ),
        Index("ix_product_niches_niche", "niche_id"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"))
    niche_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("niches.id"))
    first_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("product_runs.id"))
    readiness_status: Mapped[str] = mapped_column(Text, server_default=text("'NO_PROGRAM'"))
    risk_flags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'::text[]"))
    persona_match: Mapped[str] = mapped_column(Text, server_default=text("'UNKNOWN'"))
    ai_recommendation: Mapped[str] = mapped_column(Text, server_default=text("'UNKNOWN'"))
    ai_recommendation_reason: Mapped[str | None] = mapped_column(Text)
    ai_levels: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    decision_status: Mapped[str] = mapped_column(Text, server_default=text("'CANDIDATE'"))
    decision_reason: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_origin: Mapped[str] = mapped_column(Text)


class ProductPainPointLink(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "product_pain_point_links"
    __table_args__ = (
        UniqueConstraint("product_niche_id", "pain_point_id", "evidence_id"),
        CheckConstraint(in_list("verification_status", LINK_STATUSES), name="verification_status"),
    )

    product_niche_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("product_niches.id"))
    pain_point_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("pain_points.id"))
    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("research_evidence.id"))
    verification_status: Mapped[str] = mapped_column(Text)


class AffiliateProgram(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "affiliate_programs"
    __table_args__ = (
        data_origin_check(),
        CheckConstraint(_len("name", 1, 200), name="name"),
        CheckConstraint(in_list("operator_type", OPERATOR_TYPES), name="operator_type"),
        CheckConstraint(_lower("operator_domain"), name="operator_domain"),
        CheckConstraint(in_list("verification_status", PROGRAM_STATUSES), name="verification_status"),
        UniqueConstraint("project_id", "data_origin", "dedup_key"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(Text)
    operator_type: Mapped[str] = mapped_column(Text, server_default=text("'UNKNOWN'"))
    operator_name: Mapped[str | None] = mapped_column(Text)
    operator_domain: Mapped[str | None] = mapped_column(Text)
    terms_url: Mapped[str | None] = mapped_column(Text)
    dedup_key: Mapped[str] = mapped_column(Text)
    verification_status: Mapped[str] = mapped_column(Text, server_default=text("'UNVERIFIED'"))
    watch_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_check_error: Mapped[str | None] = mapped_column(Text)
    data_origin: Mapped[str] = mapped_column(Text)


class ProductProgram(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "product_programs"
    __table_args__ = (UniqueConstraint("product_id", "program_id"),)

    product_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"))
    program_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("affiliate_programs.id"))


class ProgramTermsVersion(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "program_terms_versions"
    __table_args__ = (
        data_origin_check(),
        UniqueConstraint("program_id", "version"),
        CheckConstraint("version >= 1", name="version"),
    )

    program_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("affiliate_programs.id"))
    version: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    changes: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_jobs.id"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_origin: Mapped[str] = mapped_column(Text)


class ProductScoringWeights(UUIDPkMixin, CreatedAtMixin, Base):
    __tablename__ = "product_scoring_weights"
    __table_args__ = (
        CheckConstraint("version >= 1", name="version"),
        CheckConstraint("coverage_min BETWEEN 0 AND 100", name="coverage_min"),
        Index("uq_product_scoring_weights_active", "is_active", unique=True, postgresql_where=text("is_active")),
    )

    version: Mapped[int] = mapped_column(Integer, unique=True)
    weights: Mapped[dict[str, Any]] = mapped_column(JSONB)
    rubric: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    coverage_min: Mapped[Decimal] = mapped_column(Numeric(5, 2), server_default=text("60"))
    confidence_params: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    query_templates: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    non_official_domains: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'::text[]"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class ProductEvaluation(UUIDPkMixin, CreatedAtMixin, Base):
    __tablename__ = "product_evaluations"
    __table_args__ = (
        data_origin_check(),
        CheckConstraint(_score("opportunity_score", nullable=True), name="opportunity_score"),
        CheckConstraint(_score("confidence_score"), name="confidence_score"),
        CheckConstraint(_score("coverage"), name="coverage"),
        CheckConstraint(in_list("scoring_status", SCORING_STATUSES), name="scoring_status"),
        CheckConstraint("(scoring_status = 'SCORED') = (opportunity_score IS NOT NULL)", name="scored_has_opportunity"),
        Index("ix_product_evaluations_pair", "product_niche_id", "created_at"),
    )

    product_niche_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("product_niches.id"))
    weights_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("product_scoring_weights.id"))
    opportunity_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    coverage: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    scoring_status: Mapped[str] = mapped_column(Text)
    criteria: Mapped[dict[str, Any]] = mapped_column(JSONB)
    confidence_components: Mapped[dict[str, Any]] = mapped_column(JSONB)
    missing: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'::text[]"))
    evidence_fingerprint: Mapped[str] = mapped_column(Text)
    computed_without_ai: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("product_runs.id"))
    data_origin: Mapped[str] = mapped_column(Text)
