"""0006_budget – budget_reservations (data-model.md §11).

Revision ID: 0006_budget
Revises: 0005_seed_ai
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql  # noqa: F401

revision = "0006_budget"
down_revision = "0005_seed_ai"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "budget_reservations",
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("step_id", sa.UUID(), nullable=True),
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.Column("amount_usd", sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'ACTIVE'"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("usage_log_id", sa.UUID(), nullable=True),
        sa.Column("actual_usd", sa.Numeric(precision=14, scale=6), nullable=True),
        sa.Column("release_reason", sa.Text(), nullable=True),
        sa.Column("uncertain_reason", sa.Text(), nullable=True),
        sa.Column("resolved_by", sa.UUID(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_budget_reservations_data_origin")),
        sa.CheckConstraint(
            "status <> 'RELEASED' OR release_reason IS NOT NULL",
            name=op.f("ck_budget_reservations_released_has_reason"),
        ),
        sa.CheckConstraint(
            "status <> 'UNCERTAIN' OR uncertain_reason IS NOT NULL",
            name=op.f("ck_budget_reservations_uncertain_has_reason"),
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','SETTLED','RELEASED','UNCERTAIN','RESOLVED')",
            name=op.f("ck_budget_reservations_status"),
        ),
        sa.CheckConstraint(
            "uncertain_reason IS NULL OR uncertain_reason IN ('TIMEOUT_AFTER_SEND','CONNECTION_LOST','WORKER_LOST','USAGE_UNREADABLE','ERROR_BILLING_UNVERIFIED')",
            name=op.f("ck_budget_reservations_uncertain_reason"),
        ),
        sa.CheckConstraint("actual_usd IS NULL OR actual_usd >= 0", name=op.f("ck_budget_reservations_actual")),
        sa.CheckConstraint("amount_usd > 0", name=op.f("ck_budget_reservations_amount")),
        sa.ForeignKeyConstraint(["job_id"], ["agent_jobs.id"], name=op.f("fk_budget_reservations_job_id_agent_jobs")),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], name=op.f("fk_budget_reservations_resolved_by_users")),
        sa.ForeignKeyConstraint(["step_id"], ["job_steps.id"], name=op.f("fk_budget_reservations_step_id_job_steps")),
        sa.ForeignKeyConstraint(
            ["usage_log_id"], ["ai_usage_logs.id"], name=op.f("fk_budget_reservations_usage_log_id_ai_usage_logs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_budget_reservations")),
    )
    op.create_index("ix_budget_reservations_job_id", "budget_reservations", ["job_id"], unique=False)
    op.create_index(
        "ix_budget_reservations_origin_status_created",
        "budget_reservations",
        ["data_origin", "status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("budget_reservations")
