"""T100 – Ngân sách lượt khám phá (FR-028, FR-030e, SC-006, SC-012): mọi lời gọi qua Gateway + giữ chỗ; vượt hạn mức → PAUSED_BUDGET,
không gửi lời gọi vượt; kết quả đã có được giữ; không tự tăng ngân sách; chi phí tách REAL/MOCK. MOCK – không có lời gọi có phí."""

from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.discovery_helpers import allow_test_source, discovery_client
from tests.discovery_run import FORUM, REVIEW, run_discovery, set_search
from tests.fakes.discovery_ai import ScriptedDiscoveryAI

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]


async def test_TC_E1_FR028_01_TC_E1_FR030e_01_run_budget_pauses_without_overspending(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    ai = ScriptedDiscoveryAI()
    async with discovery_client(migrated_db, ai=ai) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        run = await run_discovery(client, {"market": "US", "budget_usd": "0.00415"})
        job_id = run["job"]["job_id"]
        async with clean_db.connect() as conn:
            job = (
                await conn.execute(
                    text(
                        "SELECT status, status_reason_code, budget_limit_usd, cost_accumulated_usd FROM agent_jobs"
                        " WHERE id = :j"
                    ),
                    {"j": job_id},
                )
            ).one()
            sent = (
                await conn.execute(text("SELECT count(*) FROM ai_usage_logs WHERE job_id = :j AND sent"), {"j": job_id})
            ).scalar_one()
            niches = (await conn.execute(text("SELECT count(*) FROM niches"))).scalar_one()
        assert job.status == "PAUSED_BUDGET" and job.status_reason_code.startswith("BUDGET_")
        assert job.budget_limit_usd == Decimal("0.004150")  # không tự tăng ngân sách
        assert job.cost_accumulated_usd <= job.budget_limit_usd
        assert (
            sent == len(ai.requests) >= 1
        )  # mọi lời gọi đi qua Gateway (có usage log); lời gọi vượt hạn mức không được gửi
        assert niches == 3  # kết quả đã có (ứng viên) được giữ


async def test_TC_E1_SC006_01_daily_limit_blocks_new_calls(clean_db: AsyncEngine, migrated_db: str) -> None:
    ai = ScriptedDiscoveryAI()
    async with discovery_client(migrated_db, ai=ai) as client:
        await allow_test_source(clean_db)
        sql = "UPDATE settings SET value = CAST(:v AS jsonb) WHERE key = 'budget.daily_usd'"
        async with clean_db.begin() as conn:
            old = (
                await conn.execute(text("SELECT value::text FROM settings WHERE key = 'budget.daily_usd'"))
            ).scalar_one()
            await conn.execute(text(sql), {"v": '"0.00415"'})  # hạn mức NGÀY chỉ đủ một lời gọi
        try:
            set_search(client, [FORUM, REVIEW])
            run = await run_discovery(client, {"market": "US", "budget_usd": "0.00415"})
            async with clean_db.connect() as conn:
                st = (
                    await conn.execute(
                        text("SELECT status, status_reason_code FROM agent_jobs WHERE id = :j"),
                        {"j": run["job"]["job_id"]},
                    )
                ).one()
            assert st.status == "PAUSED_BUDGET"
            calls_before = len(ai.requests)
            # tiếp tục khi vẫn vượt hạn mức → bị từ chối, không gửi thêm lời gọi
            from tests.api_helpers import csrf_headers

            r = await client.post(f"/api/v1/jobs/{run['job']['job_id']}/resume", headers=csrf_headers(client))
            assert r.status_code >= 400 and len(ai.requests) == calls_before
        finally:
            async with clean_db.begin() as conn:
                await conn.execute(text(sql), {"v": old})


async def test_TC_E1_SC012_01_costs_reported_separately(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        run = await run_discovery(client)
        m = run["metrics"]
        assert Decimal(m["cost_real_usd"]) == 0 and Decimal(m["cost_mock_usd"]) > 0
        async with clean_db.connect() as conn:
            real = (
                await conn.execute(text("SELECT count(*) FROM ai_usage_logs WHERE data_origin = 'REAL'"))
            ).scalar_one()
        assert real == 0
