"""0004_ai_jobs – ai_models, model_pricing, model_task_profiles, job_schedules, agent_jobs, job_steps,
tool_executions, ai_usage_logs (data-model.md §5–§10, §12). job_schedules trước agent_jobs vì khóa ngoại.

Revision ID: 0004_ai_jobs
Revises: 0003_seed_core
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_ai_jobs"
down_revision = "0003_seed_core"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_models",
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model_id", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("verification_source", sa.Text(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by", sa.Text(), nullable=True),
        sa.Column("supports_structured_output", sa.Boolean(), nullable=True),
        sa.Column("supports_tools", sa.Boolean(), nullable=True),
        sa.Column("supports_effort", sa.Boolean(), nullable=True),
        sa.Column("max_input_tokens", sa.BigInteger(), nullable=True),
        sa.Column("max_output_tokens", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("model_id !~* 'latest'", name=op.f("ck_ai_models_no_latest_alias")),
        sa.CheckConstraint("provider IN ('anthropic','openai','mock')", name=op.f("ck_ai_models_provider")),
        sa.CheckConstraint("status IN ('ACTIVE','DEPRECATED','UNAVAILABLE')", name=op.f("ck_ai_models_status")),
        sa.CheckConstraint(
            "NOT verified OR (verification_source IS NOT NULL AND verified_at IS NOT NULL)",
            name=op.f("ck_ai_models_verified_has_source"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_models")),
        sa.UniqueConstraint("provider", "model_id", name=op.f("uq_ai_models_provider_model_id")),
    )
    op.create_table(
        "model_pricing",
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("input_per_mtok", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("output_per_mtok", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("cache_read_per_mtok", sa.Numeric(precision=14, scale=6), nullable=True),
        sa.Column("cache_write_per_mtok", sa.Numeric(precision=14, scale=6), nullable=True),
        sa.Column("long_context_threshold_tokens", sa.BigInteger(), nullable=True),
        sa.Column("long_input_per_mtok", sa.Numeric(precision=14, scale=6), nullable=True),
        sa.Column("long_output_per_mtok", sa.Numeric(precision=14, scale=6), nullable=True),
        sa.Column("source_note", sa.Text(), nullable=False),
        sa.Column("verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "(cache_read_per_mtok IS NULL OR cache_read_per_mtok >= 0) AND (cache_write_per_mtok IS NULL OR cache_write_per_mtok >= 0)",
            name=op.f("ck_model_pricing_cache_non_negative"),
        ),
        sa.CheckConstraint("input_per_mtok >= 0 AND output_per_mtok >= 0", name=op.f("ck_model_pricing_non_negative")),
        sa.CheckConstraint("length(source_note) > 0", name=op.f("ck_model_pricing_source_note")),
        sa.CheckConstraint(
            "long_context_threshold_tokens IS NULL OR (long_input_per_mtok IS NOT NULL AND long_output_per_mtok IS NOT NULL)",
            name=op.f("ck_model_pricing_long_context_complete"),
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_model_pricing_version")),
        sa.ForeignKeyConstraint(
            ["provider", "model"],
            ["ai_models.provider", "ai_models.model_id"],
            name=op.f("fk_model_pricing_provider_ai_models"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_pricing")),
        sa.UniqueConstraint("provider", "model", "version", name=op.f("uq_model_pricing_provider_model_version")),
    )
    op.create_table(
        "model_task_profiles",
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("effort", sa.Text(), nullable=True),
        sa.Column("max_output_tokens", sa.Integer(), nullable=False),
        sa.Column("timeout_s", sa.Integer(), server_default=sa.text("120"), nullable=False),
        sa.Column("schema_retry_max", sa.Integer(), server_default=sa.text("2"), nullable=False),
        sa.Column("fallback_provider", sa.Text(), nullable=True),
        sa.Column("fallback_model", sa.Text(), nullable=True),
        sa.Column("fallback_on", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "effort IS NULL OR effort IN ('low','medium','high','xhigh','max')",
            name=op.f("ck_model_task_profiles_effort"),
        ),
        sa.CheckConstraint(
            "fallback_on <@ ARRAY['PROVIDER_UNAVAILABLE']::text[]", name=op.f("ck_model_task_profiles_fallback_on")
        ),
        sa.CheckConstraint(
            "fallback_provider IS NULL OR (fallback_provider IN ('anthropic','openai') AND fallback_provider <> provider AND fallback_model IS NOT NULL)",
            name=op.f("ck_model_task_profiles_fallback"),
        ),
        sa.CheckConstraint("provider IN ('anthropic','openai','mock')", name=op.f("ck_model_task_profiles_provider")),
        sa.CheckConstraint(
            "max_output_tokens BETWEEN 1 AND 128000", name=op.f("ck_model_task_profiles_max_output_tokens")
        ),
        sa.CheckConstraint("schema_retry_max BETWEEN 0 AND 5", name=op.f("ck_model_task_profiles_schema_retry_max")),
        sa.CheckConstraint("timeout_s BETWEEN 5 AND 900", name=op.f("ck_model_task_profiles_timeout_s")),
        sa.ForeignKeyConstraint(
            ["provider", "model"],
            ["ai_models.provider", "ai_models.model_id"],
            name=op.f("fk_model_task_profiles_provider_ai_models"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_model_task_profiles")),
        sa.UniqueConstraint("task_type", name=op.f("uq_model_task_profiles_task_type")),
    )
    op.create_table(
        "job_schedules",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column(
            "params", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("cron_expr", sa.Text(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("misfire_policy", sa.Text(), server_default=sa.text("'RUN_ONCE'"), nullable=False),
        sa.Column("budget_limit_usd", sa.Numeric(precision=14, scale=6), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("misfire_policy IN ('SKIP','RUN_ONCE')", name=op.f("ck_job_schedules_misfire_policy")),
        sa.CheckConstraint(
            "budget_limit_usd IS NULL OR budget_limit_usd > 0", name=op.f("ck_job_schedules_budget_limit")
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_job_schedules_project_id_projects")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_schedules")),
        sa.UniqueConstraint("project_id", "name", name=op.f("uq_job_schedules_project_id_name")),
    )
    op.create_table(
        "agent_jobs",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("job_type", sa.Text(), nullable=False),
        sa.Column(
            "params", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'QUEUED'"), nullable=False),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column("schedule_id", sa.UUID(), nullable=True),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.Column("budget_limit_usd", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column(
            "cost_accumulated_usd", sa.Numeric(precision=14, scale=6), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("max_steps", sa.Integer(), nullable=False),
        sa.Column("max_ai_calls", sa.Integer(), nullable=False),
        sa.Column("timeout_s", sa.Integer(), nullable=False),
        sa.Column("step_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("ai_call_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_completed_seq", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("checkpoint", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("pause_requested", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("attempt", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default=sa.text("3"), nullable=False),
        sa.Column("status_reason_code", sa.Text(), nullable=True),
        sa.Column("status_reason_detail", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("queue_job_id", sa.BigInteger(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_agent_jobs_data_origin")),
        sa.CheckConstraint(
            "status IN ('QUEUED','RUNNING','PAUSED','PAUSED_BUDGET','RETRY_SCHEDULED','SUCCEEDED','FAILED','CANCELLED')",
            name=op.f("ck_agent_jobs_status"),
        ),
        sa.CheckConstraint("trigger IN ('MANUAL','SCHEDULE','RETRY')", name=op.f("ck_agent_jobs_trigger")),
        sa.CheckConstraint("budget_limit_usd > 0", name=op.f("ck_agent_jobs_budget_limit")),
        sa.CheckConstraint("last_completed_seq >= 0", name=op.f("ck_agent_jobs_last_completed_seq")),
        sa.CheckConstraint("max_attempts >= 1", name=op.f("ck_agent_jobs_max_attempts")),
        sa.CheckConstraint(
            "max_steps >= 1 AND max_ai_calls >= 1 AND timeout_s >= 1", name=op.f("ck_agent_jobs_limits")
        ),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_agent_jobs_project_id_projects")),
        sa.ForeignKeyConstraint(
            ["schedule_id"],
            ["job_schedules.id"],
            name=op.f("fk_agent_jobs_schedule_id_job_schedules"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_jobs")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_agent_jobs_idempotency_key")),
    )
    op.create_index("ix_agent_jobs_project_created", "agent_jobs", ["project_id", "created_at"], unique=False)
    op.create_index(
        "ix_agent_jobs_schedule_scheduled_for", "agent_jobs", ["schedule_id", "scheduled_for"], unique=False
    )
    op.create_index("ix_agent_jobs_status", "agent_jobs", ["status"], unique=False)
    op.create_table(
        "job_steps",
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("step_type", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("attempt", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.Column("input_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(precision=14, scale=6), server_default=sa.text("0"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_job_steps_data_origin")),
        sa.CheckConstraint(
            "status IN ('RUNNING','SUCCEEDED','FAILED','REFUSED','TRUNCATED','SKIPPED','BLOCKED')",
            name=op.f("ck_job_steps_status"),
        ),
        sa.CheckConstraint("step_type IN ('AI_CALL','TOOL_CALL','LOGIC')", name=op.f("ck_job_steps_step_type")),
        sa.CheckConstraint("seq >= 1", name=op.f("ck_job_steps_seq")),
        sa.ForeignKeyConstraint(
            ["job_id"], ["agent_jobs.id"], name=op.f("fk_job_steps_job_id_agent_jobs"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_job_steps")),
        sa.UniqueConstraint("job_id", "seq", name=op.f("uq_job_steps_job_id_seq")),
    )
    op.create_table(
        "tool_executions",
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("step_id", sa.UUID(), nullable=True),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column("tool_version", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("denial_reason", sa.Text(), nullable=True),
        sa.Column("input", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_tool_executions_data_origin")),
        sa.CheckConstraint(
            "status <> 'DENIED' OR denial_reason IS NOT NULL", name=op.f("ck_tool_executions_denied_has_reason")
        ),
        sa.CheckConstraint(
            "status IN ('SUCCEEDED','FAILED','DENIED','TIMEOUT')", name=op.f("ck_tool_executions_status")
        ),
        sa.ForeignKeyConstraint(
            ["job_id"], ["agent_jobs.id"], name=op.f("fk_tool_executions_job_id_agent_jobs"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["step_id"], ["job_steps.id"], name=op.f("fk_tool_executions_step_id_job_steps"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tool_executions")),
    )
    op.create_index("ix_tool_executions_job_id", "tool_executions", ["job_id"], unique=False)
    op.create_table(
        "ai_usage_logs",
        sa.Column("job_id", sa.UUID(), nullable=True),
        sa.Column("step_id", sa.UUID(), nullable=True),
        sa.Column("provider", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.Column("is_fallback", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("provider_request_id", sa.Text(), nullable=True),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("billing_status", sa.Text(), nullable=False),
        sa.Column("sent", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("stop_reason", sa.Text(), nullable=True),
        sa.Column("refusal_category", sa.Text(), nullable=True),
        sa.Column("refusal_explanation", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("output_tokens", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("cache_read_tokens", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("cache_write_tokens", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("cost_usd", sa.Numeric(precision=14, scale=6), server_default=sa.text("0"), nullable=False),
        sa.Column("pricing_id", sa.UUID(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "billing_status IN ('BILLED','NOT_BILLED','UNCERTAIN')", name=op.f("ck_ai_usage_logs_billing_status")
        ),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_ai_usage_logs_data_origin")),
        sa.CheckConstraint(
            "outcome IN ('SUCCESS','SCHEMA_INVALID','TIMEOUT','RATE_LIMITED','AUTH_ERROR','NETWORK_ERROR','PROVIDER_ERROR','BAD_REQUEST','REFUSED','TRUNCATED')",
            name=op.f("ck_ai_usage_logs_outcome"),
        ),
        sa.CheckConstraint("cost_usd >= 0", name=op.f("ck_ai_usage_logs_cost")),
        sa.CheckConstraint(
            "input_tokens >= 0 AND output_tokens >= 0 AND cache_read_tokens >= 0 AND cache_write_tokens >= 0",
            name=op.f("ck_ai_usage_logs_tokens"),
        ),
        sa.ForeignKeyConstraint(["job_id"], ["agent_jobs.id"], name=op.f("fk_ai_usage_logs_job_id_agent_jobs")),
        sa.ForeignKeyConstraint(
            ["pricing_id"], ["model_pricing.id"], name=op.f("fk_ai_usage_logs_pricing_id_model_pricing")
        ),
        sa.ForeignKeyConstraint(["step_id"], ["job_steps.id"], name=op.f("fk_ai_usage_logs_step_id_job_steps")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_usage_logs")),
    )
    op.create_index("ix_ai_usage_logs_job_id", "ai_usage_logs", ["job_id"], unique=False)
    op.create_index("ix_ai_usage_logs_origin_created", "ai_usage_logs", ["data_origin", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_table("ai_usage_logs")
    op.drop_table("tool_executions")
    op.drop_table("job_steps")
    op.drop_table("agent_jobs")
    op.drop_table("job_schedules")
    op.drop_table("model_task_profiles")
    op.drop_table("model_pricing")
    op.drop_table("ai_models")
