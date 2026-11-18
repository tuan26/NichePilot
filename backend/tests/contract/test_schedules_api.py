"""T105 – Contract test CRUD /api/v1/schedules (FR-033, FR-034, FR-051)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import api_client, csrf_headers, setup_owner
from tests.integration.budget_helpers import restore_budget_defaults, set_setting

pytestmark = [pytest.mark.integration, pytest.mark.mock]


async def test_TC_FR033_08_schedule_api_crud(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        h = csrf_headers(client)
        body = {"name": "nightly", "job_type": "system.diagnostic", "cron_expr": "0 2 * * *", "enabled": True}
        r = await client.post("/api/v1/schedules", json=body, headers=h)
        assert r.status_code == 201, r.text
        sched = r.json()
        assert sched["timezone"] == "Asia/Ho_Chi_Minh" and sched["misfire_policy"] == "RUN_ONCE"
        assert datetime.fromisoformat(sched["next_run_at"]).astimezone(UTC).hour == 19  # 02:00 giờ Việt Nam
        assert (await client.post("/api/v1/schedules", json=body, headers=h)).status_code == 409  # trùng tên
        bad = await client.post("/api/v1/schedules", json={**body, "name": "x", "cron_expr": "* * * * *"}, headers=h)
        assert bad.status_code == 422
        bad = await client.post("/api/v1/schedules", json={**body, "name": "y", "job_type": "nope"}, headers=h)
        assert bad.status_code == 422
        sid = sched["id"]
        r = await client.patch(f"/api/v1/schedules/{sid}", json={**body, "enabled": False}, headers=h)
        assert r.status_code == 200 and r.json()["enabled"] is False
        assert len((await client.get("/api/v1/schedules")).json()) == 1
        assert (await client.get(f"/api/v1/schedules/{sid}")).json()["name"] == "nightly"

        await set_setting(clean_db, "budget.daily_usd", '"0"')
        try:
            r = await client.patch(f"/api/v1/schedules/{sid}", json={**body, "enabled": True}, headers=h)
            assert r.status_code == 422 and r.json()["code"] == "BUDGET_NOT_CONFIGURED"
        finally:
            await restore_budget_defaults(clean_db)

        assert (await client.delete(f"/api/v1/schedules/{sid}", headers=h)).status_code == 204
        assert (await client.get(f"/api/v1/schedules/{sid}")).status_code == 404
    async with clean_db.connect() as conn:
        actions = {
            r[0]
            for r in (await conn.execute(text("SELECT action FROM audit_logs WHERE action LIKE 'schedule.%'"))).all()
        }
    assert {"schedule.created", "schedule.updated", "schedule.deleted"} <= actions
