"""T040 – đánh giá theo cặp, tái lập, tính lại khi bằng chứng bị xóa (FR-007, FR-027…FR-029a; R-06; SC-004). MOCK."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from nichepilot.modules.products import evaluation
from tests.api_helpers import csrf_headers
from tests.discovery_helpers import allow_test_source
from tests.products_helpers import product_id, products_client, run_products, seed_niche

pytestmark = [pytest.mark.integration, pytest.mark.products, pytest.mark.mock]


async def test_TC_E2_FR027_07_reproducible_and_versioned(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        await run_products(client, niche)
        pid = await product_id(clean_db, "StockPal")
        item = (await client.get(f"/api/v1/products/{pid}", params={"niche_id": niche})).json()
        ev = item["evaluation"]
        assert (
            ev["opportunity_score"] == 88.24 and ev["coverage"] == 85.0 and ev["weights_version"] == 1
        )  # ví dụ tính tay
        assert set(ev["criteria"]) == {"fit", "affiliate", "eligibility", "quality", "price_fit"}
        assert "price_fit" in ev["missing"]  # TC_E2_FR028_04: hiển thị thông tin còn thiếu
        async with clean_db.connect() as conn:
            pair = (
                await conn.execute(text("SELECT id FROM product_niches WHERE product_id = :p"), {"p": pid})
            ).scalar_one()
            n_before = (
                await conn.execute(
                    text("SELECT count(*) FROM product_evaluations WHERE product_niche_id = :p"), {"p": pair}
                )
            ).scalar_one()
        async with async_sessionmaker(clean_db)() as s, s.begin():
            again = await evaluation.evaluate_pair(
                s, pair
            )  # SC-004: tính lại từ dữ liệu + phiên bản đã lưu → cùng kết quả
        assert not again.created and float(again.opportunity or 0) == 88.24
        async with clean_db.connect() as conn:
            n_after = (
                await conn.execute(
                    text("SELECT count(*) FROM product_evaluations WHERE product_niche_id = :p"), {"p": pair}
                )
            ).scalar_one()
        assert n_after == n_before


async def test_TC_E2_FR029a_01_same_product_two_niches(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        await run_products(client, niche)
        pid = await product_id(clean_db, "StockPal")
        async with clean_db.begin() as conn:
            row = (await conn.execute(text("SELECT project_id FROM niches WHERE id = :n"), {"n": niche})).scalar_one()
            other = uuid.uuid4()
            await conn.execute(
                text(
                    "INSERT INTO niches (id, project_id, name, micro_niche, country, customer_group, core_problem, dedup_key,"
                    " data_origin, evidence_status) VALUES (:i, :p, '[MOCK] UK bakeries', '[MOCK] UK', 'GB', 'bakers',"
                    " 'stock', 'mock-uk', 'MOCK', 'EVIDENCE_SUFFICIENT')"
                ),
                {"i": other, "p": row},
            )
            pair2 = (
                await conn.execute(
                    text(
                        "INSERT INTO product_niches (product_id, niche_id, data_origin) VALUES (:p, :n, 'MOCK') RETURNING id"
                    ),
                    {"p": pid, "n": other},
                )
            ).scalar_one()
        async with async_sessionmaker(clean_db)() as s, s.begin():
            res = await evaluation.evaluate_pair(s, pair2)
        # cùng sản phẩm, ngách khác: không có liên kết pain point → fit UNKNOWN → điểm khác ngách gốc
        assert res.scoring_status == "INSUFFICIENT_SCORING_DATA" and res.readiness == "READY_TO_PROMOTE"


async def test_TC_E2_FR007_02_erasing_commission_recomputes(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        await run_products(client, niche)
        pid = await product_id(clean_db, "StockPal")
        async with clean_db.connect() as conn:
            ids = (
                (await conn.execute(text("SELECT id FROM research_evidence WHERE claim_key = 'commission'")))
                .scalars()
                .all()
            )
        for eid in ids:
            r = await client.post(
                f"/api/v1/evidence/{eid}/erase", json={"reason": "Owner request (test)"}, headers=csrf_headers(client)
            )
            assert r.status_code in (200, 202), r.text
        item = (await client.get(f"/api/v1/products/{pid}", params={"niche_id": niche})).json()
        assert item["evaluation"]["criteria"]["affiliate"]["level"] is None
        assert "commission" in item["evaluation"]["missing"]
        attrs = {a["key"]: a for a in item["programs"][0]["attributes"]}
        assert attrs["commission"]["status"] == "UNKNOWN"
