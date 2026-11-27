"""T031 – quyết định cluster (lý do bắt buộc, audit, điểm không đổi) và báo cáo JSON/Markdown VI/EN (FR-022…FR-026; BR-11; SC-007)."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import csrf_headers
from tests.discovery_helpers import allow_test_source
from tests.keywords_helpers import keywords_client, run_keywords, seed_niche_with_products

pytestmark = [pytest.mark.integration, pytest.mark.keywords, pytest.mark.mock]


async def _top(client: object, niche: str) -> dict[str, object]:
    r = await client.get(f"/api/v1/niches/{niche}/keyword-clusters", params={"include_mock": True})  # type: ignore[attr-defined]
    return dict(r.json()["items"][0])


async def test_TC_E3_FR025_01_decision_requires_reason_keeps_score(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with keywords_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche_with_products(client)
        await run_keywords(client, niche)
        top = await _top(client, niche)
        cid = top["cluster_id"]
        r = await client.post(
            f"/api/v1/keyword-clusters/{cid}/decision",
            json={"decision": "WATCH", "reason": ""},
            headers=csrf_headers(client),
        )
        assert r.status_code == 422
        r = await client.post(
            f"/api/v1/keyword-clusters/{cid}/decision",
            json={"decision": "WATCH", "reason": "Theo dõi thêm"},
            headers=csrf_headers(client),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["decision_status"] == "WATCH" and body["decision_reason"] == "Theo dõi thêm"
        assert body["opportunity_score"] == top["opportunity_score"]
        r = await client.post(
            f"/api/v1/keyword-clusters/{cid}/decision",
            json={"decision": "REJECTED", "reason": "Không phù hợp"},
            headers=csrf_headers(client),
        )
        ranked = (await client.get(f"/api/v1/niches/{niche}/keyword-clusters", params={"include_mock": True})).json()[
            "items"
        ]
        assert cid not in {i["cluster_id"] for i in ranked}  # REJECTED không vào danh sách xếp hạng
        async with clean_db.connect() as conn:
            n = (
                await conn.execute(text("SELECT count(*) FROM audit_logs WHERE action = 'keyword.cluster_decision'"))
            ).scalar_one()
        assert n == 2


async def test_TC_E3_FR024_02_persona_strategy_and_claims(clean_db: AsyncEngine, migrated_db: str) -> None:
    """TC_E3_FR022_02 persona có bằng chứng hoặc UNKNOWN; TC_E3_FR024_02 strategy; TC_E3_BR11_02 câu 'we tested' bị loại; TC_E3_FR023_02 kênh."""
    async with keywords_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche_with_products(client)
        run = await run_keywords(client, niche)
        assert run["metrics"]["rejected_claims"] >= 1
        top = await _top(client, niche)
        d = (await client.get(f"/api/v1/keyword-clusters/{top['cluster_id']}")).json()
        assert d["persona"]["goals"]["status"] == "INFERRED" and d["persona"]["goals"]["evidence_ids"]
        assert d["persona"]["barriers"]["status"] == "UNKNOWN"
        assert d["strategy"]["status"] == "INFERRED" and d["strategy"]["content_type"] == "GUIDE"
        assert "tested" not in d["strategy"]["angle"].lower()
        main = [
            c
            for c in (
                await client.get(f"/api/v1/niches/{niche}/keyword-clusters", params={"include_mock": True})
            ).json()["items"]
        ]
        found_channels = False
        for c in main:
            det = (await client.get(f"/api/v1/keyword-clusters/{c['cluster_id']}")).json()
            if det["channels"]["status"] == "OBSERVED" and det["channels"]["items"]:
                found_channels = True
                assert {i["kind"] for i in det["channels"]["items"]} <= {"forum", "qa", "video"}
                assert all(i["evidence_urls"] for i in det["channels"]["items"])
        assert found_channels


async def test_TC_E3_FR026_01_report_json_markdown_vi_en(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with keywords_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche_with_products(client)
        await run_keywords(client, niche)
        default = (await client.get(f"/api/v1/niches/{niche}/keyword-report")).json()
        assert default["ranked"] == [] and default["needs_research"] == []  # SC-007: 0 MOCK mặc định
        data = (await client.get(f"/api/v1/niches/{niche}/keyword-report", params={"include_mock": True})).json()
        assert data["ranked"] and data["disclaimer_key"] == "keywords.opportunity.disclaimer"
        vi = (
            await client.get(
                f"/api/v1/niches/{niche}/keyword-report", params={"include_mock": True, "format": "markdown"}
            )
        ).text
        en = (
            await client.get(
                f"/api/v1/niches/{niche}/keyword-report",
                params={"include_mock": True, "format": "markdown", "lang": "en"},
            )
        ).text
        assert "# Báo cáo keyword & audience" in vi and "không phải dự báo traffic" in vi and "[MOCK]" in vi
        assert "# Keyword & audience report" in en and "not a traffic or revenue forecast" in en
        assert "| UNKNOWN | UNKNOWN | UNKNOWN |" in en  # Search Volume / CPC / KD
