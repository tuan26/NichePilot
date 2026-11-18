"""T021 – Giữ chỗ ngân sách nguyên tử khi nhiều tiến trình worker tranh chấp (FR-043, SC-004, QA-11)."""

from __future__ import annotations

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.integration.budget_helpers import insert_job, restore_budget_defaults, set_setting

pytestmark = pytest.mark.integration

BACKEND_DIR = Path(__file__).resolve().parents[2]


async def _run_contenders(db_url: str, job_id: str, amount: str, processes: int = 2, n: int = 10) -> list[str]:
    procs = [
        await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "tests.integration._budget_contender",
            db_url,
            job_id,
            amount,
            str(n),
            cwd=BACKEND_DIR,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        for _ in range(processes)
    ]
    outputs = []
    for p in procs:
        out, err = await p.communicate()
        assert p.returncode == 0, err.decode()
        # Dòng cuối là kết quả; các dòng trước là log của tiến trình con.
        outputs.extend(out.decode().strip().splitlines()[-1].split(","))
    return outputs


async def _held(engine: AsyncEngine) -> Decimal:
    async with engine.connect() as conn:
        return Decimal(
            (
                await conn.execute(
                    text("SELECT COALESCE(SUM(amount_usd),0) FROM budget_reservations WHERE status='ACTIVE'")
                )
            ).scalar_one()
        )


@pytest.mark.parametrize(
    ("setting", "value", "job_limit", "scope"),
    [
        ("budget.daily_usd", '"1.00"', "2.00", "DAILY"),
        ("budget.monthly_usd", '"1.00"', "2.00", "MONTHLY"),
        (None, None, "1.00", "JOB"),
    ],
)
async def test_TC_SC004_01_two_processes_never_exceed_limits(
    clean_db: AsyncEngine, migrated_db: str, setting: str | None, value: str | None, job_limit: str, scope: str
) -> None:
    try:
        if setting:
            await set_setting(clean_db, setting, value or "")
        job_id = await insert_job(clean_db, budget_limit=job_limit)
        results = await _run_contenders(migrated_db, str(job_id), "0.25")
        # 20 yêu cầu × $0.25 tranh chấp giới hạn $1.00 → đúng 4 thành công, 16 bị chặn ở đúng phạm vi
        assert results.count("OK") == 4, results
        assert results.count(scope) == 16, results
        assert await _held(clean_db) == Decimal("1.00")
    finally:
        await restore_budget_defaults(clean_db)
