"""T045 – Contract trạng thái hệ thống (FR-002, FR-054)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import api_client, setup_owner

pytestmark = pytest.mark.integration


async def test_TC_FR002_03_status_without_api_keys_is_not_an_error(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        r = await client.get("/api/v1/system/status")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["database"] == "OK"
    assert body["worker"] in {"OK", "STALE", "NOT_RUNNING"}
    assert body["app_env"] == "test"
    assert body["paid_calls_enabled"] is False
    assert body["provider_override"] == "mock"
    assert body["schema_revision"]
    providers = {p["provider"]: p for p in body["providers"]}
    assert providers["anthropic"]["configured"] is False and providers["anthropic"]["key_hint"] is None
    assert providers["openai"]["configured"] is False


async def test_TC_FR054_04_key_hint_never_reveals_key(clean_db: AsyncEngine, migrated_db: str) -> None:
    key = "sk-ant-api03-THIS-IS-A-TEST-ONLY-KEY-wxyz"
    async with api_client(migrated_db, anthropic_api_key=key) as client:
        await setup_owner(client)
        r = await client.get("/api/v1/system/status")
    assert key not in r.text
    assert "sk-ant" not in r.text
    anthropic = next(p for p in r.json()["providers"] if p["provider"] == "anthropic")
    assert anthropic["configured"] is True and anthropic["key_hint"] == "…wxyz"
