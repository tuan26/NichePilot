"""T015 – Migration trên PostgreSQL 17 trống (FR-003, FR-004, FR-005, AC-15).

Dùng một database riêng (không phải DB dùng chung của phiên test) để kiểm tra upgrade → downgrade → upgrade.
"""

from __future__ import annotations

import uuid

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from tests.helpers import alembic_config

pytestmark = pytest.mark.integration

BUSINESS_TABLES = {
    "projects",
    "users",
    "auth_sessions",
    "settings",
    "audit_logs",
    "ai_models",
    "model_pricing",
    "model_task_profiles",
    "job_schedules",
    "agent_jobs",
    "job_steps",
    "tool_executions",
    "ai_usage_logs",
    "budget_reservations",
    "research_sources",
    "research_evidence",
    # E1 (specs/002-niche-discovery, migration 0009)
    "scoring_weights_versions",
    "source_policies",
    "discovery_runs",
    "niches",
    "niche_run_links",
    "niche_similarity",
    "niche_evaluations",
    "niche_findings",
    "pain_points",
    "buyer_personas",
    "competitors",
    "niche_evidence_links",
    "page_fetch_log",
    "evidence_erasure_requests",
    # E2 (specs/003-product-affiliate-discovery, migration 0011)
    "product_runs",
    "products",
    "product_niches",
    "product_pain_point_links",
    "affiliate_programs",
    "product_programs",
    "program_terms_versions",
    "product_scoring_weights",
    "product_evaluations",
}
# Bảng E1 có khóa chính tự nhiên (không phải UUID) theo data-model E1 §2
NATURAL_PK_TABLES = {"domain_access_state", "erasure_ledger_state"}
PROCRASTINATE_TABLES = {
    "procrastinate_jobs",
    "procrastinate_events",
    "procrastinate_periodic_defers",
    "procrastinate_workers",
}
IMMUTABLE_NO_UPDATED_AT = {
    "audit_logs",
    "ai_usage_logs",
    # E1: bản ghi chỉ thêm (append-only/nhật ký) – không có updated_at
    "scoring_weights_versions",
    "niche_run_links",
    "niche_evaluations",
    "page_fetch_log",
    "evidence_erasure_requests",
    # E2: lần chấm điểm (bất biến, trigger) và phiên bản trọng số – chỉ thêm
    "product_evaluations",
    "product_scoring_weights",
}


@pytest.fixture
def fresh_db_url(pg_url: str) -> str:
    """Tạo database trống riêng cho test migration."""
    name = f"mig_{uuid.uuid4().hex[:10]}"
    sync_url = pg_url.replace("+psycopg", "+psycopg")
    admin = create_engine(sync_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    admin.dispose()
    base, _, _ = sync_url.rpartition("/")
    return f"{base}/{name}"


def _tables(url: str) -> set[str]:
    eng = create_engine(url)
    try:
        return set(inspect(eng).get_table_names())
    finally:
        eng.dispose()


def test_TC_FR004_01_upgrade_downgrade_upgrade_on_empty_database(fresh_db_url: str) -> None:
    cfg = alembic_config(fresh_db_url)
    command.upgrade(cfg, "head")
    tables = _tables(fresh_db_url) - {"alembic_version"}
    present_business = tables & BUSINESS_TABLES
    # E0 hiện tại: bảng evidence do migration 0007 tạo (Phase 10); các bảng còn lại phải có đủ.
    assert BUSINESS_TABLES - {"research_sources", "research_evidence"} <= present_business
    assert PROCRASTINATE_TABLES <= tables
    assert tables <= BUSINESS_TABLES | PROCRASTINATE_TABLES | NATURAL_PK_TABLES

    command.downgrade(cfg, "base")
    assert _tables(fresh_db_url) - {"alembic_version"} == set()

    command.upgrade(cfg, "head")
    assert PROCRASTINATE_TABLES <= _tables(fresh_db_url)


def test_TC_FR005_01_uuid_pk_and_timestamps(migrated_db: str) -> None:
    eng = create_engine(migrated_db)
    try:
        insp = inspect(eng)
        for table in sorted(set(insp.get_table_names()) & BUSINESS_TABLES):
            cols = {c["name"]: c for c in insp.get_columns(table)}
            assert str(cols["id"]["type"]) == "UUID", table
            assert insp.get_pk_constraint(table)["constrained_columns"] == ["id"], table
            assert "created_at" in cols, table
            if table not in IMMUTABLE_NO_UPDATED_AT:
                assert "updated_at" in cols, table
    finally:
        eng.dispose()


def test_TC_FR004_02_orm_metadata_matches_migrations(migrated_db: str) -> None:
    """Model SQLAlchemy và migration phải khớp (không có thay đổi schema 'ẩn')."""
    from nichepilot.core.models_base import Base
    from nichepilot.db_models import import_all_models

    import_all_models()
    eng = create_engine(migrated_db)
    try:
        with eng.connect() as conn:
            ctx = MigrationContext.configure(
                conn,
                opts={
                    "include_name": lambda name, type_, _parent: (
                        not (type_ == "table" and (name or "").startswith("procrastinate_"))
                    ),
                    "compare_type": True,
                },
            )
            diff = compare_metadata(ctx, Base.metadata)
    finally:
        eng.dispose()
    assert diff == [], diff
