"""Model E3 – Keyword & Audience Research (specs/004-keyword-audience-research/data-model.md §2).

Ràng buộc nghiệp vụ đặt ở CHECK của DB (fail-closed). Chỉ số keyword (Search Volume/CPC/KD) NULL = `UNKNOWN`; có giá
trị thì bắt
buộc có nguồn, thời điểm và thị trường (FR-009). Bằng chứng trang SERP/đối thủ là dòng `research_evidence` (subject
`keyword_run`).
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
)
from sqlalchemy import (
    text as sa_text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from nichepilot.core.models_base import Base, CreatedAtMixin, TimestampMixin, UUIDPkMixin, data_origin_check, in_list

RUN_OUTCOMES = ("COMPLETED", "PARTIAL_COMPLETED", "FAILED")
KEYWORD_TYPES = ("PROBLEM", "SOLUTION", "PRODUCT", "COMPARISON", "INFORMATIONAL")
LENGTH_CLASSES = ("HEAD", "MID", "LONG_TAIL")
INTENTS = ("INFORMATIONAL", "COMMERCIAL_INVESTIGATION", "TRANSACTIONAL", "NAVIGATIONAL")
INTENT_STATUSES = ("INFERRED", "VERIFIED")
KEYWORD_RISK_FLAGS = ("BRAND_TERM", "COMPLIANCE_SENSITIVE")
ORIGIN_TYPES = ("PAIN_POINT", "PERSONA", "PRODUCT")
DECISION_STATUSES = ("CANDIDATE", "SELECTED", "WATCH", "REJECTED")
SCORING_STATUSES = ("SCORED", "INSUFFICIENT_SCORING_DATA")


def _subset(col: str, values: tuple[str, ...]) -> str:
    quoted = ",".join(f"'{v}'" for v in values)
    return f"{col} <@ ARRAY[{quoted}]::text[]"


def _score(col: str, nullable: bool = False) -> str:
    rule = f"{col} BETWEEN 0 AND 100"
    return f"{col} IS NULL OR ({rule})" if nullable else rule


def _metric_sourced(col: str) -> str:
    return (
        f"{col} IS NULL OR (metrics_source IS NOT NULL AND metrics_collected_at IS NOT NULL"
        " AND metrics_market IS NOT NULL)"
    )


class KeywordRun(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "keyword_runs"
    __table_args__ = (
        data_origin_check(),
        CheckConstraint(f"outcome IS NULL OR {in_list('outcome', RUN_OUTCOMES)}", name="outcome"),
        CheckConstraint("jsonb_typeof(params) = 'object'", name="params"),
        CheckConstraint("jsonb_typeof(metrics) = 'object'", name="metrics"),
        Index("ix_keyword_runs_niche", "niche_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_jobs.id"), unique=True)
    niche_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("niches.id"))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=sa_text("'{}'::jsonb"))
    outcome: Mapped[str | None] = mapped_column(Text)
    stop_reason: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=sa_text("'{}'::jsonb"))
    data_origin: Mapped[str] = mapped_column(Text)


class KeywordCluster(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "keyword_clusters"
    __table_args__ = (
        data_origin_check(),
        UniqueConstraint("niche_id", "data_origin", "cluster_key"),
        CheckConstraint(in_list("intent", INTENTS), name="intent"),
        CheckConstraint(in_list("decision_status", DECISION_STATUSES), name="decision_status"),
        CheckConstraint(
            "decision_status = 'CANDIDATE' OR"
            " (decided_by IS NOT NULL AND char_length(decision_reason) BETWEEN 1 AND 1000)",
            name="decision_reason",
        ),
        CheckConstraint("jsonb_typeof(insights) = 'object'", name="insights"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    niche_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("niches.id"))
    cluster_key: Mapped[str] = mapped_column(Text)
    primary_keyword_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("keywords.id", use_alter=True, name="fk_keyword_clusters_primary_keyword_id")
    )
    intent: Mapped[str] = mapped_column(Text)
    pain_point_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("pain_points.id"))
    product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"))
    insights: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=sa_text("'{}'::jsonb"))
    decision_status: Mapped[str] = mapped_column(Text, server_default=sa_text("'CANDIDATE'"))
    decision_reason: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    watch_enabled: Mapped[bool] = mapped_column(Boolean, server_default=sa_text("false"))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_check_error: Mapped[str | None] = mapped_column(Text)
    data_origin: Mapped[str] = mapped_column(Text)


class Keyword(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "keywords"
    __table_args__ = (
        data_origin_check(),
        UniqueConstraint("project_id", "niche_id", "data_origin", "dedup_key"),
        CheckConstraint("char_length(text) BETWEEN 2 AND 150", name="text"),
        CheckConstraint("language ~ '^[a-z]{2}$'", name="language"),
        CheckConstraint("market ~ '^[A-Z]{2}$'", name="market"),
        CheckConstraint(in_list("keyword_type", KEYWORD_TYPES), name="keyword_type"),
        CheckConstraint(in_list("length_class", LENGTH_CLASSES), name="length_class"),
        CheckConstraint(in_list("intent", INTENTS), name="intent"),
        CheckConstraint(in_list("intent_status", INTENT_STATUSES), name="intent_status"),
        CheckConstraint(_subset("risk_flags", KEYWORD_RISK_FLAGS), name="risk_flags"),
        CheckConstraint(_metric_sourced("search_volume"), name="search_volume_sourced"),
        CheckConstraint(_metric_sourced("cpc"), name="cpc_sourced"),
        CheckConstraint(_metric_sourced("keyword_difficulty"), name="keyword_difficulty_sourced"),
        CheckConstraint("search_volume IS NULL OR search_volume >= 0", name="search_volume"),
        CheckConstraint("cpc IS NULL OR cpc >= 0", name="cpc"),
        CheckConstraint(_score("keyword_difficulty", nullable=True), name="keyword_difficulty"),
        Index("ix_keywords_niche", "niche_id"),
        Index("ix_keywords_cluster", "cluster_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    niche_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("niches.id"))
    text: Mapped[str] = mapped_column(Text)
    normalized: Mapped[str] = mapped_column(Text)
    dedup_key: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(Text, server_default=sa_text("'en'"))
    market: Mapped[str] = mapped_column(Text, server_default=sa_text("'US'"))
    keyword_type: Mapped[str] = mapped_column(Text)
    length_class: Mapped[str] = mapped_column(Text)
    intent: Mapped[str] = mapped_column(Text)
    intent_status: Mapped[str] = mapped_column(Text, server_default=sa_text("'INFERRED'"))
    intent_reason: Mapped[str | None] = mapped_column(Text)
    search_volume: Mapped[int | None] = mapped_column(Integer)
    cpc: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    keyword_difficulty: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    metrics_source: Mapped[str | None] = mapped_column(Text)
    metrics_collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metrics_market: Mapped[str | None] = mapped_column(Text)
    risk_flags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=sa_text("'{}'::text[]"))
    cluster_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("keyword_clusters.id"))
    ai_levels: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=sa_text("'{}'::jsonb"))
    first_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("keyword_runs.id"))
    data_origin: Mapped[str] = mapped_column(Text)


class KeywordOrigin(UUIDPkMixin, CreatedAtMixin, Base):
    __tablename__ = "keyword_origins"
    __table_args__ = (
        CheckConstraint(in_list("origin_type", ORIGIN_TYPES), name="origin_type"),
        CheckConstraint(
            "(origin_type = 'PAIN_POINT' AND pain_point_id IS NOT NULL AND product_id IS NULL"
            " AND persona_attribute IS NULL)"
            " OR (origin_type = 'PRODUCT' AND product_id IS NOT NULL AND pain_point_id IS NULL"
            " AND persona_attribute IS NULL)"
            " OR (origin_type = 'PERSONA' AND persona_attribute IS NOT NULL AND pain_point_id IS NULL"
            " AND product_id IS NULL)",
            name="origin_ref",
        ),
        Index(
            "uq_keyword_origins_ref",
            "keyword_id",
            "origin_type",
            sa_text("coalesce(pain_point_id::text, '')"),
            sa_text("coalesce(product_id::text, '')"),
            sa_text("coalesce(persona_attribute, '')"),
            unique=True,
        ),
    )

    keyword_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("keywords.id"))
    origin_type: Mapped[str] = mapped_column(Text)
    pain_point_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("pain_points.id"))
    product_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("products.id"))
    persona_attribute: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)


class SerpObservation(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "serp_observations"
    __table_args__ = (
        data_origin_check(),
        UniqueConstraint("keyword_id", "version"),
        CheckConstraint("version >= 1", name="version"),
        CheckConstraint("jsonb_typeof(results) = 'array'", name="results"),
    )

    keyword_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("keywords.id"))
    version: Mapped[int] = mapped_column(Integer)
    results: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    source_policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("source_policies.id"))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    changes: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=sa_text("'{}'::jsonb"))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_jobs.id"))
    data_origin: Mapped[str] = mapped_column(Text)


class CompetitorPage(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "competitor_pages"
    __table_args__ = (
        data_origin_check(),
        UniqueConstraint("keyword_id", "url"),
        CheckConstraint("jsonb_typeof(summary) = 'object'", name="summary"),
    )

    keyword_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("keywords.id"))
    url: Mapped[str] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(Text)
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("research_evidence.id"))
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=sa_text("'{}'::jsonb"))
    data_origin: Mapped[str] = mapped_column(Text)


class KeywordScoringWeights(UUIDPkMixin, CreatedAtMixin, Base):
    __tablename__ = "keyword_scoring_weights"
    __table_args__ = (
        CheckConstraint("version >= 1", name="version"),
        CheckConstraint("coverage_min BETWEEN 0 AND 100", name="coverage_min"),
        Index("uq_keyword_scoring_weights_active", "is_active", unique=True, postgresql_where=sa_text("is_active")),
    )

    version: Mapped[int] = mapped_column(Integer, unique=True)
    weights: Mapped[dict[str, Any]] = mapped_column(JSONB)
    rubric: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=sa_text("'{}'::jsonb"))
    coverage_min: Mapped[Decimal] = mapped_column(Numeric(5, 2), server_default=sa_text("60"))
    confidence_params: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=sa_text("'{}'::jsonb"))
    templates: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=sa_text("'{}'::jsonb"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=sa_text("false"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class KeywordEvaluation(UUIDPkMixin, CreatedAtMixin, Base):
    __tablename__ = "keyword_evaluations"
    __table_args__ = (
        data_origin_check(),
        CheckConstraint(_score("opportunity_score", nullable=True), name="opportunity_score"),
        CheckConstraint(_score("confidence_score"), name="confidence_score"),
        CheckConstraint(_score("coverage"), name="coverage"),
        CheckConstraint(in_list("scoring_status", SCORING_STATUSES), name="scoring_status"),
        CheckConstraint("(scoring_status = 'SCORED') = (opportunity_score IS NOT NULL)", name="scored_has_opportunity"),
        Index("ix_keyword_evaluations_keyword", "keyword_id", "created_at"),
    )

    keyword_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("keywords.id"))
    weights_version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("keyword_scoring_weights.id"))
    opportunity_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    coverage: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    scoring_status: Mapped[str] = mapped_column(Text)
    criteria: Mapped[dict[str, Any]] = mapped_column(JSONB)
    confidence_components: Mapped[dict[str, Any]] = mapped_column(JSONB)
    missing: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=sa_text("'{}'::text[]"))
    evidence_fingerprint: Mapped[str] = mapped_column(Text)
    computed_without_ai: Mapped[bool] = mapped_column(Boolean, server_default=sa_text("false"))
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("keyword_runs.id"))
    data_origin: Mapped[str] = mapped_column(Text)
