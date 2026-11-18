"""Model job (data-model.md §12 job_schedules, §7 agent_jobs, §8 job_steps, §9 tool_executions)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    BigInteger,
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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from nichepilot.core.models_base import Base, TimestampMixin, UUIDPkMixin, data_origin_check, in_list

JOB_STATUSES = (
    "QUEUED",
    "RUNNING",
    "PAUSED",
    "PAUSED_BUDGET",
    "RETRY_SCHEDULED",
    "SUCCEEDED",
    "FAILED",
    "CANCELLED",
)
JOB_TRIGGERS = ("MANUAL", "SCHEDULE", "RETRY")
STEP_TYPES = ("AI_CALL", "TOOL_CALL", "LOGIC")
STEP_STATUSES = ("RUNNING", "SUCCEEDED", "FAILED", "REFUSED", "TRUNCATED", "SKIPPED", "BLOCKED")
TOOL_STATUSES = ("SUCCEEDED", "FAILED", "DENIED", "TIMEOUT")
MISFIRE_POLICIES = ("SKIP", "RUN_ONCE")
MONEY = Numeric(14, 6)


class JobSchedule(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "job_schedules"
    __table_args__ = (
        UniqueConstraint("project_id", "name"),
        CheckConstraint(in_list("misfire_policy", MISFIRE_POLICIES), name="misfire_policy"),
        CheckConstraint("budget_limit_usd IS NULL OR budget_limit_usd > 0", name="budget_limit"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    name: Mapped[str] = mapped_column(Text)
    job_type: Mapped[str] = mapped_column(Text)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    cron_expr: Mapped[str] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    misfire_policy: Mapped[str] = mapped_column(Text, server_default=text("'RUN_ONCE'"))
    budget_limit_usd: Mapped[Decimal | None] = mapped_column(MONEY)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AgentJob(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "agent_jobs"
    __table_args__ = (
        data_origin_check(),
        CheckConstraint(in_list("status", JOB_STATUSES), name="status"),
        CheckConstraint(in_list("trigger", JOB_TRIGGERS), name="trigger"),
        CheckConstraint("budget_limit_usd > 0", name="budget_limit"),
        CheckConstraint("last_completed_seq >= 0", name="last_completed_seq"),
        CheckConstraint("max_attempts >= 1", name="max_attempts"),
        CheckConstraint("max_steps >= 1 AND max_ai_calls >= 1 AND timeout_s >= 1", name="limits"),
        Index("ix_agent_jobs_status", "status"),
        Index("ix_agent_jobs_project_created", "project_id", "created_at"),
        Index("ix_agent_jobs_schedule_scheduled_for", "schedule_id", "scheduled_for"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"))
    job_type: Mapped[str] = mapped_column(Text)
    params: Mapped[dict[str, Any]] = mapped_column(JSONB, server_default=text("'{}'::jsonb"))
    idempotency_key: Mapped[str] = mapped_column(Text, unique=True)
    status: Mapped[str] = mapped_column(Text, server_default=text("'QUEUED'"))
    trigger: Mapped[str] = mapped_column(Text)
    schedule_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_schedules.id", ondelete="SET NULL")
    )
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    data_origin: Mapped[str] = mapped_column(Text)
    budget_limit_usd: Mapped[Decimal] = mapped_column(MONEY)
    cost_accumulated_usd: Mapped[Decimal] = mapped_column(MONEY, server_default=text("0"))
    max_steps: Mapped[int] = mapped_column(Integer)
    max_ai_calls: Mapped[int] = mapped_column(Integer)
    timeout_s: Mapped[int] = mapped_column(Integer)
    step_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    ai_call_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    last_completed_seq: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    checkpoint: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    pause_requested: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    cancel_requested: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    attempt: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    max_attempts: Mapped[int] = mapped_column(Integer, server_default=text("3"))
    status_reason_code: Mapped[str | None] = mapped_column(Text)
    status_reason_detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    queue_job_id: Mapped[int | None] = mapped_column(BigInteger)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class JobStep(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "job_steps"
    __table_args__ = (
        UniqueConstraint("job_id", "seq"),
        data_origin_check(),
        CheckConstraint("seq >= 1", name="seq"),
        CheckConstraint(in_list("step_type", STEP_TYPES), name="step_type"),
        CheckConstraint(in_list("status", STEP_STATUSES), name="status"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_jobs.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer)
    step_type: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    attempt: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    data_origin: Mapped[str] = mapped_column(Text)
    input_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    cost_usd: Mapped[Decimal] = mapped_column(MONEY, server_default=text("0"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ToolExecution(UUIDPkMixin, TimestampMixin, Base):
    __tablename__ = "tool_executions"
    __table_args__ = (
        data_origin_check(),
        CheckConstraint(in_list("status", TOOL_STATUSES), name="status"),
        CheckConstraint("status <> 'DENIED' OR denial_reason IS NOT NULL", name="denied_has_reason"),
        Index("ix_tool_executions_job_id", "job_id"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_jobs.id", ondelete="CASCADE"))
    step_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("job_steps.id", ondelete="CASCADE")
    )
    tool_name: Mapped[str] = mapped_column(Text)
    tool_version: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    denial_reason: Mapped[str | None] = mapped_column(Text)
    input: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    data_origin: Mapped[str] = mapped_column(Text)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
