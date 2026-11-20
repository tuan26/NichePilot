"""T017 – Cổng erasure ledger (FR-013f; X4/H1): BLOCKED/lệch → dữ liệu E1 trả 503, agent dừng ở preflight; E0 không đổi."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from nichepilot.core.discovery_config import DiscoverySettings
from nichepilot.core.errors import AppError
from tests.api_helpers import api_client, setup_owner

pytestmark = [pytest.mark.integration, pytest.mark.discovery]


def _ds(tmp: Path) -> DiscoverySettings:
    return DiscoverySettings(
        app_env="test",
        discovery_source_mode="mock",
        erasure_ledger_dir=tmp / "ledger",
        searxng_config_dir=tmp / "searxng",
    )


async def test_TC_E1_FR013f_07_status_and_gate(clean_db: AsyncEngine, migrated_db: str, tmp_path: Path) -> None:
    async with api_client(migrated_db, discovery_settings=_ds(tmp_path)) as client:
        await setup_owner(client)
        e0_status_before = (await client.get("/api/v1/system/status")).json().keys()
        r = await client.get("/api/v1/discovery/status")
        assert r.status_code == 200
        body = r.json()
        assert body["erasure_ledger"]["status"] == "OUT_OF_SYNC"  # sổ chưa khởi tạo (migrate chưa chạy trong test)
        assert body["pii_engine"] == "regex-phone/1" and body["searxng"] == "NOT_CONFIGURED"
        assert body["usable_sources"] == 0
        gate = client.services.discovery.require_ledger_ok  # type: ignore[attr-defined]
        with pytest.raises(Exception) as exc:
            await gate(force=True)
        assert getattr(exc.value, "code", None) == "ERASURE_LEDGER_NOT_APPLIED"
        await client.services.discovery.apply_ledger()  # type: ignore[attr-defined]
        await gate(force=True)  # OK sau khi áp dụng
        async with clean_db.begin() as conn:
            await conn.execute(text("UPDATE erasure_ledger_state SET status = 'BLOCKED', last_error = 'TEST'"))
        with pytest.raises(AppError):
            await gate(force=True)
        assert (await client.get("/api/v1/discovery/status")).json()["erasure_ledger"]["status"] == "BLOCKED"
        assert (await client.get("/health")).json() == {"status": "ok"}
        assert (await client.get("/api/v1/system/status")).json().keys() == e0_status_before  # E0 không đổi


async def test_TC_E1_FR013f_08_agent_preflight_stops_when_blocked(
    clean_db: AsyncEngine, migrated_db: str, tmp_path: Path
) -> None:
    from tests.api_helpers import csrf_headers, run_worker_once

    async with api_client(migrated_db, discovery_settings=_ds(tmp_path)) as client:
        await setup_owner(client)
        await client.services.discovery.apply_ledger()  # type: ignore[attr-defined]
        async with clean_db.begin() as conn:
            await conn.execute(text("UPDATE erasure_ledger_state SET status = 'BLOCKED', last_error = 'TEST'"))
        r = await client.post(
            "/api/v1/jobs", json={"job_type": "discovery.run", "params": {"market": "US"}}, headers=csrf_headers(client)
        )
        assert r.status_code == 201, r.text
        await run_worker_once(client)
        job = (await client.get(f"/api/v1/jobs/{r.json()['id']}")).json()
        assert job["status"] == "FAILED" and job["status_reason_code"] == "ERASURE_LEDGER_NOT_APPLIED"
        async with clean_db.connect() as conn:
            assert (
                await conn.execute(text("SELECT count(*) FROM ai_usage_logs WHERE job_id = :j"), {"j": r.json()["id"]})
            ).scalar_one() == 0
            assert (await conn.execute(text("SELECT count(*) FROM discovery_runs"))).scalar_one() == 0
