"""T060 – lệnh nạp sản phẩm DEMO (R-10; FR-035; SC-007): MOCK, idempotent, ẩn mặc định, từ chối production. Không phải dữ liệu
nghiên cứu/doanh thu; không liên quan SC-008."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from nichepilot.core.config import ConfigError
from nichepilot.core.discovery_config import DiscoverySettings
from nichepilot.jobs import discovery_demo_seed, products_demo_seed
from nichepilot.tools.sources.backends import build_source_backends
from tests.products_helpers import products_client

pytestmark = [pytest.mark.integration, pytest.mark.products, pytest.mark.mock]


async def test_TC_E2_FR035_03_demo_products_mock_idempotent_hidden(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        sm = client.services.discovery.sessionmaker  # type: ignore[attr-defined]
        assert (await products_demo_seed.seed_demo(sm))["status"] == "MISSING_DISCOVERY_DEMO"
        niche = (await discovery_demo_seed.seed_demo(sm))["niche_id"]
        first = await products_demo_seed.seed_demo(sm)
        again = await products_demo_seed.seed_demo(sm)
        assert first["status"] == "CREATED" and again == {"status": "EXISTS", "products": 2}
        assert sorted(p["readiness"] for p in first["products"]) == ["ELIGIBILITY_UNVERIFIED", "READY_TO_PROMOTE"]  # type: ignore[union-attr]
        async with clean_db.connect() as conn:
            origins = {
                t: (await conn.execute(text(f"SELECT DISTINCT data_origin FROM {t}"))).scalars().all()  # noqa: S608
                for t in ("products", "product_niches", "affiliate_programs", "product_evaluations")
            }
        assert all(v == ["MOCK"] for v in origins.values()), origins
        assert (await client.get(f"/api/v1/niches/{niche}/products")).json()["items"] == []
        shown = (await client.get(f"/api/v1/niches/{niche}/products", params={"include_mock": True})).json()["items"]
        assert {i["name"] for i in shown} == {"[MOCK DEMO] ShelfAlert", "[MOCK DEMO] CrumbCount"}


async def test_TC_E2_SC007_01_production_refuses_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    class Prod:
        is_production = True

    monkeypatch.setattr(products_demo_seed, "get_settings", lambda: Prod())
    with pytest.raises(products_demo_seed.DemoSeedRefusedError):
        await products_demo_seed.seed()
    with pytest.raises(ConfigError):  # đường E2 dùng chung guard nguồn giả lập của E1 khi khởi động api/worker
        build_source_backends(DiscoverySettings(app_env="production", discovery_source_mode="mock"))
