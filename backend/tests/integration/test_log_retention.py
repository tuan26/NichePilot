"""T117 – Retention log ứng dụng (FR-057): xóa file quá hạn lưu, KHÔNG xóa vì dung lượng, cảnh báo khi vượt ngưỡng."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from nichepilot.core.logging import configure_logging
from nichepilot.jobs.maintenance import run_log_maintenance
from tests.api_helpers import api_client, setup_owner
from tests.integration.budget_helpers import set_setting

pytestmark = [pytest.mark.integration]
TODAY = date(2026, 11, 18)


def _file(d: Path, days_ago: int, size: int = 10) -> Path:
    p = d / f"app-{(TODAY - timedelta(days=days_ago)).isoformat()}.jsonl"
    p.write_bytes(b"x" * size)
    return p


async def test_TC_FR057_10_retention_and_size_warning(clean_db: AsyncEngine, tmp_path: Path) -> None:
    logs = tmp_path / "logs"
    logs.mkdir()
    old = [_file(logs, 91), _file(logs, 120)]
    kept = [_file(logs, 90), _file(logs, 89, size=3_000_000), _file(logs, 0)]
    other = logs / "notes.txt"
    other.write_text("không phải log ứng dụng")
    async with clean_db.begin() as conn:
        audit_before = (await conn.execute(text("SELECT COUNT(*) FROM audit_logs"))).scalar_one()
    await set_setting(clean_db, "logging.disk_warn_gb", "0.001")  # ~1 MB → vượt ngưỡng
    try:
        configure_logging(level="INFO", fmt="json", log_dir=tmp_path / "app")
        report = await run_log_maintenance(async_sessionmaker(clean_db), logs, today=TODAY)
    finally:
        await set_setting(clean_db, "logging.disk_warn_gb", "2")
    assert sorted(report.deleted) == sorted(p.name for p in old)
    assert all(not p.exists() for p in old)
    assert all(p.exists() for p in kept) and other.exists()  # 89 ngày vẫn giữ dù vượt ngưỡng dung lượng
    assert report.retention_days == 90 and report.warning is True
    assert report.used_bytes >= 3_000_000
    app_log = "\n".join(p.read_text() for p in (tmp_path / "app").glob("*.jsonl"))
    assert "logs.disk_warning" in app_log
    async with clean_db.begin() as conn:
        assert (await conn.execute(text("SELECT COUNT(*) FROM audit_logs"))).scalar_one() == audit_before


async def test_TC_FR057_11_longer_retention_respected(clean_db: AsyncEngine, tmp_path: Path) -> None:
    f = _file(tmp_path, 100)
    await set_setting(clean_db, "logging.retention_days", "120")
    try:
        report = await run_log_maintenance(async_sessionmaker(clean_db), tmp_path, today=TODAY)
    finally:
        await set_setting(clean_db, "logging.retention_days", "90")
    assert report.deleted == [] and f.exists()


async def test_TC_FR057_12_status_log_storage(clean_db: AsyncEngine, migrated_db: str, tmp_path: Path) -> None:
    (tmp_path / f"app-{datetime.now(UTC).date().isoformat()}.jsonl").write_bytes(b"y" * 2_000_000)
    await set_setting(clean_db, "logging.disk_warn_gb", "0.001")
    try:
        async with api_client(migrated_db, log_dir=str(tmp_path)) as client:
            await setup_owner(client)
            st = (await client.get("/api/v1/system/status")).json()["log_storage"]
    finally:
        await set_setting(clean_db, "logging.disk_warn_gb", "2")
    assert st["retention_days"] == 90 and st["warning"] is True
    assert st["used_gb"] > 0.0018 and st["warn_gb"] == 0.001
