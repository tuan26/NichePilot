"""T105 – Metrics lượt (FR-032): trang theo kết quả/lý do, needs_review_segments, nguồn độc lập, ứng viên, đủ/thiếu bằng chứng, lời gọi
AI, chi phí REAL/MOCK, thời gian thực thi, outcome + stop_reason. MOCK."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.discovery_helpers import allow_test_source, discovery_client
from tests.discovery_run import FORUM, PII_PAGE, REVIEW, run_discovery, set_search

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]
REQUIRED = {
    "pages_attempted",
    "pages_succeeded",
    "pages_failed",
    "pages_skipped",
    "skipped_by_reason",
    "needs_review_segments",
    "elapsed_active_s",
    "independent_sources",
    "candidates",
    "evidence_items",
    "evidence_sufficient",
    "insufficient_evidence",
    "insufficient_scoring_data",
    "ai_calls",
    "cost_real_usd",
    "cost_mock_usd",
    "source_status",
}


async def test_TC_E1_FR032_01_metrics_complete_and_consistent(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW, PII_PAGE, "https://broken.example/page"])
        run = await run_discovery(client)
        m = run["metrics"]
        assert REQUIRED <= set(m)
        assert m["pages_attempted"] == m["pages_succeeded"] + m["pages_failed"] + m["pages_skipped"] == 4
        assert sum(m["skipped_by_reason"].values()) == m["pages_failed"] + m["pages_skipped"]
        assert m["needs_review_segments"] >= 1  # "Thanks, Morgan"
        assert m["candidates"] == 3 and m["evidence_sufficient"] + m["insufficient_evidence"] == 3
        assert m["independent_sources"] == 2  # forum.example (2 trang cùng eTLD+1) và reviews.example
        assert m["ai_calls"] >= 3 and float(m["elapsed_active_s"]) > 0
        assert run["outcome"] in ("COMPLETED", "PARTIAL_COMPLETED") and run["stop_reason"]
