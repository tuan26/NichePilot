"""T025 – độ bền & idempotent (FR-003…FR-005, FR-015; SC-003): chạy lại không trùng, hủy qua API job E0, hết ngân sách → PAUSED_BUDGET.
MOCK."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import csrf_headers, run_worker_once
from tests.discovery_helpers import allow_test_source
from tests.fakes.products_ai import ScriptedProductsAI
from tests.products_helpers import products_client, run_products, seed_niche

pytestmark = [pytest.mark.integration, pytest.mark.products, pytest.mark.mock]
DUP = {
    "products": "SELECT count(*) FROM (SELECT 1 FROM products GROUP BY project_id, data_origin, dedup_key HAVING count(*) > 1) d",
    "programs": "SELECT count(*) FROM (SELECT 1 FROM affiliate_programs GROUP BY project_id, data_origin, dedup_key HAVING count(*) > 1) d",
    "sources": "SELECT count(*) FROM (SELECT 1 FROM research_sources GROUP BY canonical_url, content_hash HAVING count(*) > 1) d",
    "attributes": (
        "SELECT count(*) FROM (SELECT 1 FROM research_evidence WHERE subject_type IN ('product','affiliate_program')"
        " GROUP BY subject_id, claim_key, content_hash HAVING count(*) > 1) d"
    ),
}


async def _dups(engine: AsyncEngine) -> dict[str, int]:
    async with engine.connect() as conn:
        return {k: int((await conn.execute(text(q))).scalar_one()) for k, q in DUP.items()}


async def test_TC_E2_FR005_02_TC_E2_FR015_01_TC_E2_SC003_01_rerun_no_duplicates(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with products_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        await run_products(client, niche)
        async with clean_db.connect() as conn:
            before = (
                await conn.execute(
                    text("SELECT count(*) FROM research_evidence WHERE subject_type IN ('product','affiliate_program')")
                )
            ).scalar_one()
        await run_products(client, niche)
        async with clean_db.connect() as conn:
            products = (await conn.execute(text("SELECT count(*) FROM products"))).scalar_one()
            pairs = (await conn.execute(text("SELECT count(*) FROM product_niches"))).scalar_one()
            after = (
                await conn.execute(
                    text("SELECT count(*) FROM research_evidence WHERE subject_type IN ('product','affiliate_program')")
                )
            ).scalar_one()
        assert (
            products == 2 and pairs == 2 and after == before
        )  # thuộc tính trùng (cùng nguồn, cùng giá trị) không được thêm
        assert await _dups(clean_db) == dict.fromkeys(DUP, 0)


async def test_TC_E2_FR003_01_cancel_via_e0_job_api(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        r = await client.post("/api/v1/product-runs", json={"niche_id": niche}, headers=csrf_headers(client))
        job = r.json()["job_id"]
        c = await client.post(f"/api/v1/jobs/{job}/cancel", headers=csrf_headers(client))
        assert c.status_code in (200, 202), c.text
        await run_worker_once(client)
        status = (await client.get(f"/api/v1/jobs/{job}")).json()["status"]
        assert status == "CANCELLED"


async def test_TC_E2_FR004_02_budget_exhausted_pauses(clean_db: AsyncEngine, migrated_db: str) -> None:
    ai = ScriptedProductsAI()
    async with products_client(migrated_db, ai=ai) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        r = await client.post(
            "/api/v1/jobs",
            json={"job_type": "products.run", "params": {"niche_id": niche}, "budget_limit_usd": "0.003"},
            headers=csrf_headers(client),
        )
        assert r.status_code in (200, 201, 202), r.text
        await run_worker_once(client)
        async with clean_db.connect() as conn:
            job = (
                await conn.execute(text("SELECT status, budget_limit_usd, cost_accumulated_usd FROM agent_jobs"))
            ).one()
            sent = (await conn.execute(text("SELECT count(*) FROM ai_usage_logs WHERE sent"))).scalar_one()
        assert job.status == "PAUSED_BUDGET" and job.budget_limit_usd == Decimal("0.003000")
        assert job.cost_accumulated_usd <= job.budget_limit_usd and sent == len(ai.requests)
