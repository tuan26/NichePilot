"""T038 – hiệu năng E3 (SC-005; plan Performance Goals). MOCK, không mạng, không AI có phí. Chạy khi NICHEPILOT_RUN_PERF=1."""

from __future__ import annotations

import json
import statistics
import time

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from nichepilot.modules.keywords.normalize import dedup_key
from tests.discovery_helpers import allow_test_source
from tests.keywords_helpers import keywords_client, run_keywords, seed_niche_with_products

pytestmark = [pytest.mark.perf, pytest.mark.integration, pytest.mark.keywords, pytest.mark.mock]


async def test_TC_E3_SC005_01_mock_run_under_10_minutes(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with keywords_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche_with_products(client)
        t0 = time.monotonic()
        run = await run_keywords(client, niche, max_keywords=60, serp_keywords=10)
        assert run["status"] == "SUCCEEDED" and time.monotonic() - t0 < 600


async def test_TC_E3_SC005_02_list_200_keywords_p95_under_500ms(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with keywords_client(migrated_db) as client:
        niche = await seed_niche_with_products(client)
        async with clean_db.begin() as conn:
            project = (
                await conn.execute(text("SELECT project_id FROM niches WHERE id = :n"), {"n": niche})
            ).scalar_one()
            pps = (
                (await conn.execute(text("SELECT id FROM pain_points WHERE niche_id = :n"), {"n": niche}))
                .scalars()
                .all()
            )
            for i in range(200):
                kw = f"perf keyword number {i} for bakery stock"
                kid = (
                    await conn.execute(
                        text(
                            "INSERT INTO keywords (project_id, niche_id, text, normalized, dedup_key, keyword_type, length_class,"
                            " intent, data_origin) VALUES (:p, :n, :t, :t, :k, 'PROBLEM', 'LONG_TAIL', :i, 'MOCK') RETURNING id"
                        ),
                        {
                            "p": project,
                            "n": niche,
                            "t": kw,
                            "k": dedup_key(kw),
                            "i": ("INFORMATIONAL", "TRANSACTIONAL")[i % 2],
                        },
                    )
                ).scalar_one()
                await conn.execute(
                    text(
                        "INSERT INTO keyword_origins (keyword_id, origin_type, pain_point_id) VALUES (:k, 'PAIN_POINT', :pp)"
                    ),
                    {"k": kid, "pp": pps[0]},
                )
        from nichepilot.modules.keywords import evaluation, store

        sm = client.services.discovery.sessionmaker  # type: ignore[attr-defined]
        async with sm() as s, s.begin():
            clusters = await store.assign_clusters(s, niche, "MOCK")
            ids = (await s.execute(text("SELECT id FROM keywords"))).scalars().all()
            await evaluation.evaluate_keywords(s, list(ids))
            await evaluation.refresh_clusters(s, clusters)
        url = f"/api/v1/niches/{niche}/keyword-clusters"
        r0 = await client.get(url, params={"include_mock": True, "list": "needs_research"})
        assert r0.status_code == 200
        times = []
        for _ in range(20):
            t0 = time.perf_counter()
            r = await client.get(url, params={"include_mock": True, "list": "needs_research"})
            times.append(time.perf_counter() - t0)
            assert r.status_code == 200
        p95 = statistics.quantiles(times, n=20)[-1]
        assert p95 < 0.5, json.dumps({"p95_s": p95})
