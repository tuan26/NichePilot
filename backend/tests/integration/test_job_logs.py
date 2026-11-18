"""T116 – Log theo job (FR-050): lọc file log theo job_id cho đủ sự kiện theo thứ tự, có mã tương quan, không secret."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from nichepilot.core.logging import configure_logging
from tests.api_helpers import api_client, csrf_headers, run_worker_once, setup_owner

pytestmark = [pytest.mark.integration, pytest.mark.mock]
KEY = "sk-ant-joblogs-1234567890abcdef"


def _read(log_dir: Path) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for p in sorted(log_dir.glob("app-*.jsonl")):
        lines += [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    return lines


async def test_TC_FR050_01_job_log_events_in_order(clean_db: AsyncEngine, migrated_db: str, tmp_path: Path) -> None:
    async with api_client(migrated_db, anthropic_api_key=KEY, log_dir=str(tmp_path)) as client:
        configure_logging(level="INFO", fmt="json", log_dir=tmp_path, secret_values=[KEY])
        await setup_owner(client)
        r = await client.post("/api/v1/jobs", json={"job_type": "system.diagnostic"}, headers=csrf_headers(client))
        job_id = r.json()["id"]
        await run_worker_once(client)
        assert (await client.get(f"/api/v1/jobs/{job_id}")).json()["status"] == "SUCCEEDED"
    events = [e for e in _read(tmp_path) if e.get("job_id") == job_id]
    names = [e["event"] for e in events]
    assert names[0] == "job.created" and names[-1] == "job.finished", names
    assert "job.started" in names
    assert names.count("step.finished") == 3
    seqs = [e["seq"] for e in events if e["event"] == "step.finished"]
    assert seqs == [1, 2, 3]
    assert all(e.get("step_id") for e in events if e["event"].startswith("step."))
    ai = [e for e in events if e["event"] == "ai.call"]
    assert ai and all(e["data_origin"] == "MOCK" and e["provider"] == "mock" and e["step_id"] for e in ai)
    assert any(e["event"] == "tool.executed" and e["tool_name"] == "system.runtime_info" for e in events)
    assert events[0].get("request_id")  # job.created gắn mã tương quan request
    blob = "\n".join(json.dumps(e) for e in _read(tmp_path))
    assert KEY not in blob and "joblogs" not in blob
