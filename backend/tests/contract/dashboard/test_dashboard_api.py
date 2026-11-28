"""T005 – hợp đồng API dashboard E4: auth, ledger 503, validate, không secret, module chỉ đọc (FR-006, FR-019, FR-023)."""

from __future__ import annotations

import inspect
import pathlib

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from nichepilot.modules.dashboard import queries
from tests.keywords_helpers import keywords_client

pytestmark = [pytest.mark.integration, pytest.mark.dashboard]


async def test_TC_E4_FR006_02_contract_auth_ledger_validation(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with keywords_client(migrated_db) as client:
        r = await client.get("/api/v1/dashboard/niches", params={"limit": 0})
        assert r.status_code == 422
        r = await client.get("/api/v1/dashboard/overview")
        assert r.status_code == 200
        assert set(r.json()) >= {"niches", "products", "keywords", "jobs", "top_niches", "include_mock", "generated_at"}
        body = r.text.lower()
        for word in ("api_key", "sk-ant", "password", "secret"):  # TC_E4_FR019_01
            assert word not in body
        await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": client.cookies.get("np_csrf", "")})
        client.cookies.clear()
        assert (await client.get("/api/v1/dashboard/overview")).status_code == 401


async def test_TC_E4_FR006_03_ledger_gate(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with keywords_client(migrated_db) as client:
        async with clean_db.begin() as conn:
            await conn.execute(text("UPDATE erasure_ledger_state SET status = 'BLOCKED', last_error = 'TEST'"))
        client.services.discovery._health = None  # type: ignore[attr-defined]
        for url in ("/api/v1/dashboard/overview", "/api/v1/dashboard/niches"):
            r = await client.get(url)
            assert r.status_code == 503 and r.json()["code"] == "ERASURE_LEDGER_NOT_APPLIED"


def test_TC_E4_FR023_01_dashboard_module_read_only() -> None:
    src = pathlib.Path(inspect.getfile(queries)).read_text(encoding="utf-8").upper()
    for verb in ("INSERT ", "UPDATE ", "DELETE ", "TRUNCATE ", "ALTER ", "CALL_AI", "CALL_TOOL"):
        assert verb not in src, verb
