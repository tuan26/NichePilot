"""T016 – idempotent & độ bền (FR-003, FR-004; SC-004): chạy lại không trùng, hủy qua API job E0, hết ngân sách → PAUSED_BUDGET. MOCK."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import csrf_headers, run_worker_once
from tests.discovery_helpers import allow_test_source
from tests.keywords_helpers import keywords_client, run_keywords, seed_niche_with_products

pytestmark = [pytest.mark.integration, pytest.mark.keywords, pytest.mark.mock]
COUNTS = {
    "keywords": "SELECT count(*) FROM keywords",
    "origins": "SELECT count(*) FROM keyword_origins",
    "clusters": "SELECT count(*) FROM keyword_clusters",
    "serp": "SELECT count(*) FROM serp_observations",
    "pages": "SELECT count(*) FROM competitor_pages",
    "sources": "SELECT count(*) FROM research_sources",
    "evidence": "SELECT count(*) FROM research_evidence WHERE subject_type = 'keyword_run'",
}


async def _counts(engine: AsyncEngine) -> dict[str, int]:
    async with engine.connect() as conn:
        return {k: int((await conn.execute(text(q))).scalar_one()) for k, q in COUNTS.items()}


async def test_TC_E3_FR004_02_TC_E3_SC004_02_rerun_no_duplicates(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with keywords_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche_with_products(client)
        await run_keywords(client, niche)
        first = await _counts(clean_db)
        await run_keywords(client, niche)
        second = await _counts(clean_db)
        assert first["keywords"] > 0 and first["serp"] > 0
        assert {k: v for k, v in second.items() if k != "evidence"} == {
            k: v for k, v in first.items() if k != "evidence"
        }
        async with clean_db.connect() as conn:
            dups = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM (SELECT 1 FROM keywords GROUP BY project_id, niche_id, data_origin, dedup_key"
                        " HAVING count(*) > 1) d"
                    )
                )
            ).scalar_one()
            unclustered = (
                await conn.execute(text("SELECT count(*) FROM keywords WHERE cluster_id IS NULL"))
            ).scalar_one()
        assert dups == 0 and unclustered == 0


async def test_TC_E3_FR003_02_cancel_via_e0_job_api(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with keywords_client(migrated_db) as client:
        niche = await seed_niche_with_products(client)
        r = await client.post("/api/v1/keyword-runs", json={"niche_id": niche}, headers=csrf_headers(client))
        job = r.json()["job_id"]
        c = await client.post(f"/api/v1/jobs/{job}/cancel", headers=csrf_headers(client))
        assert c.status_code in (200, 202), c.text
        await run_worker_once(client)
        assert (await client.get(f"/api/v1/jobs/{job}")).json()["status"] == "CANCELLED"


async def test_TC_E3_FR003_03_budget_exhausted_pauses(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with keywords_client(migrated_db) as client:
        niche = await seed_niche_with_products(client)
        r = await client.post(
            "/api/v1/jobs",
            json={"job_type": "keywords.run", "params": {"niche_id": niche}, "budget_limit_usd": "0.003"},
            headers=csrf_headers(client),
        )
        assert r.status_code in (200, 201, 202), r.text
        await run_worker_once(client)
        async with clean_db.connect() as conn:
            status = (
                await conn.execute(text("SELECT status FROM agent_jobs WHERE job_type = 'keywords.run'"))
            ).scalar_one()
        assert status == "PAUSED_BUDGET"
