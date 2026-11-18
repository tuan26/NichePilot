"""Tạo client API cho test với DB PostgreSQL thật (không dùng dữ liệu nghiên cứu)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx

from nichepilot.core.config import Settings
from nichepilot.core.db import dispose_db, init_db
from nichepilot.main import create_app

PASSWORD = "correct-horse-battery"  # mật khẩu chỉ dùng trong test


def make_settings(db_url: str, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "database_url": db_url,
        "app_env": "test",
        "ai_provider_override": "mock",
        "log_format": "json",
    }
    values.update(overrides)
    return Settings(_env_file=None, _secrets_dir=None, **values)


@asynccontextmanager
async def api_client(db_url: str, **overrides: Any) -> AsyncIterator[httpx.AsyncClient]:
    settings = make_settings(db_url, **overrides)
    app = create_app(settings=settings)
    init_db(db_url)
    app.state.settings = settings
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client
    await dispose_db()


async def setup_owner(client: httpx.AsyncClient, username: str = "owner", locale: str = "vi") -> httpx.Response:
    return await client.post(
        "/api/v1/auth/setup", json={"username": username, "password": PASSWORD, "ui_locale": locale}
    )


def csrf_headers(client: httpx.AsyncClient) -> dict[str, str]:
    token = client.cookies.get("np_csrf")
    return {"X-CSRF-Token": token} if token else {}
