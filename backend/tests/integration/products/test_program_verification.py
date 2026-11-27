"""T032 – xác minh chương trình affiliate (FR-008, FR-009, FR-017, FR-018, FR-022; QA-04, QA-05). MOCK."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.discovery_helpers import allow_test_source
from tests.fakes.products_ai import ScriptedProductsAI, default_program_extract
from tests.products_helpers import product_id, products_client, run_products, seed_niche

pytestmark = [pytest.mark.integration, pytest.mark.products, pytest.mark.mock]


async def _program(client: Any, engine: AsyncEngine, niche: str, name: str) -> dict[str, Any]:
    pid = await product_id(engine, name)
    detail = (await client.get(f"/api/v1/products/{pid}", params={"niche_id": niche})).json()
    assert detail["programs"], detail
    return dict(detail["programs"][0])


async def test_TC_E2_FR017_01_TC_E2_FR008_05_vendor_program_and_conflict(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with products_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        await run_products(client, niche)
        prog = await _program(client, clean_db, niche, "StockPal")
        assert prog["operator_type"] == "VENDOR" and prog["operator_domain"] == "stockpal.example"
        assert prog["terms_url"] == "https://stockpal.example/partners" and prog["verification_status"] == "VERIFIED"
        attrs = {a["key"]: a for a in prog["attributes"]}
        com = attrs["commission"]
        assert (
            com["status"] == "CONFLICTING" and "THIRD_PARTY_DISAGREES" in com["flags"]
        )  # QA-05: đủ mọi giá trị + nguồn
        assert {(v["value"]["value"], v["status"]) for v in com["values"]} == {(30.0, "VERIFIED"), (25.0, "INFERRED")}
        assert {v["source_url"] for v in com["values"]} == {
            "https://stockpal.example/partners",
            "https://affiliatedeals.example/stockpal-review",
        }
        assert (
            attrs["vn_eligibility"]["value"] == {"status": "ALLOWED"}
            and attrs["vn_eligibility"]["status"] == "VERIFIED"
        )


async def test_TC_E2_FR022_02_unreadable_terms_and_silent_vietnam(clean_db: AsyncEngine, migrated_db: str) -> None:
    """DoughTrack: điều khoản không nêu Việt Nam/thị trường → UNKNOWN; trang cần đăng nhập bị bỏ qua (TC_E2_FR018_03 – QA-04)."""
    async with products_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        run = await run_products(client, niche)
        prog = await _program(client, clean_db, niche, "DoughTrack")
        attrs = {a["key"]: a for a in prog["attributes"]}
        assert attrs["vn_eligibility"]["status"] == "UNKNOWN" and attrs["vn_eligibility"]["value"] is None
        assert attrs["promotion_regions"]["status"] == "UNKNOWN"
        assert attrs["ad_restrictions"]["status"] == "UNKNOWN"  # không thấy ≠ "không có giới hạn"
        assert "members.example" not in " ".join(v["source_url"] or "" for a in prog["attributes"] for v in a["values"])
        assert run["metrics"]["pages_attempted"] >= run["metrics"]["pages_succeeded"]


async def test_TC_E2_FR018_03_no_terms_page_means_unverified(clean_db: AsyncEngine, migrated_db: str) -> None:
    def only_third_party(req: Any) -> dict[str, Any]:
        out = default_program_extract(req)
        for p in out["programs"]:
            p["operator_type"] = "NETWORK"
            p["terms_url"] = (
                "https://unknown-network.example/terms"  # không có trong kết quả tìm kiếm → không thành tên miền vận hành
            )
        return out

    async with products_client(
        migrated_db, ai=ScriptedProductsAI({"products.program_extract": only_third_party})
    ) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        await run_products(client, niche)
        prog = await _program(client, clean_db, niche, "StockPal")
        assert prog["operator_domain"] is None and prog["verification_status"] == "PARTIAL"
        assert all(v["status"] == "INFERRED" for a in prog["attributes"] for v in a["values"])
        pid = await product_id(clean_db, "StockPal")
        item = (await client.get(f"/api/v1/products/{pid}", params={"niche_id": niche})).json()
        assert item["readiness_status"] == "ELIGIBILITY_UNVERIFIED"  # VN/thị trường chỉ INFERRED → không READY


async def test_TC_E2_FR009_04_fabricated_commission_becomes_unknown(clean_db: AsyncEngine, migrated_db: str) -> None:
    def fabricate(req: Any) -> dict[str, Any]:
        out = default_program_extract(req)
        for p in out["programs"]:
            if "commission" in p:
                p["commission"] = {**p["commission"], "value": 45}
        return out

    async with products_client(migrated_db, ai=ScriptedProductsAI({"products.program_extract": fabricate})) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        run = await run_products(client, niche)
        assert run["metrics"]["rejected_values"] >= 2
        async with clean_db.connect() as conn:
            n = (
                await conn.execute(text("SELECT count(*) FROM research_evidence WHERE claim_key = 'commission'"))
            ).scalar_one()
        assert n == 0  # không có hoa hồng nào không truy về được trích đoạn chứa nó
