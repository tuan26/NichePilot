"""T056 – Contract test API lượt khám phá (FR-001, FR-002, FR-003; contracts/openapi.yaml)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import csrf_headers
from tests.discovery_helpers import allow_test_source, discovery_client

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]


async def test_TC_E1_FR001_01_create_run_with_defaults(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        r = await client.post("/api/v1/discovery/runs", json={"market": "US"}, headers=csrf_headers(client))
        assert r.status_code == 201, r.text
        run = r.json()
        assert run["market"] == "US" and run["seed_topic"] is None
        assert (run["max_candidates"], run["budget_usd"], run["time_limit_minutes"], run["page_limit"]) == (
            20,
            "2.000000",
            90,
            300,
        )
        assert run["job"]["job_type"] == "discovery.run" and run["trigger"] == "MANUAL"
        assert run["weights_version"] == 1 and run["data_origin"] == "MOCK" and run["source_mode"] == "MOCK"
        assert [s["source_key"] for s in run["sources"]] == ["test:mock-engine"]
        got = await client.get(f"/api/v1/discovery/runs/{run['id']}")
        assert got.status_code == 200 and got.json()["id"] == run["id"]
        listed = (await client.get("/api/v1/discovery/runs")).json()
        assert [x["id"] for x in listed["items"]] == [run["id"]]
        assert (await client.get("/api/v1/discovery/runs/00000000-0000-0000-0000-000000000000")).json()["code"] == (
            "DISCOVERY_RUN_NOT_FOUND"
        )


async def test_TC_E1_FR002_01_idempotency_and_validation(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        h = {**csrf_headers(client), "Idempotency-Key": "abc-123"}
        first = await client.post("/api/v1/discovery/runs", json={"market": "VN", "seed_topic": "giáo dục"}, headers=h)
        again = await client.post("/api/v1/discovery/runs", json={"market": "VN", "seed_topic": "giáo dục"}, headers=h)
        assert first.status_code == 201 and again.status_code == 200 and again.json()["id"] == first.json()["id"]
        for bad in (
            {"market": "usa"},
            {"market": "US", "max_candidates": 51},
            {"market": "US", "page_limit": 5},
            {"market": "US", "include_unverified_sources": True},  # không có tùy chọn dùng nguồn chưa xác minh (A1)
            {"market": "US", "per_domain_interval_s": 0.5},
        ):
            r = await client.post("/api/v1/discovery/runs", json=bad, headers=csrf_headers(client))
            assert r.status_code == 422, (bad, r.text)


async def test_TC_E1_FR003_01_run_endpoints_gated_by_erasure_ledger(clean_db: AsyncEngine, migrated_db: str) -> None:
    from sqlalchemy import text

    async with discovery_client(migrated_db) as client:
        async with clean_db.begin() as conn:
            await conn.execute(text("UPDATE erasure_ledger_state SET status = 'BLOCKED', last_error = 'TEST'"))
        client.services.discovery._health = None  # type: ignore[attr-defined]
        r = await client.get("/api/v1/discovery/runs")
        assert r.status_code == 503 and r.json()["code"] == "ERASURE_LEDGER_NOT_APPLIED"
