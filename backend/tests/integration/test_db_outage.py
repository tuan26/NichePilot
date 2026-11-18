"""T069 – Database mất kết nối tạm thời (QA-08, FR-003, FR-061, SC-009).

Mô phỏng: ngắt mọi kết nối của ứng dụng và tạm cấm kết nối mới vào database (ALLOW_CONNECTIONS false), sau đó
mở lại. Dùng database riêng để không ảnh hưởng DB dùng chung của phiên test.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from alembic import command
from sqlalchemy import create_engine, text

from tests.api_helpers import api_client, setup_owner
from tests.helpers import alembic_config

pytestmark = pytest.mark.integration


async def test_TC_QA08_01_db_outage_returns_503_and_recovers(pg_url: str) -> None:
    name = f"outage_{uuid.uuid4().hex[:8]}"
    admin = create_engine(pg_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{name}"'))
    url = f"{pg_url.rpartition('/')[0]}/{name}"
    command.upgrade(alembic_config(url), "head")
    try:
        async with api_client(url) as client:
            assert (await setup_owner(client)).status_code == 201
            assert (await client.get("/api/v1/auth/me")).status_code == 200

            with admin.connect() as c:  # DB "biến mất": chặn kết nối mới + ngắt kết nối hiện có
                c.execute(text(f'ALTER DATABASE "{name}" ALLOW_CONNECTIONS false'))
                c.execute(
                    text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :d"), {"d": name}
                )
            try:
                r = await asyncio.wait_for(client.get("/api/v1/jobs"), timeout=30)
            finally:
                with admin.connect() as c:
                    c.execute(text(f'ALTER DATABASE "{name}" ALLOW_CONNECTIONS true'))
            assert r.status_code == 503
            assert r.json()["code"] == "SERVICE_UNAVAILABLE"
            assert "psycopg" not in r.text and "Traceback" not in r.text and "password" not in r.text.lower()

            for _ in range(20):  # tự phục hồi khi DB trở lại
                r = await client.get("/api/v1/auth/me")
                if r.status_code == 200:
                    break
                await asyncio.sleep(0.5)
            assert r.status_code == 200
    finally:
        with admin.connect() as c:
            c.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :d"), {"d": name})
            c.execute(text(f'DROP DATABASE IF EXISTS "{name}"'))
        admin.dispose()
