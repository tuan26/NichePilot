"""T092 – Hiệu năng E1 (marker `perf`, chạy khi đặt NICHEPILOT_RUN_PERF=1): `GET /api/v1/niches` p95 < 500 ms với 5.000 ngách giả
lập; tính lại 1.000 ngách ≤ 60 s, 0 lời gọi AI (FR-024, FR-018). Dữ liệu sinh bằng SQL trong DB test – KHÔNG phải nghiên cứu thật."""

from __future__ import annotations

import json
import statistics
import time
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.discovery_helpers import discovery_client

pytestmark = [pytest.mark.perf, pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]
CRIT = {
    k: {"score": 50, "status": "INFERRED", "reason": "perf", "evidence_ids": ["x"]}
    for k in (
        "problem_severity",
        "monetization",
        "market_gap",
        "reachability",
        "competition_opportunity",
        "demand_stability",
    )
}


async def _seed(engine: AsyncEngine, n: int) -> list[str]:
    async with engine.begin() as conn:
        project = (await conn.execute(text("SELECT id FROM projects LIMIT 1"))).scalar_one()
        wv = (await conn.execute(text("SELECT id FROM scoring_weights_versions WHERE is_active"))).scalar_one()
        tag = uuid.uuid4().hex[:8]
        await conn.execute(
            text(
                "INSERT INTO niches (project_id, name, micro_niche, country, customer_group, core_problem, dedup_key,"
                " evidence_status, monetization_status, data_origin) SELECT :p, 'perf ' || g, 'perf ' || g, 'US', 'cg', 'cp',"
                " :t || '-' || g, CASE WHEN g % 3 = 0 THEN 'INSUFFICIENT_EVIDENCE' ELSE 'EVIDENCE_SUFFICIENT' END,"
                " CASE WHEN g % 2 = 0 THEN 'SIGNALS_FOUND' ELSE 'MONETIZATION_UNVERIFIED' END, 'REAL'"
                " FROM generate_series(1, :n) g"
            ),
            {"p": project, "t": tag, "n": n},
        )
        await conn.execute(
            text(
                "WITH ev AS (INSERT INTO niche_evaluations (niche_id, weights_version_id, criteria, coverage, scoring_status,"
                " opportunity_score, confidence_score, confidence_components, evidence_status, independent_groups,"
                " computed_without_ai, data_origin) SELECT id, :w, CAST(:c AS jsonb), 100, 'SCORED', (random() * 100)::numeric(5,2),"
                " (random() * 100)::numeric(5,2), '{}', evidence_status, 2, true, 'REAL' FROM niches WHERE dedup_key LIKE"
                " :t || '-%' RETURNING id, niche_id) UPDATE niches n SET latest_evaluation_id = ev.id FROM ev WHERE"
                " n.id = ev.niche_id"
            ),
            {"w": wv, "c": json.dumps(CRIT), "t": tag},
        )
        rows = (
            (await conn.execute(text("SELECT id FROM niches WHERE dedup_key LIKE :t || '-%'"), {"t": tag}))
            .scalars()
            .all()
        )
    return [str(r) for r in rows]


async def test_TC_E1_FR024_02_ranking_p95_under_500ms_with_5000_niches(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with discovery_client(migrated_db) as client:
        await _seed(clean_db, 5000)
        timings = []
        for i in range(30):
            lst = ("research", "affiliate", "needs_research")[i % 3]
            t0 = time.perf_counter()
            r = await client.get(f"/api/v1/niches?list={lst}&limit=50")
            timings.append(time.perf_counter() - t0)
            assert r.status_code == 200 and len(r.json()["items"]) == 50
        p95 = statistics.quantiles(timings, n=20)[18]
        print(f"perf: GET /niches p95 = {p95 * 1000:.1f} ms")
        assert p95 < 0.5


async def test_TC_E1_FR018_03_recompute_1000_niches_within_60s_without_ai(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    from nichepilot.modules.discovery.evaluation import evaluate_and_store

    async with discovery_client(migrated_db) as client:
        ids = await _seed(clean_db, 1000)
        sm = client.services.discovery.sessionmaker  # type: ignore[attr-defined]
        t0 = time.perf_counter()
        async with sm() as s, s.begin():
            for nid in ids:
                await evaluate_and_store(s, uuid.UUID(nid), computed_without_ai=True)
        elapsed = time.perf_counter() - t0
        print(f"perf: recompute 1000 niches = {elapsed:.1f} s")
        async with clean_db.connect() as conn:
            ai = (await conn.execute(text("SELECT count(*) FROM ai_usage_logs"))).scalar_one()
        assert elapsed <= 60 and ai == 0
