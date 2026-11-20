"""T012 – Migration 0009/0010 trên database trống: upgrade → downgrade → upgrade; dữ liệu E0 giữ nguyên (FR-029, FR-013e).

So khớp ORM ↔ migration do test E0 TC_FR004_02 đảm nhiệm (db_models nạp cả model E1).
"""

from __future__ import annotations

import uuid

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text

from tests.helpers import alembic_config

pytestmark = [pytest.mark.integration, pytest.mark.discovery]
E1_TABLES = {
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
    "domain_access_state",
    "page_fetch_log",
    "evidence_erasure_requests",
    "erasure_ledger_state",
}


@pytest.fixture
def fresh_db_url(pg_url: str) -> str:
    name = f"mig_e1_{uuid.uuid4().hex[:8]}"
    admin = create_engine(pg_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    admin.dispose()
    return f"{pg_url.rpartition('/')[0]}/{name}"


def test_TC_E1_FR029_01_upgrade_downgrade_upgrade_keeps_e0_data(fresh_db_url: str) -> None:
    cfg = alembic_config(fresh_db_url)
    command.upgrade(cfg, "0008_pricing_source_date")
    eng = create_engine(fresh_db_url)
    try:
        with eng.begin() as conn:
            project = conn.execute(text("SELECT id FROM projects LIMIT 1")).scalar_one()
            conn.execute(
                text(
                    "INSERT INTO research_sources (project_id, source_type, url, canonical_url, content_hash, data_origin)"
                    " VALUES (:p, 'WEB_PAGE', 'https://e0.example/a', 'https://e0.example/a', 'h0', 'REAL')"
                ),
                {"p": project},
            )
        command.upgrade(cfg, "head")
        insp = inspect(eng)
        assert E1_TABLES <= set(insp.get_table_names())
        with eng.connect() as conn:
            row = conn.execute(text("SELECT lifecycle_status, erased_at FROM research_sources")).one()
            assert row == ("ACTIVE", None)  # nguồn E0 cũ nhận giá trị mặc định hợp lệ
            assert conn.execute(text("SELECT count(*) FROM source_policies WHERE enabled")).scalar_one() == 0
        command.downgrade(cfg, "0008_pricing_source_date")
        assert not (E1_TABLES & set(inspect(eng).get_table_names()))
        with eng.connect() as conn:
            assert conn.execute(text("SELECT count(*) FROM research_sources")).scalar_one() == 1
        command.upgrade(cfg, "head")
        assert E1_TABLES <= set(inspect(eng).get_table_names())
    finally:
        eng.dispose()
