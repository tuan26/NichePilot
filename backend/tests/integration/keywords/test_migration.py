"""T007 – migration 0013/0014: upgrade → downgrade → upgrade sạch; UNIQUE chống trùng; CHECK chỉ số có nguồn (FR-004, FR-009)."""

from __future__ import annotations

import uuid

import pytest
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from tests.helpers import alembic_config

pytestmark = [pytest.mark.integration, pytest.mark.keywords]
E3_TABLES = {
    "keyword_runs",
    "keywords",
    "keyword_origins",
    "keyword_clusters",
    "serp_observations",
    "competitor_pages",
    "keyword_scoring_weights",
    "keyword_evaluations",
}


@pytest.fixture
def fresh_db_url(pg_url: str) -> str:
    name = f"mig_e3_{uuid.uuid4().hex[:8]}"
    admin = create_engine(pg_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    admin.dispose()
    return f"{pg_url.rpartition('/')[0]}/{name}"


def _insert_keyword(conn: object, extra_cols: str = "", extra_vals: str = "") -> None:
    conn.execute(  # type: ignore[attr-defined]
        text(
            "INSERT INTO keywords (project_id, niche_id, text, normalized, dedup_key, keyword_type, length_class, intent,"  # noqa: S608
            f" data_origin{extra_cols}) SELECT p.id, n.id, 'flour stock alerts', 'flour stock alerts', 'alert flour stock',"
            f" 'PROBLEM', 'MID', 'INFORMATIONAL', 'MOCK'{extra_vals} FROM projects p, niches n LIMIT 1"
        )
    )


def test_TC_E3_FR004_01_TC_E3_FR009_01_migration_roundtrip_unique_and_metric_checks(fresh_db_url: str) -> None:
    cfg = alembic_config(fresh_db_url)
    command.upgrade(cfg, "head")
    eng = create_engine(fresh_db_url)
    try:
        insp = inspect(eng)
        assert E3_TABLES <= set(insp.get_table_names())
        uniques = {t: {tuple(u["column_names"]) for u in insp.get_unique_constraints(t)} for t in E3_TABLES}
        assert ("project_id", "niche_id", "data_origin", "dedup_key") in uniques["keywords"]
        assert ("niche_id", "data_origin", "cluster_key") in uniques["keyword_clusters"]
        assert ("keyword_id", "version") in uniques["serp_observations"]
        assert ("keyword_id", "url") in uniques["competitor_pages"]
        assert ("job_id",) in uniques["keyword_runs"]
        with eng.begin() as conn:
            w = conn.execute(
                text("SELECT version, weights, coverage_min FROM keyword_scoring_weights WHERE is_active")
            ).one()
            assert w.version == 1 and w.coverage_min == 60
            assert w.weights == {"fit": 30, "intent_value": 20, "competition": 20, "content_gap": 15, "demand": 15}
            conn.execute(
                text(
                    "INSERT INTO niches (project_id, name, micro_niche, country, customer_group, core_problem, dedup_key,"
                    " data_origin) SELECT id, '[MOCK] n', '[MOCK] m', 'US', 'g', 'p', 'k', 'MOCK' FROM projects LIMIT 1"
                )
            )
        # chỉ số không nguồn bị DB từ chối (FR-009)
        with pytest.raises(IntegrityError), eng.begin() as conn:
            _insert_keyword(conn, ", search_volume", ", 1200")
        with eng.begin() as conn:
            _insert_keyword(
                conn,
                ", search_volume, metrics_source, metrics_collected_at, metrics_market",
                ", 1200, 'licensed-test-source', now(), 'US'",
            )
        with pytest.raises(IntegrityError), eng.begin() as conn:
            _insert_keyword(conn)  # trùng dedup_key
        with eng.begin() as conn:
            conn.execute(text("DELETE FROM keywords"))
        command.downgrade(cfg, "0012_products_seed")
        assert not (E3_TABLES & set(inspect(eng).get_table_names()))
        command.upgrade(cfg, "head")
        assert E3_TABLES <= set(inspect(eng).get_table_names())
    finally:
        eng.dispose()


def test_TC_E3_FR020_04_evaluations_append_only(fresh_db_url: str) -> None:
    cfg = alembic_config(fresh_db_url)
    command.upgrade(cfg, "head")
    eng = create_engine(fresh_db_url)
    try:
        with eng.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO niches (project_id, name, micro_niche, country, customer_group, core_problem, dedup_key,"
                    " data_origin) SELECT id, '[MOCK] n', '[MOCK] m', 'US', 'g', 'p', 'k', 'MOCK' FROM projects LIMIT 1"
                )
            )
            _insert_keyword(conn)
            conn.execute(
                text(
                    "INSERT INTO keyword_evaluations (keyword_id, weights_version_id, confidence_score, coverage,"
                    " scoring_status, criteria, confidence_components, evidence_fingerprint, data_origin)"
                    " SELECT k.id, w.id, 10, 30, 'INSUFFICIENT_SCORING_DATA', '{}', '{}', 'fp', 'MOCK'"
                    " FROM keywords k, keyword_scoring_weights w LIMIT 1"
                )
            )
        with pytest.raises(DBAPIError), eng.begin() as conn:
            conn.execute(text("UPDATE keyword_evaluations SET coverage = 99"))
    finally:
        eng.dispose()
