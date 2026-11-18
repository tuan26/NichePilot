"""T067 – Job chẩn đoán qua API + worker Procrastinate thật, với MockAIProvider.

(FR-018, FR-026, FR-031, SC-003b, SC-005, SC-009, QA-01, QA-02, QA-15). Đây KHÔNG phải kiểm thử API Claude/OpenAI thật.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import api_client, csrf_headers, run_worker_once, setup_owner
from tests.conftest import OutboundNetworkBlockedError

pytestmark = [pytest.mark.integration, pytest.mark.mock]


async def _run(client: httpx.AsyncClient, params: dict[str, Any] | None = None) -> dict[str, Any]:
    r = await client.post(
        "/api/v1/jobs", json={"job_type": "system.diagnostic", "params": params or {}}, headers=csrf_headers(client)
    )
    assert r.status_code == 201, r.text
    job = r.json()
    assert job["status"] == "QUEUED" and job["data_origin"] == "MOCK"
    await run_worker_once(client)
    return (await client.get(f"/api/v1/jobs/{job['id']}")).json()


async def test_TC_FR026_01_diagnostic_job_succeeds_with_mock(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        job = await _run(client)
        assert job["status"] == "SUCCEEDED", job
        assert job["result"]["status"] == "ok" and job["result"]["note"].startswith("[MOCK]")
        assert job["result"]["data_origin"] == "MOCK" and job["result"]["provider"] == "mock"
        assert "server_time_utc" in job["result"]["runtime"]
        steps = (await client.get(f"/api/v1/jobs/{job['id']}/steps")).json()
        assert [(s["seq"], s["step_type"], s["status"], s["data_origin"]) for s in steps] == [
            (1, "AI_CALL", "SUCCEEDED", "MOCK"),
            (2, "TOOL_CALL", "SUCCEEDED", "MOCK"),
            (3, "AI_CALL", "SUCCEEDED", "MOCK"),
        ]
        assert steps[1]["tool_executions"][0]["tool_name"] == "system.runtime_info"
        usage_mock = (await client.get(f"/api/v1/costs/usage?job_id={job['id']}&data_origin=MOCK")).json()
        assert usage_mock["total"] == 2 and {u["provider"] for u in usage_mock["items"]} == {"mock"}
        usage_real = (await client.get(f"/api/v1/costs/usage?job_id={job['id']}")).json()
        assert usage_real["total"] == 0  # mặc định chỉ chi phí thật – mock không lẫn vào
        types = (await client.get("/api/v1/job-types")).json()
        assert types[0]["job_type"] == "system.diagnostic"
        tools = (await client.get("/api/v1/tools")).json()
        assert tools[0]["name"] == "system.runtime_info" and tools[0]["enabled"] is True


@pytest.mark.parametrize(
    ("scenario", "code", "step_status"),
    [
        ("timeout", "PROVIDER_TIMEOUT", "FAILED"),
        ("rate_limit", "PROVIDER_RATE_LIMITED", "FAILED"),
        ("schema_invalid", "AI_SCHEMA_INVALID", "FAILED"),
        ("provider_error", "PROVIDER_UNAVAILABLE", "FAILED"),
        ("auth_error", "PROVIDER_AUTH_ERROR", "FAILED"),
        ("refusal", "AI_REFUSED", "REFUSED"),
        ("truncated", "AI_TRUNCATED", "TRUNCATED"),
    ],
)
async def test_TC_QA01_01_error_scenarios(
    clean_db: AsyncEngine, migrated_db: str, scenario: str, code: str, step_status: str
) -> None:
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        job = await _run(client, {"mock_scenario": scenario})
        assert job["status"] == "FAILED" and job["status_reason_code"] == code, job
        assert job["result"] is None  # không lưu kết quả thiếu/sai
        steps = (await client.get(f"/api/v1/jobs/{job['id']}/steps")).json()
        assert steps[-1]["status"] == step_status and steps[-1]["error_code"] == code


async def test_TC_SC003b_01_no_network_and_validation(clean_db: AsyncEngine, migrated_db: str) -> None:
    import socket

    async with api_client(migrated_db) as client:
        await setup_owner(client)
        with pytest.raises(OutboundNetworkBlockedError):  # chứng minh guard mạng đang bật trong test
            socket.create_connection(("api.anthropic.com", 443), timeout=1)
        r = await client.post("/api/v1/jobs", json={"job_type": "nope"}, headers=csrf_headers(client))
        assert r.status_code == 422
        r = await client.post(
            "/api/v1/jobs",
            json={"job_type": "system.diagnostic", "params": {"mock_scenario": "invalid!"}},
            headers=csrf_headers(client),
        )
        assert r.status_code in (409, 422)
        r = await client.post(
            "/api/v1/jobs",
            json={"job_type": "system.diagnostic", "budget_limit_usd": "50"},
            headers=csrf_headers(client),
        )
        assert r.status_code == 422  # vượt ngân sách ngày


async def test_TC_FR037_02_idempotency_key(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        body = {"job_type": "system.diagnostic", "idempotency_key": "same-key"}
        a = await client.post("/api/v1/jobs", json=body, headers=csrf_headers(client))
        b = await client.post("/api/v1/jobs", json=body, headers=csrf_headers(client))
        assert a.status_code == 201 and b.status_code == 200 and a.json()["id"] == b.json()["id"]
    async with clean_db.connect() as conn:
        assert (await conn.execute(text("SELECT COUNT(*) FROM procrastinate_jobs"))).scalar() == 1
