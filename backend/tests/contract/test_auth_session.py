"""T043 – Contract đăng nhập, phiên, CSRF (FR-052, FR-053)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import PASSWORD, api_client, csrf_headers, setup_owner

pytestmark = pytest.mark.integration


async def test_TC_FR052_04_protected_endpoints_require_session(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with api_client(migrated_db) as client:
        for path in ("/api/v1/auth/me", "/api/v1/system/status"):
            r = await client.get(path)
            assert r.status_code == 401, path
            assert r.json()["code"] == "AUTH_REQUIRED"


async def test_TC_FR052_05_login_logout_and_me(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        client.cookies.clear()

        bad = await client.post("/api/v1/auth/login", json={"username": "owner", "password": "wrong-password-x"})
        assert bad.status_code == 401 and bad.json()["code"] == "AUTH_INVALID_CREDENTIALS"
        unknown = await client.post("/api/v1/auth/login", json={"username": "nobody", "password": PASSWORD})
        assert unknown.status_code == 401 and unknown.json()["code"] == "AUTH_INVALID_CREDENTIALS"

        ok = await client.post("/api/v1/auth/login", json={"username": "owner", "password": PASSWORD})
        assert ok.status_code == 200
        assert ok.json()["last_login_at"] is not None
        me = await client.get("/api/v1/auth/me")
        assert me.status_code == 200 and me.json()["username"] == "owner"

        r = await client.post("/api/v1/auth/logout", headers=csrf_headers(client))
        assert r.status_code == 204
        assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_TC_FR052_06_old_session_token_revoked_after_logout(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        token = client.cookies.get("np_session")
        await client.post("/api/v1/auth/logout", headers=csrf_headers(client))
        client.cookies.set("np_session", token or "")
        assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_TC_FR052_07_csrf_required_for_mutations(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        r = await client.patch("/api/v1/auth/me", json={"ui_locale": "en"})
        assert r.status_code == 403 and r.json()["code"] == "CSRF_INVALID"
        r = await client.patch("/api/v1/auth/me", json={"ui_locale": "en"}, headers={"X-CSRF-Token": "forged"})
        assert r.status_code == 403
        r = await client.patch("/api/v1/auth/me", json={"ui_locale": "en"}, headers=csrf_headers(client))
        assert r.status_code == 200 and r.json()["ui_locale"] == "en"
        assert (await client.get("/api/v1/auth/me")).json()["ui_locale"] == "en"
