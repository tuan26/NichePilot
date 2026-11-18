"""I3 – Hủy job thành công luôn ghi `status_reason_code = JOB_CANCELLED` ở mọi trạng thái nguồn hợp lệ (FR-032).

Trạng thái nguồn được dựng trực tiếp trong DB làm dữ liệu test (fixture), không phải thao tác vận hành.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import api_client, csrf_headers, run_worker_once, setup_owner

pytestmark = [pytest.mark.integration, pytest.mark.mock]


async def _job(engine: AsyncEngine, status: str, reason: str | None = None) -> uuid.UUID:
    async with engine.begin() as conn:
        pid = (await conn.execute(text("SELECT id FROM projects WHERE is_default"))).scalar_one()
        jid = uuid.uuid4()
        await conn.execute(
            text(
                "INSERT INTO agent_jobs (id, project_id, job_type, params, idempotency_key, status, trigger, data_origin,"
                " budget_limit_usd, max_steps, max_ai_calls, timeout_s, max_attempts, status_reason_code)"
                " VALUES (:id, :p, 'system.diagnostic', '{}', :k, :s, 'MANUAL', 'MOCK', 2, 20, 30, 1800, 3, :r)"
            ),
            {"id": jid, "p": pid, "k": f"test:{jid}", "s": status, "r": reason},
        )
    return jid


@pytest.mark.parametrize(
    ("status", "reason"),
    [
        ("QUEUED", None),
        ("RETRY_SCHEDULED", "PROVIDER_TIMEOUT"),
        ("PAUSED", None),
        ("PAUSED_BUDGET", "BUDGET_JOB_EXCEEDED"),
    ],
)
async def test_TC_FR032_20_cancel_sets_job_cancelled(
    clean_db: AsyncEngine, migrated_db: str, status: str, reason: str | None
) -> None:
    jid = await _job(clean_db, status, reason)
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        r = await client.post(f"/api/v1/jobs/{jid}/cancel", headers=csrf_headers(client))
        assert r.status_code == 202, r.text
        job = (await client.get(f"/api/v1/jobs/{jid}")).json()
    assert job["status"] == "CANCELLED" and job["status_reason_code"] == "JOB_CANCELLED", job
    assert job["finished_at"] is not None
    assert (job["status_reason_detail"] or {}).get("previous_status") == status  # giữ dấu vết trạng thái trước


async def test_TC_FR032_21_cancel_paused_budget_keeps_uncertain_reservations(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    jid = await _job(clean_db, "PAUSED_BUDGET", "UNCERTAIN_RESERVATION_LIMIT")
    async with clean_db.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO budget_reservations (job_id, data_origin, amount_usd, status, sent_at, expires_at,"
                " uncertain_reason) VALUES (:j, 'MOCK', :a, 'UNCERTAIN', now(), now(), 'TIMEOUT_AFTER_SEND')"
            ),
            {"j": jid, "a": Decimal("0.01")},
        )
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        r = await client.post(f"/api/v1/jobs/{jid}/cancel", headers=csrf_headers(client))
        assert r.status_code == 202
        job = (await client.get(f"/api/v1/jobs/{jid}")).json()
        assert job["status_reason_code"] == "JOB_CANCELLED"
        assert (job["status_reason_detail"] or {}).get("previous_reason_code") == "UNCERTAIN_RESERVATION_LIMIT"
        unc = (await client.get("/api/v1/budget/reservations", params={"status": "UNCERTAIN"})).json()
    assert unc["total"] == 1  # hủy KHÔNG tự giải phóng reservation chưa xác định chi phí – vẫn chờ đối soát


async def test_TC_FR032_22_cancel_running_job_via_worker(clean_db: AsyncEngine, migrated_db: str) -> None:
    jid = await _job(clean_db, "RUNNING")
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        r = await client.post(f"/api/v1/jobs/{jid}/cancel", headers=csrf_headers(client))
        assert r.status_code == 202 and r.json()["status"] == "RUNNING"  # cờ hủy; worker dừng trước bước kế tiếp
        async with clean_db.begin() as conn:  # mô phỏng worker nhận lại lượt chạy (fixture)
            await conn.execute(text("UPDATE agent_jobs SET status = 'QUEUED' WHERE id = :j"), {"j": jid})
        await client.services.job_queue.enqueue_run(jid)  # type: ignore[attr-defined]
        await run_worker_once(client)
        job = (await client.get(f"/api/v1/jobs/{jid}")).json()
    assert job["status"] == "CANCELLED" and job["status_reason_code"] == "JOB_CANCELLED"
    assert job["ai_call_count"] == 0


@pytest.mark.parametrize("status", ["SUCCEEDED", "FAILED", "CANCELLED"])
async def test_TC_FR032_23_cancel_rejected_for_terminal_or_failed(
    clean_db: AsyncEngine, migrated_db: str, status: str
) -> None:
    jid = await _job(clean_db, status, "X" if status == "FAILED" else None)
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        r = await client.post(f"/api/v1/jobs/{jid}/cancel", headers=csrf_headers(client))
        assert r.status_code == 409 and r.json()["code"] == "INVALID_JOB_TRANSITION"
        job = (await client.get(f"/api/v1/jobs/{jid}")).json()
    assert job["status"] == status  # không đổi
