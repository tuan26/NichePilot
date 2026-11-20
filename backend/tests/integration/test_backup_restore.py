"""T118 – Backup/restore (FR-073, SC-012): chạy script thật trong image postgres:17-alpine (giống service `backup`),
khôi phục vào DB trống và so khớp số bản ghi mọi bảng; xoay vòng giữ BACKUP_RETENTION bản; file backup chỉ chủ sở hữu đọc.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlparse

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from tests.api_helpers import api_client, csrf_headers, run_worker_once, setup_owner

pytestmark = [pytest.mark.integration, pytest.mark.mock]
SCRIPTS = Path(__file__).resolve().parents[3] / "deploy" / "scripts"
IMAGE = "postgres:17-alpine"


def _docker_ok() -> bool:
    if shutil.which("docker") is None:
        return False
    return subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True).returncode == 0  # noqa: S603, S607


def _run(
    script: str, db_url: str, backups: Path, *args: str, ledger: Path | None = None, **env: str
) -> subprocess.CompletedProcess[str]:
    u = urlparse(db_url.replace("postgresql+psycopg://", "postgresql://"))
    envs = {
        "PGHOST": u.hostname or "localhost",
        "PGPORT": str(u.port or 5432),
        "POSTGRES_USER": u.username or "",
        "POSTGRES_PASSWORD": u.password or "",
        "POSTGRES_DB": u.path.lstrip("/"),
        "BACKUP_DIR": "/backups",
        **env,
    }
    cmd = ["docker", "run", "--rm", "--network", "host", "-v", f"{SCRIPTS}:/scripts:ro", "-v", f"{backups}:/backups"]
    if ledger is not None:  # E1 (X4): volume erasure-ledger gắn chỉ đọc như service `backup`
        cmd += ["-v", f"{ledger}:/ledger:ro"]
    for k, v in envs.items():
        cmd += ["-e", f"{k}={v}"]
    cmd += [IMAGE, f"/scripts/{script}", *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=180)  # noqa: S603


async def _counts(url: str) -> dict[str, int]:
    eng = create_async_engine(url)
    try:
        async with eng.connect() as conn:
            tables = [
                r[0]
                for r in (
                    await conn.execute(
                        text("SELECT quote_ident(tablename) FROM pg_tables WHERE schemaname = 'public' ORDER BY 1")
                    )
                ).all()
            ]
            return {t: int((await conn.execute(text(f"SELECT COUNT(*) FROM {t}"))).scalar_one()) for t in tables}  # noqa: S608
    finally:
        await eng.dispose()


@pytest.mark.skipif(not _docker_ok(), reason="BLOCKED: cần Docker và image postgres:17-alpine")
async def test_TC_SC012_01_backup_restore_roundtrip(clean_db: AsyncEngine, migrated_db: str, tmp_path: Path) -> None:
    async with api_client(migrated_db) as client:  # dữ liệu thật trong DB: owner, job mock, audit, usage, reservation
        await setup_owner(client)
        await client.post("/api/v1/jobs", json={"job_type": "system.diagnostic"}, headers=csrf_headers(client))
        await run_worker_once(client)
    backups = tmp_path / "backups"
    backups.mkdir()
    for _ in range(3):
        r = _run("backup.sh", migrated_db, backups, BACKUP_RETENTION="2")
        assert r.returncode == 0, r.stderr
    dumps = sorted(backups.glob("nichepilot-*.dump"))
    assert len(dumps) == 2, dumps  # xoay vòng
    assert not list(backups.glob("*.partial"))
    assert stat.S_IMODE(os.stat(dumps[-1]).st_mode) == 0o600  # bảo vệ dữ liệu nhạy cảm trong backup

    target = f"restore_{uuid.uuid4().hex[:8]}"
    async with clean_db.connect() as conn:
        await conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(text(f'CREATE DATABASE "{target}"'))
    target_url = migrated_db.rsplit("/", 1)[0] + f"/{target}"
    try:
        r = _run("restore.sh", target_url, backups, f"/backups/{dumps[-1].name}")
        assert r.returncode == 0, r.stderr
        source, restored = await _counts(migrated_db), await _counts(target_url)
        assert source == restored
        assert restored["agent_jobs"] >= 1 and restored["audit_logs"] >= 1 and restored["alembic_version"] == 1
        # restore lần hai vào DB đã có dữ liệu bị từ chối (không ghi đè ngoài ý muốn)
        again = _run("restore.sh", target_url, backups, f"/backups/{dumps[-1].name}")
        assert again.returncode != 0 and "not empty" in (again.stderr + again.stdout)
    finally:
        async with clean_db.connect() as conn:
            await conn.execution_options(isolation_level="AUTOCOMMIT")
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{target}" WITH (FORCE)'))


@pytest.mark.skipif(not _docker_ok(), reason="BLOCKED: cần Docker và image postgres:17-alpine")
async def test_TC_E1_FR013f_11_restore_blocks_e1_data_until_ledger_reapplied(
    clean_db: AsyncEngine, migrated_db: str, tmp_path: Path
) -> None:
    """E1 (T040, X4): backup sao kèm erasure ledger; restore đặt BLOCKED; áp dụng ledger --strict → OK."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from nichepilot.modules.discovery.erasure import Ledger, apply_erasure_ledger, ledger_health

    ledger_dir = tmp_path / "ledger"
    await apply_erasure_ledger(async_sessionmaker(clean_db), Ledger(ledger_dir))  # khởi tạo sổ trên DB nguồn
    os.chmod(ledger_dir, 0o755)  # noqa: S103 – thư mục tạm của test, container postgres cần đọc
    os.chmod(ledger_dir / "ledger.jsonl", 0o644)
    backups = tmp_path / "backups"
    backups.mkdir()
    r = _run("backup.sh", migrated_db, backups, ledger=ledger_dir)
    assert r.returncode == 0, r.stderr
    copies = list(backups.glob("nichepilot-*.ledger.jsonl"))
    assert len(copies) == 1 and stat.S_IMODE(os.stat(copies[0]).st_mode) == 0o600
    dump = sorted(backups.glob("nichepilot-*.dump"))[-1]
    target = f"restore_e1_{uuid.uuid4().hex[:8]}"
    async with clean_db.connect() as conn:
        await conn.execution_options(isolation_level="AUTOCOMMIT")
        await conn.execute(text(f'CREATE DATABASE "{target}"'))
    target_url = migrated_db.rsplit("/", 1)[0] + f"/{target}"
    eng = create_async_engine(target_url)
    try:
        r = _run("restore.sh", target_url, backups, f"/backups/{dump.name}")
        assert r.returncode == 0, r.stderr
        sm = async_sessionmaker(eng)
        health = await ledger_health(sm, Ledger(ledger_dir))
        assert health.status == "BLOCKED" and health.error == "RESTORED_PENDING_LEDGER_APPLY"
        await apply_erasure_ledger(sm, Ledger(ledger_dir))
        assert (await ledger_health(sm, Ledger(ledger_dir))).status == "OK"
    finally:
        await eng.dispose()
        async with clean_db.connect() as conn:
            await conn.execution_options(isolation_level="AUTOCOMMIT")
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{target}" WITH (FORCE)'))
