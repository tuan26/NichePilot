"""T115 – `GET /api/v1/discovery/runs/{run_id}/report` (FR-024, SC-009): JSON và Markdown, ba danh sách tách biệt, `disclaimer_key`,
MOCK bị loại khỏi báo cáo mặc định; nhãn song ngữ. MOCK."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.discovery_helpers import allow_test_source, discovery_client
from tests.discovery_run import FORUM, REVIEW, run_discovery, set_search

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]


async def test_TC_E1_FR024_01_TC_E1_SC009_02_report_json_markdown_three_lists(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        run = await run_discovery(client)
        default = (await client.get(f"/api/v1/discovery/runs/{run['id']}/report")).json()
        assert {
            "run",
            "research_ranking",
            "affiliate_priority",
            "needs_research",
            "disclaimer_key",
            "generated_at",
        } <= set(default)
        assert default["disclaimer_key"] == "discovery.opportunity.disclaimer"
        assert (
            default["research_ranking"] == default["affiliate_priority"] == default["needs_research"] == []
        )  # MOCK ẩn
        mock = (await client.get(f"/api/v1/discovery/runs/{run['id']}/report?include_mock=true")).json()
        assert [n["opportunity_score"] for n in mock["research_ranking"]] == [60.71]
        assert mock["affiliate_priority"] == []  # MONETIZATION_UNVERIFIED không vào danh sách affiliate
        assert len(mock["needs_research"]) == 2 and all(n["data_origin"] == "MOCK" for n in mock["needs_research"])
        md = await client.get(f"/api/v1/discovery/runs/{run['id']}/report?format=markdown&include_mock=true")
        assert md.status_code == 200 and md.headers["content-type"].startswith("text/markdown")
        text = md.text
        assert "# Báo cáo xếp hạng ngách" in text and "## Bảng xếp hạng cơ hội nghiên cứu" in text
        assert "## Danh sách ưu tiên affiliate" in text and "## Cần nghiên cứu thêm" in text
        assert "không phải dự báo doanh thu" in text and "MOCK" in text and "60.71" in text
        en = (await client.get(f"/api/v1/discovery/runs/{run['id']}/report?format=markdown&lang=en")).text
        assert "# Niche ranking report" in en and "not a revenue forecast" in en and "(no niches)" in en
        missing = await client.get("/api/v1/discovery/runs/00000000-0000-0000-0000-000000000000/report")
        assert missing.status_code == 404
