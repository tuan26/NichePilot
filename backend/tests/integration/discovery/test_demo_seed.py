"""Lệnh nạp ngách DEMO cho E2E (chủ sở hữu duyệt 2026-11-25): dữ liệu `MOCK`, đi qua pipeline chấm điểm thật, idempotent, ẩn khỏi
danh sách/báo cáo mặc định; từ chối ở production. Không phải dữ liệu nghiên cứu; không liên quan SC-013."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from nichepilot.jobs import discovery_demo_seed
from tests.discovery_helpers import discovery_client

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]


async def test_TC_E1_FR026_05_demo_seed_is_mock_scored_idempotent_and_hidden(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with discovery_client(migrated_db) as client:
        sm = client.services.discovery.sessionmaker  # type: ignore[attr-defined]
        first = await discovery_demo_seed.seed_demo(sm)
        again = await discovery_demo_seed.seed_demo(sm)
        assert first["status"] == "CREATED" and first["evidence_status"] == "EVIDENCE_SUFFICIENT"
        assert again == {"status": "EXISTS", "niche_id": first["niche_id"]}
        async with clean_db.connect() as conn:
            origins = {
                t: (await conn.execute(text(f"SELECT DISTINCT data_origin FROM {t}"))).scalars().all()  # noqa: S608
                for t in ("niches", "research_sources", "research_evidence", "niche_evaluations", "pain_points")
            }
        assert all(v == ["MOCK"] for v in origins.values()), origins
        assert (await client.get("/api/v1/niches?list=research")).json()["items"] == []  # MOCK ẩn mặc định
        shown = (await client.get("/api/v1/niches?list=research&include_mock=true")).json()["items"]
        assert [n["name"] for n in shown] == [discovery_demo_seed.DEMO_NAME] and shown[0]["opportunity_score"] == 60.71
        detail = (await client.get(f"/api/v1/niches/{first['niche_id']}")).json()
        assert detail["data_origin"] == "MOCK" and len(detail["evidence"]) == 2


async def test_TC_E1_FR026_06_demo_seed_refused_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    class Prod:
        is_production = True

    monkeypatch.setattr(discovery_demo_seed, "get_settings", lambda: Prod())
    with pytest.raises(discovery_demo_seed.DemoSeedRefusedError):
        await discovery_demo_seed.seed()


async def test_TC_E1_FR026_07_demo_seed_failure_leaves_no_partial_niche(
    clean_db: AsyncEngine, migrated_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def boom(*_a: object, **_k: object) -> None:
        raise RuntimeError("scoring failed")

    async with discovery_client(migrated_db) as client:
        sm = client.services.discovery.sessionmaker  # type: ignore[attr-defined]
        monkeypatch.setattr(discovery_demo_seed.evaluation, "evaluate_and_store", boom)
        with pytest.raises(RuntimeError):
            await discovery_demo_seed.seed_demo(sm)
        async with clean_db.connect() as conn:
            assert (await conn.execute(text("SELECT count(*) FROM niches"))).scalar_one() == 0
            assert (await conn.execute(text("SELECT count(*) FROM research_evidence"))).scalar_one() == 0
        monkeypatch.undo()
        assert (await discovery_demo_seed.seed_demo(sm))["status"] == "CREATED"  # chạy lại được sau lỗi
