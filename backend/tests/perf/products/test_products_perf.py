"""T062 – hiệu năng E2 (SC-005; plan Performance Goals). MOCK, không mạng, không AI có phí."""

from __future__ import annotations

import json
import statistics
import time
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.discovery_helpers import allow_test_source
from tests.products_helpers import products_client, run_products, seed_niche

pytestmark = [pytest.mark.perf, pytest.mark.integration, pytest.mark.products, pytest.mark.mock]


async def test_TC_E2_SC005_01_mock_run_under_5_minutes(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        t0 = time.monotonic()
        run = await run_products(client, niche, max_products=10)
        assert run["status"] == "SUCCEEDED" and time.monotonic() - t0 < 300


async def test_TC_E2_SC005_02_list_500_products_p95_under_500ms(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        niche = await seed_niche(client)
        async with clean_db.begin() as conn:
            project = (
                await conn.execute(text("SELECT project_id FROM niches WHERE id = :n"), {"n": niche})
            ).scalar_one()
            wid = (await conn.execute(text("SELECT id FROM product_scoring_weights WHERE is_active"))).scalar_one()
            for i in range(500):
                pid, pair = uuid.uuid4(), uuid.uuid4()
                await conn.execute(
                    text(
                        "INSERT INTO products (id, project_id, name, normalized_name, dedup_key, data_origin)"
                        " VALUES (:i, :p, :n, :n, :k, 'MOCK')"
                    ),
                    {"i": pid, "p": project, "n": f"[MOCK] perf {i}", "k": f"name:|perf {i}"},
                )
                await conn.execute(
                    text(
                        "INSERT INTO product_niches (id, product_id, niche_id, data_origin) VALUES (:i, :p, :n, 'MOCK')"
                    ),
                    {"i": pair, "p": pid, "n": niche},
                )
            # đánh giá ban đầu được tính qua đường chuẩn (lần đọc đầu), sau đó đo các lần đọc ổn định
        r0 = await client.get(
            f"/api/v1/niches/{niche}/products", params={"include_mock": True, "list": "needs_research"}
        )
        assert r0.status_code == 200 and len(r0.json()["items"]) == 500
        times = []
        for _ in range(20):
            t0 = time.perf_counter()
            r = await client.get(
                f"/api/v1/niches/{niche}/products", params={"include_mock": True, "list": "needs_research"}
            )
            times.append(time.perf_counter() - t0)
            assert r.status_code == 200
        p95 = statistics.quantiles(times, n=20)[-1]
        assert p95 < 0.5, json.dumps({"p95_s": p95})
        assert wid
