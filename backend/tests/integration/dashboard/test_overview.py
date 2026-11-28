"""T003/T004 – API tổng hợp dashboard E4 (FR-006…FR-012; SC-002). Dữ liệu MOCK từ lệnh seed E1–E3; không mạng, không AI."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from nichepilot.jobs import keywords_demo_seed
from tests.keywords_helpers import keywords_client, seed_niche_with_products

pytestmark = [pytest.mark.integration, pytest.mark.dashboard, pytest.mark.mock]


async def _seed_all(client: object) -> str:
    niche = await seed_niche_with_products(client)  # type: ignore[arg-type]
    await keywords_demo_seed.seed_demo(client.services.discovery.sessionmaker)  # type: ignore[attr-defined]
    return niche


async def test_TC_E4_FR006_01_TC_E4_SC002_01_overview_matches_db(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with keywords_client(migrated_db) as client:
        niche = await _seed_all(client)
        data = (await client.get("/api/v1/dashboard/overview", params={"include_mock": True})).json()
        async with clean_db.connect() as conn:
            n_niches = (
                await conn.execute(text("SELECT count(*) FROM niches WHERE merged_into_id IS NULL"))
            ).scalar_one()
            n_kw = (await conn.execute(text("SELECT count(*) FROM keywords"))).scalar_one()
            n_cl = (await conn.execute(text("SELECT count(DISTINCT cluster_id) FROM keywords"))).scalar_one()
            n_lt = (
                await conn.execute(text("SELECT count(*) FROM keywords WHERE length_class = 'LONG_TAIL'"))
            ).scalar_one()
            n_ready = (
                await conn.execute(
                    text("SELECT count(*) FROM product_niches WHERE readiness_status = 'READY_TO_PROMOTE'")
                )
            ).scalar_one()
        assert data["niches"]["total"] == n_niches and data["niches"]["by_evidence_status"]["EVIDENCE_SUFFICIENT"] >= 1
        assert data["products"] == {"total": 2, "ready_to_promote": n_ready}
        assert data["keywords"] == {"total": n_kw, "clusters": n_cl, "long_tail": n_lt}
        assert set(data["jobs"]) == {"by_status", "failed_7d"}
        top = data["top_niches"]
        assert top and top[0]["niche_id"] == niche  # TC_E4_FR012_01: điểm kèm Confidence
        assert top[0]["opportunity_score"] is not None and top[0]["confidence_score"] is not None


async def test_TC_E4_FR007_01_mock_hidden_by_default(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with keywords_client(migrated_db) as client:
        await _seed_all(client)
        data = (await client.get("/api/v1/dashboard/overview")).json()
        assert data["include_mock"] is False
        assert data["niches"]["total"] == 0 and data["products"]["total"] == 0 and data["keywords"]["total"] == 0
        assert data["top_niches"] == []


async def test_TC_E4_FR008_01_empty_database(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with keywords_client(migrated_db) as client:
        data = (await client.get("/api/v1/dashboard/overview", params={"include_mock": True})).json()
        assert data["niches"] == {"total": 0, "by_evidence_status": {}, "by_decision": {}}
        assert data["top_niches"] == [] and data["keywords"]["total"] == 0
        rows = (await client.get("/api/v1/dashboard/niches", params={"include_mock": True})).json()
        assert rows == {"items": [], "total": 0, "limit": 200}


async def test_TC_E4_FR010_01_TC_E4_FR011_01_research_niches(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with keywords_client(migrated_db) as client:
        niche = await _seed_all(client)
        data = (await client.get("/api/v1/dashboard/niches", params={"include_mock": True})).json()
        row = next(i for i in data["items"] if i["niche_id"] == niche)
        assert row["eligible"] is True and row["data_origin"] == "MOCK"  # TC_E4_FR009_01
        assert row["products"]["has_run"] is True and row["products"]["total"] == 2
        assert row["products"]["ready_to_promote"] == 1
        kw = row["keywords"]
        assert kw["has_run"] is True and kw["total"] > 0 and kw["clusters"] > 0
        best = kw["best_cluster"]
        assert best and best["opportunity_score"] is not None and best["confidence_score"] is not None
        clusters = (await client.get(f"/api/v1/niches/{niche}/keyword-clusters", params={"include_mock": True})).json()[
            "items"
        ]
        assert best["cluster_id"] == clusters[0]["cluster_id"]  # cùng xếp hạng với E3
        assert best["opportunity_score"] == clusters[0]["opportunity_score"]


async def test_TC_E4_FR009_02_not_run_and_ineligible(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with keywords_client(migrated_db) as client:
        from nichepilot.jobs import discovery_demo_seed

        niche = str((await discovery_demo_seed.seed_demo(client.services.discovery.sessionmaker))["niche_id"])  # type: ignore[attr-defined]
        row = (await client.get("/api/v1/dashboard/niches", params={"include_mock": True})).json()["items"][0]
        assert row["niche_id"] == niche
        assert row["products"] == {"has_run": False, "total": 0, "ready_to_promote": 0}
        assert row["keywords"]["has_run"] is False and row["keywords"]["best_cluster"] is None
        async with clean_db.begin() as conn:
            await conn.execute(text("UPDATE niches SET evidence_status = 'INSUFFICIENT_EVIDENCE'"))
        row = (await client.get("/api/v1/dashboard/niches", params={"include_mock": True})).json()["items"][0]
        assert row["eligible"] is False
