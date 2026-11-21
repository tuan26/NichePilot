"""T076 – Xóa bằng chứng khi lượt đang chạy (FR-013e): bằng chứng bị xóa giữa `fetch` và `extract` không xuất hiện trong prompt
`extract`/`assess`, không được tính ở bước đánh giá; URL trùng nội dung đã xóa → `ERASED_CONTENT`. Tiếp tục job (resume) sau khi
xóa cũng không dùng lại bằng chứng đã xóa (checkpoint chỉ chứa ID). MOCK – không mạng, không API có phí."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import csrf_headers, run_worker_once
from tests.discovery_helpers import allow_test_source, discovery_client
from tests.discovery_run import COPY, FORUM, REVIEW, bakery_evidence, erase, niche_status, set_search
from tests.fakes.discovery_ai import ScriptedDiscoveryAI

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]
FORUM_TEXT = "We lose about three hours each week"


async def _start(client: Any) -> str:
    r = await client.post("/api/v1/discovery/runs", json={"market": "US"}, headers=csrf_headers(client))
    assert r.status_code == 201, r.text
    return str(r.json()["job"]["job_id"])


async def test_TC_E1_FR013e_05_erasure_between_fetch_and_extract(clean_db: AsyncEngine, migrated_db: str) -> None:
    ai = ScriptedDiscoveryAI()
    async with discovery_client(migrated_db, ai=ai) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW, COPY])
        fetcher = client.mock_fetcher  # type: ignore[attr-defined]
        real_fetch = fetcher.fetch
        erased: dict[str, Any] = {}

        async def fetch_with_erasure(url: str, *, timeout_s: float) -> Any:
            if url == COPY and not erased:  # bản gốc FORUM đã được lưu; chủ sở hữu xóa nguồn ngay lúc này
                ids = await bakery_evidence(clean_db, "forum.example")
                erased["resp"] = await erase(client, ids[0], scope="SOURCE")
            return await real_fetch(url, timeout_s=timeout_s)

        fetcher.fetch = fetch_with_erasure
        job_id = await _start(client)
        await run_worker_once(client)
        assert erased["resp"].status_code == 202, erased["resp"].text
        async with clean_db.connect() as conn:
            status = (
                await conn.execute(text("SELECT status FROM agent_jobs WHERE id = :j"), {"j": job_id})
            ).scalar_one()
            reasons = (await conn.execute(text("SELECT reason FROM page_fetch_log"))).scalars().all()
            counted = (
                (
                    await conn.execute(
                        text(
                            "SELECT s.registered_domain FROM niche_evidence_links l JOIN research_evidence e ON e.id ="
                            " l.evidence_id JOIN research_sources s ON s.id = e.source_id WHERE l.counted_for_threshold"
                        )
                    )
                )
                .scalars()
                .all()
            )
        assert status == "SUCCEEDED"
        assert "ERASED_CONTENT" in reasons  # bản sao khác tên miền của nội dung đã xóa không được thu thập
        for task in ("discovery.extract", "discovery.assess"):
            reqs = ai.requests_for(task)
            assert reqs, task
            assert all(FORUM_TEXT not in str(m.content) for r in reqs for m in r.messages), task
        assert set(counted) == {"reviews.example"}
        assert await niche_status(clean_db) == "INSUFFICIENT_EVIDENCE"


async def test_TC_E1_FR013e_09_resume_after_erasure_does_not_reuse_erased_evidence(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    ai = ScriptedDiscoveryAI()
    async with discovery_client(migrated_db, ai=ai) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        fetcher = client.mock_fetcher  # type: ignore[attr-defined]
        real_fetch = fetcher.fetch
        job: dict[str, str] = {}

        async def fetch_then_pause(url: str, *, timeout_s: float) -> Any:
            if url == REVIEW:  # yêu cầu tạm dừng (như POST /jobs/{id}/pause) – runtime dừng sau bước hiện tại
                async with clean_db.begin() as conn:
                    await conn.execute(
                        text("UPDATE agent_jobs SET pause_requested = true WHERE id = :j"), {"j": uuid.UUID(job["id"])}
                    )
            return await real_fetch(url, timeout_s=timeout_s)

        fetcher.fetch = fetch_then_pause
        job["id"] = await _start(client)
        await run_worker_once(client)
        async with clean_db.connect() as conn:
            st = (
                await conn.execute(text("SELECT status, checkpoint FROM agent_jobs WHERE id = :j"), {"j": job["id"]})
            ).one()
        assert st.status == "PAUSED" and not ai.requests_for("discovery.extract")
        assert FORUM_TEXT not in str(st.checkpoint)
        ids = await bakery_evidence(clean_db, "forum.example")
        assert (await erase(client, ids[0], scope="SOURCE")).status_code == 202
        fetcher.fetch = real_fetch
        r = await client.post(f"/api/v1/jobs/{job['id']}/resume", headers=csrf_headers(client))
        assert r.status_code == 202, r.text
        await run_worker_once(client)
        async with clean_db.connect() as conn:
            final = (
                await conn.execute(text("SELECT status FROM agent_jobs WHERE id = :j"), {"j": job["id"]})
            ).scalar_one()
        assert final == "SUCCEEDED"
        prompts = ai.prompt_text()
        assert ai.requests_for("discovery.extract") and FORUM_TEXT not in prompts
        assert await niche_status(clean_db) == "INSUFFICIENT_EVIDENCE"
