"""T071 – Đạt ngưỡng bằng chứng ≠ sinh lợi (FR-013d, FR-010): ngách EVIDENCE_SUFFICIENT nhưng không có tín hiệu affiliate có bằng
chứng → MONETIZATION_UNVERIFIED + cờ MONETIZATION_RISK; evidence_status không phụ thuộc monetization. Phần bảng cơ hội / danh sách
affiliate (xếp hạng) được kiểm thử ở US3 (T085+) – chưa có ở US2."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.discovery_helpers import allow_test_source, discovery_client
from tests.discovery_run import FORUM, REVIEW, run_discovery, set_search
from tests.fakes.discovery_ai import ScriptedDiscoveryAI, default_extract

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]


def _with_monetization(req: object) -> dict[str, object]:
    out = default_extract(req)  # type: ignore[arg-type]
    if out.get("findings"):
        ids = out["pain_points"][0]["evidence_ids"]  # type: ignore[index]
        out["findings"]["MONETIZATION"] = {  # type: ignore[index]
            "value": "[MOCK] inventory apps advertise a public affiliate programme",
            "status": "VERIFIED",
            "evidence_ids": ids[:1],
        }
    return out


async def test_TC_E1_FR013d_01_evidence_sufficient_is_not_profitability(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        await run_discovery(client)
        async with clean_db.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT id, evidence_status, monetization_status, risk_flags FROM niches WHERE name LIKE '%bakery%'"
                    )
                )
            ).one()
        assert row.evidence_status == "EVIDENCE_SUFFICIENT"
        assert row.monetization_status == "MONETIZATION_UNVERIFIED" and "MONETIZATION_RISK" in row.risk_flags
        detail = (await client.get(f"/api/v1/niches/{row.id}")).json()
        assert detail["evidence_status"] == "EVIDENCE_SUFFICIENT"
        assert detail["monetization_status"] == "MONETIZATION_UNVERIFIED"
        assert detail["disclaimer_key"] == "discovery.disclaimer.evidence_not_profitability"


async def test_TC_E1_FR013d_02_monetization_signal_does_not_change_evidence_status(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    ai = ScriptedDiscoveryAI({"discovery.extract": _with_monetization})
    async with discovery_client(migrated_db, ai=ai) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM])  # một nguồn → không đạt ngưỡng dù có tín hiệu monetization
        await run_discovery(client)
        async with clean_db.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT evidence_status, monetization_status, risk_flags FROM niches WHERE name LIKE '%bakery%'"
                    )
                )
            ).one()
        assert row.monetization_status == "SIGNALS_FOUND" and "MONETIZATION_RISK" not in row.risk_flags
        assert row.evidence_status == "INSUFFICIENT_EVIDENCE"
