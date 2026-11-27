"""0013_keywords – bảng E3 Keyword & Audience Research (specs/004-keyword-audience-research/data-model.md §2; T010–T011).

Sinh bằng autogenerate từ ORM `modules/keywords/models.py`; FK vòng `keyword_clusters.primary_keyword_id` tạo sau bảng `keywords`;
trigger bất biến cho `keyword_evaluations` (như product_evaluations E2). Không sửa bảng E0/E1/E2.

Revision ID: 0013_keywords
Revises: 0012_products_seed
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0013_keywords"
down_revision = "0012_products_seed"
branch_labels = None
depends_on = None

IMMUTABLE_FN = """
CREATE OR REPLACE FUNCTION keyword_evaluations_immutable() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'keyword_evaluations is append-only (E3 data-model §2)';
END;
$$ LANGUAGE plpgsql
"""


def upgrade() -> None:
    op.create_table(
        "keyword_scoring_weights",
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
            "templates", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("coverage_min BETWEEN 0 AND 100", name=op.f("ck_keyword_scoring_weights_coverage_min")),
        sa.CheckConstraint("version >= 1", name=op.f("ck_keyword_scoring_weights_version")),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name=op.f("fk_keyword_scoring_weights_created_by_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_keyword_scoring_weights")),
        sa.UniqueConstraint("version", name=op.f("uq_keyword_scoring_weights_version")),
    )
    op.create_index(
        "uq_keyword_scoring_weights_active",
        "keyword_scoring_weights",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "keyword_clusters",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("niche_id", sa.UUID(), nullable=False),
        sa.Column("cluster_key", sa.Text(), nullable=False),
        sa.Column("primary_keyword_id", sa.UUID(), nullable=True),
        sa.Column("intent", sa.Text(), nullable=False),
        sa.Column("pain_point_id", sa.UUID(), nullable=True),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column(
            "insights", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("decision_status", sa.Text(), server_default=sa.text("'CANDIDATE'"), nullable=False),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("watch_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_check_error", sa.Text(), nullable=True),
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_keyword_clusters_data_origin")),
        sa.CheckConstraint(
            "decision_status = 'CANDIDATE' OR (decided_by IS NOT NULL AND char_length(decision_reason) BETWEEN 1 AND 1000)",
            name=op.f("ck_keyword_clusters_decision_reason"),
        ),
        sa.CheckConstraint(
            "decision_status IN ('CANDIDATE','SELECTED','WATCH','REJECTED')",
            name=op.f("ck_keyword_clusters_decision_status"),
        ),
        sa.CheckConstraint(
            "intent IN ('INFORMATIONAL','COMMERCIAL_INVESTIGATION','TRANSACTIONAL','NAVIGATIONAL')",
            name=op.f("ck_keyword_clusters_intent"),
        ),
        sa.CheckConstraint("jsonb_typeof(insights) = 'object'", name=op.f("ck_keyword_clusters_insights")),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], name=op.f("fk_keyword_clusters_decided_by_users")),
        sa.ForeignKeyConstraint(["niche_id"], ["niches.id"], name=op.f("fk_keyword_clusters_niche_id_niches")),
        sa.ForeignKeyConstraint(
            ["pain_point_id"], ["pain_points.id"], name=op.f("fk_keyword_clusters_pain_point_id_pain_points")
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], name=op.f("fk_keyword_clusters_product_id_products")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_keyword_clusters_project_id_projects")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_keyword_clusters")),
        sa.UniqueConstraint(
            "niche_id", "data_origin", "cluster_key", name=op.f("uq_keyword_clusters_niche_id_data_origin_cluster_key")
        ),
    )
    op.create_table(
        "keyword_runs",
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
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_keyword_runs_data_origin")),
        sa.CheckConstraint("jsonb_typeof(metrics) = 'object'", name=op.f("ck_keyword_runs_metrics")),
        sa.CheckConstraint("jsonb_typeof(params) = 'object'", name=op.f("ck_keyword_runs_params")),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('COMPLETED','PARTIAL_COMPLETED','FAILED')",
            name=op.f("ck_keyword_runs_outcome"),
        ),
        sa.ForeignKeyConstraint(["job_id"], ["agent_jobs.id"], name=op.f("fk_keyword_runs_job_id_agent_jobs")),
        sa.ForeignKeyConstraint(["niche_id"], ["niches.id"], name=op.f("fk_keyword_runs_niche_id_niches")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_keyword_runs_project_id_projects")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_keyword_runs")),
        sa.UniqueConstraint("job_id", name=op.f("uq_keyword_runs_job_id")),
    )
    op.create_index("ix_keyword_runs_niche", "keyword_runs", ["niche_id"], unique=False)
    op.create_table(
        "keywords",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("niche_id", sa.UUID(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("normalized", sa.Text(), nullable=False),
        sa.Column("dedup_key", sa.Text(), nullable=False),
        sa.Column("language", sa.Text(), server_default=sa.text("'en'"), nullable=False),
        sa.Column("market", sa.Text(), server_default=sa.text("'US'"), nullable=False),
        sa.Column("keyword_type", sa.Text(), nullable=False),
        sa.Column("length_class", sa.Text(), nullable=False),
        sa.Column("intent", sa.Text(), nullable=False),
        sa.Column("intent_status", sa.Text(), server_default=sa.text("'INFERRED'"), nullable=False),
        sa.Column("intent_reason", sa.Text(), nullable=True),
        sa.Column("search_volume", sa.Integer(), nullable=True),
        sa.Column("cpc", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("keyword_difficulty", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("metrics_source", sa.Text(), nullable=True),
        sa.Column("metrics_collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metrics_market", sa.Text(), nullable=True),
        sa.Column("risk_flags", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
        sa.Column("cluster_id", sa.UUID(), nullable=True),
        sa.Column(
            "ai_levels", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("first_run_id", sa.UUID(), nullable=True),
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_keywords_data_origin")),
        sa.CheckConstraint(
            "intent IN ('INFORMATIONAL','COMMERCIAL_INVESTIGATION','TRANSACTIONAL','NAVIGATIONAL')",
            name=op.f("ck_keywords_intent"),
        ),
        sa.CheckConstraint("intent_status IN ('INFERRED','VERIFIED')", name=op.f("ck_keywords_intent_status")),
        sa.CheckConstraint(
            "keyword_type IN ('PROBLEM','SOLUTION','PRODUCT','COMPARISON','INFORMATIONAL')",
            name=op.f("ck_keywords_keyword_type"),
        ),
        sa.CheckConstraint("language ~ '^[a-z]{2}$'", name=op.f("ck_keywords_language")),
        sa.CheckConstraint("length_class IN ('HEAD','MID','LONG_TAIL')", name=op.f("ck_keywords_length_class")),
        sa.CheckConstraint("market ~ '^[A-Z]{2}$'", name=op.f("ck_keywords_market")),
        sa.CheckConstraint(
            "risk_flags <@ ARRAY['BRAND_TERM','COMPLIANCE_SENSITIVE']::text[]", name=op.f("ck_keywords_risk_flags")
        ),
        sa.CheckConstraint("char_length(text) BETWEEN 2 AND 150", name=op.f("ck_keywords_text")),
        sa.CheckConstraint(
            "cpc IS NULL OR (metrics_source IS NOT NULL AND metrics_collected_at IS NOT NULL AND metrics_market IS NOT NULL)",
            name=op.f("ck_keywords_cpc_sourced"),
        ),
        sa.CheckConstraint("cpc IS NULL OR cpc >= 0", name=op.f("ck_keywords_cpc")),
        sa.CheckConstraint(
            "keyword_difficulty IS NULL OR (keyword_difficulty BETWEEN 0 AND 100)",
            name=op.f("ck_keywords_keyword_difficulty"),
        ),
        sa.CheckConstraint(
            "keyword_difficulty IS NULL OR (metrics_source IS NOT NULL AND metrics_collected_at IS NOT NULL AND metrics_market IS NOT NULL)",
            name=op.f("ck_keywords_keyword_difficulty_sourced"),
        ),
        sa.CheckConstraint(
            "search_volume IS NULL OR (metrics_source IS NOT NULL AND metrics_collected_at IS NOT NULL AND metrics_market IS NOT NULL)",
            name=op.f("ck_keywords_search_volume_sourced"),
        ),
        sa.CheckConstraint("search_volume IS NULL OR search_volume >= 0", name=op.f("ck_keywords_search_volume")),
        sa.ForeignKeyConstraint(
            ["cluster_id"], ["keyword_clusters.id"], name=op.f("fk_keywords_cluster_id_keyword_clusters")
        ),
        sa.ForeignKeyConstraint(
            ["first_run_id"], ["keyword_runs.id"], name=op.f("fk_keywords_first_run_id_keyword_runs")
        ),
        sa.ForeignKeyConstraint(["niche_id"], ["niches.id"], name=op.f("fk_keywords_niche_id_niches")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_keywords_project_id_projects")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_keywords")),
        sa.UniqueConstraint(
            "project_id",
            "niche_id",
            "data_origin",
            "dedup_key",
            name=op.f("uq_keywords_project_id_niche_id_data_origin_dedup_key"),
        ),
    )
    op.create_index("ix_keywords_cluster", "keywords", ["cluster_id"], unique=False)
    op.create_index("ix_keywords_niche", "keywords", ["niche_id"], unique=False)
    op.create_table(
        "competitor_pages",
        sa.Column("keyword_id", sa.UUID(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("evidence_id", sa.UUID(), nullable=True),
        sa.Column(
            "summary", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_competitor_pages_data_origin")),
        sa.CheckConstraint("jsonb_typeof(summary) = 'object'", name=op.f("ck_competitor_pages_summary")),
        sa.ForeignKeyConstraint(
            ["evidence_id"], ["research_evidence.id"], name=op.f("fk_competitor_pages_evidence_id_research_evidence")
        ),
        sa.ForeignKeyConstraint(["keyword_id"], ["keywords.id"], name=op.f("fk_competitor_pages_keyword_id_keywords")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_competitor_pages")),
        sa.UniqueConstraint("keyword_id", "url", name=op.f("uq_competitor_pages_keyword_id_url")),
    )
    op.create_table(
        "keyword_evaluations",
        sa.Column("keyword_id", sa.UUID(), nullable=False),
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
            name=op.f("ck_keyword_evaluations_scored_has_opportunity"),
        ),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_keyword_evaluations_data_origin")),
        sa.CheckConstraint(
            "scoring_status IN ('SCORED','INSUFFICIENT_SCORING_DATA')",
            name=op.f("ck_keyword_evaluations_scoring_status"),
        ),
        sa.CheckConstraint("confidence_score BETWEEN 0 AND 100", name=op.f("ck_keyword_evaluations_confidence_score")),
        sa.CheckConstraint("coverage BETWEEN 0 AND 100", name=op.f("ck_keyword_evaluations_coverage")),
        sa.CheckConstraint(
            "opportunity_score IS NULL OR (opportunity_score BETWEEN 0 AND 100)",
            name=op.f("ck_keyword_evaluations_opportunity_score"),
        ),
        sa.ForeignKeyConstraint(
            ["keyword_id"], ["keywords.id"], name=op.f("fk_keyword_evaluations_keyword_id_keywords")
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["keyword_runs.id"], name=op.f("fk_keyword_evaluations_run_id_keyword_runs")
        ),
        sa.ForeignKeyConstraint(
            ["weights_version_id"],
            ["keyword_scoring_weights.id"],
            name=op.f("fk_keyword_evaluations_weights_version_id_keyword_scoring_weights"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_keyword_evaluations")),
    )
    op.create_index("ix_keyword_evaluations_keyword", "keyword_evaluations", ["keyword_id", "created_at"], unique=False)
    op.create_table(
        "keyword_origins",
        sa.Column("keyword_id", sa.UUID(), nullable=False),
        sa.Column("origin_type", sa.Text(), nullable=False),
        sa.Column("pain_point_id", sa.UUID(), nullable=True),
        sa.Column("product_id", sa.UUID(), nullable=True),
        sa.Column("persona_attribute", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "(origin_type = 'PAIN_POINT' AND pain_point_id IS NOT NULL AND product_id IS NULL AND persona_attribute IS NULL) OR (origin_type = 'PRODUCT' AND product_id IS NOT NULL AND pain_point_id IS NULL AND persona_attribute IS NULL) OR (origin_type = 'PERSONA' AND persona_attribute IS NOT NULL AND pain_point_id IS NULL AND product_id IS NULL)",
            name=op.f("ck_keyword_origins_origin_ref"),
        ),
        sa.CheckConstraint(
            "origin_type IN ('PAIN_POINT','PERSONA','PRODUCT')", name=op.f("ck_keyword_origins_origin_type")
        ),
        sa.ForeignKeyConstraint(["keyword_id"], ["keywords.id"], name=op.f("fk_keyword_origins_keyword_id_keywords")),
        sa.ForeignKeyConstraint(
            ["pain_point_id"], ["pain_points.id"], name=op.f("fk_keyword_origins_pain_point_id_pain_points")
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], name=op.f("fk_keyword_origins_product_id_products")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_keyword_origins")),
    )
    op.create_index(
        "uq_keyword_origins_ref",
        "keyword_origins",
        [
            "keyword_id",
            "origin_type",
            sa.literal_column("coalesce(pain_point_id::text, '')"),
            sa.literal_column("coalesce(product_id::text, '')"),
            sa.literal_column("coalesce(persona_attribute, '')"),
        ],
        unique=True,
    )
    op.create_table(
        "serp_observations",
        sa.Column("keyword_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("results", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_policy_id", sa.UUID(), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "changes", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("job_id", sa.UUID(), nullable=True),
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_serp_observations_data_origin")),
        sa.CheckConstraint("jsonb_typeof(results) = 'array'", name=op.f("ck_serp_observations_results")),
        sa.CheckConstraint("version >= 1", name=op.f("ck_serp_observations_version")),
        sa.ForeignKeyConstraint(["job_id"], ["agent_jobs.id"], name=op.f("fk_serp_observations_job_id_agent_jobs")),
        sa.ForeignKeyConstraint(["keyword_id"], ["keywords.id"], name=op.f("fk_serp_observations_keyword_id_keywords")),
        sa.ForeignKeyConstraint(
            ["source_policy_id"],
            ["source_policies.id"],
            name=op.f("fk_serp_observations_source_policy_id_source_policies"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_serp_observations")),
        sa.UniqueConstraint("keyword_id", "version", name=op.f("uq_serp_observations_keyword_id_version")),
    )
    op.create_foreign_key(
        "fk_keyword_clusters_primary_keyword_id", "keyword_clusters", "keywords", ["primary_keyword_id"], ["id"]
    )
    op.execute(IMMUTABLE_FN)
    op.execute(
        "CREATE TRIGGER trg_keyword_evaluations_immutable BEFORE UPDATE OR DELETE ON keyword_evaluations"
        " FOR EACH ROW EXECUTE FUNCTION keyword_evaluations_immutable()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_keyword_evaluations_immutable ON keyword_evaluations")
    op.execute("DROP FUNCTION IF EXISTS keyword_evaluations_immutable()")
    op.drop_constraint("fk_keyword_clusters_primary_keyword_id", "keyword_clusters", type_="foreignkey")
    op.drop_table("serp_observations")
    op.drop_index("uq_keyword_origins_ref", table_name="keyword_origins")
    op.drop_table("keyword_origins")
    op.drop_index("ix_keyword_evaluations_keyword", table_name="keyword_evaluations")
    op.drop_table("keyword_evaluations")
    op.drop_table("competitor_pages")
    op.drop_index("ix_keywords_niche", table_name="keywords")
    op.drop_index("ix_keywords_cluster", table_name="keywords")
    op.drop_table("keywords")
    op.drop_index("ix_keyword_runs_niche", table_name="keyword_runs")
    op.drop_table("keyword_runs")
    op.drop_table("keyword_clusters")
    op.drop_index(
        "uq_keyword_scoring_weights_active", table_name="keyword_scoring_weights", postgresql_where=sa.text("is_active")
    )
    op.drop_table("keyword_scoring_weights")
