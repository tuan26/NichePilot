"""FR-044 – Tổng hợp chi phí ngày/tháng/job/model; mặc định chỉ chi phí thật (REAL); MOCK tách riêng; cảnh báo 80%.

Bản ghi usage dưới đây là DỮ LIỆU TEST tự tạo (không phải chi phí thật của provider nào).
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import api_client, setup_owner
from tests.integration.budget_helpers import insert_job, insert_usage

pytestmark = [pytest.mark.integration, pytest.mark.mock]


async def test_TC_FR044_01_summary_real_by_default_mock_separate(clean_db: AsyncEngine, migrated_db: str) -> None:
    real_job = await insert_job(clean_db, origin="REAL")
    mock_job = await insert_job(clean_db, origin="MOCK")
    await insert_usage(clean_db, real_job, "2.50", origin="REAL")  # 83% hạn mức ngày $3 → cảnh báo
    await insert_usage(clean_db, mock_job, "0.10", origin="MOCK")
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        day = (await client.get("/api/v1/costs/summary", params={"period": "day"})).json()
        month = (await client.get("/api/v1/costs/summary", params={"period": "month"})).json()
        mock = (await client.get("/api/v1/costs/summary", params={"period": "day", "data_origin": "MOCK"})).json()
        budget = (await client.get("/api/v1/budget")).json()
    assert day["data_origin"] == "REAL" and day["total_usd"] == "2.500000" and day["call_count"] == 1
    assert month["total_usd"] == "2.500000"
    assert day["by_job_type"] == [{"job_type": "system.diagnostic", "cost_usd": "2.500000", "job_count": 1}]
    assert len(day["by_model"]) == 1 and len(day["by_day"]) == 1
    assert mock["total_usd"] == "0.100000"  # MOCK chỉ hiện khi yêu cầu rõ, tách riêng
    assert any(w.startswith("DAILY_") for w in budget["real"]["warnings"])
    assert not any(w.startswith("DAILY_") for w in budget["mock"]["warnings"])
