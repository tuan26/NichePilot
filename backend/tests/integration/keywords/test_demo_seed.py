"""T037 – lệnh nạp keyword DEMO (R-10; FR-027; SC-007): MOCK, idempotent, ẩn mặc định, từ chối production, không ghi chỉ số keyword.
Không phải dữ liệu nghiên cứu; không liên quan SC-008."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from nichepilot.jobs import discovery_demo_seed, keywords_demo_seed, products_demo_seed
from tests.keywords_helpers import keywords_client

pytestmark = [pytest.mark.integration, pytest.mark.keywords, pytest.mark.mock]


async def test_TC_E3_FR027_02_demo_keywords_mock_idempotent_hidden(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with keywords_client(migrated_db) as client:
        sm = client.services.discovery.sessionmaker  # type: ignore[attr-defined]
        assert (await keywords_demo_seed.seed_demo(sm))["status"] == "MISSING_DISCOVERY_DEMO"
        niche = (await discovery_demo_seed.seed_demo(sm))["niche_id"]
        await products_demo_seed.seed_demo(sm)
        first = await keywords_demo_seed.seed_demo(sm)
        again = await keywords_demo_seed.seed_demo(sm)
        assert first["status"] == "CREATED" and again["status"] == "EXISTS"
        async with clean_db.connect() as conn:
            origins = {
                t: (await conn.execute(text(f"SELECT DISTINCT data_origin FROM {t}"))).scalars().all()  # noqa: S608
                for t in ("keywords", "keyword_clusters", "serp_observations", "keyword_evaluations")
            }
            metrics = (
                await conn.execute(
                    text("SELECT count(*) FROM keywords WHERE search_volume IS NOT NULL OR cpc IS NOT NULL")
                )
            ).scalar_one()
        assert all(v == ["MOCK"] for v in origins.values()), origins
        assert metrics == 0
        assert (await client.get(f"/api/v1/niches/{niche}/keyword-clusters")).json()["items"] == []
        shown = (await client.get(f"/api/v1/niches/{niche}/keyword-clusters", params={"include_mock": True})).json()[
            "items"
        ]
        assert shown and shown[0]["opportunity_score"] is not None


async def test_TC_E3_SC007_02_production_refuses_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    class Prod:
        is_production = True

    monkeypatch.setattr(keywords_demo_seed, "get_settings", lambda: Prod())
    with pytest.raises(keywords_demo_seed.DemoSeedRefusedError):
        await keywords_demo_seed.seed()
