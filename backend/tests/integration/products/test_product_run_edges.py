"""T024 – lượt rỗng/lỗi (FR-006, FR-011, FR-016, FR-039; QA-03). MOCK."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from nichepilot.jobs.agents.product_discovery import ProductDiscoveryAgent
from tests.api_helpers import csrf_headers, run_worker_once
from tests.discovery_helpers import allow_test_source
from tests.fakes.products_ai import ScriptedProductsAI
from tests.products_helpers import products_client, run_products, seed_niche

pytestmark = [pytest.mark.integration, pytest.mark.products, pytest.mark.mock]


async def test_TC_E2_FR011_03_no_products_found_creates_nothing(clean_db: AsyncEngine, migrated_db: str) -> None:
    ai = ScriptedProductsAI({"products.extract": {"products": []}})
    async with products_client(migrated_db, ai=ai) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        run = await run_products(client, niche)
        assert (run["outcome"], run["stop_reason"]) == ("COMPLETED", "NO_PRODUCTS_FOUND")
        summary = (await client.get(f"/api/v1/niches/{niche}/product-summary", params={"include_mock": True})).json()
        assert summary["products"] == 0 and summary["monetization_risk"] is True
        async with clean_db.connect() as conn:
            assert (await conn.execute(text("SELECT count(*) FROM products"))).scalar_one() == 0


async def test_TC_E2_FR006_02_blocked_pages_are_skipped_with_reason(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        await allow_test_source(clean_db)
        web = client.mock_web  # type: ignore[attr-defined]
        web.robots["doughtrack.example"] = "User-agent: *\nDisallow: /\n"
        niche = await seed_niche(client)
        run = await run_products(client, niche)
        assert run["status"] == "SUCCEEDED"
        assert run["metrics"]["skipped_by_reason"].get("ROBOTS_DISALLOWED", 0) >= 2
        fetched = client.mock_fetcher.requested  # type: ignore[attr-defined]
        assert not [u for u in fetched if "doughtrack.example/" in u]  # robots tôn trọng: không tải trang


async def test_TC_E2_FR006_03_scheduled_run_without_sources_makes_no_ai_call(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    ai = ScriptedProductsAI()
    async with products_client(migrated_db, ai=ai) as client:
        niche = await seed_niche(client)
        r = await client.post(
            "/api/v1/jobs",
            json={"job_type": "products.run", "params": {"niche_id": niche}},
            headers=csrf_headers(client),
        )
        assert r.status_code in (200, 201, 202), r.text
        await run_worker_once(client)
        async with clean_db.connect() as conn:
            row = (await conn.execute(text("SELECT outcome, stop_reason FROM product_runs"))).one()
        assert tuple(row) == ("PARTIAL_COMPLETED", "NO_COMPLIANT_SEARCH_SOURCE") and ai.requests == []


async def test_TC_E2_FR016_01_sensitive_product_flagged_not_removed(clean_db: AsyncEngine, migrated_db: str) -> None:
    def extract(req: object) -> dict[str, object]:
        from tests.fakes.products_ai import default_extract

        out = default_extract(req)  # type: ignore[arg-type]
        for p in out["products"]:
            p["name"] = p["name"] + " CBD gummies"
        return out

    async with products_client(migrated_db, ai=ScriptedProductsAI({"products.extract": extract})) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        await run_products(client, niche, max_products=2)
        async with clean_db.connect() as conn:
            flags = (await conn.execute(text("SELECT risk_flags FROM products"))).scalars().all()
        assert flags and all("COMPLIANCE_SENSITIVE" in f for f in flags)


async def test_TC_E2_FR039_02_schema_invalid_output_not_stored(clean_db: AsyncEngine, migrated_db: str) -> None:
    ai = ScriptedProductsAI({"products.extract": {"products": [{"name": "X", "rating": 5}]}})
    async with products_client(migrated_db, ai=ai) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        run = await run_products(client, niche)
        assert run["stop_reason"] == "NO_PRODUCTS_FOUND"
        async with clean_db.connect() as conn:
            assert (await conn.execute(text("SELECT count(*) FROM products"))).scalar_one() == 0
        assert ProductDiscoveryAgent.definition.max_ai_calls == 60
