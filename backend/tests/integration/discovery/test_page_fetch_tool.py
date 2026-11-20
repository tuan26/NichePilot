"""T025 – Tool `page.fetch` (FR-005, FR-012b, FR-031): output VÀ bản ghi tool_executions chỉ chứa văn bản đã che PII.

Dùng ToolRegistry của E0 (bản ghi được ghi qua `record`) với trang fixture tự soạn – không truy cập mạng.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

import pytest

from nichepilot.core.discovery_config import DiscoverySettings
from nichepilot.tools.builtin.page_fetch import build_page_fetch_tool
from nichepilot.tools.builtin.robots_fetch import build_robots_fetch_tool
from nichepilot.tools.mock_sources import MockPageFetcher, MockWeb
from nichepilot.tools.registry import ToolContext, ToolRegistry

pytestmark = pytest.mark.discovery
FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "discovery"
PII_STRINGS = ["owner.fake@example.com", "202-555-0143", "groomfixer99", "Taylor Brennan", "Jordan Ellis", "Morgan"]


def _registry() -> tuple[ToolRegistry, list[dict[str, Any]]]:
    web = MockWeb.from_json(FIXTURES / "mock_web.json")
    fetcher = MockPageFetcher(web)
    reg = ToolRegistry()
    reg.register(build_page_fetch_tool(DiscoverySettings(), fetcher=fetcher))
    reg.register(build_robots_fetch_tool(DiscoverySettings(), fetcher=fetcher))
    return reg, []


async def _exec(reg: ToolRegistry, rows: list[dict[str, Any]], name: str, inp: dict[str, Any]) -> dict[str, Any]:
    async def record(row: dict[str, Any]) -> None:
        rows.append(row)

    ctx = ToolContext(uuid.uuid4(), None, frozenset({"page.fetch", "robots.fetch"}), "MOCK", record)
    return await reg.execute(name, inp, ctx)


async def test_TC_E1_FR012b_02_tool_output_and_record_contain_only_redacted_text() -> None:
    reg, rows = _registry()
    out = await _exec(
        reg, rows, "page.fetch", {"url": "https://forum.example/t/grooming-chaos", "language": "en", "country": "US"}
    )
    assert out["status"] == "SUCCESS"
    dumped = json.dumps(out) + json.dumps(rows, default=str)
    for secret in PII_STRINGS:
        assert secret not in dumped, secret  # không có trong output lẫn bản ghi tool_executions
    assert out["needs_review_segments"] >= 1  # "Thanks, Morgan" – không lưu, không gửi AI
    assert all(seg["redaction_status"] == "REDACTED" for seg in out["segments"])
    assert out["redaction_counts"].get("EMAIL") == 1


async def test_TC_E1_FR005_01_clean_page_extracted_without_author_metadata() -> None:
    reg, rows = _registry()
    out = await _exec(
        reg, rows, "page.fetch", {"url": "https://forum.example/t/bakery-inventory", "language": "en", "country": "US"}
    )
    assert out["status"] == "SUCCESS" and out["needs_review_segments"] == 0
    text = " ".join(s["text"] for s in out["segments"])
    assert "run out of flour" in text and "Jordan Ellis" not in json.dumps(out)  # meta author bị bỏ
    assert "Home | Forums" not in text  # chỉ nội dung chính
    assert len(out["content_hash"]) == 64 and out["pii_engine"] == "regex-phone/1"


@pytest.mark.parametrize(
    ("url", "status", "reason"),
    [
        ("https://blocked.example/page", "SKIPPED", "ACCESS_RESTRICTED"),  # CAPTCHA – không thử vượt
        ("https://members.example/thread", "SKIPPED", "ACCESS_RESTRICTED"),  # yêu cầu đăng nhập
        ("https://broken.example/page", "FAILED", "HTTP_ERROR"),
        ("https://slow.example/page", "SKIPPED", "RATE_LIMITED"),
        ("https://unknown.example/x", "FAILED", "HTTP_ERROR"),
    ],
)
async def test_TC_E1_FR031_01_unusable_pages_skipped_with_reason(url: str, status: str, reason: str) -> None:
    reg, rows = _registry()
    out = await _exec(reg, rows, "page.fetch", {"url": url, "language": "en", "country": "US"})
    assert (out["status"], out["reason"]) == (status, reason)
    assert out["segments"] == []


async def test_TC_E1_FR030a_05_robots_fetch_statuses() -> None:
    reg, rows = _registry()
    ok = await _exec(reg, rows, "robots.fetch", {"domain": "forum.example"})
    assert ok["status"] == "OK" and "Crawl-delay" in ok["content"]
    missing = await _exec(reg, rows, "robots.fetch", {"domain": "nothing.example"})
    assert missing["status"] == "NOT_FOUND" and missing["content"] == ""
