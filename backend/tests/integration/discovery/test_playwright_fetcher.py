"""T128 – Profile tùy chọn browser-fetcher (marker `browser`, chạy khi NICHEPILOT_RUN_BROWSER=1; FR-005, FR-006f, FR-031).

Trang fixture cần JavaScript, phục vụ qua HTTP trên 127.0.0.1 (không ra Internet). Kiểm tra: nội dung sau render được lấy; User-Agent là
UA nhận diện được (không giả trình duyệt); kết quả đi qua tool `page.fetch` nên PII vẫn được che; đo RSS của tiến trình Chromium."""

from __future__ import annotations

import asyncio
import http.server
import os
import threading
import uuid
from pathlib import Path
from typing import Any, ClassVar

import pytest

from nichepilot.core.discovery_config import DiscoverySettings
from nichepilot.tools.builtin.page_fetch import build_page_fetch_tool
from nichepilot.tools.registry import ToolContext, ToolRegistry

pytestmark = [pytest.mark.browser, pytest.mark.discovery]
FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "discovery"
UA = "NichePilotResearchBot/0.1 (+self-hosted research; contact: site owner)"


class _Handler(http.server.SimpleHTTPRequestHandler):
    seen_ua: ClassVar[list[str]] = []

    def __init__(self, *a: Any, **k: Any) -> None:
        super().__init__(*a, directory=str(FIXTURES), **k)

    def do_GET(self) -> None:
        _Handler.seen_ua.append(self.headers.get("User-Agent", ""))
        super().do_GET()

    def log_message(self, *_a: Any) -> None:
        return None


def _chromium_rss_mb() -> float:
    total = 0
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            cmd = Path(f"/proc/{pid}/cmdline").read_bytes()
            if b"chrom" in cmd and b"headless" in cmd:
                for line in Path(f"/proc/{pid}/status").read_text().splitlines():
                    if line.startswith("VmRSS:"):
                        total += int(line.split()[1])
        except OSError:
            continue
    return total / 1024


async def test_TC_E1_FR031_03_js_page_rendered_without_stealth_and_redacted() -> None:
    from nichepilot.tools.fetchers.playwright_fetcher import PlaywrightPageFetcher

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/js_rendered.html"
    try:
        fetcher = PlaywrightPageFetcher(
            user_agent=UA, max_bytes=3 * 1024 * 1024, executable_path=os.environ.get("BROWSER_EXECUTABLE_PATH")
        )
        raw = await fetcher.fetch(url, timeout_s=20)
        assert raw.http_status == 200 and raw.body and "Seed library inventory" in raw.body
        assert _Handler.seen_ua and all(u == UA for u in _Handler.seen_ua)  # UA nhận diện được, không giả trình duyệt
        reg = ToolRegistry()
        reg.register(build_page_fetch_tool(DiscoverySettings(), fetcher=fetcher))  # type: ignore[arg-type]

        async def record(_row: dict[str, Any]) -> None:
            return None

        ctx = ToolContext(uuid.uuid4(), None, frozenset({"page.fetch"}), "REAL", record)
        rss: list[float] = []

        async def sample() -> None:
            for _ in range(40):
                rss.append(_chromium_rss_mb())
                await asyncio.sleep(0.1)

        sampler = asyncio.create_task(sample())
        out = await reg.execute("page.fetch", {"url": url, "language": "en", "country": "US"}, ctx)
        await sampler
        assert out["status"] == "SUCCESS"
        text_out = " ".join(s["text"] for s in out["segments"])
        assert "paper ledger gets wet" in text_out and "fake.organiser@example.com" not in text_out
        print(f"browser-fetcher: peak Chromium RSS ≈ {max(rss):.0f} MB")
    finally:
        server.shutdown()
