"""T077 – `GET /api/v1/niches/{niche_id}` (FR-023, SC-003; contracts/openapi.yaml NicheDetail): 16 trường BR-07 (giá trị hoặc
UNKNOWN), bằng chứng có `redaction_status`, `policy_verified_at`, nhóm độc lập; không trả bằng chứng đã xóa. MOCK."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.discovery_helpers import allow_test_source, discovery_client
from tests.discovery_run import FORUM, REVIEW, run_discovery, set_search

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]

SUMMARY_REQUIRED = {"id", "name", "country", "evidence_status", "decision_status", "monetization_status", "data_origin"}
DETAIL_REQUIRED = {
    "customer_group",
    "core_problem",
    "pain_points",
    "persona",
    "findings",
    "competitors",
    "evidence",
    "latest_evaluation",
}
EVIDENCE_REQUIRED = {
    "id",
    "source_url",
    "excerpt",
    "collected_at",
    "verification_status",
    "redaction_status",
    "data_origin",
}
FINDING_FIELDS = {"CURRENT_SOLUTIONS", "MARKET_GAPS", "POTENTIAL_PRODUCTS", "MONETIZATION", "CHANNELS", "RISKS"}


def br07(detail: dict[str, object]) -> dict[str, object]:
    """16 trường BR-07 → giá trị trong DTO (UNKNOWN nếu thiếu)."""
    f = detail["findings"]
    assert isinstance(f, dict)
    return {
        "name": detail["name"],
        "micro_niche": detail["micro_niche"],
        "country": detail["country"],
        "customer_group": detail["customer_group"],
        "pain_points": detail["pain_points"] or "UNKNOWN",
        "current_solutions": f["CURRENT_SOLUTIONS"],
        "market_gaps": f["MARKET_GAPS"],
        "competitors": detail["competitors"] or "UNKNOWN",
        "potential_products": f["POTENTIAL_PRODUCTS"],
        "monetization": f["MONETIZATION"],
        "channels": f["CHANNELS"],
        "opportunity_score": detail["opportunity_score"] if detail["opportunity_score"] is not None else "UNKNOWN",
        "confidence_score": detail["confidence_score"] if detail["confidence_score"] is not None else "UNKNOWN",
        "sources": detail["evidence"] or "UNKNOWN",
        "risks": f["RISKS"],
        "recommendation": detail["ai_recommendation"],
    }


async def test_TC_E1_FR023_01_TC_E1_SC003_01_detail_has_all_br07_fields(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        await run_discovery(client)
        async with clean_db.connect() as conn:
            ids = (await conn.execute(text("SELECT id, name FROM niches ORDER BY name"))).all()
        for niche_id, name in ids:
            r = await client.get(f"/api/v1/niches/{niche_id}")
            assert r.status_code == 200, r.text
            d = r.json()
            assert SUMMARY_REQUIRED <= set(d) and DETAIL_REQUIRED <= set(d), name
            fields = br07(d)
            assert len(fields) == 16 and all(v is not None for v in fields.values()), name
            assert set(d["findings"]) == FINDING_FIELDS
            for f in d["findings"].values():  # Finding: UNKNOWN không giá trị; còn lại phải dẫn bằng chứng
                assert (f["status"] == "UNKNOWN") == (f["value"] is None) and (
                    f["status"] == "UNKNOWN" or f["evidence_ids"]
                )
            assert set(d["persona"]) == {"segment", "context", "goals", "obstacles", "ability_to_pay"}
            assert d["data_origin"] == "MOCK" and d["disclaimer_key"]
            assert d["latest_evaluation"] is None  # chấm điểm ở US3
        bakery = next(i for i, n in ids if "bakery" in n)
        d = (await client.get(f"/api/v1/niches/{bakery}")).json()
        assert d["evidence_status"] == "EVIDENCE_SUFFICIENT" and d["pain_points"][0]["status"] == "VERIFIED"
        ev = d["evidence"]
        assert ev and all(EVIDENCE_REQUIRED <= set(e) for e in ev)
        assert all(e["redaction_status"] == "REDACTED" and e["policy_verified_at"] == "2026-11-01" for e in ev)
        assert {e["source_domain"] for e in ev} == {"forum.example", "reviews.example"}
        assert any(e["counted_for_threshold"] for e in ev) and all(e["independence_group"] for e in ev)
        assert all(len(e["excerpt"]) <= 1000 for e in ev)
        assert d["run_ids"] and d["customer_group"] == "owners of one- to three-person bakeries"
        missing = await client.get("/api/v1/niches/00000000-0000-0000-0000-000000000000")
        assert missing.status_code == 404 and missing.json()["code"] == "NICHE_NOT_FOUND"
