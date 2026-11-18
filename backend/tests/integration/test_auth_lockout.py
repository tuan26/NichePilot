"""T044 – Khóa tạm, hết hạn phiên, audit đăng nhập (FR-051, FR-053)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import PASSWORD, api_client, setup_owner
from tests.integration.budget_helpers import set_setting

pytestmark = pytest.mark.integration


async def _actions(engine: AsyncEngine) -> list[str]:
    async with engine.connect() as conn:
        return list((await conn.execute(text("SELECT action FROM audit_logs ORDER BY created_at"))).scalars())


async def test_TC_FR053_01_lockout_after_threshold(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        client.cookies.clear()
        for _ in range(5):
            r = await client.post("/api/v1/auth/login", json={"username": "owner", "password": "wrong-password-x"})
            assert r.status_code == 401
        # Lần thứ 6, kể cả đúng mật khẩu, vẫn bị khóa
        r = await client.post("/api/v1/auth/login", json={"username": "owner", "password": PASSWORD})
        assert r.status_code == 423
        body = r.json()
        assert body["code"] == "AUTH_LOCKED" and "locked_until" in body["params"]
        locked_until = datetime.fromisoformat(body["params"]["locked_until"])
        delta = locked_until - datetime.now(UTC)
        assert timedelta(minutes=14) < delta <= timedelta(minutes=15)

    actions = await _actions(clean_db)
    assert actions.count("auth.login_failed") >= 5
    assert "auth.account_locked" in actions
    assert "auth.owner_created" in actions


async def test_TC_FR053_02_lockout_settings_configurable(clean_db: AsyncEngine, migrated_db: str) -> None:
    await set_setting(clean_db, "auth.lockout_threshold", "2")
    try:
        async with api_client(migrated_db) as client:
            await setup_owner(client)
            client.cookies.clear()
            for _ in range(2):
                await client.post("/api/v1/auth/login", json={"username": "owner", "password": "wrong-password-x"})
            r = await client.post("/api/v1/auth/login", json={"username": "owner", "password": PASSWORD})
            assert r.status_code == 423
    finally:
        await set_setting(clean_db, "auth.lockout_threshold", "5")


async def test_TC_FR053_03_lock_expires(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        client.cookies.clear()
        for _ in range(5):
            await client.post("/api/v1/auth/login", json={"username": "owner", "password": "wrong-password-x"})
        async with clean_db.begin() as conn:
            await conn.execute(text("UPDATE users SET locked_until = now() - interval '1 second'"))
        r = await client.post("/api/v1/auth/login", json={"username": "owner", "password": PASSWORD})
        assert r.status_code == 200


async def test_TC_FR053_04_idle_session_expires(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        assert (await client.get("/api/v1/auth/me")).status_code == 200
        async with clean_db.begin() as conn:
            await conn.execute(text("UPDATE auth_sessions SET expires_at = now() - interval '1 second'"))
        assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_TC_FR051_03_logout_audited(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        await client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": client.cookies.get("np_csrf") or ""})
    assert "auth.logout" in await _actions(clean_db)
