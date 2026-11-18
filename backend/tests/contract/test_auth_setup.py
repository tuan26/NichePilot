"""T042 – Contract khởi tạo tài khoản chủ sở hữu (FR-052)."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import PASSWORD, api_client, setup_owner

pytestmark = pytest.mark.integration


async def test_TC_FR052_01_setup_flow(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with api_client(migrated_db) as client:
        r = await client.get("/api/v1/auth/setup-status")
        assert r.status_code == 200 and r.json() == {"setup_required": True}

        r = await setup_owner(client)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["username"] == "owner" and body["ui_locale"] == "vi"
        assert "password" not in r.text and "password_hash" not in r.text
        assert client.cookies.get("np_session") and client.cookies.get("np_csrf")
        set_cookie = r.headers.get_list("set-cookie")
        session_cookie = next(c for c in set_cookie if c.startswith("np_session="))
        assert "HttpOnly" in session_cookie and "SameSite=lax" in session_cookie.replace("Lax", "lax")

        assert (await client.get("/api/v1/auth/setup-status")).json() == {"setup_required": False}


async def test_TC_FR052_02_second_setup_rejected(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with api_client(migrated_db) as client:
        assert (await setup_owner(client)).status_code == 201
        r = await setup_owner(client, username="intruder")
        assert r.status_code == 409 and r.json()["code"] == "ALREADY_SETUP"


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"username": "owner", "password": "short", "ui_locale": "vi"}, "password"),
        ({"username": "Bad Name!", "password": PASSWORD, "ui_locale": "vi"}, "username"),
        ({"username": "owner", "password": PASSWORD, "ui_locale": "fr"}, "ui_locale"),
    ],
)
async def test_TC_FR052_03_setup_validation(
    clean_db: AsyncEngine, migrated_db: str, payload: dict[str, str], field: str
) -> None:
    async with api_client(migrated_db) as client:
        r = await client.post("/api/v1/auth/setup", json=payload)
        assert r.status_code == 422
        assert r.json()["code"] == "VALIDATION_ERROR"
        assert any(e["field"].endswith(field) for e in r.json()["errors"])
