"""T072 – Trích xuất pain point, persona, giải pháp/khoảng trống, đối thủ, monetization, kênh (FR-007…FR-011, FR-013, FR-014,
SC-004, SC-008/QA-05). AI kịch bản (MOCK) – không chứng minh chất lượng phân tích của model thật."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.discovery_helpers import allow_test_source, discovery_client
from tests.discovery_run import FORUM, REVIEW, run_discovery, set_search
from tests.fakes.discovery_ai import ScriptedDiscoveryAI, default_extract, excerpts_in

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]


async def _rows(engine: AsyncEngine, sql: str) -> list[Any]:
    async with engine.connect() as conn:
        return list((await conn.execute(text(sql))).mappings().all())


async def test_TC_E1_FR007_01_pain_points_grouped_with_severity_and_evidence(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        await run_discovery(client)
    pps = await _rows(clean_db, "SELECT * FROM pain_points")
    assert len(pps) == 1
    pp = pps[0]
    assert pp["severity"] == 4 and pp["severity_reason"] and pp["verification_status"] == "VERIFIED"
    links = await _rows(clean_db, f"SELECT * FROM niche_evidence_links WHERE pain_point_id = '{pp['id']}'")  # noqa: S608
    assert pp["evidence_count"] == len(links) >= 2
    assert all(lk["purpose"] == "PAIN_POINT" and lk["relevance"] is not None for lk in links)


async def test_TC_E1_FR008_01_persona_five_attributes_each_with_status(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        await run_discovery(client)
    persona = (await _rows(clean_db, "SELECT attributes FROM buyer_personas"))[0]["attributes"]
    assert set(persona) == {"segment", "context", "goals", "obstacles", "ability_to_pay"}
    assert persona["segment"]["status"] == "VERIFIED" and persona["segment"]["evidence_ids"]
    assert persona["context"]["status"] == "INFERRED"
    # không dẫn bằng chứng → UNKNOWN, không giá trị (FR-013, FR-014)
    assert persona["obstacles"] == {"value": None, "status": "UNKNOWN", "evidence_ids": []}
    assert persona["ability_to_pay"] == {"value": None, "status": "UNKNOWN", "evidence_ids": []}


async def test_TC_E1_FR009_01_solutions_gaps_and_competitors(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        await run_discovery(client)
    findings = {r["field"]: r for r in await _rows(clean_db, "SELECT * FROM niche_findings")}
    assert set(findings) == {
        "CURRENT_SOLUTIONS",
        "MARKET_GAPS",
        "POTENTIAL_PRODUCTS",
        "MONETIZATION",
        "CHANNELS",
        "RISKS",
    }
    assert findings["CURRENT_SOLUTIONS"]["verification_status"] == "VERIFIED"
    assert findings["MARKET_GAPS"]["verification_status"] == "INFERRED" and findings["MARKET_GAPS"]["evidence_ids"]
    comps = await _rows(clean_db, "SELECT * FROM competitors")
    assert [(c["kind"], c["weaknesses"]) for c in comps] == [("MANUAL_WORKAROUND", ["[MOCK] slow"])]


async def test_TC_E1_FR010_01_TC_E1_FR011_01_no_signal_means_unknown_and_no_invented_metrics(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        await run_discovery(client)
    findings = {r["field"]: r for r in await _rows(clean_db, "SELECT * FROM niche_findings")}
    for f in ("MONETIZATION", "CHANNELS", "POTENTIAL_PRODUCTS", "RISKS"):
        assert findings[f]["verification_status"] == "UNKNOWN" and findings[f]["value"] is None, f
    niche = (await _rows(clean_db, "SELECT monetization_status, risk_flags FROM niches WHERE name LIKE '%bakery%'"))[0]
    assert niche["monetization_status"] == "MONETIZATION_UNVERIFIED" and "MONETIZATION_RISK" in niche["risk_flags"]


async def test_TC_E1_SC004_01_invented_metric_fields_reject_the_output(clean_db: AsyncEngine, migrated_db: str) -> None:
    def with_volume(req: Any) -> dict[str, Any]:
        out = default_extract(req)
        out["search_volume"] = 12000  # hệ thống không được tạo search volume / CPC
        return out

    ai = ScriptedDiscoveryAI({"discovery.extract": with_volume})
    async with discovery_client(migrated_db, ai=ai) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        run = await run_discovery(client)
    assert run["metrics"]["ai_outputs_rejected"] >= 1
    assert await _rows(clean_db, "SELECT id FROM pain_points") == []
    prompt = ai.requests_for("discovery.extract")[0].system
    assert "search volume" in prompt and "Do not invent" in prompt
    # mọi kết luận hiển thị: có bằng chứng hoặc UNKNOWN (không có kết luận nào được lưu ở đây)
    assert await _rows(clean_db, "SELECT id FROM niche_findings WHERE verification_status <> 'UNKNOWN'") == []


async def test_TC_E1_FR013_01_unknown_evidence_id_rejects_whole_output(clean_db: AsyncEngine, migrated_db: str) -> None:
    def fabricated(req: Any) -> dict[str, Any]:
        out = default_extract(req)
        if out.get("competitors"):
            out["competitors"][0]["evidence_ids"] = [str(uuid.uuid4())]  # ID không được cung cấp
        return out

    ai = ScriptedDiscoveryAI({"discovery.extract": fabricated})
    async with discovery_client(migrated_db, ai=ai) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        run = await run_discovery(client)
    assert run["metrics"]["ai_outputs_rejected"] == 1
    for table in ("pain_points", "buyer_personas", "niche_findings", "competitors", "niche_evidence_links"):
        assert await _rows(clean_db, f"SELECT id FROM {table}") == [], table  # noqa: S608
    niche = (await _rows(clean_db, "SELECT evidence_status FROM niches WHERE name LIKE '%bakery%'"))[0]
    assert niche["evidence_status"] == "INSUFFICIENT_EVIDENCE"  # không "mượn" bằng chứng


async def test_TC_E1_FR014_01_TC_E1_SC008_01_conflicting_sources_keep_all_values(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    def conflicting(req: Any) -> dict[str, Any]:
        out = default_extract(req)
        ids = [e["evidence_id"] for e in excerpts_in(req)]
        if len(ids) >= 2:
            out["persona"]["ability_to_pay"] = {
                "status": "CONFLICTING",
                "conflicting_values": [
                    {"value": "[MOCK] would pay a small monthly fee", "evidence_ids": [ids[0]]},
                    {"value": "[MOCK] apps are too expensive", "evidence_ids": [ids[-1]]},
                ],
            }
            out["findings"]["CHANNELS"] = {
                "status": "CONFLICTING",
                "conflicting_values": [{"value": "[MOCK] forum", "evidence_ids": [ids[0]]}],
            }  # < 2 giá trị → UNKNOWN, không tự chọn
            out["findings"]["RISKS"] = {"value": "[MOCK] none", "status": "VERIFIED", "evidence_ids": []}
        return out

    ai = ScriptedDiscoveryAI({"discovery.extract": conflicting})
    async with discovery_client(migrated_db, ai=ai) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        run = await run_discovery(client)
    assert run["outcome"] == "COMPLETED"
    pay = (await _rows(clean_db, "SELECT attributes FROM buyer_personas"))[0]["attributes"]["ability_to_pay"]
    assert pay["status"] == "CONFLICTING" and len(pay["value"]) == 2
    assert all(v["evidence_ids"] for v in pay["value"]) and len(pay["evidence_ids"]) == 2
    findings = {r["field"]: r for r in await _rows(clean_db, "SELECT * FROM niche_findings")}
    assert findings["CHANNELS"]["verification_status"] == "UNKNOWN" and findings["CHANNELS"]["value"] is None
    assert findings["RISKS"]["verification_status"] == "UNKNOWN"  # VERIFIED không bằng chứng → UNKNOWN
