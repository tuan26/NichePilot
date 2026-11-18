"""US3 – Giới hạn ngân sách AI (T083–T087; FR-042, FR-044, FR-045, FR-047, FR-048, FR-049, SC-004b, QA-11).

Chạy với MockAIProvider (sổ MOCK) – không phát sinh chi phí thật.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from nichepilot.ai.budget import BudgetService
from tests.api_helpers import api_client, csrf_headers, run_worker_once, setup_owner
from tests.integration.budget_helpers import insert_job, restore_budget_defaults, set_setting

pytestmark = [pytest.mark.integration, pytest.mark.mock]


@pytest.fixture
async def db(clean_db: AsyncEngine) -> AsyncIterator[AsyncEngine]:
    yield clean_db
    await restore_budget_defaults(clean_db)
    await set_setting(clean_db, "billing.error_responses_not_billed_verified", '{"anthropic": false, "openai": false}')


async def _create(client: httpx.AsyncClient, **body: Any) -> dict[str, Any]:
    r = await client.post("/api/v1/jobs", json={"job_type": "system.diagnostic", **body}, headers=csrf_headers(client))
    assert r.status_code == 201, r.text
    await run_worker_once(client)
    return (await client.get(f"/api/v1/jobs/{r.json()['id']}")).json()


async def _count(engine: AsyncEngine, sql: str, **p: Any) -> int:
    async with engine.connect() as conn:
        return int((await conn.execute(text(sql), p)).scalar_one())


async def test_TC_FR045_01_paused_budget_then_resume_from_checkpoint(db: AsyncEngine, migrated_db: str) -> None:
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        # Giữ chỗ tối đa mỗi lời gọi mock = 2000×0.10/1e6 + 1024×0.50/1e6 = $0.000712; chi phí thực bước 1 = $0.00045.
        # Giới hạn job $0.001: bước 1 đủ, bước 3 còn $0.00055 < $0.000712 → PAUSED_BUDGET ở bước 3.
        job = await _create(client, budget_limit_usd="0.001")
        assert job["status"] == "PAUSED_BUDGET", job
        assert job["status_reason_code"] == "BUDGET_JOB_EXCEEDED"
        detail = job["status_reason_detail"]
        assert {"limit_usd", "spent_usd", "held_usd", "requested_usd"} <= detail.keys()
        assert job["last_completed_seq"] == 2
        usage_before = await _count(db, "SELECT COUNT(*) FROM ai_usage_logs WHERE job_id = :j", j=job["id"])

        r = await client.post(f"/api/v1/jobs/{job['id']}/resume", headers=csrf_headers(client))
        assert r.status_code == 402 and r.json()["code"] == "BUDGET_STILL_INSUFFICIENT"

        await run_worker_once(client)  # không tự resume
        assert (await client.get(f"/api/v1/jobs/{job['id']}")).json()["status"] == "PAUSED_BUDGET"
        assert await _count(db, "SELECT COUNT(*) FROM ai_usage_logs WHERE job_id = :j", j=job["id"]) == usage_before

        async with db.begin() as conn:
            await conn.execute(text("UPDATE agent_jobs SET budget_limit_usd = 2 WHERE id = :j"), {"j": job["id"]})
        r = await client.post(f"/api/v1/jobs/{job['id']}/resume", headers=csrf_headers(client))
        assert r.status_code == 202 and r.json()["status"] == "QUEUED"
        await run_worker_once(client)
        done = (await client.get(f"/api/v1/jobs/{job['id']}")).json()
        assert done["status"] == "SUCCEEDED", done
        steps = (await client.get(f"/api/v1/jobs/{job['id']}/steps")).json()
        assert [s["seq"] for s in steps] == [1, 2, 3]  # không lặp bước đã hoàn tất
        assert steps[2]["attempt"] == 2


async def test_TC_FR049_03_uncertain_limit_pauses_and_requires_reconciliation(db: AsyncEngine, migrated_db: str) -> None:
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        job = await _create(client, params={"mock_scenario": "timeout_after_send"})
        assert job["status"] == "PAUSED_BUDGET" and job["status_reason_code"] == "UNCERTAIN_RESERVATION_LIMIT", job
        unc = (await client.get("/api/v1/budget/reservations?status=UNCERTAIN")).json()
        assert unc["total"] == 3
        assert all(i["uncertain_reason"] == "TIMEOUT_AFTER_SEND" for i in unc["items"])
        budget = (await client.get("/api/v1/budget")).json()
        assert budget["mock"]["uncertain_count"] == 3 and "UNCERTAIN_RESERVATIONS" in budget["mock"]["warnings"]
        assert budget["real"]["uncertain_count"] == 0

        r = await client.post(f"/api/v1/jobs/{job['id']}/resume", headers=csrf_headers(client))
        assert r.status_code == 423 and r.json()["code"] == "UNCERTAIN_RESERVATIONS_UNRESOLVED"
        await run_worker_once(client)
        assert await _count(db, "SELECT COUNT(*) FROM budget_reservations WHERE job_id = :j", j=job["id"]) == 3

        for item in unc["items"]:
            r = await client.post(
                f"/api/v1/budget/reservations/{item['id']}/resolve",
                json={"actual_usd": "0", "resolution_note": "Đối chiếu trang usage của provider"},
                headers=csrf_headers(client),
            )
            assert r.status_code == 200 and r.json()["status"] == "RESOLVED"
        again = await client.post(
            f"/api/v1/budget/reservations/{unc['items'][0]['id']}/resolve",
            json={"actual_usd": "0", "resolution_note": "lần hai"},
            headers=csrf_headers(client),
        )
        assert again.status_code == 409 and again.json()["code"] == "RESERVATION_NOT_UNCERTAIN"
        assert await _count(db, "SELECT COUNT(*) FROM audit_logs WHERE action = 'budget.reservation_resolved'") == 3

        async with db.begin() as conn:  # chuyển sang kịch bản thành công để job hoàn tất sau khi tiếp tục
            await conn.execute(text("UPDATE agent_jobs SET params = '{}'::jsonb WHERE id = :j"), {"j": job["id"]})
        r = await client.post(f"/api/v1/jobs/{job['id']}/resume", headers=csrf_headers(client))
        assert r.status_code == 202
        await run_worker_once(client)
        assert (await client.get(f"/api/v1/jobs/{job['id']}")).json()["status"] == "SUCCEEDED"


async def test_TC_FR049_04_limit_configurable(db: AsyncEngine, migrated_db: str) -> None:
    await set_setting(db, "budget.max_uncertain_per_job", "1")
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        job = await _create(client, params={"mock_scenario": "timeout_after_send"})
        assert job["status_reason_code"] == "UNCERTAIN_RESERVATION_LIMIT"
    assert await _count(db, "SELECT COUNT(*) FROM budget_reservations WHERE status = 'UNCERTAIN'") == 1


async def test_TC_FR047_06_error_response_policy(db: AsyncEngine, migrated_db: str) -> None:
    sm = async_sessionmaker(db, expire_on_commit=False)
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        await set_setting(db, "billing.error_responses_not_billed_verified", '{"mock": false}')
        job = await _create(client, params={"mock_scenario": "provider_error"})
        assert job["status_reason_code"] == "UNCERTAIN_RESERVATION_LIMIT"
        assert await _count(db, "SELECT COUNT(*) FROM budget_reservations WHERE uncertain_reason = 'ERROR_BILLING_UNVERIFIED'") == 3
        await set_setting(db, "billing.error_responses_not_billed_verified", '{"mock": true}')
        job2 = await _create(client, params={"mock_scenario": "provider_error"})
        assert job2["status_reason_code"] == "PROVIDER_UNAVAILABLE"
        assert await _count(
            db, "SELECT COUNT(*) FROM budget_reservations WHERE job_id = :j AND release_reason = 'ERROR_RESPONSE_NOT_BILLED'", j=job2["id"]
        ) == 3
    _ = sm


async def test_TC_FR048_01_sweep_stale(db: AsyncEngine) -> None:
    svc = BudgetService(async_sessionmaker(db, expire_on_commit=False))
    job = await insert_job(db)
    not_sent = await svc.reserve(job, __import__("decimal").Decimal("0.10"), "MOCK", call_timeout_s=1)
    sent = await svc.reserve(job, __import__("decimal").Decimal("0.10"), "MOCK", call_timeout_s=1)
    await svc.mark_sent(sent.id)
    unc = await svc.reserve(job, __import__("decimal").Decimal("0.10"), "MOCK", call_timeout_s=1)
    await svc.mark_sent(unc.id)
    await svc.mark_uncertain(unc.id, "TIMEOUT_AFTER_SEND")
    async with db.begin() as conn:
        await conn.execute(text("UPDATE budget_reservations SET expires_at = now() - interval '1 second'"))
    assert await svc.sweep_stale() == {"released": 1, "uncertain": 1}
    async with db.connect() as conn:
        rows = dict((await conn.execute(text(
            "SELECT id, status || ':' || COALESCE(release_reason, uncertain_reason) FROM budget_reservations"))).all())
    assert rows[not_sent.id] == "RELEASED:NOT_SENT"
    assert rows[sent.id] == "UNCERTAIN:WORKER_LOST"
    assert rows[unc.id] == "UNCERTAIN:TIMEOUT_AFTER_SEND"  # không bao giờ tự giải phóng UNCERTAIN
    assert await svc.sweep_stale() == {"released": 0, "uncertain": 0}


async def test_TC_FR042_02_budget_api_validation_and_summary(db: AsyncEngine, migrated_db: str) -> None:
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        b = (await client.get("/api/v1/budget")).json()
        assert b["limits"]["daily_usd"] == "3.000000" and b["limits"]["max_uncertain_per_job"] == 3
        bad = await client.put("/api/v1/budget", json={"daily_usd": "1", "monthly_usd": "30", "per_job_default_usd": "2"},
                               headers=csrf_headers(client))
        assert bad.status_code == 422
        bad2 = await client.put("/api/v1/budget", json={"daily_usd": "3", "monthly_usd": "30", "per_job_default_usd": "2",
                                                        "max_uncertain_per_job": 0}, headers=csrf_headers(client))
        assert bad2.status_code == 422
        ok = await client.put("/api/v1/budget", json={"daily_usd": "0.001", "monthly_usd": "30", "per_job_default_usd": "0.001",
                                                      "warning_threshold": 0.4}, headers=csrf_headers(client))
        assert ok.status_code == 200 and ok.json()["limits"]["daily_usd"] == "0.001000"
        assert await _count(db, "SELECT COUNT(*) FROM audit_logs WHERE action = 'budget.limits_updated'") == 1
        await _create(client)  # chạm ngân sách ngày (sổ MOCK)
        warnings = (await client.get("/api/v1/budget")).json()["mock"]["warnings"]
        assert any(w.startswith("DAILY_") for w in warnings)
        real = (await client.get("/api/v1/costs/summary?period=day")).json()
        mock = (await client.get("/api/v1/costs/summary?period=day&data_origin=MOCK")).json()
        assert real["total_usd"] == "0.000000" and real["call_count"] == 0  # mock không lẫn vào chi phí thật
        assert mock["call_count"] >= 1 and mock["by_model"][0]["provider"] == "mock"
