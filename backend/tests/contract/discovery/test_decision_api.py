"""T116 – `PUT /api/v1/niches/{niche_id}/decision` (FR-025, FR-036): 5 trạng thái, lý do bắt buộc, audit `niche.decision_recorded`;
quyết định không ghi đè đề xuất AI và AI không tự đổi quyết định. MOCK."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import csrf_headers
from tests.discovery_helpers import allow_test_source, discovery_client
from tests.discovery_run import FORUM, REVIEW, run_discovery, set_search

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]


async def test_TC_E1_FR025_01_owner_decision_audited_ai_recommendation_kept(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        await run_discovery(client)
        async with clean_db.connect() as conn:
            nid = (await conn.execute(text("SELECT id FROM niches WHERE name LIKE '%bakery%'"))).scalar_one()
        url = f"/api/v1/niches/{nid}/decision"
        assert (await client.put(url, json={"decision": "PURSUE"}, headers=csrf_headers(client))).status_code == 422
        assert (
            await client.put(url, json={"decision": "MAYBE", "reason": "x"}, headers=csrf_headers(client))
        ).status_code == 422
        for decision in ("WATCH", "PURSUE", "REJECTED", "HIDDEN", "CANDIDATE"):
            r = await client.put(
                url, json={"decision": decision, "reason": f"Owner reason {decision}"}, headers=csrf_headers(client)
            )
            assert r.status_code == 200 and r.json()["decision_status"] == decision
            assert r.json()["ai_recommendation"] == "PURSUE"  # đề xuất AI giữ nguyên
        await client.put(url, json={"decision": "REJECTED", "reason": "Too small"}, headers=csrf_headers(client))
        # tính lại (không AI) không được đổi quyết định của chủ sở hữu
        from nichepilot.modules.discovery.evaluation import evaluate_and_store

        sm = client.services.discovery.sessionmaker  # type: ignore[attr-defined]
        async with sm() as s, s.begin():
            await evaluate_and_store(s, nid, computed_without_ai=True)
        async with clean_db.connect() as conn:
            row = (
                await conn.execute(
                    text("SELECT decision_status, owner_decision_reason, decided_by FROM niches WHERE id = :n"),
                    {"n": nid},
                )
            ).one()
            audits = (
                await conn.execute(text("SELECT count(*) FROM audit_logs WHERE action = 'niche.decision_recorded'"))
            ).scalar_one()
        assert row.decision_status == "REJECTED" and row.owner_decision_reason == "Too small" and row.decided_by
        assert audits == 6
        listed = (await client.get("/api/v1/niches?list=research&include_mock=true")).json()["items"]
        assert str(nid) not in [x["id"] for x in listed]  # REJECTED không vào bảng cơ hội
        missing = await client.put(
            "/api/v1/niches/00000000-0000-0000-0000-000000000000/decision",
            json={"decision": "WATCH", "reason": "abc"},
            headers=csrf_headers(client),
        )
        assert missing.status_code == 404
