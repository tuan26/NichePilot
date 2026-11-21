"""T103 – Độ bền lượt (FR-027, FR-029, SC-007): worker chết giữa `fetch` → phục hồi job treo (E0) → tiếp tục từ checkpoint, 0 trùng
ngách/pain point/nguồn/bằng chứng/page_fetch_log; hủy qua API job E0 → CANCELLED, lượt có stop_reason CANCELLED. MOCK."""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from nichepilot.jobs.maintenance import recover_stalled_jobs
from tests.api_helpers import csrf_headers, run_worker_once
from tests.discovery_helpers import allow_test_source, discovery_client
from tests.discovery_run import COPY, FORUM, REVIEW, set_search

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]

DUP_CHECKS = {
    "niches": "SELECT count(*) FROM (SELECT dedup_key FROM niches GROUP BY project_id, data_origin, dedup_key HAVING count(*) > 1) d",
    "pain_points": "SELECT count(*) FROM (SELECT 1 FROM pain_points GROUP BY niche_id, normalized_title HAVING count(*) > 1) d",
    "research_sources": "SELECT count(*) FROM (SELECT 1 FROM research_sources GROUP BY canonical_url, content_hash HAVING count(*) > 1) d",
    "research_evidence": (
        "SELECT count(*) FROM (SELECT 1 FROM research_evidence GROUP BY source_id, subject_id, content_hash"
        " HAVING count(*) > 1) d"
    ),
    "page_fetch_log": "SELECT count(*) FROM (SELECT 1 FROM page_fetch_log GROUP BY run_id, url_hash HAVING count(*) > 1) d",
}


async def _start(client: Any) -> uuid.UUID:
    r = await client.post("/api/v1/discovery/runs", json={"market": "US"}, headers=csrf_headers(client))
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["job"]["job_id"])


async def _duplicates(engine: AsyncEngine) -> dict[str, int]:
    async with engine.connect() as conn:
        return {k: int((await conn.execute(text(sql))).scalar_one()) for k, sql in DUP_CHECKS.items()}


async def test_TC_E1_FR027_01_TC_E1_SC007_01_worker_crash_mid_fetch_resumes_without_duplicates(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW, COPY])
        runtime = client.services.runtime  # type: ignore[attr-defined]
        fetcher = client.mock_fetcher  # type: ignore[attr-defined]
        real_fetch = fetcher.fetch
        entered, never = asyncio.Event(), asyncio.Event()

        async def hang_on_review(url: str, *, timeout_s: float) -> Any:
            if url == REVIEW:
                entered.set()
                await never.wait()  # worker "chết" khi đang thu thập trang thứ 2
            return await real_fetch(url, timeout_s=timeout_s)

        fetcher.fetch = hang_on_review
        job = await _start(client)
        task = asyncio.create_task(runtime.run(job))
        await asyncio.wait_for(entered.wait(), 30)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        async with clean_db.begin() as conn:
            await conn.execute(
                text("UPDATE agent_jobs SET heartbeat_at = now() - interval '10 minutes' WHERE id = :j"), {"j": job}
            )
        fetcher.fetch = real_fetch
        sm = async_sessionmaker(clean_db, expire_on_commit=False)
        requeued: list[uuid.UUID] = []

        async def requeue(job_id: uuid.UUID) -> None:
            requeued.append(job_id)

        assert (await recover_stalled_jobs(sm, requeue, stalled_after_s=60))["requeued"] == 1
        assert await runtime.run(job) == "SUCCEEDED"
        async with clean_db.connect() as conn:
            seqs = (
                (await conn.execute(text("SELECT seq FROM job_steps WHERE job_id = :j ORDER BY seq"), {"j": job}))
                .scalars()
                .all()
            )
            fetched = (await conn.execute(text("SELECT count(*) FROM page_fetch_log"))).scalar_one()
        assert len(seqs) == len(set(seqs))  # không lặp bước đã hoàn tất
        assert fetched == 3
        assert await _duplicates(clean_db) == dict.fromkeys(DUP_CHECKS, 0)


async def test_TC_E1_FR029_02_rerun_same_inputs_creates_no_duplicates(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        for _ in range(2):
            await _start(client)
            await run_worker_once(client)
        async with clean_db.connect() as conn:
            niches = (await conn.execute(text("SELECT count(*) FROM niches"))).scalar_one()
            links = (await conn.execute(text("SELECT count(*) FROM niche_run_links"))).scalar_one()
        assert niches == 3 and links == 6  # ngách dùng lại, chỉ thêm liên kết lượt
        assert await _duplicates(clean_db) == dict.fromkeys(DUP_CHECKS, 0)


async def test_TC_E1_FR027_03_cancel_via_e0_job_api(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        fetcher = client.mock_fetcher  # type: ignore[attr-defined]
        real_fetch = fetcher.fetch
        job: dict[str, uuid.UUID] = {}

        async def cancel_during_fetch(url: str, *, timeout_s: float) -> Any:
            r = await client.post(f"/api/v1/jobs/{job['id']}/cancel", headers=csrf_headers(client))
            assert r.status_code == 202, r.text
            return await real_fetch(url, timeout_s=timeout_s)

        fetcher.fetch = cancel_during_fetch
        job["id"] = await _start(client)
        await run_worker_once(client)
        async with clean_db.connect() as conn:
            st = (
                await conn.execute(text("SELECT status FROM agent_jobs WHERE id = :j"), {"j": job["id"]})
            ).scalar_one()
            run_id = (
                await conn.execute(text("SELECT id FROM discovery_runs WHERE job_id = :j"), {"j": job["id"]})
            ).scalar_one()
        assert st == "CANCELLED"
        run = (await client.get(f"/api/v1/discovery/runs/{run_id}")).json()
        assert run["outcome"] == "PARTIAL_COMPLETED" and run["stop_reason"] == "CANCELLED"
