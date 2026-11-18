"""T068 – Không có internet (QA-14, FR-014, FR-018, SC-009). MockAIProvider mô phỏng lỗi kết nối trước khi gửi."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import api_client, csrf_headers, run_worker_once, setup_owner

pytestmark = [pytest.mark.integration, pytest.mark.mock]


async def test_TC_QA14_01_job_fails_with_network_error_rest_of_system_works(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        r = await client.post(
            "/api/v1/jobs",
            json={"job_type": "system.diagnostic", "params": {"mock_scenario": "network_error"}},
            headers=csrf_headers(client),
        )
        job_id = r.json()["id"]
        await run_worker_once(client)
        job = (await client.get(f"/api/v1/jobs/{job_id}")).json()
        assert job["status"] == "FAILED" and job["status_reason_code"] == "PROVIDER_NETWORK_ERROR"
        # Phần còn lại của hệ thống vẫn hoạt động
        for path in ("/health", "/api/v1/auth/me", "/api/v1/system/status", "/api/v1/jobs"):
            assert (await client.get(path)).status_code == 200, path
    async with clean_db.connect() as conn:
        rows = (await conn.execute(text("SELECT DISTINCT status, release_reason FROM budget_reservations"))).all()
    assert [tuple(r) for r in rows] == [("RELEASED", "NOT_SENT")]  # lỗi trước khi gửi → chắc chắn không tính phí
