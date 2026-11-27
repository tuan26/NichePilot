"""T023 – lượt `products.run` đầy đủ với nguồn + AI giả lập (FR-007, FR-010…FR-014, FR-035, FR-038).

Không mạng, không API có phí; mọi dữ liệu gắn MOCK. KHÔNG chứng minh nguồn thật hay Claude API thật.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.discovery_helpers import allow_test_source
from tests.fakes.products_ai import ScriptedProductsAI
from tests.products_helpers import product_id, products_client, run_products, seed_niche

pytestmark = [pytest.mark.integration, pytest.mark.products, pytest.mark.mock]


async def test_TC_E2_FR011_02_full_run_links_products_to_pain_points(clean_db: AsyncEngine, migrated_db: str) -> None:
    ai = ScriptedProductsAI()
    async with products_client(migrated_db, ai=ai) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        run = await run_products(client, niche)
        assert run["status"] == "SUCCEEDED", run
        assert (run["outcome"], run["stop_reason"]) == ("COMPLETED", "PRODUCTS_EXHAUSTED"), run
        async with clean_db.connect() as conn:
            prods = (
                await conn.execute(text("SELECT name, official_domain, data_origin FROM products ORDER BY name"))
            ).all()
            links = (
                await conn.execute(
                    text(
                        "SELECT p.name, count(*) FROM product_pain_point_links l JOIN product_niches pn ON pn.id = l.product_niche_id"
                        " JOIN products p ON p.id = pn.product_id JOIN research_evidence e ON e.id = l.evidence_id"
                        " WHERE e.lifecycle_status = 'ACTIVE' GROUP BY p.name"
                    )
                )
            ).all()
        assert [(p.name, p.official_domain, p.data_origin) for p in prods] == [
            ("DoughTrack", "doughtrack.example", "MOCK"),
            ("StockPal", "stockpal.example", "MOCK"),
        ]
        assert {n for n, c in links if c >= 1} == {"DoughTrack", "StockPal"}


async def test_TC_E2_FR013_01_attributes_have_source_and_status(clean_db: AsyncEngine, migrated_db: str) -> None:
    """TC_E2_FR012_01 website chính thức; TC_E2_FR013_01 giá theo gói; TC_E2_FR014_01 khách hàng mục tiêu; TC_E2_FR007_01 nguồn."""
    async with products_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        await run_products(client, niche)
        pid = await product_id(clean_db, "StockPal")
        detail = (await client.get(f"/api/v1/products/{pid}", params={"niche_id": niche})).json()
        attrs = {a["key"]: a for a in detail["attributes"]}
        assert attrs["official_website"]["status"] == "VERIFIED"
        assert attrs["price"]["status"] == "VERIFIED"
        assert attrs["price"]["value"] == [
            {"plan": "Starter", "amount": 19.0, "currency": "USD", "period": "month", "promo": False}
        ]
        assert attrs["feature"]["status"] == "VERIFIED" and len(attrs["feature"]["value"]) == 4
        assert attrs["target_customer"]["status"] == "VERIFIED"
        for a in detail["attributes"]:
            for v in a["values"]:  # TC_E2_FR007_01: URL nguồn, trích đoạn, thời điểm thu thập; VERIFIED có verified_at
                assert v["source_url"] and v["excerpt"] and v["collected_at"]
                assert (v["status"] == "VERIFIED") == (v["verified_at"] is not None)
        assert detail["persona_match"] == "MATCH" and detail["pain_points"]  # TC_E2_FR014_01
        assert detail["data_origin"] == "MOCK" and detail["disclaimer_key"] == "products.opportunity.disclaimer"


async def test_TC_E2_FR038_01_run_metrics_and_mock_origin(clean_db: AsyncEngine, migrated_db: str) -> None:
    """TC_E2_FR035_01: lượt mock gắn MOCK, chi phí tách REAL/MOCK; TC_E2_FR010_01: chỉ trích đoạn REDACTED vào prompt."""
    ai = ScriptedProductsAI()
    async with products_client(migrated_db, ai=ai) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        run = await run_products(client, niche)
        m = run["metrics"]
        for key in (
            "ai_calls",
            "cost_real_usd",
            "cost_mock_usd",
            "pages_attempted",
            "pages_succeeded",
            "pages_failed",
            "pages_skipped",
            "skipped_by_reason",
            "products_found",
            "programs_by_status",
            "elapsed_active_s",
        ):
            assert key in m, key
        assert run["data_origin"] == "MOCK" and float(m["cost_real_usd"]) == 0 and float(m["cost_mock_usd"]) > 0
        assert m["products_found"] == 2 and m["pages_succeeded"] >= 5
        assert m["skipped_by_reason"].get("LOGIN_REQUIRED") == 1 or "members.example" not in str(m)
        async with clean_db.connect() as conn:
            ev = (
                (
                    await conn.execute(
                        text(
                            "SELECT DISTINCT redaction_status FROM research_evidence WHERE subject_type IN ('product_run','product','affiliate_program')"
                        )
                    )
                )
                .scalars()
                .all()
            )
        assert ev == ["REDACTED"]
        assert "<untrusted_content" in ai.prompt_text()
