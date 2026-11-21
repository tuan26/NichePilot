"""T088 – `GET/POST /api/v1/scoring/weights` (FR-018, FR-036): phiên bản mới active, bản cũ và đánh giá cũ không đổi, audit;
`recompute_existing` → job `discovery.recompute` 0 lời gọi AI, Opportunity tính lại theo trọng số mới. MOCK."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import csrf_headers, run_worker_once
from tests.discovery_helpers import allow_test_source, discovery_client
from tests.discovery_run import FORUM, REVIEW, run_discovery, set_search

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]
W2 = {
    "problem_severity": 35,
    "monetization": 20,
    "market_gap": 10,
    "reachability": 15,
    "competition_opportunity": 10,
    "demand_stability": 10,
}


async def test_TC_E1_FR018_01_invalid_weights_rejected_and_old_version_unchanged(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with discovery_client(migrated_db) as client:
        before = (await client.get("/api/v1/scoring/weights")).json()
        assert [v["version"] for v in before] == [1] and before[0]["is_active"]
        for bad in (
            {**W2, "problem_severity": 36},  # tổng 101
            {k: v for k, v in W2.items() if k != "demand_stability"},  # thiếu tiêu chí
            {**W2, "problem_severity": -5, "market_gap": 50},  # âm
            {**W2, "extra": 0},
        ):
            r = await client.post("/api/v1/scoring/weights", json={"weights": bad}, headers=csrf_headers(client))
            assert r.status_code == 422 and r.json()["code"] == "WEIGHTS_INVALID", bad
        assert (await client.get("/api/v1/scoring/weights")).json() == before


async def test_TC_E1_FR018_02_new_version_recompute_without_ai(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        await run_discovery(client)
        async with clean_db.connect() as conn:
            niche_id, old_eval = (
                await conn.execute(text("SELECT id, latest_evaluation_id FROM niches WHERE name LIKE '%bakery%'"))
            ).one()
            old = (
                await conn.execute(
                    text("SELECT opportunity_score FROM niche_evaluations WHERE id = :e"), {"e": old_eval}
                )
            ).scalar_one()
            ai_before = (await conn.execute(text("SELECT count(*) FROM ai_usage_logs"))).scalar_one()
        assert float(old) == 60.71  # ví dụ tính tay scoring-rubric §3
        r = await client.post(
            "/api/v1/scoring/weights",
            json={"weights": W2, "coverage_threshold": 60, "recompute_existing": True},
            headers=csrf_headers(client),
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["version"] == 2 and body["is_active"] and body["recompute_jobs"]
        await run_worker_once(client)
        async with clean_db.connect() as conn:
            versions = (
                await conn.execute(text("SELECT version, is_active FROM scoring_weights_versions ORDER BY version"))
            ).all()
            new_eval = (
                await conn.execute(
                    text(
                        "SELECT e.opportunity_score, e.computed_without_ai, w.version FROM niches n JOIN niche_evaluations e"
                        " ON e.id = n.latest_evaluation_id JOIN scoring_weights_versions w ON w.id = e.weights_version_id"
                        " WHERE n.id = :n"
                    ),
                    {"n": niche_id},
                )
            ).one()
            old_again = (
                await conn.execute(
                    text("SELECT opportunity_score FROM niche_evaluations WHERE id = :e"), {"e": old_eval}
                )
            ).scalar_one()
            ai_after = (await conn.execute(text("SELECT count(*) FROM ai_usage_logs"))).scalar_one()
            audit = (
                await conn.execute(
                    text("SELECT count(*) FROM audit_logs WHERE action = 'scoring.weights_version_created'")
                )
            ).scalar_one()
        assert [tuple(v) for v in versions] == [(1, False), (2, True)]
        assert float(new_eval.opportunity_score) == 64.29 and new_eval.computed_without_ai and new_eval.version == 2
        assert old_again == old  # đánh giá cũ bất biến
        assert ai_after == ai_before  # chấm lại không gọi AI
        assert audit == 1
        evals = (await client.get(f"/api/v1/niches/{niche_id}/evaluations")).json()
        assert [e["weights_version"] for e in evals][:2] == [2, 1]
