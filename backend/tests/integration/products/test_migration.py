"""T007 – migration 0011/0012: upgrade → downgrade → upgrade sạch; UNIQUE chống trùng (FR-005, DATA-01).

So khớp ORM ↔ migration do test E0 TC_FR004_02 đảm nhiệm (db_models nạp cả model E2).
"""

from __future__ import annotations

import uuid

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text

from tests.helpers import alembic_config

pytestmark = [pytest.mark.integration, pytest.mark.products]
E2_TABLES = {
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


@pytest.fixture
def fresh_db_url(pg_url: str) -> str:
    name = f"mig_e2_{uuid.uuid4().hex[:8]}"
    admin = create_engine(pg_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    admin.dispose()
    return f"{pg_url.rpartition('/')[0]}/{name}"


def test_TC_E2_FR005_01_migration_roundtrip_and_unique_keys(fresh_db_url: str) -> None:
    cfg = alembic_config(fresh_db_url)
    command.upgrade(cfg, "head")
    eng = create_engine(fresh_db_url)
    try:
        insp = inspect(eng)
        assert E2_TABLES <= set(insp.get_table_names())
        uniques = {
            t: {tuple(u["column_names"]) for u in insp.get_unique_constraints(t)}
            for t in ("products", "affiliate_programs", "product_niches", "product_runs", "program_terms_versions")
        }
        assert ("project_id", "data_origin", "dedup_key") in uniques["products"]
        assert ("project_id", "data_origin", "dedup_key") in uniques["affiliate_programs"]
        assert ("product_id", "niche_id") in uniques["product_niches"]
        assert ("job_id",) in uniques["product_runs"]
        assert ("program_id", "version") in uniques["program_terms_versions"]
        with eng.connect() as conn:
            w = conn.execute(
                text("SELECT version, weights, coverage_min FROM product_scoring_weights WHERE is_active")
            ).one()
            assert w.version == 1 and w.coverage_min == 60
            assert w.weights == {"fit": 25, "affiliate": 25, "eligibility": 20, "quality": 15, "price_fit": 15}
        command.downgrade(cfg, "0010_discovery_seed")
        assert not (E2_TABLES & set(inspect(eng).get_table_names()))
        command.upgrade(cfg, "head")
        assert E2_TABLES <= set(inspect(eng).get_table_names())
    finally:
        eng.dispose()
