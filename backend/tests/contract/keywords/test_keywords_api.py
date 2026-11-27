"""T027 – hợp đồng API E3: danh sách/chi tiết cluster, MOCK ẩn mặc định, disclaimer, chỉ số UNKNOWN, ledger 503, ngân sách (FR-009, FR-021, FR-027, FR-028)."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.discovery_helpers import allow_test_source
from tests.keywords_helpers import keywords_client, run_keywords, seed_niche_with_products, start_run

pytestmark = [pytest.mark.integration, pytest.mark.keywords, pytest.mark.mock]


async def test_TC_E3_FR028_01_TC_E3_FR027_01_lists_detail_and_mock_filter(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with keywords_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche_with_products(client)
        run = await run_keywords(client, niche)
        default = (await client.get(f"/api/v1/niches/{niche}/keyword-clusters")).json()
        assert default["items"] == [] and default["disclaimer_key"] == "keywords.opportunity.disclaimer"  # MOCK ẩn
        ranked = (await client.get(f"/api/v1/niches/{niche}/keyword-clusters", params={"include_mock": True})).json()[
            "items"
        ]
        assert ranked and all(i["data_origin"] == "MOCK" for i in ranked)
        scores = [i["opportunity_score"] for i in ranked]
        assert scores == sorted(scores, reverse=True) and None not in scores
        for i in ranked:
            assert set(i) >= {
                "cluster_id",
                "name",
                "intent",
                "keyword_count",
                "long_tail_count",
                "confidence_score",
                "decision_status",
            }
        info = (
            await client.get(
                f"/api/v1/niches/{niche}/keyword-clusters", params={"include_mock": True, "intent": "INFORMATIONAL"}
            )
        ).json()["items"]
        assert info and {i["intent"] for i in info} == {"INFORMATIONAL"}
        detail = (await client.get(f"/api/v1/keyword-clusters/{ranked[0]['cluster_id']}")).json()
        assert detail["disclaimer_key"] == "keywords.opportunity.disclaimer"  # TC_E3_FR021_01
        assert detail["keywords"] and detail["keyword_count"] == len(detail["keywords"])
        for k in detail["keywords"]:  # TC_E3_FR009_03
            assert k["origins"] and all(o["label"] for o in k["origins"])
            assert {
                m: k["metrics"][m]["value"] for m in ("search_volume", "cpc", "keyword_difficulty")
            } == dict.fromkeys(("search_volume", "cpc", "keyword_difficulty"))
        summary = (await client.get(f"/api/v1/niches/{niche}/keyword-summary", params={"include_mock": True})).json()
        assert summary["keyword_count"] == run["metrics"]["keywords_found"] and summary["top_clusters"]
        assert (await client.get(f"/api/v1/niches/{niche}/keyword-summary")).json()["keyword_count"] == 0
        runs = (await client.get("/api/v1/keyword-runs", params={"niche_id": niche, "include_mock": True})).json()[
            "items"
        ]
        assert [r["id"] for r in runs] == [run["id"]]
        nf = await client.get("/api/v1/keyword-clusters/00000000-0000-0000-0000-000000000000")
        assert nf.status_code == 404 and nf.json()["code"] == "KEYWORD_CLUSTER_NOT_FOUND"
        nf = await client.get("/api/v1/keyword-runs/00000000-0000-0000-0000-000000000000")
        assert nf.status_code == 404 and nf.json()["code"] == "KEYWORD_RUN_NOT_FOUND"
        nn = await client.get("/api/v1/niches/00000000-0000-0000-0000-000000000000/keyword-clusters")
        assert nn.json()["code"] == "NICHE_NOT_FOUND"


async def test_TC_E3_FR028_02_ledger_gate(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with keywords_client(migrated_db) as client:
        async with clean_db.begin() as conn:
            await conn.execute(text("UPDATE erasure_ledger_state SET status = 'BLOCKED', last_error = 'TEST'"))
        client.services.discovery._health = None  # type: ignore[attr-defined]
        r = await client.get("/api/v1/keyword-runs")
        assert r.status_code == 503 and r.json()["code"] == "ERASURE_LEDGER_NOT_APPLIED"


async def test_TC_E3_FR028_04_budget_not_configured_and_validation(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with keywords_client(migrated_db) as client:
        niche = await seed_niche_with_products(client)
        for bad in ({"max_keywords": 500}, {"serp_keywords": -1}, {"search_volume_source": "x"}):
            r = await start_run(client, niche, **bad)
            assert r.status_code == 422, (bad, r.text)
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
