"""T007 – hiệu năng dashboard E4 (SC-003): 500 ngách + 500 job, p95 < 500 ms. MOCK; chạy khi NICHEPILOT_RUN_PERF=1."""

from __future__ import annotations

import json
import statistics
import time
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.keywords_helpers import keywords_client

pytestmark = [pytest.mark.perf, pytest.mark.integration, pytest.mark.dashboard, pytest.mark.mock]


async def test_TC_E4_SC003_01_overview_and_niches_p95_under_500ms(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with keywords_client(migrated_db) as client:
        async with clean_db.begin() as conn:
            pid = (await conn.execute(text("SELECT id FROM projects WHERE is_default"))).scalar_one()
            for i in range(500):
                await conn.execute(
                    text(
                        "INSERT INTO niches (project_id, name, micro_niche, country, customer_group, core_problem, dedup_key,"
                        " data_origin, evidence_status) VALUES (:p, :n, :n, 'US', 'g', 'p', :k, 'MOCK', 'EVIDENCE_SUFFICIENT')"
                    ),
                    {"p": pid, "n": f"[MOCK] perf niche {i}", "k": f"perf-{i}"},
                )
                jid = uuid.uuid4()
                await conn.execute(
                    text(
                        "INSERT INTO agent_jobs (id, project_id, job_type, params, idempotency_key, status, trigger,"
                        " data_origin, budget_limit_usd, max_steps, max_ai_calls, timeout_s, max_attempts)"
                        " VALUES (:id, :p, 'system.diagnostic', '{}', :k, :s, 'MANUAL', 'MOCK', 2, 20, 30, 1800, 3)"
                    ),
                    {"id": jid, "p": pid, "k": f"perf:{jid}", "s": ("SUCCEEDED", "FAILED", "CANCELLED")[i % 3]},
                )
        for url in ("/api/v1/dashboard/overview", "/api/v1/dashboard/niches", "/api/v1/jobs"):
            params = {"include_mock": "true", "limit": "500"} if "niches" in url else {"include_mock": "true"}
            r0 = await client.get(url, params=params)
            assert r0.status_code == 200, r0.text
            times = []
            for _ in range(20):
                t0 = time.perf_counter()
                r = await client.get(url, params=params)
                times.append(time.perf_counter() - t0)
                assert r.status_code == 200
            p95 = statistics.quantiles(times, n=20)[-1]
            assert p95 < 0.5, json.dumps({"url": url, "p95_s": p95})
        assert (
            len(
                (await client.get("/api/v1/dashboard/niches", params={"include_mock": True, "limit": 500})).json()[
                    "items"
                ]
            )
            == 500
        )
