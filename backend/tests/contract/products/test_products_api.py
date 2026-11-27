"""T041 – hợp đồng danh sách/chi tiết/trọng số (FR-027, FR-031, FR-032, FR-035, FR-037). MOCK."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import csrf_headers, run_worker_once
from tests.discovery_helpers import allow_test_source
from tests.products_helpers import products_client, run_products, seed_niche

pytestmark = [pytest.mark.integration, pytest.mark.products, pytest.mark.mock]


async def test_TC_E2_FR032_01_TC_E2_FR035_02_lists_and_mock_filter(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        await run_products(client, niche)
        assert (await client.get(f"/api/v1/niches/{niche}/products")).json()["items"] == []  # MOCK ẩn mặc định
        ranked = (await client.get(f"/api/v1/niches/{niche}/products", params={"include_mock": True})).json()["items"]
        needs = (
            await client.get(
                f"/api/v1/niches/{niche}/products", params={"include_mock": True, "list": "needs_research"}
            )
        ).json()["items"]
        assert [i["name"] for i in ranked] == ["StockPal", "DoughTrack"]  # Opportunity giảm dần
        assert ranked[0]["readiness_status"] == "READY_TO_PROMOTE"
        assert (
            ranked[1]["readiness_status"] == "ELIGIBILITY_UNVERIFIED" and "MONETIZATION_RISK" in ranked[1]["risk_flags"]
        )
        assert needs == [] and all(i["data_origin"] == "MOCK" for i in ranked)
        # nâng ngưỡng Coverage → đọc lại tính lại theo phiên bản mới, sản phẩm chuyển sang "cần nghiên cứu thêm"
        r = await client.post(
            "/api/v1/product-scoring/weights",
            json={
                "weights": {"fit": 25, "affiliate": 25, "eligibility": 20, "quality": 15, "price_fit": 15},
                "coverage_min": 90,
            },
            headers=csrf_headers(client),
        )
        assert r.status_code == 201
        needs = (
            await client.get(
                f"/api/v1/niches/{niche}/products", params={"include_mock": True, "list": "needs_research"}
            )
        ).json()["items"]
        assert {i["name"] for i in needs} == {"StockPal", "DoughTrack"}
        assert all(i["evaluation"]["scoring_status"] == "INSUFFICIENT_SCORING_DATA" for i in needs)
        missing = (await client.get("/api/v1/niches/00000000-0000-0000-0000-000000000000/products")).json()
        assert missing["code"] == "NICHE_NOT_FOUND"


async def test_TC_E2_FR031_01_disclaimer_key(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        await run_products(client, niche)
        async with clean_db.connect() as conn:
            pid = (await conn.execute(text("SELECT id FROM products LIMIT 1"))).scalar_one()
        d = (await client.get(f"/api/v1/products/{pid}", params={"niche_id": niche})).json()
        assert d["disclaimer_key"] == "products.opportunity.disclaimer"
        nf = await client.get(f"/api/v1/products/{pid}", params={"niche_id": "00000000-0000-0000-0000-000000000000"})
        assert nf.json()["code"] == "PRODUCT_NOT_FOUND"


async def test_TC_E2_FR027_08_TC_E2_FR037_01_weights_versioning(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        got = (await client.get("/api/v1/product-scoring/weights")).json()
        assert got["active"]["version"] == 1 and got["active"]["coverage_min"] == 60
        bad = await client.post(
            "/api/v1/product-scoring/weights",
            json={"weights": {"fit": 30, "affiliate": 25, "eligibility": 20, "quality": 15, "price_fit": 15}},
            headers=csrf_headers(client),
        )
        assert bad.status_code == 422 and bad.json()["code"] == "PRODUCT_WEIGHTS_INVALID"
        ok = await client.post(
            "/api/v1/product-scoring/weights",
            json={"weights": {"fit": 30, "affiliate": 20, "eligibility": 20, "quality": 15, "price_fit": 15}},
            headers=csrf_headers(client),
        )
        assert ok.status_code == 201 and ok.json()["version"] == 2 and ok.json()["recompute_job_id"]
        await run_worker_once(client)
        async with clean_db.connect() as conn:
            audit = (
                await conn.execute(text("SELECT count(*) FROM audit_logs WHERE action = 'product.weights_created'"))
            ).scalar_one()
            job = (
                await conn.execute(text("SELECT status FROM agent_jobs WHERE job_type = 'products.recompute'"))
            ).scalar_one()
        assert audit == 1 and job == "SUCCEEDED"
        assert (await client.get("/api/v1/product-scoring/weights")).json()["active"]["version"] == 2
