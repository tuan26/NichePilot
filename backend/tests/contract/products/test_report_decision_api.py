"""T049 – quyết định, tóm tắt ngách, báo cáo (FR-032…FR-034, FR-037). MOCK."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import csrf_headers
from tests.discovery_helpers import allow_test_source
from tests.products_helpers import product_id, products_client, run_products, seed_niche

E1_SNAPSHOT = "SELECT n.*, (SELECT count(*) FROM niche_evaluations) AS evals FROM niches n"
pytestmark = [pytest.mark.integration, pytest.mark.products, pytest.mark.mock]


async def test_TC_E2_FR033_01_decision_requires_reason_keeps_score(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        await run_products(client, niche)
        pid = await product_id(clean_db, "StockPal")
        before = (await client.get(f"/api/v1/products/{pid}", params={"niche_id": niche})).json()
        bad = await client.post(
            f"/api/v1/products/{pid}/decision",
            json={"niche_id": niche, "decision": "WATCH", "reason": ""},
            headers=csrf_headers(client),
        )
        assert bad.status_code == 422
        ok = await client.post(
            f"/api/v1/products/{pid}/decision",
            json={"niche_id": niche, "decision": "WATCH", "reason": "[MOCK] wait for real terms check"},
            headers=csrf_headers(client),
        )
        assert ok.status_code == 200 and ok.json()["decision_status"] == "WATCH"
        assert ok.json()["evaluation"]["opportunity_score"] == before["evaluation"]["opportunity_score"]
        async with clean_db.connect() as conn:
            audit = (
                await conn.execute(text("SELECT after FROM audit_logs WHERE action = 'product.decision'"))
            ).scalar_one()
        assert audit["decision_status"] == "WATCH"
        rej = await client.post(
            f"/api/v1/products/{pid}/decision",
            json={"niche_id": niche, "decision": "REJECTED", "reason": "[MOCK] not a fit"},
            headers=csrf_headers(client),
        )
        assert rej.status_code == 200
        ranked = (await client.get(f"/api/v1/niches/{niche}/products", params={"include_mock": True})).json()["items"]
        assert "StockPal" not in [i["name"] for i in ranked]  # REJECTED không vào xếp hạng


async def test_TC_E2_FR034_01_summary_does_not_touch_e1(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        async with clean_db.connect() as conn:
            before = [tuple(r) for r in (await conn.execute(text(E1_SNAPSHOT))).all()]
        await run_products(client, niche)
        summary = (await client.get(f"/api/v1/niches/{niche}/product-summary", params={"include_mock": True})).json()
        assert summary == {
            "products": 2,
            "programs_verified": 2,
            "ready_to_promote": 1,
            "monetization_risk": False,
            "last_run_id": summary["last_run_id"],
        }
        assert (await client.get(f"/api/v1/niches/{niche}/product-summary")).json()["products"] == 0  # MOCK ẩn
        async with clean_db.connect() as conn:
            after = [
                tuple(r)
                for r in (
                    await conn.execute(
                        text("SELECT n.*, (SELECT count(*) FROM niche_evaluations) AS evals FROM niches n")
                    )
                ).all()
            ]
        assert after == before  # không đổi điểm/đánh giá E1


async def test_TC_E2_FR032_02_markdown_report_vi_en(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        await run_products(client, niche)
        hidden = await client.get(f"/api/v1/niches/{niche}/product-report", params={"format": "markdown"})
        assert "StockPal" not in hidden.text and "(không có sản phẩm)" in hidden.text
        vi = await client.get(
            f"/api/v1/niches/{niche}/product-report", params={"format": "markdown", "include_mock": True}
        )
        en = await client.get(
            f"/api/v1/niches/{niche}/product-report", params={"format": "markdown", "include_mock": True, "lang": "en"}
        )
        assert (
            "Báo cáo sản phẩm" in vi.text and "StockPal [MOCK]" in vi.text and "không phải dự báo doanh thu" in vi.text
        )
        assert "Product & affiliate report" in en.text and "not a revenue forecast" in en.text
        data = (await client.get(f"/api/v1/niches/{niche}/product-report", params={"include_mock": True})).json()
        assert [i["name"] for i in data["ranked"]] == ["StockPal", "DoughTrack"]
