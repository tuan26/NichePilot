"""Model AI & ngân sách (data-model.md §5a ai_models, §5 model_pricing, §6 model_task_profiles,
§10 ai_usage_logs, §11 budget_reservations).

Model ID và giá CHỈ nằm trong dữ liệu (seed/API), không trong business logic (FR-019c).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column

from nichepilot.core.models_base import (
    Base,
    CreatedAtMixin,
    TimestampMixin,
    UUIDPkMixin,
    data_origin_check,
    in_list,
)

PROVIDERS = ("anthropic", "openai", "mock")
PAID_PROVIDERS = ("anthropic", "openai")
MODEL_STATUSES = ("ACTIVE", "DEPRECATED", "UNAVAILABLE")
EFFORTS = ("low", "medium", "high", "xhigh", "max")
AI_OUTCOMES = (
    "SUCCESS",
    "SCHEMA_INVALID",
    "TIMEOUT",
    "RATE_LIMITED",
    "AUTH_ERROR",
    "NETWORK_ERROR",
    "PROVIDER_ERROR",
    "BAD_REQUEST",
    "REFUSED",
    "TRUNCATED",
)
BILLING_STATUSES = ("BILLED", "NOT_BILLED", "UNCERTAIN")
RESERVATION_STATUSES = ("ACTIVE", "SETTLED", "RELEASED", "UNCERTAIN", "RESOLVED")
UNCERTAIN_REASONS = (
    "TIMEOUT_AFTER_SEND",
    "CONNECTION_LOST",
    "WORKER_LOST",
    "USAGE_UNREADABLE",
    "ERROR_BILLING_UNVERIFIED",
)
FALLBACK_TRIGGERS = ("PROVIDER_UNAVAILABLE",)
MONEY = Numeric(14, 6)


class AiModel(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "ai_models"
    __table_args__ = (
        UniqueConstraint("provider", "model_id"),
        CheckConstraint(in_list("provider", PROVIDERS), name="provider"),
        CheckConstraint(in_list("status", MODEL_STATUSES), name="status"),
        CheckConstraint("model_id !~* 'latest'", name="no_latest_alias"),
        CheckConstraint(
            "NOT verified OR (verification_source IS NOT NULL AND verified_at IS NOT NULL)",
            name="verified_has_source",
        ),
    )

    provider: Mapped[str] = mapped_column(Text)
    model_id: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    verification_source: Mapped[str | None] = mapped_column(Text)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by: Mapped[str | None] = mapped_column(Text)
    supports_structured_output: Mapped[bool | None] = mapped_column(Boolean)
    supports_tools: Mapped[bool | None] = mapped_column(Boolean)
    supports_effort: Mapped[bool | None] = mapped_column(Boolean)
    max_input_tokens: Mapped[int | None] = mapped_column(BigInteger)
    max_output_tokens: Mapped[int | None] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(Text, server_default=text("'ACTIVE'"))


class ModelPricing(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "model_pricing"
    __table_args__ = (
        UniqueConstraint("provider", "model", "version"),
        ForeignKeyConstraint(["provider", "model"], ["ai_models.provider", "ai_models.model_id"]),
        CheckConstraint("version >= 1", name="version"),
        CheckConstraint("input_per_mtok >= 0 AND output_per_mtok >= 0", name="non_negative"),
        CheckConstraint(
            "(cache_read_per_mtok IS NULL OR cache_read_per_mtok >= 0) AND "
            "(cache_write_per_mtok IS NULL OR cache_write_per_mtok >= 0)",
            name="cache_non_negative",
        ),
        CheckConstraint(
            "long_context_threshold_tokens IS NULL OR "
            "(long_input_per_mtok IS NOT NULL AND long_output_per_mtok IS NOT NULL)",
            name="long_context_complete",
        ),
        CheckConstraint("length(source_note) > 0", name="source_note"),
    )

    provider: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    input_per_mtok: Mapped[Decimal] = mapped_column(MONEY)
    output_per_mtok: Mapped[Decimal] = mapped_column(MONEY)
    cache_read_per_mtok: Mapped[Decimal | None] = mapped_column(MONEY)
    cache_write_per_mtok: Mapped[Decimal | None] = mapped_column(MONEY)
    long_context_threshold_tokens: Mapped[int | None] = mapped_column(BigInteger)
    long_input_per_mtok: Mapped[Decimal | None] = mapped_column(MONEY)
    long_output_per_mtok: Mapped[Decimal | None] = mapped_column(MONEY)
    source_note: Mapped[str] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class ModelTaskProfile(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "model_task_profiles"
    __table_args__ = (
        ForeignKeyConstraint(["provider", "model"], ["ai_models.provider", "ai_models.model_id"]),
        CheckConstraint(in_list("provider", PROVIDERS), name="provider"),
        CheckConstraint(f"effort IS NULL OR {in_list('effort', EFFORTS)}", name="effort"),
        CheckConstraint("max_output_tokens BETWEEN 1 AND 128000", name="max_output_tokens"),
        CheckConstraint("timeout_s BETWEEN 5 AND 900", name="timeout_s"),
        CheckConstraint("schema_retry_max BETWEEN 0 AND 5", name="schema_retry_max"),
        CheckConstraint(
            f"fallback_provider IS NULL OR ({in_list('fallback_provider', PAID_PROVIDERS)} "
            "AND fallback_provider <> provider AND fallback_model IS NOT NULL)",
            name="fallback",
        ),
        CheckConstraint("fallback_on <@ ARRAY['PROVIDER_UNAVAILABLE']::text[]", name="fallback_on"),
    )

    task_type: Mapped[str] = mapped_column(Text, unique=True)
    provider: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    effort: Mapped[str | None] = mapped_column(Text)
    max_output_tokens: Mapped[int] = mapped_column(Integer)
    timeout_s: Mapped[int] = mapped_column(Integer, server_default=text("120"))
    schema_retry_max: Mapped[int] = mapped_column(Integer, server_default=text("2"))
    fallback_provider: Mapped[str | None] = mapped_column(Text)
    fallback_model: Mapped[str | None] = mapped_column(Text)
    fallback_on: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'::text[]"))
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))


class AiUsageLog(UUIDPkMixin, CreatedAtMixin, Base):
    """Bất biến: mỗi lời gọi AI một bản ghi (kể cả lỗi)."""

    __tablename__ = "ai_usage_logs"
    __table_args__ = (
        data_origin_check(),
        CheckConstraint(in_list("outcome", AI_OUTCOMES), name="outcome"),
        CheckConstraint(in_list("billing_status", BILLING_STATUSES), name="billing_status"),
        CheckConstraint(
            "input_tokens >= 0 AND output_tokens >= 0 AND cache_read_tokens >= 0 AND cache_write_tokens >= 0",
            name="tokens",
        ),
        CheckConstraint("cost_usd >= 0", name="cost"),
        Index("ix_ai_usage_logs_origin_created", "data_origin", "created_at"),
        Index("ix_ai_usage_logs_job_id", "job_id"),
    )

    job_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_jobs.id"))
    step_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("job_steps.id"))
    provider: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(Text)
    task_type: Mapped[str] = mapped_column(Text)
    data_origin: Mapped[str] = mapped_column(Text)
    is_fallback: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    provider_request_id: Mapped[str | None] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(Text)
    billing_status: Mapped[str] = mapped_column(Text)
    sent: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    stop_reason: Mapped[str | None] = mapped_column(Text)
    refusal_category: Mapped[str | None] = mapped_column(Text)
    refusal_explanation: Mapped[str | None] = mapped_column(Text)
    input_tokens: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    output_tokens: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    cache_read_tokens: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    cache_write_tokens: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    cost_usd: Mapped[Decimal] = mapped_column(MONEY, server_default=text("0"))
    pricing_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("model_pricing.id"))
    latency_ms: Mapped[int | None] = mapped_column(Integer)


class BudgetReservation(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "budget_reservations"
    __table_args__ = (
        data_origin_check(),
        CheckConstraint("amount_usd > 0", name="amount"),
        CheckConstraint(in_list("status", RESERVATION_STATUSES), name="status"),
        CheckConstraint(
            f"uncertain_reason IS NULL OR {in_list('uncertain_reason', UNCERTAIN_REASONS)}",
            name="uncertain_reason",
        ),
        CheckConstraint("status <> 'UNCERTAIN' OR uncertain_reason IS NOT NULL", name="uncertain_has_reason"),
        CheckConstraint("status <> 'RELEASED' OR release_reason IS NOT NULL", name="released_has_reason"),
        CheckConstraint("actual_usd IS NULL OR actual_usd >= 0", name="actual"),
        Index("ix_budget_reservations_origin_status_created", "data_origin", "status", "created_at"),
        Index("ix_budget_reservations_job_id", "job_id"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_jobs.id"))
    step_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("job_steps.id"))
    data_origin: Mapped[str] = mapped_column(Text)
    amount_usd: Mapped[Decimal] = mapped_column(MONEY)
    status: Mapped[str] = mapped_column(Text, server_default=text("'ACTIVE'"))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    usage_log_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("ai_usage_logs.id"))
    actual_usd: Mapped[Decimal | None] = mapped_column(MONEY)
    release_reason: Mapped[str | None] = mapped_column(Text)
    uncertain_reason: Mapped[str | None] = mapped_column(Text)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolution_note: Mapped[str | None] = mapped_column(Text)
