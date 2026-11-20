"""Model E1 – Autonomous Niche Discovery (specs/002-niche-discovery/data-model.md §2).

Ràng buộc nghiệp vụ được đặt ở CHECK của DB (fail-closed) và kiểm tra lại ở service. Tên ràng buộc theo quy ước E0.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from nichepilot.core.models_base import Base, CreatedAtMixin, TimestampMixin, UUIDPkMixin, data_origin_check, in_list

CRITERIA = (
    "problem_severity",
    "monetization",
    "market_gap",
    "reachability",
    "competition_opportunity",
    "demand_stability",
)
VERIFICATION_STATUSES = ("VERIFIED", "INFERRED", "UNKNOWN", "CONFLICTING")
ADAPTER_TYPES = ("searxng_engine", "http_json_api", "open_dataset", "licensed_data")
ACCESS_METHODS = ("SEARXNG_ENGINE", "OFFICIAL_API", "DATASET_DOWNLOAD")
COMPLIANCE_STATUSES = ("ALLOWED", "UNVERIFIED", "PROHIBITED")
RUN_TRIGGERS = ("MANUAL", "SCHEDULE", "RETRY")  # = JOB_TRIGGERS của E0
RUN_OUTCOMES = ("COMPLETED", "PARTIAL_COMPLETED")
STOP_REASONS = (
    "ALL_CANDIDATES_SUFFICIENT",
    "CANDIDATES_EXHAUSTED",
    "TIME_LIMIT_REACHED",
    "PAGE_LIMIT_REACHED",
    "NO_COMPLIANT_SEARCH_SOURCE",
    "SOURCES_UNAVAILABLE",
    "CANCELLED",
)
EVIDENCE_STATUSES = ("EVIDENCE_SUFFICIENT", "INSUFFICIENT_EVIDENCE")
DECISION_STATUSES = ("CANDIDATE", "WATCH", "PURSUE", "REJECTED", "HIDDEN")
AI_RECOMMENDATIONS = ("PURSUE", "REJECT", "UNKNOWN")
MONETIZATION_STATUSES = ("SIGNALS_FOUND", "MONETIZATION_UNVERIFIED", "NO_AFFILIATE_FOUND")
RISK_FLAGS = ("MONETIZATION_RISK", "COMPLIANCE_SENSITIVE", "LOW_EVIDENCE_FRESHNESS")
SIMILARITY_STATUSES = ("POSSIBLE", "CONFIRMED_DUPLICATE", "NOT_DUPLICATE")
SCORING_STATUSES = ("SCORED", "INSUFFICIENT_SCORING_DATA")
FINDING_FIELDS = ("CURRENT_SOLUTIONS", "MARKET_GAPS", "POTENTIAL_PRODUCTS", "MONETIZATION", "CHANNELS", "RISKS")
COMPETITOR_KINDS = ("PRODUCT", "SERVICE", "MANUAL_WORKAROUND")
LINK_PURPOSES = ("PAIN_POINT", "PERSONA", "SOLUTION", "COMPETITOR", "MONETIZATION", "CHANNEL")
ROBOTS_STATUSES = ("OK", "NOT_FOUND", "UNREACHABLE", "PENDING")
BLOCK_REASONS = ("RATE_LIMITED", "ACCESS_RESTRICTED", "ROBOTS_UNREACHABLE")
FETCH_OUTCOMES = ("SUCCESS", "FAILED", "SKIPPED")
FETCH_REASONS = (
    "ROBOTS_DISALLOWED",
    "RATE_LIMITED",
    "ACCESS_RESTRICTED",
    "HTTP_ERROR",
    "TIMEOUT",
    "NETWORK_ERROR",
    "NON_HTML",
    "TOO_LARGE",
    "PII_UNSAFE",
    "PAGE_LIMIT",
    "TIME_LIMIT",
    "ERASED_CONTENT",
)
ERASURE_TARGETS = ("EVIDENCE", "SOURCE")
LEDGER_STATUSES = ("OK", "BLOCKED")
SHA256_RE = "^[0-9a-f]{64}$"
MONEY = Numeric(14, 6)


def _len(col: str, lo: int, hi: int) -> str:
    return f"char_length({col}) BETWEEN {lo} AND {hi}"


def _subset(col: str, values: tuple[str, ...]) -> str:
    quoted = ",".join(f"'{v}'" for v in values)
    return f"{col} <@ ARRAY[{quoted}]::text[]"


class ScoringWeightsVersion(UUIDPkMixin, CreatedAtMixin, Base):
    __tablename__ = "scoring_weights_versions"
    __table_args__ = (
        CheckConstraint("version >= 1", name="version"),
        CheckConstraint("coverage_threshold > 0 AND coverage_threshold <= 100", name="coverage_threshold"),
        # PostgreSQL không cho subquery trong CHECK: tổng = 100 và từng giá trị 0–100 kiểm tra ở WeightsService/seed.
        CheckConstraint(
            "jsonb_typeof(weights) = 'object' AND weights ?& ARRAY['problem_severity','monetization','market_gap',"
            "'reachability','competition_opportunity','demand_stability']",
            name="weights_keys",
        ),
        Index("uq_scoring_weights_versions_active", "is_active", unique=True, postgresql_where=text("is_active")),
    )

    version: Mapped[int] = mapped_column(Integer, unique=True)
    weights: Mapped[dict[str, Any]] = mapped_column(JSONB)
    coverage_threshold: Mapped[Decimal] = mapped_column(Numeric(5, 2), server_default=text("60"))
    evidence_rules: Mapped[dict[str, Any]] = mapped_column(JSONB)
    confidence_params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    dedup_params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class SourcePolicy(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "source_policies"
    __table_args__ = (
        CheckConstraint("source_key ~ '^[a-z0-9_:.-]{2,64}$'", name="source_key"),
        CheckConstraint(_len("display_name", 1, 120), name="display_name"),
        CheckConstraint(in_list("adapter_type", ADAPTER_TYPES), name="adapter_type"),
        CheckConstraint("jsonb_typeof(config) = 'object'", name="config_object"),
        CheckConstraint("tos_url ~ '^https://' AND char_length(tos_url) <= 2000", name="tos_url"),
        CheckConstraint("verified_at IS NULL OR verified_at <= CURRENT_DATE", name="verified_at"),
        CheckConstraint("verification_note IS NULL OR " + _len("verification_note", 10, 2000), name="note"),
        CheckConstraint(_subset("allowed_access_methods", ACCESS_METHODS), name="access_methods"),
        CheckConstraint("permitted_use_scope IS NULL OR " + _len("permitted_use_scope", 10, 1000), name="scope"),
        CheckConstraint("known_limits IS NULL OR char_length(known_limits) <= 1000", name="known_limits"),
        CheckConstraint(in_list("compliance_status", COMPLIANCE_STATUSES), name="compliance_status"),
        # A1: chỉ nguồn ALLOWED được bật – UNVERIFIED/PROHIBITED không bật được, không có xác nhận cảnh báo.
        CheckConstraint("NOT enabled OR compliance_status = 'ALLOWED'", name="enabled_only_allowed"),
        CheckConstraint(
            "compliance_status <> 'ALLOWED' OR (verified_at IS NOT NULL AND verified_by IS NOT NULL AND"
            " verification_note IS NOT NULL AND cardinality(allowed_access_methods) > 0 AND"
            " permitted_use_scope IS NOT NULL)",
            name="allowed_has_evidence",
        ),
        CheckConstraint(
            "compliance_status <> 'PROHIBITED' OR (verified_at IS NOT NULL AND verification_note IS NOT NULL)",
            name="prohibited_has_evidence",
        ),
    )

    source_key: Mapped[str] = mapped_column(Text, unique=True)
    display_name: Mapped[str] = mapped_column(Text)
    adapter_type: Mapped[str] = mapped_column(Text)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    tos_url: Mapped[str] = mapped_column(Text)
    verified_at: Mapped[date | None] = mapped_column(Date)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    verification_note: Mapped[str | None] = mapped_column(Text)
    allowed_access_methods: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'::text[]"))
    permitted_use_scope: Mapped[str | None] = mapped_column(Text)
    known_limits: Mapped[str | None] = mapped_column(Text)
    compliance_status: Mapped[str] = mapped_column(Text, server_default=text("'UNVERIFIED'"))
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))


class DiscoveryRun(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "discovery_runs"
    __table_args__ = (
        data_origin_check(),
        CheckConstraint("market ~ '^[A-Z]{2}$'", name="market"),
        CheckConstraint("research_language ~ '^[a-z]{2}(-[A-Z]{2})?$'", name="research_language"),
        CheckConstraint("seed_topic IS NULL OR char_length(seed_topic) <= 200", name="seed_topic"),
        CheckConstraint("max_candidates BETWEEN 1 AND 50", name="max_candidates"),
        CheckConstraint("budget_usd > 0", name="budget_usd"),
        CheckConstraint("time_limit_s BETWEEN 300 AND 14400", name="time_limit_s"),
        CheckConstraint("page_limit BETWEEN 10 AND 2000", name="page_limit"),
        CheckConstraint("per_domain_interval_s >= 1", name="per_domain_interval_s"),
        CheckConstraint(in_list("trigger", RUN_TRIGGERS), name="trigger"),
        CheckConstraint(in_list("source_mode", ("REAL", "MOCK")), name="source_mode"),
        CheckConstraint("outcome IS NULL OR " + in_list("outcome", RUN_OUTCOMES), name="outcome"),
        CheckConstraint("stop_reason IS NULL OR " + in_list("stop_reason", STOP_REASONS), name="stop_reason"),
        CheckConstraint("jsonb_typeof(metrics) = 'object'", name="metrics_object"),
        CheckConstraint("idempotency_key IS NULL OR char_length(idempotency_key) <= 128", name="idempotency_key"),
        Index("ix_discovery_runs_project_created", "project_id", "created_at"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_jobs.id"), unique=True)
    market: Mapped[str] = mapped_column(Text)
    research_language: Mapped[str] = mapped_column(Text)
    seed_topic: Mapped[str | None] = mapped_column(Text)
    max_candidates: Mapped[int] = mapped_column(Integer, server_default=text("20"))
    budget_usd: Mapped[Decimal] = mapped_column(MONEY, server_default=text("2"))
    time_limit_s: Mapped[int] = mapped_column(Integer, server_default=text("5400"))
    page_limit: Mapped[int] = mapped_column(Integer, server_default=text("300"))
    per_domain_interval_s: Mapped[Decimal] = mapped_column(Numeric(6, 2), server_default=text("2"))
    trigger: Mapped[str] = mapped_column(Text)
    source_policy_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), server_default=text("'{}'::uuid[]")
    )
    weights_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scoring_weights_versions.id")
    )
    source_mode: Mapped[str] = mapped_column(Text)
    outcome: Mapped[str | None] = mapped_column(Text)
    stop_reason: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    data_origin: Mapped[str] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(Text, unique=True)


class Niche(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "niches"
    __table_args__ = (
        data_origin_check(),
        CheckConstraint(_len("name", 1, 200), name="name"),
        CheckConstraint(_len("micro_niche", 1, 200), name="micro_niche"),
        CheckConstraint("country ~ '^[A-Z]{2}$'", name="country"),
        CheckConstraint(_len("customer_group", 1, 300), name="customer_group"),
        CheckConstraint(_len("core_problem", 1, 500), name="core_problem"),
        CheckConstraint(in_list("evidence_status", EVIDENCE_STATUSES), name="evidence_status"),
        CheckConstraint(in_list("decision_status", DECISION_STATUSES), name="decision_status"),
        CheckConstraint(in_list("ai_recommendation", AI_RECOMMENDATIONS), name="ai_recommendation"),
        CheckConstraint(
            "ai_recommendation_reason IS NULL OR char_length(ai_recommendation_reason) <= 2000", name="ai_reason"
        ),
        CheckConstraint(
            "owner_decision_reason IS NULL OR char_length(owner_decision_reason) <= 2000", name="owner_reason"
        ),
        CheckConstraint("decision_status = 'CANDIDATE' OR decided_by IS NOT NULL", name="decided_by"),
        CheckConstraint(in_list("monetization_status", MONETIZATION_STATUSES), name="monetization_status"),
        CheckConstraint(_subset("risk_flags", RISK_FLAGS), name="risk_flags"),
        CheckConstraint("merged_into_id IS NULL OR merged_into_id <> id", name="merged_into"),
        Index(
            "uq_niches_project_origin_dedup_key",
            "project_id",
            "data_origin",
            "dedup_key",
            unique=True,
            postgresql_where=text("merged_into_id IS NULL"),
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(Text)
    micro_niche: Mapped[str] = mapped_column(Text)
    country: Mapped[str] = mapped_column(Text)
    customer_group: Mapped[str] = mapped_column(Text)
    core_problem: Mapped[str] = mapped_column(Text)
    dedup_key: Mapped[str] = mapped_column(Text)
    evidence_status: Mapped[str] = mapped_column(Text, server_default=text("'INSUFFICIENT_EVIDENCE'"))
    decision_status: Mapped[str] = mapped_column(Text, server_default=text("'CANDIDATE'"))
    ai_recommendation: Mapped[str] = mapped_column(Text, server_default=text("'UNKNOWN'"))
    ai_recommendation_reason: Mapped[str | None] = mapped_column(Text)
    owner_decision_reason: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    monetization_status: Mapped[str] = mapped_column(Text, server_default=text("'MONETIZATION_UNVERIFIED'"))
    risk_flags: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'::text[]"))
    merged_into_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("niches.id"))
    latest_evaluation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("niche_evaluations.id", use_alter=True)
    )
    data_origin: Mapped[str] = mapped_column(Text)


class NicheRunLink(UUIDPkMixin, CreatedAtMixin, Base):
    __tablename__ = "niche_run_links"
    __table_args__ = (
        UniqueConstraint("niche_id", "run_id"),
        CheckConstraint(in_list("role", ("DISCOVERED", "REEVALUATED")), name="role"),
    )

    niche_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("niches.id"))
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("discovery_runs.id"))
    role: Mapped[str] = mapped_column(Text)


class NicheSimilarity(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "niche_similarity"
    __table_args__ = (
        UniqueConstraint("niche_a_id", "niche_b_id"),
        CheckConstraint("niche_a_id < niche_b_id", name="ordered_pair"),
        CheckConstraint("score BETWEEN 0 AND 1", name="score"),
        CheckConstraint(in_list("status", SIMILARITY_STATUSES), name="status"),
        CheckConstraint("status = 'POSSIBLE' OR resolved_by IS NOT NULL", name="resolved_by"),
    )

    niche_a_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("niches.id"))
    niche_b_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("niches.id"))
    score: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    status: Mapped[str] = mapped_column(Text, server_default=text("'POSSIBLE'"))
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class NicheEvaluation(UUIDPkMixin, CreatedAtMixin, Base):
    """Bất biến: trigger trong migration chặn UPDATE/DELETE."""

    __tablename__ = "niche_evaluations"
    __table_args__ = (
        data_origin_check(),
        CheckConstraint("coverage BETWEEN 0 AND 100", name="coverage"),
        CheckConstraint(in_list("scoring_status", SCORING_STATUSES), name="scoring_status"),
        CheckConstraint("opportunity_score IS NULL OR opportunity_score BETWEEN 0 AND 100", name="opportunity"),
        CheckConstraint(
            "(opportunity_score IS NULL) = (scoring_status = 'INSUFFICIENT_SCORING_DATA')", name="opportunity_status"
        ),
        CheckConstraint("confidence_score BETWEEN 0 AND 100", name="confidence"),
        CheckConstraint(in_list("evidence_status", EVIDENCE_STATUSES), name="evidence_status"),
        CheckConstraint("independent_groups >= 0", name="independent_groups"),
        Index("ix_niche_evaluations_niche_created", "niche_id", "created_at"),
    )

    niche_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("niches.id"))
    run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("discovery_runs.id"))
    weights_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scoring_weights_versions.id")
    )
    criteria: Mapped[dict[str, Any]] = mapped_column(JSONB)
    coverage: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    scoring_status: Mapped[str] = mapped_column(Text)
    opportunity_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    confidence_components: Mapped[dict[str, Any]] = mapped_column(JSONB)
    evidence_status: Mapped[str] = mapped_column(Text)
    independent_groups: Mapped[int] = mapped_column(Integer)
    computed_without_ai: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    data_origin: Mapped[str] = mapped_column(Text)


class NicheFinding(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "niche_findings"
    __table_args__ = (
        data_origin_check(),
        UniqueConstraint("niche_id", "field"),
        CheckConstraint(in_list("field", FINDING_FIELDS), name="field"),
        CheckConstraint(in_list("verification_status", VERIFICATION_STATUSES), name="verification_status"),
        CheckConstraint("(value IS NULL) = (verification_status = 'UNKNOWN')", name="unknown_no_value"),
        CheckConstraint("verification_status <> 'VERIFIED' OR cardinality(evidence_ids) > 0", name="verified_ev"),
    )

    niche_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("niches.id"))
    field: Mapped[str] = mapped_column(Text)
    value: Mapped[Any | None] = mapped_column(JSONB(none_as_null=True))
    verification_status: Mapped[str] = mapped_column(Text)
    evidence_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), server_default=text("'{}'"))
    data_origin: Mapped[str] = mapped_column(Text)


class PainPoint(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "pain_points"
    __table_args__ = (
        data_origin_check(),
        UniqueConstraint("niche_id", "normalized_title"),
        CheckConstraint(_len("title", 1, 200), name="title"),
        CheckConstraint("severity IS NULL OR severity BETWEEN 1 AND 5", name="severity"),
        CheckConstraint("evidence_count >= 0", name="evidence_count"),
        CheckConstraint(in_list("verification_status", VERIFICATION_STATUSES), name="verification_status"),
    )

    niche_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("niches.id"))
    title: Mapped[str] = mapped_column(Text)
    normalized_title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[int | None] = mapped_column(SmallInteger)
    severity_reason: Mapped[str | None] = mapped_column(Text)
    evidence_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    verification_status: Mapped[str] = mapped_column(Text)
    data_origin: Mapped[str] = mapped_column(Text)


class BuyerPersona(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "buyer_personas"
    __table_args__ = (
        data_origin_check(),
        CheckConstraint(
            "attributes ?& ARRAY['segment','context','goals','obstacles','ability_to_pay']", name="attributes_keys"
        ),
    )

    niche_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("niches.id"), unique=True)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB)
    data_origin: Mapped[str] = mapped_column(Text)


class Competitor(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "competitors"
    __table_args__ = (
        data_origin_check(),
        UniqueConstraint("niche_id", "normalized_name"),
        CheckConstraint(_len("name", 1, 200), name="name"),
        CheckConstraint(in_list("kind", COMPETITOR_KINDS), name="kind"),
        CheckConstraint("url IS NULL OR url ~ '^https?://'", name="url"),
        CheckConstraint(
            "jsonb_typeof(strengths) = 'array' AND jsonb_typeof(weaknesses) = 'array'", name="lists"
        ),
    )

    niche_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("niches.id"))
    name: Mapped[str] = mapped_column(Text)
    normalized_name: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(Text)
    strengths: Mapped[list[Any]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    weaknesses: Mapped[list[Any]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    data_origin: Mapped[str] = mapped_column(Text)


class NicheEvidenceLink(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "niche_evidence_links"
    __table_args__ = (
        data_origin_check(),
        UniqueConstraint("niche_id", "evidence_id"),
        CheckConstraint(in_list("purpose", LINK_PURPOSES), name="purpose"),
        CheckConstraint("(pain_point_id IS NOT NULL) = (purpose = 'PAIN_POINT')", name="pain_point"),
        CheckConstraint("relevance IS NULL OR relevance BETWEEN 0 AND 1", name="relevance"),
        CheckConstraint("quality IS NULL OR quality BETWEEN 0 AND 1", name="quality"),
    )

    niche_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("niches.id"))
    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("research_evidence.id"))
    purpose: Mapped[str] = mapped_column(Text)
    pain_point_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("pain_points.id"))
    relevance: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    quality: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    assessment_reason: Mapped[str | None] = mapped_column(Text)
    copy_suspected: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    independence_group: Mapped[str] = mapped_column(Text)
    counted_for_threshold: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    data_origin: Mapped[str] = mapped_column(Text)


class DomainAccessState(TimestampMixin, Base):
    __tablename__ = "domain_access_state"
    __table_args__ = (
        CheckConstraint("domain = lower(domain)", name="domain_lower"),
        CheckConstraint("min_interval_s >= 1", name="min_interval"),
        CheckConstraint(in_list("robots_status", ROBOTS_STATUSES), name="robots_status"),
        CheckConstraint("crawl_delay_s IS NULL OR crawl_delay_s >= 0", name="crawl_delay"),
        CheckConstraint("block_reason IS NULL OR " + in_list("block_reason", BLOCK_REASONS), name="block_reason"),
    )

    domain: Mapped[str] = mapped_column(Text, primary_key=True)
    last_request_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    min_interval_s: Mapped[Decimal] = mapped_column(Numeric(8, 2), server_default=text("2"))
    robots_status: Mapped[str] = mapped_column(Text, server_default=text("'PENDING'"))
    robots_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    robots_rules: Mapped[str | None] = mapped_column(Text)  # chỉ nội dung robots.txt cần cho luật (≤ 64 KB)
    crawl_delay_s: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    block_reason: Mapped[str | None] = mapped_column(Text)


class PageFetchLog(UUIDPkMixin, CreatedAtMixin, Base):
    __tablename__ = "page_fetch_log"
    __table_args__ = (
        UniqueConstraint("run_id", "url_hash"),
        CheckConstraint(f"url_hash ~ '{SHA256_RE}'", name="url_hash"),
        CheckConstraint("domain = lower(domain)", name="domain_lower"),
        CheckConstraint(in_list("outcome", FETCH_OUTCOMES), name="outcome"),
        CheckConstraint("reason IS NULL OR " + in_list("reason", FETCH_REASONS), name="reason"),
        CheckConstraint("outcome = 'SUCCESS' OR reason IS NOT NULL", name="reason_required"),
        CheckConstraint("http_status IS NULL OR http_status BETWEEN 100 AND 599", name="http_status"),
        CheckConstraint("(source_id IS NOT NULL) = (outcome = 'SUCCESS')", name="source_on_success"),
    )

    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("discovery_runs.id"))
    url_hash: Mapped[str] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(Text)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    outcome: Mapped[str] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(Text)
    http_status: Mapped[int | None] = mapped_column(SmallInteger)
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("research_sources.id"))


class EvidenceErasureRequest(UUIDPkMixin, CreatedAtMixin, Base):
    __tablename__ = "evidence_erasure_requests"
    __table_args__ = (
        CheckConstraint(in_list("target_type", ERASURE_TARGETS), name="target_type"),
        CheckConstraint(f"content_hash IS NULL OR content_hash ~ '{SHA256_RE}'", name="content_hash"),
        CheckConstraint(_len("reason", 3, 500), name="reason"),
        CheckConstraint("ledger_seq >= 1", name="ledger_seq"),
    )

    target_type: Mapped[str] = mapped_column(Text)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    content_hash: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    requested_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ledger_seq: Mapped[int] = mapped_column(BigInteger, unique=True)


class ErasureLedgerState(TimestampMixin, Base):
    __tablename__ = "erasure_ledger_state"
    __table_args__ = (
        CheckConstraint("id = 1", name="singleton"),
        CheckConstraint("applied_seq >= 0", name="applied_seq"),
        CheckConstraint(f"applied_hash IS NULL OR applied_hash ~ '{SHA256_RE}'", name="applied_hash"),
        CheckConstraint(in_list("status", LEDGER_STATUSES), name="status"),
        CheckConstraint("last_error IS NULL OR char_length(last_error) <= 500", name="last_error"),
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    ledger_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    applied_seq: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    applied_hash: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default=text("'OK'"))
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
