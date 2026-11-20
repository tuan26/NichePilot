"""Tạo client API cho test với DB PostgreSQL thật (không dùng dữ liệu nghiên cứu)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx

from nichepilot.core.config import Settings
from nichepilot.core.db import dispose_db, init_db
from nichepilot.main import create_app
from nichepilot.services import build_services

PASSWORD = "correct-horse-battery"  # mật khẩu chỉ dùng trong test


def make_discovery_settings(**overrides: Any) -> Any:
    """Cấu hình E1 cho test: nguồn giả lập (MOCK), thư mục sổ xóa tạm – không truy cập mạng."""
    import tempfile
    from pathlib import Path

    from nichepilot.core.discovery_config import DiscoverySettings

    tmp = Path(tempfile.mkdtemp(prefix="np-e1-"))
    values: dict[str, Any] = {
        "app_env": "test",
        "discovery_source_mode": "mock",
        "erasure_ledger_dir": tmp / "ledger",
        "searxng_config_dir": tmp / "searxng",
    }
    values.update(overrides)
    return DiscoverySettings(**values)


def make_settings(db_url: str, **overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "database_url": db_url,
        "app_env": "test",
        "ai_provider_override": "mock",
        "log_format": "json",
        "job_retry_delay_s": 0,
    }
    values.update(overrides)
    return Settings(_env_file=None, _secrets_dir=None, **values)


@asynccontextmanager
async def api_client(
    db_url: str, *, gateway_backoff_zero: bool = True, discovery_settings: Any = None, **overrides: Any
) -> AsyncIterator[httpx.AsyncClient]:
    settings = make_settings(db_url, **overrides)
    app = create_app(settings=settings)
    sessionmaker = init_db(db_url)
    app.state.settings = settings
    services = build_services(
        settings, sessionmaker, discovery_settings=discovery_settings or make_discovery_settings()
    )
    if gateway_backoff_zero:
        services.gateway.backoff_base_s = 0
    app.state.services = services
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with services.procrastinate_app.open_async():
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            client.services = services  # type: ignore[attr-defined]
            yield client
    await dispose_db()


async def setup_owner(client: httpx.AsyncClient, username: str = "owner", locale: str = "vi") -> httpx.Response:
    return await client.post(
        "/api/v1/auth/setup", json={"username": username, "password": PASSWORD, "ui_locale": locale}
    )


def csrf_headers(client: httpx.AsyncClient) -> dict[str, str]:
    token = client.cookies.get("np_csrf")
    return {"X-CSRF-Token": token} if token else {}


async def run_worker_once(client: httpx.AsyncClient) -> None:
    """Chạy Procrastinate worker thật cho tới khi hết job trong hàng đợi (wait=False) – mô phỏng tiến trình worker."""
    services = client.services  # type: ignore[attr-defined]
    await services.procrastinate_app.run_worker_async(
        queues=["agent_jobs"], wait=False, install_signal_handlers=False, listen_notify=False
    )
