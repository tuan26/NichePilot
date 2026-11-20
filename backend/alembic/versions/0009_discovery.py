"""0009_discovery – bảng E1 Autonomous Niche Discovery + mở rộng research_sources/research_evidence (X2).

specs/002-niche-discovery/data-model.md; tasks T030–T034. Sinh bằng autogenerate từ ORM rồi bổ sung: CHECK cho cột mới của
bảng E0, FK vòng niches ↔ niche_evaluations, trigger bất biến cho niche_evaluations.

Revision ID: 0009_discovery
Revises: 0008_pricing_source_date
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0009_discovery"
down_revision = "0008_pricing_source_date"
branch_labels = None
depends_on = None

E0_CHECKS = [
    # (bảng, tên, điều kiện) – trùng với CheckConstraint trong modules/evidence/models.py
    ("research_sources", "lifecycle_status", "lifecycle_status IN ('ACTIVE','ERASED')"),
    ("research_sources", "erased_at", "(lifecycle_status = 'ERASED') = (erased_at IS NOT NULL)"),
    ("research_sources", "reg_domain", "registered_domain IS NULL OR registered_domain = lower(registered_domain)"),
    (
        "research_evidence",
        "redaction_status",
        "redaction_status IS NULL OR redaction_status IN ('REDACTED','NEEDS_REVIEW')",
    ),
    (
        "research_evidence",
        "redaction_counts",
        "redaction_counts IS NULL OR (jsonb_typeof(redaction_counts) = 'object' AND"
        " redaction_counts - ARRAY['EMAIL','PHONE','USER','PERSON'] = '{}'::jsonb)",
    ),
    ("research_evidence", "lifecycle_status", "lifecycle_status IN ('ACTIVE','ERASED')"),
    ("research_evidence", "erased_no_content", "lifecycle_status <> 'ERASED' OR (excerpt IS NULL AND value IS NULL)"),
    ("research_evidence", "erased_at", "(lifecycle_status = 'ERASED') = (erased_at IS NOT NULL)"),
    ("research_evidence", "content_hash", "content_hash IS NULL OR content_hash ~ '^[0-9a-f]{64}$'"),
]

IMMUTABLE_FN = """
CREATE OR REPLACE FUNCTION niche_evaluations_immutable() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'niche_evaluations is append-only (E1 data-model §2)';
END;
$$ LANGUAGE plpgsql
"""


def upgrade() -> None:
    op.create_table(
        "domain_access_state",
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("last_request_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("min_interval_s", sa.Numeric(precision=8, scale=2), server_default=sa.text("2"), nullable=False),
        sa.Column("robots_status", sa.Text(), server_default=sa.text("'PENDING'"), nullable=False),
        sa.Column("robots_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("robots_rules", sa.Text(), nullable=True),
        sa.Column("crawl_delay_s", sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column("blocked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("block_reason", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "block_reason IS NULL OR block_reason IN ('RATE_LIMITED','ACCESS_RESTRICTED','ROBOTS_UNREACHABLE')",
            name=op.f("ck_domain_access_state_block_reason"),
        ),
        sa.CheckConstraint(
            "robots_status IN ('OK','NOT_FOUND','UNREACHABLE','PENDING')",
            name=op.f("ck_domain_access_state_robots_status"),
        ),
        sa.CheckConstraint(
            "crawl_delay_s IS NULL OR crawl_delay_s >= 0", name=op.f("ck_domain_access_state_crawl_delay")
        ),
        sa.CheckConstraint("domain = lower(domain)", name=op.f("ck_domain_access_state_domain_lower")),
        sa.CheckConstraint("min_interval_s >= 1", name=op.f("ck_domain_access_state_min_interval")),
        sa.PrimaryKeyConstraint("domain", name=op.f("pk_domain_access_state")),
    )
    op.create_table(
        "erasure_ledger_state",
        sa.Column("id", sa.SmallInteger(), nullable=False),
        sa.Column("ledger_id", sa.UUID(), nullable=True),
        sa.Column("applied_seq", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("applied_hash", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'OK'"), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "applied_hash IS NULL OR applied_hash ~ '^[0-9a-f]{64}$'", name=op.f("ck_erasure_ledger_state_applied_hash")
        ),
        sa.CheckConstraint("status IN ('OK','BLOCKED')", name=op.f("ck_erasure_ledger_state_status")),
        sa.CheckConstraint("applied_seq >= 0", name=op.f("ck_erasure_ledger_state_applied_seq")),
        sa.CheckConstraint("id = 1", name=op.f("ck_erasure_ledger_state_singleton")),
        sa.CheckConstraint(
            "last_error IS NULL OR char_length(last_error) <= 500", name=op.f("ck_erasure_ledger_state_last_error")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_erasure_ledger_state")),
    )
    op.create_table(
        "evidence_erasure_requests",
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("requested_by", sa.UUID(), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ledger_seq", sa.BigInteger(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "content_hash IS NULL OR content_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_evidence_erasure_requests_content_hash"),
        ),
        sa.CheckConstraint(
            "target_type IN ('EVIDENCE','SOURCE')", name=op.f("ck_evidence_erasure_requests_target_type")
        ),
        sa.CheckConstraint("char_length(reason) BETWEEN 3 AND 500", name=op.f("ck_evidence_erasure_requests_reason")),
        sa.CheckConstraint("ledger_seq >= 1", name=op.f("ck_evidence_erasure_requests_ledger_seq")),
        sa.ForeignKeyConstraint(
            ["requested_by"], ["users.id"], name=op.f("fk_evidence_erasure_requests_requested_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evidence_erasure_requests")),
        sa.UniqueConstraint("ledger_seq", name=op.f("uq_evidence_erasure_requests_ledger_seq")),
    )
    op.create_table(
        "niches",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("micro_niche", sa.Text(), nullable=False),
        sa.Column("country", sa.Text(), nullable=False),
        sa.Column("customer_group", sa.Text(), nullable=False),
        sa.Column("core_problem", sa.Text(), nullable=False),
        sa.Column("dedup_key", sa.Text(), nullable=False),
        sa.Column("evidence_status", sa.Text(), server_default=sa.text("'INSUFFICIENT_EVIDENCE'"), nullable=False),
        sa.Column("decision_status", sa.Text(), server_default=sa.text("'CANDIDATE'"), nullable=False),
        sa.Column("ai_recommendation", sa.Text(), server_default=sa.text("'UNKNOWN'"), nullable=False),
        sa.Column("ai_recommendation_reason", sa.Text(), nullable=True),
        sa.Column("owner_decision_reason", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.UUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "monetization_status", sa.Text(), server_default=sa.text("'MONETIZATION_UNVERIFIED'"), nullable=False
        ),
        sa.Column("risk_flags", postgresql.ARRAY(sa.Text()), server_default=sa.text("'{}'::text[]"), nullable=False),
        sa.Column("merged_into_id", sa.UUID(), nullable=True),
        sa.Column("latest_evaluation_id", sa.UUID(), nullable=True),
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "ai_recommendation IN ('PURSUE','REJECT','UNKNOWN')", name=op.f("ck_niches_ai_recommendation")
        ),
        sa.CheckConstraint("country ~ '^[A-Z]{2}$'", name=op.f("ck_niches_country")),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_niches_data_origin")),
        sa.CheckConstraint(
            "decision_status = 'CANDIDATE' OR decided_by IS NOT NULL", name=op.f("ck_niches_decided_by")
        ),
        sa.CheckConstraint(
            "decision_status IN ('CANDIDATE','WATCH','PURSUE','REJECTED','HIDDEN')",
            name=op.f("ck_niches_decision_status"),
        ),
        sa.CheckConstraint(
            "evidence_status IN ('EVIDENCE_SUFFICIENT','INSUFFICIENT_EVIDENCE')", name=op.f("ck_niches_evidence_status")
        ),
        sa.CheckConstraint(
            "monetization_status IN ('SIGNALS_FOUND','MONETIZATION_UNVERIFIED','NO_AFFILIATE_FOUND')",
            name=op.f("ck_niches_monetization_status"),
        ),
        sa.CheckConstraint(
            "risk_flags <@ ARRAY['MONETIZATION_RISK','COMPLIANCE_SENSITIVE','LOW_EVIDENCE_FRESHNESS']::text[]",
            name=op.f("ck_niches_risk_flags"),
        ),
        sa.CheckConstraint(
            "ai_recommendation_reason IS NULL OR char_length(ai_recommendation_reason) <= 2000",
            name=op.f("ck_niches_ai_reason"),
        ),
        sa.CheckConstraint("char_length(core_problem) BETWEEN 1 AND 500", name=op.f("ck_niches_core_problem")),
        sa.CheckConstraint("char_length(customer_group) BETWEEN 1 AND 300", name=op.f("ck_niches_customer_group")),
        sa.CheckConstraint("char_length(micro_niche) BETWEEN 1 AND 200", name=op.f("ck_niches_micro_niche")),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 200", name=op.f("ck_niches_name")),
        sa.CheckConstraint("merged_into_id IS NULL OR merged_into_id <> id", name=op.f("ck_niches_merged_into")),
        sa.CheckConstraint(
            "owner_decision_reason IS NULL OR char_length(owner_decision_reason) <= 2000",
            name=op.f("ck_niches_owner_reason"),
        ),
        sa.ForeignKeyConstraint(["decided_by"], ["users.id"], name=op.f("fk_niches_decided_by_users")),
        sa.ForeignKeyConstraint(["merged_into_id"], ["niches.id"], name=op.f("fk_niches_merged_into_id_niches")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_niches_project_id_projects")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_niches")),
    )
    op.create_index(
        "uq_niches_project_origin_dedup_key",
        "niches",
        ["project_id", "data_origin", "dedup_key"],
        unique=True,
        postgresql_where=sa.text("merged_into_id IS NULL"),
    )
    op.create_table(
        "scoring_weights_versions",
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("weights", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("coverage_threshold", sa.Numeric(precision=5, scale=2), server_default=sa.text("60"), nullable=False),
        sa.Column("evidence_rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("confidence_params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("dedup_params", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "jsonb_typeof(weights) = 'object' AND weights ?& ARRAY['problem_severity','monetization','market_gap','reachability','competition_opportunity','demand_stability']",
            name=op.f("ck_scoring_weights_versions_weights_keys"),
        ),
        sa.CheckConstraint(
            "coverage_threshold > 0 AND coverage_threshold <= 100",
            name=op.f("ck_scoring_weights_versions_coverage_threshold"),
        ),
        sa.CheckConstraint("version >= 1", name=op.f("ck_scoring_weights_versions_version")),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name=op.f("fk_scoring_weights_versions_created_by_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scoring_weights_versions")),
        sa.UniqueConstraint("version", name=op.f("uq_scoring_weights_versions_version")),
    )
    op.create_index(
        "uq_scoring_weights_versions_active",
        "scoring_weights_versions",
        ["is_active"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_table(
        "source_policies",
        sa.Column("source_key", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("adapter_type", sa.Text(), nullable=False),
        sa.Column(
            "config", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("tos_url", sa.Text(), nullable=False),
        sa.Column("verified_at", sa.Date(), nullable=True),
        sa.Column("verified_by", sa.UUID(), nullable=True),
        sa.Column("verification_note", sa.Text(), nullable=True),
        sa.Column(
            "allowed_access_methods",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
        sa.Column("permitted_use_scope", sa.Text(), nullable=True),
        sa.Column("known_limits", sa.Text(), nullable=True),
        sa.Column("compliance_status", sa.Text(), server_default=sa.text("'UNVERIFIED'"), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("updated_by", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "NOT enabled OR compliance_status = 'ALLOWED'", name=op.f("ck_source_policies_enabled_only_allowed")
        ),
        sa.CheckConstraint(
            "adapter_type IN ('searxng_engine','http_json_api','open_dataset','licensed_data')",
            name=op.f("ck_source_policies_adapter_type"),
        ),
        sa.CheckConstraint(
            "allowed_access_methods <@ ARRAY['SEARXNG_ENGINE','OFFICIAL_API','DATASET_DOWNLOAD']::text[]",
            name=op.f("ck_source_policies_access_methods"),
        ),
        sa.CheckConstraint(
            "compliance_status <> 'ALLOWED' OR (verified_at IS NOT NULL AND verified_by IS NOT NULL AND verification_note IS NOT NULL AND cardinality(allowed_access_methods) > 0 AND permitted_use_scope IS NOT NULL)",
            name=op.f("ck_source_policies_allowed_has_evidence"),
        ),
        sa.CheckConstraint(
            "compliance_status <> 'PROHIBITED' OR (verified_at IS NOT NULL AND verification_note IS NOT NULL)",
            name=op.f("ck_source_policies_prohibited_has_evidence"),
        ),
        sa.CheckConstraint(
            "compliance_status IN ('ALLOWED','UNVERIFIED','PROHIBITED')",
            name=op.f("ck_source_policies_compliance_status"),
        ),
        sa.CheckConstraint("jsonb_typeof(config) = 'object'", name=op.f("ck_source_policies_config_object")),
        sa.CheckConstraint("source_key ~ '^[a-z0-9_:.-]{2,64}$'", name=op.f("ck_source_policies_source_key")),
        sa.CheckConstraint(
            "tos_url ~ '^https://' AND char_length(tos_url) <= 2000", name=op.f("ck_source_policies_tos_url")
        ),
        sa.CheckConstraint("char_length(display_name) BETWEEN 1 AND 120", name=op.f("ck_source_policies_display_name")),
        sa.CheckConstraint(
            "known_limits IS NULL OR char_length(known_limits) <= 1000", name=op.f("ck_source_policies_known_limits")
        ),
        sa.CheckConstraint(
            "permitted_use_scope IS NULL OR char_length(permitted_use_scope) BETWEEN 10 AND 1000",
            name=op.f("ck_source_policies_scope"),
        ),
        sa.CheckConstraint(
            "verification_note IS NULL OR char_length(verification_note) BETWEEN 10 AND 2000",
            name=op.f("ck_source_policies_note"),
        ),
        sa.CheckConstraint(
            "verified_at IS NULL OR verified_at <= CURRENT_DATE", name=op.f("ck_source_policies_verified_at")
        ),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], name=op.f("fk_source_policies_updated_by_users")),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"], name=op.f("fk_source_policies_verified_by_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_policies")),
        sa.UniqueConstraint("source_key", name=op.f("uq_source_policies_source_key")),
    )
    op.create_table(
        "buyer_personas",
        sa.Column("niche_id", sa.UUID(), nullable=False),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "attributes ?& ARRAY['segment','context','goals','obstacles','ability_to_pay']",
            name=op.f("ck_buyer_personas_attributes_keys"),
        ),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_buyer_personas_data_origin")),
        sa.ForeignKeyConstraint(["niche_id"], ["niches.id"], name=op.f("fk_buyer_personas_niche_id_niches")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_buyer_personas")),
        sa.UniqueConstraint("niche_id", name=op.f("uq_buyer_personas_niche_id")),
    )
    op.create_table(
        "competitors",
        sa.Column("niche_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("normalized_name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column(
            "strengths", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column(
            "weaknesses", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False
        ),
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_competitors_data_origin")),
        sa.CheckConstraint(
            "jsonb_typeof(strengths) = 'array' AND jsonb_typeof(weaknesses) = 'array'",
            name=op.f("ck_competitors_lists"),
        ),
        sa.CheckConstraint("kind IN ('PRODUCT','SERVICE','MANUAL_WORKAROUND')", name=op.f("ck_competitors_kind")),
        sa.CheckConstraint("url IS NULL OR url ~ '^https?://'", name=op.f("ck_competitors_url")),
        sa.CheckConstraint("char_length(name) BETWEEN 1 AND 200", name=op.f("ck_competitors_name")),
        sa.ForeignKeyConstraint(["niche_id"], ["niches.id"], name=op.f("fk_competitors_niche_id_niches")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_competitors")),
        sa.UniqueConstraint("niche_id", "normalized_name", name=op.f("uq_competitors_niche_id_normalized_name")),
    )
    op.create_table(
        "niche_findings",
        sa.Column("niche_id", sa.UUID(), nullable=False),
        sa.Column("field", sa.Text(), nullable=False),
        sa.Column("value", postgresql.JSONB(none_as_null=True, astext_type=sa.Text()), nullable=True),
        sa.Column("verification_status", sa.Text(), nullable=False),
        sa.Column("evidence_ids", postgresql.ARRAY(sa.UUID()), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "(value IS NULL) = (verification_status = 'UNKNOWN')", name=op.f("ck_niche_findings_unknown_no_value")
        ),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_niche_findings_data_origin")),
        sa.CheckConstraint(
            "field IN ('CURRENT_SOLUTIONS','MARKET_GAPS','POTENTIAL_PRODUCTS','MONETIZATION','CHANNELS','RISKS')",
            name=op.f("ck_niche_findings_field"),
        ),
        sa.CheckConstraint(
            "verification_status <> 'VERIFIED' OR cardinality(evidence_ids) > 0",
            name=op.f("ck_niche_findings_verified_ev"),
        ),
        sa.CheckConstraint(
            "verification_status IN ('VERIFIED','INFERRED','UNKNOWN','CONFLICTING')",
            name=op.f("ck_niche_findings_verification_status"),
        ),
        sa.ForeignKeyConstraint(["niche_id"], ["niches.id"], name=op.f("fk_niche_findings_niche_id_niches")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_niche_findings")),
        sa.UniqueConstraint("niche_id", "field", name=op.f("uq_niche_findings_niche_id_field")),
    )
    op.create_table(
        "niche_similarity",
        sa.Column("niche_a_id", sa.UUID(), nullable=False),
        sa.Column("niche_b_id", sa.UUID(), nullable=False),
        sa.Column("score", sa.Numeric(precision=4, scale=3), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'POSSIBLE'"), nullable=False),
        sa.Column("resolved_by", sa.UUID(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status = 'POSSIBLE' OR resolved_by IS NOT NULL", name=op.f("ck_niche_similarity_resolved_by")
        ),
        sa.CheckConstraint(
            "status IN ('POSSIBLE','CONFIRMED_DUPLICATE','NOT_DUPLICATE')", name=op.f("ck_niche_similarity_status")
        ),
        sa.CheckConstraint("niche_a_id < niche_b_id", name=op.f("ck_niche_similarity_ordered_pair")),
        sa.CheckConstraint("score BETWEEN 0 AND 1", name=op.f("ck_niche_similarity_score")),
        sa.ForeignKeyConstraint(["niche_a_id"], ["niches.id"], name=op.f("fk_niche_similarity_niche_a_id_niches")),
        sa.ForeignKeyConstraint(["niche_b_id"], ["niches.id"], name=op.f("fk_niche_similarity_niche_b_id_niches")),
        sa.ForeignKeyConstraint(["resolved_by"], ["users.id"], name=op.f("fk_niche_similarity_resolved_by_users")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_niche_similarity")),
        sa.UniqueConstraint("niche_a_id", "niche_b_id", name=op.f("uq_niche_similarity_niche_a_id_niche_b_id")),
    )
    op.create_table(
        "pain_points",
        sa.Column("niche_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("normalized_title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.SmallInteger(), nullable=True),
        sa.Column("severity_reason", sa.Text(), nullable=True),
        sa.Column("evidence_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("verification_status", sa.Text(), nullable=False),
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_pain_points_data_origin")),
        sa.CheckConstraint(
            "verification_status IN ('VERIFIED','INFERRED','UNKNOWN','CONFLICTING')",
            name=op.f("ck_pain_points_verification_status"),
        ),
        sa.CheckConstraint("char_length(title) BETWEEN 1 AND 200", name=op.f("ck_pain_points_title")),
        sa.CheckConstraint("evidence_count >= 0", name=op.f("ck_pain_points_evidence_count")),
        sa.CheckConstraint("severity IS NULL OR severity BETWEEN 1 AND 5", name=op.f("ck_pain_points_severity")),
        sa.ForeignKeyConstraint(["niche_id"], ["niches.id"], name=op.f("fk_pain_points_niche_id_niches")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pain_points")),
        sa.UniqueConstraint("niche_id", "normalized_title", name=op.f("uq_pain_points_niche_id_normalized_title")),
    )
    op.create_table(
        "discovery_runs",
        sa.Column("project_id", sa.UUID(), nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("market", sa.Text(), nullable=False),
        sa.Column("research_language", sa.Text(), nullable=False),
        sa.Column("seed_topic", sa.Text(), nullable=True),
        sa.Column("max_candidates", sa.Integer(), server_default=sa.text("20"), nullable=False),
        sa.Column("budget_usd", sa.Numeric(precision=14, scale=6), server_default=sa.text("2"), nullable=False),
        sa.Column("time_limit_s", sa.Integer(), server_default=sa.text("5400"), nullable=False),
        sa.Column("page_limit", sa.Integer(), server_default=sa.text("300"), nullable=False),
        sa.Column(
            "per_domain_interval_s", sa.Numeric(precision=6, scale=2), server_default=sa.text("2"), nullable=False
        ),
        sa.Column("trigger", sa.Text(), nullable=False),
        sa.Column(
            "source_policy_ids", postgresql.ARRAY(sa.UUID()), server_default=sa.text("'{}'::uuid[]"), nullable=False
        ),
        sa.Column("weights_version_id", sa.UUID(), nullable=False),
        sa.Column("source_mode", sa.Text(), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=True),
        sa.Column("stop_reason", sa.Text(), nullable=True),
        sa.Column(
            "metrics", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False
        ),
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_discovery_runs_data_origin")),
        sa.CheckConstraint("jsonb_typeof(metrics) = 'object'", name=op.f("ck_discovery_runs_metrics_object")),
        sa.CheckConstraint("market ~ '^[A-Z]{2}$'", name=op.f("ck_discovery_runs_market")),
        sa.CheckConstraint(
            "outcome IS NULL OR outcome IN ('COMPLETED','PARTIAL_COMPLETED')", name=op.f("ck_discovery_runs_outcome")
        ),
        sa.CheckConstraint(
            "research_language ~ '^[a-z]{2}(-[A-Z]{2})?$'", name=op.f("ck_discovery_runs_research_language")
        ),
        sa.CheckConstraint("source_mode IN ('REAL','MOCK')", name=op.f("ck_discovery_runs_source_mode")),
        sa.CheckConstraint(
            "stop_reason IS NULL OR stop_reason IN ('ALL_CANDIDATES_SUFFICIENT','CANDIDATES_EXHAUSTED','TIME_LIMIT_REACHED','PAGE_LIMIT_REACHED','NO_COMPLIANT_SEARCH_SOURCE','SOURCES_UNAVAILABLE','CANCELLED')",
            name=op.f("ck_discovery_runs_stop_reason"),
        ),
        sa.CheckConstraint("trigger IN ('MANUAL','SCHEDULE','RETRY')", name=op.f("ck_discovery_runs_trigger")),
        sa.CheckConstraint("budget_usd > 0", name=op.f("ck_discovery_runs_budget_usd")),
        sa.CheckConstraint(
            "idempotency_key IS NULL OR char_length(idempotency_key) <= 128",
            name=op.f("ck_discovery_runs_idempotency_key"),
        ),
        sa.CheckConstraint("max_candidates BETWEEN 1 AND 50", name=op.f("ck_discovery_runs_max_candidates")),
        sa.CheckConstraint("page_limit BETWEEN 10 AND 2000", name=op.f("ck_discovery_runs_page_limit")),
        sa.CheckConstraint("per_domain_interval_s >= 1", name=op.f("ck_discovery_runs_per_domain_interval_s")),
        sa.CheckConstraint(
            "seed_topic IS NULL OR char_length(seed_topic) <= 200", name=op.f("ck_discovery_runs_seed_topic")
        ),
        sa.CheckConstraint("time_limit_s BETWEEN 300 AND 14400", name=op.f("ck_discovery_runs_time_limit_s")),
        sa.ForeignKeyConstraint(["job_id"], ["agent_jobs.id"], name=op.f("fk_discovery_runs_job_id_agent_jobs")),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], name=op.f("fk_discovery_runs_project_id_projects")),
        sa.ForeignKeyConstraint(
            ["weights_version_id"],
            ["scoring_weights_versions.id"],
            name=op.f("fk_discovery_runs_weights_version_id_scoring_weights_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_discovery_runs")),
        sa.UniqueConstraint("idempotency_key", name=op.f("uq_discovery_runs_idempotency_key")),
        sa.UniqueConstraint("job_id", name=op.f("uq_discovery_runs_job_id")),
    )
    op.create_index("ix_discovery_runs_project_created", "discovery_runs", ["project_id", "created_at"], unique=False)
    op.create_table(
        "niche_evaluations",
        sa.Column("niche_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=True),
        sa.Column("weights_version_id", sa.UUID(), nullable=False),
        sa.Column("criteria", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("coverage", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("scoring_status", sa.Text(), nullable=False),
        sa.Column("opportunity_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("confidence_components", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("evidence_status", sa.Text(), nullable=False),
        sa.Column("independent_groups", sa.Integer(), nullable=False),
        sa.Column("computed_without_ai", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "(opportunity_score IS NULL) = (scoring_status = 'INSUFFICIENT_SCORING_DATA')",
            name=op.f("ck_niche_evaluations_opportunity_status"),
        ),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_niche_evaluations_data_origin")),
        sa.CheckConstraint(
            "evidence_status IN ('EVIDENCE_SUFFICIENT','INSUFFICIENT_EVIDENCE')",
            name=op.f("ck_niche_evaluations_evidence_status"),
        ),
        sa.CheckConstraint(
            "scoring_status IN ('SCORED','INSUFFICIENT_SCORING_DATA')", name=op.f("ck_niche_evaluations_scoring_status")
        ),
        sa.CheckConstraint("confidence_score BETWEEN 0 AND 100", name=op.f("ck_niche_evaluations_confidence")),
        sa.CheckConstraint("coverage BETWEEN 0 AND 100", name=op.f("ck_niche_evaluations_coverage")),
        sa.CheckConstraint("independent_groups >= 0", name=op.f("ck_niche_evaluations_independent_groups")),
        sa.CheckConstraint(
            "opportunity_score IS NULL OR opportunity_score BETWEEN 0 AND 100",
            name=op.f("ck_niche_evaluations_opportunity"),
        ),
        sa.ForeignKeyConstraint(["niche_id"], ["niches.id"], name=op.f("fk_niche_evaluations_niche_id_niches")),
        sa.ForeignKeyConstraint(
            ["run_id"], ["discovery_runs.id"], name=op.f("fk_niche_evaluations_run_id_discovery_runs")
        ),
        sa.ForeignKeyConstraint(
            ["weights_version_id"],
            ["scoring_weights_versions.id"],
            name=op.f("fk_niche_evaluations_weights_version_id_scoring_weights_versions"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_niche_evaluations")),
    )
    op.create_index("ix_niche_evaluations_niche_created", "niche_evaluations", ["niche_id", "created_at"], unique=False)
    op.create_table(
        "niche_evidence_links",
        sa.Column("niche_id", sa.UUID(), nullable=False),
        sa.Column("evidence_id", sa.UUID(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("pain_point_id", sa.UUID(), nullable=True),
        sa.Column("relevance", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("quality", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("assessment_reason", sa.Text(), nullable=True),
        sa.Column("copy_suspected", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("independence_group", sa.Text(), nullable=False),
        sa.Column("counted_for_threshold", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("data_origin", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "(pain_point_id IS NOT NULL) = (purpose = 'PAIN_POINT')", name=op.f("ck_niche_evidence_links_pain_point")
        ),
        sa.CheckConstraint("data_origin IN ('REAL','MOCK')", name=op.f("ck_niche_evidence_links_data_origin")),
        sa.CheckConstraint(
            "purpose IN ('PAIN_POINT','PERSONA','SOLUTION','COMPETITOR','MONETIZATION','CHANNEL')",
            name=op.f("ck_niche_evidence_links_purpose"),
        ),
        sa.CheckConstraint("quality IS NULL OR quality BETWEEN 0 AND 1", name=op.f("ck_niche_evidence_links_quality")),
        sa.CheckConstraint(
            "relevance IS NULL OR relevance BETWEEN 0 AND 1", name=op.f("ck_niche_evidence_links_relevance")
        ),
        sa.ForeignKeyConstraint(
            ["evidence_id"],
            ["research_evidence.id"],
            name=op.f("fk_niche_evidence_links_evidence_id_research_evidence"),
        ),
        sa.ForeignKeyConstraint(["niche_id"], ["niches.id"], name=op.f("fk_niche_evidence_links_niche_id_niches")),
        sa.ForeignKeyConstraint(
            ["pain_point_id"], ["pain_points.id"], name=op.f("fk_niche_evidence_links_pain_point_id_pain_points")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_niche_evidence_links")),
        sa.UniqueConstraint("niche_id", "evidence_id", name=op.f("uq_niche_evidence_links_niche_id_evidence_id")),
    )
    op.create_table(
        "niche_run_links",
        sa.Column("niche_id", sa.UUID(), nullable=False),
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role IN ('DISCOVERED','REEVALUATED')", name=op.f("ck_niche_run_links_role")),
        sa.ForeignKeyConstraint(["niche_id"], ["niches.id"], name=op.f("fk_niche_run_links_niche_id_niches")),
        sa.ForeignKeyConstraint(
            ["run_id"], ["discovery_runs.id"], name=op.f("fk_niche_run_links_run_id_discovery_runs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_niche_run_links")),
        sa.UniqueConstraint("niche_id", "run_id", name=op.f("uq_niche_run_links_niche_id_run_id")),
    )
    op.create_table(
        "page_fetch_log",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("url_hash", sa.Text(), nullable=False),
        sa.Column("domain", sa.Text(), nullable=False),
        sa.Column("attempted_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("outcome", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("http_status", sa.SmallInteger(), nullable=True),
        sa.Column("source_id", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "(source_id IS NOT NULL) = (outcome = 'SUCCESS')", name=op.f("ck_page_fetch_log_source_on_success")
        ),
        sa.CheckConstraint("outcome = 'SUCCESS' OR reason IS NOT NULL", name=op.f("ck_page_fetch_log_reason_required")),
        sa.CheckConstraint("outcome IN ('SUCCESS','FAILED','SKIPPED')", name=op.f("ck_page_fetch_log_outcome")),
        sa.CheckConstraint(
            "reason IS NULL OR reason IN ('ROBOTS_DISALLOWED','RATE_LIMITED','ACCESS_RESTRICTED','HTTP_ERROR','TIMEOUT','NETWORK_ERROR','NON_HTML','TOO_LARGE','PII_UNSAFE','PAGE_LIMIT','TIME_LIMIT','ERASED_CONTENT')",
            name=op.f("ck_page_fetch_log_reason"),
        ),
        sa.CheckConstraint("url_hash ~ '^[0-9a-f]{64}$'", name=op.f("ck_page_fetch_log_url_hash")),
        sa.CheckConstraint("domain = lower(domain)", name=op.f("ck_page_fetch_log_domain_lower")),
        sa.CheckConstraint(
            "http_status IS NULL OR http_status BETWEEN 100 AND 599", name=op.f("ck_page_fetch_log_http_status")
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["discovery_runs.id"], name=op.f("fk_page_fetch_log_run_id_discovery_runs")
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["research_sources.id"], name=op.f("fk_page_fetch_log_source_id_research_sources")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_page_fetch_log")),
        sa.UniqueConstraint("run_id", "url_hash", name=op.f("uq_page_fetch_log_run_id_url_hash")),
    )
    op.add_column("research_evidence", sa.Column("redaction_status", sa.Text(), nullable=True))
    op.add_column(
        "research_evidence", sa.Column("redaction_counts", postgresql.JSONB(astext_type=sa.Text()), nullable=True)
    )
    op.add_column("research_evidence", sa.Column("pii_engine", sa.Text(), nullable=True))
    op.add_column(
        "research_evidence",
        sa.Column("lifecycle_status", sa.Text(), server_default=sa.text("'ACTIVE'"), nullable=False),
    )
    op.add_column("research_evidence", sa.Column("erased_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("research_evidence", sa.Column("content_hash", sa.Text(), nullable=True))
    op.add_column("research_sources", sa.Column("registered_domain", sa.Text(), nullable=True))
    op.add_column("research_sources", sa.Column("simhash", sa.BigInteger(), nullable=True))
    op.add_column(
        "research_sources", sa.Column("lifecycle_status", sa.Text(), server_default=sa.text("'ACTIVE'"), nullable=False)
    )
    op.add_column("research_sources", sa.Column("erased_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("research_sources", sa.Column("source_policy_id", sa.UUID(), nullable=True))
    op.add_column("research_sources", sa.Column("policy_verified_at", sa.Date(), nullable=True))
    op.create_foreign_key(
        op.f("fk_research_sources_source_policy_id_source_policies"),
        "research_sources",
        "source_policies",
        ["source_policy_id"],
        ["id"],
    )
    # FK vòng: niches.latest_evaluation_id → niche_evaluations (tạo sau khi cả hai bảng tồn tại)
    op.create_foreign_key(
        op.f("fk_niches_latest_evaluation_id_niche_evaluations"),
        "niches",
        "niche_evaluations",
        ["latest_evaluation_id"],
        ["id"],
    )
    for table, name, cond in E0_CHECKS:
        op.create_check_constraint(op.f(f"ck_{table}_{name}"), table, cond)
    op.execute(IMMUTABLE_FN)
    op.execute(
        "CREATE TRIGGER trg_niche_evaluations_immutable BEFORE UPDATE OR DELETE ON niche_evaluations"
        " FOR EACH ROW EXECUTE FUNCTION niche_evaluations_immutable()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_niche_evaluations_immutable ON niche_evaluations")
    op.execute("DROP FUNCTION IF EXISTS niche_evaluations_immutable()")
    for table, name, _cond in reversed(E0_CHECKS):
        op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.drop_constraint(op.f("fk_niches_latest_evaluation_id_niche_evaluations"), "niches", type_="foreignkey")
    op.drop_constraint(
        op.f("fk_research_sources_source_policy_id_source_policies"), "research_sources", type_="foreignkey"
    )
    op.drop_column("research_sources", "policy_verified_at")
    op.drop_column("research_sources", "source_policy_id")
    op.drop_column("research_sources", "erased_at")
    op.drop_column("research_sources", "lifecycle_status")
    op.drop_column("research_sources", "simhash")
    op.drop_column("research_sources", "registered_domain")
    op.drop_column("research_evidence", "content_hash")
    op.drop_column("research_evidence", "erased_at")
    op.drop_column("research_evidence", "lifecycle_status")
    op.drop_column("research_evidence", "pii_engine")
    op.drop_column("research_evidence", "redaction_counts")
    op.drop_column("research_evidence", "redaction_status")
    op.drop_table("page_fetch_log")
    op.drop_table("niche_run_links")
    op.drop_table("niche_evidence_links")
    op.drop_index("ix_niche_evaluations_niche_created", table_name="niche_evaluations")
    op.drop_table("niche_evaluations")
    op.drop_index("ix_discovery_runs_project_created", table_name="discovery_runs")
    op.drop_table("discovery_runs")
    op.drop_table("pain_points")
    op.drop_table("niche_similarity")
    op.drop_table("niche_findings")
    op.drop_table("competitors")
    op.drop_table("buyer_personas")
    op.drop_table("source_policies")
    op.drop_index(
        "uq_scoring_weights_versions_active",
        table_name="scoring_weights_versions",
        postgresql_where=sa.text("is_active"),
    )
    op.drop_table("scoring_weights_versions")
    op.drop_index(
        "uq_niches_project_origin_dedup_key", table_name="niches", postgresql_where=sa.text("merged_into_id IS NULL")
    )
    op.drop_table("niches")
    op.drop_table("evidence_erasure_requests")
    op.drop_table("erasure_ledger_state")
    op.drop_table("domain_access_state")
