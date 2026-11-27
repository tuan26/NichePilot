"""T021 – hợp đồng `/api/v1/product-runs` (contracts/openapi.yaml; FR-001…FR-004, FR-006). MOCK."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import csrf_headers
from tests.discovery_helpers import allow_test_source
from tests.products_helpers import products_client, seed_niche, start_run

pytestmark = [pytest.mark.integration, pytest.mark.products, pytest.mark.mock]


async def test_TC_E2_FR001_03_TC_E2_FR002_01_create_and_read_run(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        r = await start_run(client, niche, max_products=3, page_limit=20)
        assert r.status_code == 202 and set(r.json()) == {"job_id", "run_id"}
        run = (await client.get(f"/api/v1/product-runs/{r.json()['run_id']}")).json()
        assert run["params"]["max_products"] == 3 and run["params"]["page_limit"] == 20 and run["niche_id"] == niche
        assert (await client.get("/api/v1/product-runs", params={"niche_id": niche})).json()["items"] == []  # MOCK ẩn
        listed = (await client.get("/api/v1/product-runs", params={"niche_id": niche, "include_mock": True})).json()
        assert [x["id"] for x in listed["items"]] == [r.json()["run_id"]]
        bad = await client.post(
            "/api/v1/product-runs", json={"niche_id": niche, "use_unverified": True}, headers=csrf_headers(client)
        )
        assert bad.status_code == 422  # trường lạ bị từ chối – không có lựa chọn dùng nguồn UNVERIFIED
        assert (await client.get("/api/v1/product-runs/00000000-0000-0000-0000-000000000000")).json()[
            "code"
        ] == "PRODUCT_RUN_NOT_FOUND"


async def test_TC_E2_FR003_02_one_active_run_per_niche(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        assert (await start_run(client, niche)).status_code == 202
        again = await start_run(client, niche)
        assert again.status_code == 409 and again.json()["code"] == "PRODUCT_RUN_ACTIVE"


async def test_TC_E2_FR006_01_no_allowed_source_rejected(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        niche = await seed_niche(client)
        r = await start_run(client, niche)
        assert r.status_code == 409 and r.json()["code"] == "NO_COMPLIANT_SEARCH_SOURCE"
        async with clean_db.connect() as conn:
            assert (await conn.execute(text("SELECT count(*) FROM agent_jobs"))).scalar_one() == 0


async def test_TC_E2_FR004_01_budget_not_configured(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        async with clean_db.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE settings SET value = to_jsonb('0'::text) WHERE key IN ('budget.daily_usd', 'budget.monthly_usd')"
                )
            )
        try:
            r = await start_run(client, niche)
            assert r.status_code == 422 and r.json()["code"] == "BUDGET_NOT_CONFIGURED"
        finally:
            async with clean_db.begin() as conn:
                await conn.execute(
                    text("UPDATE settings SET value = to_jsonb('3.00'::text) WHERE key = 'budget.daily_usd'")
                )
                await conn.execute(
                    text("UPDATE settings SET value = to_jsonb('30.00'::text) WHERE key = 'budget.monthly_usd'")
                )


async def test_TC_E2_FR001_04_schedule_requires_niche_and_no_batch(clean_db: AsyncEngine, migrated_db: str) -> None:
    """Không chạy hàng loạt: lịch `products.run` thiếu niche_id bị từ chối (Clarification Q1)."""
    async with products_client(migrated_db) as client:
        body = {
            "name": "[MOCK] all niches",
            "job_type": "products.run",
            "params": {},
            "cron_expr": "0 3 * * 1",
            "enabled": False,
        }
        r = await client.post("/api/v1/schedules", json=body, headers=csrf_headers(client))
        assert r.status_code == 422 and any(e["field"] == "params.niche_id" for e in r.json()["errors"])
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        # ngách bị loại sau khi lịch đã tạo → job dừng ở preflight, 0 lời gọi AI
        async with clean_db.begin() as conn:
            user = (await conn.execute(text("SELECT id FROM users LIMIT 1"))).scalar_one()
            await conn.execute(
                text(
                    "UPDATE niches SET decision_status = 'REJECTED', owner_decision_reason = '[MOCK]', decided_by = :u"
                ),
                {"u": user},
            )
        r2 = await client.post(
            "/api/v1/jobs",
            json={"job_type": "products.run", "params": {"niche_id": niche}},
            headers=csrf_headers(client),
        )
        assert r2.status_code in (200, 201, 202), r2.text
        from tests.api_helpers import run_worker_once

        await run_worker_once(client)
        async with clean_db.connect() as conn:
            row = (await conn.execute(text("SELECT outcome, stop_reason FROM product_runs"))).one()
            ai = (await conn.execute(text("SELECT count(*) FROM ai_usage_logs"))).scalar_one()
        assert tuple(row) == ("PARTIAL_COMPLETED", "NICHE_NOT_ELIGIBLE") and ai == 0


async def test_TC_E2_FR001_05_ineligible_niche_api(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        async with clean_db.begin() as conn:
            await conn.execute(text("UPDATE niches SET evidence_status = 'INSUFFICIENT_EVIDENCE'"))
        r = await start_run(client, niche)
        assert r.status_code == 409 and r.json()["code"] == "NICHE_NOT_ELIGIBLE"
