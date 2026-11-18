"""0007_evidence – research_sources, research_evidence (data-model.md §14, FR-007).

E0 chỉ tạo cấu trúc; không có dữ liệu nghiên cứu.

Revision ID: 0007_evidence
Revises: 0006_budget
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_evidence"
down_revision = "0006_budget"
branch_labels = None
depends_on = None

SOURCE_TYPES = "'WEB_PAGE','FORUM','REVIEW_SITE','VIDEO','API','DOCUMENT','OTHER'"
STATUSES = "'VERIFIED','INFERRED','UNKNOWN','CONFLICTING'"


def _common() -> list[sa.Column]:  # type: ignore[type-arg]
    return [
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "research_sources",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("publisher", sa.Text(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("data_origin", sa.Text(), nullable=False),
        *_common(),
        sa.CheckConstraint(f"source_type IN ({SOURCE_TYPES})", name=op.f("ck_research_sources_source_type")),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_research_sources_data_origin")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_research_sources_project_id_projects")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_research_sources")),
        sa.UniqueConstraint(
            "project_id",
            "canonical_url",
            "content_hash",
            name=op.f("uq_research_sources_project_id_canonical_url_content_hash"),
        ),
    )
    op.create_table(
        "research_evidence",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=True),
        sa.Column("subject_type", sa.Text(), nullable=True),
        sa.Column("subject_id", sa.UUID(), nullable=True),
        sa.Column("claim_key", sa.Text(), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("verification_status", sa.Text(), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collected_by_job_id", sa.UUID(), nullable=True),
        sa.Column("data_origin", sa.Text(), nullable=False),
        *_common(),
        sa.CheckConstraint(
            f"verification_status IN ({STATUSES})", name=op.f("ck_research_evidence_verification_status")
        ),
        sa.CheckConstraint(
            "verification_status <> 'VERIFIED' OR source_id IS NOT NULL",
            name=op.f("ck_research_evidence_verified_has_source"),
        ),
        sa.CheckConstraint(
            "verification_status <> 'UNKNOWN' OR value IS NULL", name=op.f("ck_research_evidence_unknown_has_no_value")
        ),
        sa.CheckConstraint(
            "excerpt IS NULL OR length(excerpt) <= 1000", name=op.f("ck_research_evidence_excerpt_length")
        ),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_research_evidence_data_origin")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_research_evidence_project_id_projects")),
        sa.ForeignKeyConstraint(
            ["source_id"], ["research_sources.id"], name=op.f("fk_research_evidence_source_id_research_sources")
        ),
        sa.ForeignKeyConstraint(
            ["collected_by_job_id"],
            ["agent_jobs.id"],
            name=op.f("fk_research_evidence_collected_by_job_id_agent_jobs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_research_evidence")),
    )
    op.create_index("ix_research_evidence_project_claim", "research_evidence", ["project_id", "claim_key"])
    op.create_index("ix_research_evidence_subject", "research_evidence", ["subject_type", "subject_id"])


def downgrade() -> None:
    op.drop_index("ix_research_evidence_subject", table_name="research_evidence")
    op.drop_index("ix_research_evidence_project_claim", table_name="research_evidence")
    op.drop_table("research_evidence")
    op.drop_table("research_sources")
