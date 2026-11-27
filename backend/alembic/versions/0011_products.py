"""0011_products – bảng E2 Product & Affiliate Discovery (specs/003-product-affiliate-discovery/data-model.md §2; T012–T013).

Sinh bằng autogenerate từ ORM `modules/products/models.py`, bổ sung trigger bất biến cho `product_evaluations` (như niche_evaluations E1).
Không sửa bảng E0/E1.

Revision ID: 0011_products
Revises: 0010_discovery_seed
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0011_products"
down_revision = "0010_discovery_seed"
branch_labels = None
depends_on = None

IMMUTABLE_FN = """
CREATE OR REPLACE FUNCTION product_evaluations_immutable() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'product_evaluations is append-only (E2 data-model §2)';
END;
$$ LANGUAGE plpgsql
"""


def upgrade() -> None:
    op.create_table(
        "affiliate_programs",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("operator_type", sa.Text(), server_default=sa.text("'UNKNOWN'"), nullable=False),
        sa.Column("operator_name", sa.Text(), nullable=True),
        sa.Column("operator_domain", sa.Text(), nullable=True),
        sa.Column("terms_url", sa.Text(), nullable=True),
        sa.Column("dedup_key", sa.Text(), nullable=False),
        sa.Column("verification_status", sa.Text(), server_default=sa.text("'UNVERIFIED'"), nullable=False),
        sa.Column("watch_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_check_error", sa.Text(), nullable=True),
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_affiliate_programs_data_origin")),
        sa.CheckConstraint(
            "operator_type IN ('VENDOR','NETWORK','UNKNOWN')", name=op.f("ck_affiliate_programs_operator_type")
        ),
        sa.CheckConstraint(
            "verification_status IN ('VERIFIED','PARTIAL','UNVERIFIED','CLOSED')",
            name=op.f("ck_affiliate_programs_verification_status"),
        ),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 200", name=op.f("ck_affiliate_programs_name")),
        sa.CheckConstraint(
            "operator_domain IS NULL OR operator_domain = lower(operator_domain)",
            name=op.f("ck_affiliate_programs_operator_domain"),
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_affiliate_programs_project_id_projects")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_affiliate_programs")),
        sa.UniqueConstraint(
            "project_id",
            "data_origin",
            "dedup_key",
            name=op.f("uq_affiliate_programs_project_id_data_origin_dedup_key"),
        ),
    )
    op.create_table(
        "product_scoring_weights",
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("weights", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "rubric", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("coverage_min", sa.Numeric(precision=5, scale=2), server_default=sa.text("60"), nullable=False),
        sa.Column(
            "confidence_params",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "query_templates",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "non_official_domains", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("coverage_min BETWEEN 0 AND 100", name=op.f("ck_product_scoring_weights_coverage_min")),
        sa.CheckConstraint("version >= 1", name=op.f("ck_product_scoring_weights_version")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_product_scoring_weights_created_by_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_scoring_weights")),
        sa.UniqueConstraint("version", name=op.f("uq_product_scoring_weights_version")),
    )
    op.create_index(
        "uq_product_scoring_weights_active",
        "product_scoring_weights",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "products",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("vendor", sa.Text(), nullable=True),
        sa.Column("official_domain", sa.Text(), nullable=True),
        sa.Column("official_url", sa.Text(), nullable=True),
        sa.Column("dedup_key", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), server_default=sa.text("'UNKNOWN'"), nullable=False),
        sa.Column("risk_flags", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
        sa.Column("merged_into_id", sa.UUID(), nullable=True),
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "category IN ('PHYSICAL','SOFTWARE','DIGITAL','UNKNOWN')", name=op.f("ck_products_category")
        ),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_products_data_origin")),
        sa.CheckConstraint("risk_flags <@ ARRAY['COMPLIANCE_SENSITIVE']::text[]", name=op.f("ck_products_risk_flags")),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 200", name=op.f("ck_products_name")),
        sa.CheckConstraint("merged_into_id IS NULL OR merged_into_id <> id", name=op.f("ck_products_merged_into")),
        sa.CheckConstraint(
            "official_domain IS NULL OR official_domain = lower(official_domain)",
            name=op.f("ck_products_official_domain"),
        ),
        sa.ForeignKeyConstraint(["merged_into_id"], ["products.id"], name=op.f("fk_products_merged_into_id_products")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_products_project_id_projects")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_products")),
        sa.UniqueConstraint(
            "project_id", "data_origin", "dedup_key", name=op.f("uq_products_project_id_data_origin_dedup_key")
        ),
    )
    op.create_table(
        "product_programs",
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("program_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], name=op.f("fk_product_programs_product_id_products")),
        sa.ForeignKeyConstraint(
            ["program_id"], ["affiliate_programs.id"], name=op.f("fk_product_programs_program_id_affiliate_programs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_programs")),
        sa.UniqueConstraint("product_id", "program_id", name=op.f("uq_product_programs_product_id_program_id")),
    )
    op.create_table(
        "product_runs",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("niche_id", sa.UUID(), nullable=False),
        sa.Column(
            "params", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("stop_reason", sa.Text(), nullable=True),
        sa.Column(
            "metrics", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_product_runs_data_origin")),
        sa.CheckConstraint("jsonb_typeof(metrics) = 'object'", name=op.f("ck_product_runs_metrics")),
        sa.CheckConstraint("jsonb_typeof(params) = 'object'", name=op.f("ck_product_runs_params")),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('COMPLETED','PARTIAL_COMPLETED','FAILED')",
            name=op.f("ck_product_runs_outcome"),
        ),
        sa.ForeignKeyConstraint(["job_id"], ["agent_jobs.id"], name=op.f("fk_product_runs_job_id_agent_jobs")),
        sa.ForeignKeyConstraint(["niche_id"], ["niches.id"], name=op.f("fk_product_runs_niche_id_niches")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_product_runs_project_id_projects")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_runs")),
        sa.UniqueConstraint("job_id", name=op.f("uq_product_runs_job_id")),
    )
    op.create_index("ix_product_runs_niche", "product_runs", ["niche_id"], unique=False)
    op.create_table(
        "program_terms_versions",
        sa.Column("program_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "changes", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_program_terms_versions_data_origin")),
        sa.CheckConstraint("version >= 1", name=op.f("ck_program_terms_versions_version")),
        sa.ForeignKeyConstraint(
            ["job_id"], ["agent_jobs.id"], name=op.f("fk_program_terms_versions_job_id_agent_jobs")
        ),
        sa.ForeignKeyConstraint(
            ["program_id"],
            ["affiliate_programs.id"],
            name=op.f("fk_program_terms_versions_program_id_affiliate_programs"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_program_terms_versions")),
        sa.UniqueConstraint("program_id", "version", name=op.f("uq_program_terms_versions_program_id_version")),
    )
    op.create_table(
        "product_niches",
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("niche_id", sa.UUID(), nullable=False),
        sa.Column("first_run_id", sa.UUID(), nullable=True),
        sa.Column("readiness_status", sa.Text(), server_default=sa.text("'NO_PROGRAM'"), nullable=False),
        sa.Column("risk_flags", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
        sa.Column("persona_match", sa.Text(), server_default=sa.text("'UNKNOWN'"), nullable=False),
        sa.Column("ai_recommendation", sa.Text(), server_default=sa.text("'UNKNOWN'"), nullable=False),
        sa.Column("ai_recommendation_reason", sa.Text(), nullable=True),
        sa.Column(
            "ai_levels", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("decision_status", sa.Text(), server_default=sa.text("'CANDIDATE'"), nullable=False),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "ai_recommendation IN ('SELECT','REJECT','UNKNOWN')", name=op.f("ck_product_niches_ai_recommendation")
        ),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_product_niches_data_origin")),
        sa.CheckConstraint(
            "decision_status = 'CANDIDATE' OR (decided_by IS NOT NULL AND char_length(decision_reason) BETWEEN 1 AND 1000)",
            name=op.f("ck_product_niches_decision_reason"),
        ),
        sa.CheckConstraint(
            "decision_status IN ('CANDIDATE','SELECTED','WATCH','REJECTED')",
            name=op.f("ck_product_niches_decision_status"),
        ),
        sa.CheckConstraint(
            "persona_match IN ('MATCH','PARTIAL','NO_MATCH','UNKNOWN')", name=op.f("ck_product_niches_persona_match")
        ),
        sa.CheckConstraint(
            "readiness_status IN ('READY_TO_PROMOTE','ELIGIBILITY_UNVERIFIED','NOT_ELIGIBLE','AFFILIATE_UNVERIFIED','NO_PROGRAM','PROGRAM_CLOSED')",
            name=op.f("ck_product_niches_readiness_status"),
        ),
        sa.CheckConstraint(
            "risk_flags <@ ARRAY['MONETIZATION_RISK','MARKET_NOT_ALLOWED','MARKET_UNKNOWN','COMPLIANCE_SENSITIVE']::text[]",
            name=op.f("ck_product_niches_risk_flags"),
        ),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], name=op.f("fk_product_niches_decided_by_users")),
        sa.ForeignKeyConstraint(
            ["first_run_id"], ["product_runs.id"], name=op.f("fk_product_niches_first_run_id_product_runs")
        ),
        sa.ForeignKeyConstraint(["niche_id"], ["niches.id"], name=op.f("fk_product_niches_niche_id_niches")),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], name=op.f("fk_product_niches_product_id_products")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_niches")),
        sa.UniqueConstraint("product_id", "niche_id", name=op.f("uq_product_niches_product_id_niche_id")),
    )
    op.create_index("ix_product_niches_niche", "product_niches", ["niche_id"], unique=False)
    op.create_table(
        "product_evaluations",
        sa.Column("product_niche_id", sa.UUID(), nullable=False),
        sa.Column("weights_version_id", sa.UUID(), nullable=False),
        sa.Column("opportunity_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("coverage", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("scoring_status", sa.Text(), nullable=False),
        sa.Column("criteria", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence_components", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("missing", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
        sa.Column("evidence_fingerprint", sa.Text(), nullable=False),
        sa.Column("computed_without_ai", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "(scoring_status = 'SCORED') = (opportunity_score IS NOT NULL)",
            name=op.f("ck_product_evaluations_scored_has_opportunity"),
        ),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_product_evaluations_data_origin")),
        sa.CheckConstraint(
            "scoring_status IN ('SCORED','INSUFFICIENT_SCORING_DATA')",
            name=op.f("ck_product_evaluations_scoring_status"),
        ),
        sa.CheckConstraint("confidence_score BETWEEN 0 AND 100", name=op.f("ck_product_evaluations_confidence_score")),
        sa.CheckConstraint("coverage BETWEEN 0 AND 100", name=op.f("ck_product_evaluations_coverage")),
        sa.CheckConstraint(
            "opportunity_score IS NULL OR (opportunity_score BETWEEN 0 AND 100)",
            name=op.f("ck_product_evaluations_opportunity_score"),
        ),
        sa.ForeignKeyConstraint(
            ["product_niche_id"],
            ["product_niches.id"],
            name=op.f("fk_product_evaluations_product_niche_id_product_niches"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["product_runs.id"], name=op.f("fk_product_evaluations_run_id_product_runs")
        ),
        sa.ForeignKeyConstraint(
            ["weights_version_id"],
            ["product_scoring_weights.id"],
            name=op.f("fk_product_evaluations_weights_version_id_product_scoring_weights"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_evaluations")),
    )
    op.create_index(
        "ix_product_evaluations_pair", "product_evaluations", ["product_niche_id", "created_at"], unique=False
    )
    op.create_table(
        "product_pain_point_links",
        sa.Column("product_niche_id", sa.UUID(), nullable=False),
        sa.Column("pain_point_id", sa.UUID(), nullable=False),
        sa.Column("evidence_id", sa.UUID(), nullable=False),
        sa.Column("verification_status", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "verification_status IN ('VERIFIED','INFERRED')",
            name=op.f("ck_product_pain_point_links_verification_status"),
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["research_evidence.id"],
            name=op.f("fk_product_pain_point_links_evidence_id_research_evidence"),
        ),
        sa.ForeignKeyConstraint(
            ["pain_point_id"], ["pain_points.id"], name=op.f("fk_product_pain_point_links_pain_point_id_pain_points")
        ),
        sa.ForeignKeyConstraint(
            ["product_niche_id"],
            ["product_niches.id"],
            name=op.f("fk_product_pain_point_links_product_niche_id_product_niches"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_product_pain_point_links")),
        sa.UniqueConstraint(
            "product_niche_id",
            "pain_point_id",
            "evidence_id",
            name=op.f("uq_product_pain_point_links_product_niche_id_pain_point_id_evidence_id"),
        ),
    )
    op.execute(IMMUTABLE_FN)
    op.execute(
        "CREATE TRIGGER trg_product_evaluations_immutable BEFORE UPDATE OR DELETE ON product_evaluations"
        " FOR EACH ROW EXECUTE FUNCTION product_evaluations_immutable()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_product_evaluations_immutable ON product_evaluations")
    op.execute("DROP FUNCTION IF EXISTS product_evaluations_immutable()")
    op.drop_table("product_pain_point_links")
    op.drop_index("ix_product_evaluations_pair", table_name="product_evaluations")
    op.drop_table("product_evaluations")
    op.drop_index("ix_product_niches_niche", table_name="product_niches")
    op.drop_table("product_niches")
    op.drop_table("program_terms_versions")
    op.drop_index("ix_product_runs_niche", table_name="product_runs")
    op.drop_table("product_runs")
    op.drop_table("product_programs")
    op.drop_table("products")
    op.drop_index(
        "uq_product_scoring_weights_active", table_name="product_scoring_weights", postgresql_where=sa.text("is_active")
    )
    op.drop_table("product_scoring_weights")
    op.drop_table("affiliate_programs")
