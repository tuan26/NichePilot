"""T057 – Từ chối sớm khi tạo lượt (FR-004, FR-006e, SC-017): không job nào được tạo, 0 lời gọi AI."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import csrf_headers
from tests.discovery_helpers import allow_test_source, discovery_client

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]


async def _counts(engine: AsyncEngine) -> tuple[int, int]:
    async with engine.connect() as conn:
        jobs = (await conn.execute(text("SELECT count(*) FROM agent_jobs"))).scalar_one()
        ai = (await conn.execute(text("SELECT count(*) FROM ai_usage_logs"))).scalar_one()
    return int(jobs), int(ai)


async def test_TC_E1_FR006e_01_no_allowed_source_rejected(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with discovery_client(migrated_db) as client:  # seed: mọi nguồn UNVERIFIED
        r = await client.post("/api/v1/discovery/runs", json={"market": "US"}, headers=csrf_headers(client))
        assert r.status_code == 409 and r.json()["code"] == "NO_COMPLIANT_SEARCH_SOURCE"
        assert await _counts(clean_db) == (0, 0)


async def test_TC_E1_SC017_02_prohibited_or_unverified_sources_never_count(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with discovery_client(migrated_db) as client:
        async with clean_db.begin() as conn:  # nguồn PROHIBITED (có căn cứ) – vẫn không bật được, không dùng được
            await conn.execute(
                text(
                    "UPDATE source_policies SET compliance_status = 'PROHIBITED', verified_at = '2026-11-01',"
                    " verification_note = 'Điều khoản cấm truy vấn tự động' WHERE source_key = 'searxng:google'"
                )
            )
        r = await client.post("/api/v1/discovery/runs", json={"market": "US"}, headers=csrf_headers(client))
        assert r.json()["code"] == "NO_COMPLIANT_SEARCH_SOURCE" and await _counts(clean_db) == (0, 0)


async def test_TC_E1_FR004_01_budget_preconditions(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        over = await client.post(
            "/api/v1/discovery/runs", json={"market": "US", "budget_usd": "3.50"}, headers=csrf_headers(client)
        )
        assert over.status_code == 409 and over.json()["code"] == "RUN_BUDGET_EXCEEDS_DAILY_LIMIT"
        async with clean_db.begin() as conn:
            before = (
                await conn.execute(text("SELECT value FROM settings WHERE key = 'budget.daily_usd'"))
            ).scalar_one()
            await conn.execute(text("UPDATE settings SET value = '0' WHERE key = 'budget.daily_usd'"))
        try:
            r = await client.post("/api/v1/discovery/runs", json={"market": "US"}, headers=csrf_headers(client))
            assert r.status_code == 422 and r.json()["code"] == "BUDGET_NOT_CONFIGURED"
        finally:
            async with clean_db.begin() as conn:
                await conn.execute(
                    text("UPDATE settings SET value = CAST(:v AS jsonb) WHERE key = 'budget.daily_usd'"),
                    {"v": __import__("json").dumps(before)},
                )
        assert await _counts(clean_db) == (0, 0)
