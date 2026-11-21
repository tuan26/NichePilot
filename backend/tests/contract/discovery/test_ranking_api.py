"""T089 – `GET /api/v1/niches?list=research|affiliate|needs_research` (scoring-rubric §4; FR-019b, FR-019c, FR-016, SC-009). MOCK.

Lượt giả lập luôn tạo dữ liệu MOCK → mặc định bị ẩn; `include_mock=true` mới hiện (kèm `data_origin`). Ngách REAL được tạo trực tiếp
trong DB test (đánh giá tính bằng mã) để kiểm tra phân loại danh sách – KHÔNG phải dữ liệu nghiên cứu thật."""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.discovery_helpers import allow_test_source, discovery_client
from tests.discovery_run import FORUM, REVIEW, run_discovery, set_search

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]


async def _real_niche(
    engine: AsyncEngine,
    name: str,
    *,
    evidence: str,
    scoring: str,
    opp: float | None,
    conf: float,
    monet: str,
    flags: list[str],
    decision: str = "CANDIDATE",
) -> str:
    """Ngách REAL dựng sẵn trong DB test (không qua AI) – chỉ để kiểm tra điều kiện danh sách."""
    async with engine.begin() as conn:
        project = (await conn.execute(text("SELECT id FROM projects LIMIT 1"))).scalar_one()
        wv = (await conn.execute(text("SELECT id FROM scoring_weights_versions WHERE is_active"))).scalar_one()
        user = (await conn.execute(text("SELECT id FROM users LIMIT 1"))).scalar_one()
        nid = (
            await conn.execute(
                text(
                    "INSERT INTO niches (project_id, name, micro_niche, country, customer_group, core_problem, dedup_key,"
                    " evidence_status, monetization_status, risk_flags, decision_status, decided_by, data_origin)"
                    " VALUES (:p, :n, :n, 'US', 'cg', 'cp', :k, :e, :m, CAST(:f AS text[]), :d, :u, 'REAL') RETURNING id"
                ),
                {
                    "p": project,
                    "n": name,
                    "k": f"k-{uuid.uuid4()}",
                    "e": evidence,
                    "m": monet,
                    "f": flags,
                    "d": decision,
                    "u": None if decision == "CANDIDATE" else user,
                },
            )
        ).scalar_one()
        crit = {
            k: {"score": None, "status": "UNKNOWN", "reason": "", "evidence_ids": []}
            for k in (
                "problem_severity",
                "monetization",
                "market_gap",
                "reachability",
                "competition_opportunity",
                "demand_stability",
            )
        }
        eid = (
            await conn.execute(
                text(
                    "INSERT INTO niche_evaluations (niche_id, weights_version_id, criteria, coverage, scoring_status,"
                    " opportunity_score, confidence_score, confidence_components, evidence_status, independent_groups,"
                    " computed_without_ai, data_origin) VALUES (:n, :w, CAST(:c AS jsonb), 70, :s, :o, :conf, '{}', :e, 2,"
                    " true, 'REAL') RETURNING id"
                ),
                {"n": nid, "w": wv, "c": json.dumps(crit), "s": scoring, "o": opp, "conf": conf, "e": evidence},
            )
        ).scalar_one()
        await conn.execute(text("UPDATE niches SET latest_evaluation_id = :e WHERE id = :n"), {"e": eid, "n": nid})
    return str(nid)


async def test_TC_E1_FR019b_01_three_lists_follow_rubric(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with discovery_client(migrated_db) as client:
        a = await _real_niche(
            clean_db,
            "A affiliate",
            evidence="EVIDENCE_SUFFICIENT",
            scoring="SCORED",
            opp=80,
            conf=60,
            monet="SIGNALS_FOUND",
            flags=[],
        )
        b = await _real_niche(
            clean_db,
            "B unverified",
            evidence="EVIDENCE_SUFFICIENT",
            scoring="SCORED",
            opp=90,
            conf=50,
            monet="MONETIZATION_UNVERIFIED",
            flags=["MONETIZATION_RISK"],
        )
        c = await _real_niche(
            clean_db,
            "C insufficient",
            evidence="INSUFFICIENT_EVIDENCE",
            scoring="SCORED",
            opp=95,
            conf=30,
            monet="SIGNALS_FOUND",
            flags=[],
        )
        d = await _real_niche(
            clean_db,
            "D low coverage",
            evidence="EVIDENCE_SUFFICIENT",
            scoring="INSUFFICIENT_SCORING_DATA",
            opp=None,
            conf=40,
            monet="MONETIZATION_UNVERIFIED",
            flags=["MONETIZATION_RISK"],
        )
        e = await _real_niche(
            clean_db,
            "E rejected",
            evidence="EVIDENCE_SUFFICIENT",
            scoring="SCORED",
            opp=99,
            conf=99,
            monet="SIGNALS_FOUND",
            flags=[],
            decision="REJECTED",
        )

        async def ids(q: str) -> list[str]:
            r = await client.get(f"/api/v1/niches?{q}")
            assert r.status_code == 200, r.text
            assert r.json()["disclaimer_key"] == "discovery.opportunity.disclaimer"
            return [x["id"] for x in r.json()["items"]]

        assert await ids("list=research") == [b, a]  # Opportunity giảm dần; C không đủ bằng chứng, E bị loại bỏ
        assert await ids("list=affiliate") == [a]  # B MONETIZATION_UNVERIFIED không vào danh sách affiliate
        assert await ids("list=needs_research") == [d, c]  # Confidence giảm dần, không xếp theo Opportunity
        assert await ids("list=research&sort=confidence_desc") == [a, b]
        assert await ids("list=research&min_opportunity=85") == [b]
        assert e not in await ids("list=needs_research")
        item = (await client.get("/api/v1/niches?list=research")).json()["items"][0]
        assert {
            "opportunity_score",
            "confidence_score",
            "coverage",
            "verification_summary",
            "monetization_status",
        } <= set(item)


async def test_TC_E1_FR016_02_SC009_01_mock_hidden_by_default(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        run = await run_discovery(client)
        for lst in ("research", "affiliate", "needs_research"):
            assert (await client.get(f"/api/v1/niches?list={lst}")).json()["items"] == []
        shown = (await client.get("/api/v1/niches?list=research&include_mock=true")).json()["items"]
        assert len(shown) == 1 and shown[0]["data_origin"] == "MOCK" and shown[0]["opportunity_score"] == 60.71
        needs = (await client.get(f"/api/v1/niches?list=needs_research&include_mock=true&run_id={run['id']}")).json()
        assert len(needs["items"]) == 2 and all(x["data_origin"] == "MOCK" for x in needs["items"])


async def test_TC_E1_FR019c_01_disclaimer_everywhere(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        await run_discovery(client)
        lst = (await client.get("/api/v1/niches?list=research&include_mock=true")).json()
        assert lst["disclaimer_key"] == "discovery.opportunity.disclaimer"
        detail = (await client.get(f"/api/v1/niches/{lst['items'][0]['id']}")).json()
        assert detail["opportunity_disclaimer_key"] == "discovery.opportunity.disclaimer"
        assert detail["latest_evaluation"]["opportunity_score"] == 60.71
        assert detail["latest_evaluation"]["confidence_score"] <= 100 and detail["ai_recommendation"] == "PURSUE"
