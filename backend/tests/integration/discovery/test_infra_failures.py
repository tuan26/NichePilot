"""T104 – Lỗi hạ tầng khi đang chạy (FR-027, FR-006a, SC-008): mất kết nối DB giữa bước → job treo được phục hồi, tiếp tục từ
checkpoint, 0 trùng; mất Internet → trang NETWORK_ERROR / mọi nguồn lỗi → PARTIAL_COMPLETED/SOURCES_UNAVAILABLE, không dữ liệu thay
thế; nhà cung cấp AI không kết nối được → theo E0 (thử lại có giới hạn), không bịa kết quả. MOCK."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from nichepilot.ai.providers.base import LLMRequest, LLMResponse, ProviderNetworkError
from nichepilot.jobs.maintenance import recover_stalled_jobs
from nichepilot.tools.fetchers.http_fetcher import RawPage
from nichepilot.tools.sources.base import SourceResult
from tests.api_helpers import csrf_headers, run_worker_once
from tests.discovery_helpers import allow_test_source, discovery_client
from tests.discovery_run import FORUM, REVIEW, run_discovery, set_search
from tests.fakes.discovery_ai import ScriptedDiscoveryAI

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]


async def test_TC_E1_FR027_02_db_connection_lost_mid_step_resumes(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        fetcher = client.mock_fetcher  # type: ignore[attr-defined]
        real_fetch = fetcher.fetch
        state = {"failed": False}

        async def db_drop(url: str, *, timeout_s: float) -> Any:
            if url == REVIEW and not state["failed"]:
                state["failed"] = True
                raise OperationalError("SELECT 1", {}, Exception("server closed the connection unexpectedly"))
            return await real_fetch(url, timeout_s=timeout_s)

        fetcher.fetch = db_drop
        r = await client.post("/api/v1/discovery/runs", json={"market": "US"}, headers=csrf_headers(client))
        job = uuid.UUID(r.json()["job"]["job_id"])
        runtime = client.services.runtime  # type: ignore[attr-defined]
        with pytest.raises(OperationalError):  # tiến trình worker thoát vì mất DB (E0: khởi động lại)
            await runtime.run(job)
        async with clean_db.begin() as conn:
            await conn.execute(
                text("UPDATE agent_jobs SET heartbeat_at = now() - interval '10 minutes' WHERE id = :j"), {"j": job}
            )

        async def requeue(_j: uuid.UUID) -> None:
            return None

        assert (await recover_stalled_jobs(async_sessionmaker(clean_db), requeue, stalled_after_s=60))["requeued"] == 1
        assert await runtime.run(job) == "SUCCEEDED"
        async with clean_db.connect() as conn:
            dup = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM (SELECT 1 FROM page_fetch_log GROUP BY run_id, url_hash HAVING count(*) > 1) d"
                    )
                )
            ).scalar_one()
            niches = (await conn.execute(text("SELECT count(*) FROM niches"))).scalar_one()
        assert dup == 0 and niches == 3


async def test_TC_E1_FR006a_02_internet_down_sources_unavailable_no_substitute_data(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        backends = client.services.discovery.backends  # type: ignore[attr-defined]
        for adapter in backends.adapters.values():

            async def down(*_a: Any, **_k: Any) -> SourceResult:
                return SourceResult("UNAVAILABLE", reason="NETWORK_ERROR")

            adapter.query = down
        run = await run_discovery(client)
        assert run["outcome"] == "PARTIAL_COMPLETED" and run["stop_reason"] == "SOURCES_UNAVAILABLE"
        assert run["metrics"]["source_status"] == {"UNAVAILABLE": 3}
        async with clean_db.connect() as conn:
            assert (await conn.execute(text("SELECT count(*) FROM research_evidence"))).scalar_one() == 0


async def test_TC_E1_FR006a_03_page_network_errors_recorded(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        fetcher = client.mock_fetcher  # type: ignore[attr-defined]

        async def offline(url: str, *, timeout_s: float) -> RawPage:
            return RawPage(None, None, None, None, error="NETWORK_ERROR")

        fetcher.fetch = offline
        run = await run_discovery(client)
        assert run["metrics"]["skipped_by_reason"].get("NETWORK_ERROR") == 2 and run["metrics"]["pages_failed"] == 2
        assert run["outcome"] == "COMPLETED" and run["metrics"]["evidence_items"] == 0


async def test_TC_E1_SC008_02_ai_provider_unreachable_follows_e0(clean_db: AsyncEngine, migrated_db: str) -> None:
    class Unreachable(ScriptedDiscoveryAI):
        async def generate(self, req: LLMRequest) -> LLMResponse:
            self.requests.append(req)
            raise ProviderNetworkError("connection refused", sent=False)

    ai = Unreachable()
    async with discovery_client(migrated_db, ai=ai) as client:
        await allow_test_source(clean_db)
        r = await client.post("/api/v1/discovery/runs", json={"market": "US"}, headers=csrf_headers(client))
        await run_worker_once(client)
        async with clean_db.connect() as conn:
            job = (
                await conn.execute(
                    text("SELECT status, status_reason_code FROM agent_jobs WHERE id = :j"),
                    {"j": r.json()["job"]["job_id"]},
                )
            ).one()
            niches = (await conn.execute(text("SELECT count(*) FROM niches"))).scalar_one()
        assert job.status in ("RETRY_SCHEDULED", "FAILED") and job.status_reason_code == "PROVIDER_NETWORK_ERROR"
        assert niches == 0  # không tạo ứng viên thay thế khi AI không trả lời
