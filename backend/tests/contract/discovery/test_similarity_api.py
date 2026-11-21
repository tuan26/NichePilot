"""T112 – Ngách trùng/tương đồng (FR-022): trùng chắc chắn → liên kết vào ngách cũ (không tạo mới); không chắc chắn → POSSIBLE chờ
chủ sở hữu; `PUT /niche-similarities/{id}` gộp giữ `keep_niche_id`, audit `niche.similarity_resolved`. MOCK (AI kịch bản)."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import csrf_headers
from tests.discovery_helpers import allow_test_source, discovery_client
from tests.discovery_run import run_discovery
from tests.fakes.discovery_ai import ScriptedDiscoveryAI

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]


def cand(name: str, group: str, problem: str) -> dict[str, Any]:
    return {
        "name": name,
        "micro_niche": name,
        "domain": "services",
        "customer_group": group,
        "core_problem": problem,
        "queries": ["q"],
    }


RUN1 = {"candidates": [cand("[MOCK] Photographer invoices", "freelance photographers", "clients pay invoices late")]}
RUN2 = {
    "candidates": [
        cand(
            "[MOCK] Photo invoicing", "freelance photographers", "late invoice payments from clients"
        ),  # trùng chắc chắn
        cand("[MOCK] Designer invoices", "freelance designers", "clients pay invoices late"),  # có thể tương đồng
    ]
}


async def test_TC_E1_FR022_02_duplicate_linked_possible_flagged_and_owner_resolves(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    ai = ScriptedDiscoveryAI({"discovery.candidates": RUN1})
    async with discovery_client(migrated_db, ai=ai) as client:
        await allow_test_source(clean_db)
        await run_discovery(client)
        ai.scripts["discovery.candidates"] = RUN2
        run2 = await run_discovery(client)
        assert run2["metrics"]["duplicates_linked"] == 1
        async with clean_db.connect() as conn:
            niches = {r.name: r.id for r in (await conn.execute(text("SELECT name, id FROM niches"))).all()}
            links = (
                await conn.execute(
                    text("SELECT count(*) FROM niche_run_links WHERE niche_id = :n"),
                    {"n": niches["[MOCK] Photographer invoices"]},
                )
            ).scalar_one()
        assert set(niches) == {"[MOCK] Photographer invoices", "[MOCK] Designer invoices"}  # không tạo ngách trùng
        assert links == 2  # ngách cũ được liên kết với lượt mới
        sims = (await client.get("/api/v1/niche-similarities")).json()
        assert len(sims) == 1 and sims[0]["status"] == "POSSIBLE" and sims[0]["score"] >= 0.85
        keep, other = str(niches["[MOCK] Photographer invoices"]), str(niches["[MOCK] Designer invoices"])
        detail = (await client.get(f"/api/v1/niches/{other}")).json()
        assert detail["has_possible_duplicate"] and detail["possible_duplicates"][0]["id"] == sims[0]["id"]
        bad = await client.put(
            f"/api/v1/niche-similarities/{sims[0]['id']}",
            json={"status": "CONFIRMED_DUPLICATE"},
            headers=csrf_headers(client),
        )
        assert bad.status_code == 422  # thiếu keep_niche_id
        r = await client.put(
            f"/api/v1/niche-similarities/{sims[0]['id']}",
            json={"status": "CONFIRMED_DUPLICATE", "keep_niche_id": keep},
            headers=csrf_headers(client),
        )
        assert r.status_code == 200 and r.json()["status"] == "CONFIRMED_DUPLICATE"
        again = await client.put(
            f"/api/v1/niche-similarities/{sims[0]['id']}",
            json={"status": "NOT_DUPLICATE"},
            headers=csrf_headers(client),
        )
        assert again.status_code == 409
        async with clean_db.connect() as conn:
            merged = (
                await conn.execute(text("SELECT merged_into_id FROM niches WHERE id = :n"), {"n": other})
            ).scalar_one()
            audit = (
                await conn.execute(text("SELECT after FROM audit_logs WHERE action = 'niche.similarity_resolved'"))
            ).scalar_one()
            resolved_by = (await conn.execute(text("SELECT resolved_by FROM niche_similarity"))).scalar_one()
        assert str(merged) == keep and audit["merged_niche_id"] == other and resolved_by is not None
        listed = (await client.get("/api/v1/niches?list=needs_research&include_mock=true")).json()["items"]
        assert other not in [x["id"] for x in listed]  # ngách đã gộp không xuất hiện trong danh sách
        assert (await client.get("/api/v1/niche-similarities")).json() == []


async def test_TC_E1_FR022_04_not_duplicate_keeps_both(clean_db: AsyncEngine, migrated_db: str) -> None:
    ai = ScriptedDiscoveryAI({"discovery.candidates": RUN1})
    async with discovery_client(migrated_db, ai=ai) as client:
        await allow_test_source(clean_db)
        await run_discovery(client)
        ai.scripts["discovery.candidates"] = {"candidates": [RUN2["candidates"][1]]}
        await run_discovery(client)
        sim = (await client.get("/api/v1/niche-similarities")).json()[0]
        r = await client.put(
            f"/api/v1/niche-similarities/{sim['id']}", json={"status": "NOT_DUPLICATE"}, headers=csrf_headers(client)
        )
        assert r.status_code == 200
        async with clean_db.connect() as conn:
            assert (
                await conn.execute(text("SELECT count(*) FROM niches WHERE merged_into_id IS NULL"))
            ).scalar_one() == 2
