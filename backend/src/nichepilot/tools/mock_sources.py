"""Nguồn giả lập cho development/test (FR-016) – dữ liệu gắn `MOCK`, bị cấm ở production.

KHÔNG phải dữ liệu nghiên cứu thật và không được dùng để báo cáo rằng nguồn thật đã hoạt động. Không truy cập mạng.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

from nichepilot.tools.fetchers.http_fetcher import RawPage
from nichepilot.tools.sources.base import PolicySnapshot, SourceHit, SourceResult


@dataclass(frozen=True)
class MockPage:
    status: int
    html: str | None = None
    published_at: str | None = None
    retry_after: float | None = None


@dataclass
class MockWeb:
    pages: dict[str, MockPage] = field(default_factory=dict)
    robots: dict[str, str] = field(default_factory=dict)
    search: dict[str, list[str]] = field(default_factory=dict)

    @classmethod
    def from_json(cls, path: Path) -> MockWeb:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        base = path.parent
        pages = {
            url: MockPage(
                status=int(p.get("status", 200)),
                html=(base / p["file"]).read_text(encoding="utf-8") if p.get("file") else None,
                published_at=p.get("published_at"),
                retry_after=p.get("retry_after"),
            )
            for url, p in data.get("pages", {}).items()
        }
        robots = {d: (base / f).read_text(encoding="utf-8") for d, f in data.get("robots", {}).items()}
        return cls(pages, robots, dict(data.get("search", {})))

    @classmethod
    def builtin(cls) -> MockWeb:
        """Bộ dữ liệu giả lập tối thiểu đóng gói sẵn (demo dev) – nội dung tự soạn, gắn MOCK."""
        html = (
            "<html><head><title>[MOCK] Small bakery inventory</title></head><body><article><h1>[MOCK]"
            " Inventory pain</h1>"
            "<p>[MOCK] We run out of flour every week and spreadsheets take too long to update after a busy morning."
            " Restaurant inventory apps are too expensive for a two-person bakery.</p></article></body></html>"
        )
        return cls(
            pages={"https://mock.example/bakery": MockPage(200, html, "2026-06-01T00:00:00Z")},
            robots={"mock.example": "User-agent: *\nAllow: /\n"},
            search={"default": ["https://mock.example/bakery"]},
        )


@dataclass
class MockSourceAdapter:
    web: MockWeb
    adapter_type: str = "searxng_engine"
    data_origin: Literal["REAL", "MOCK"] = "MOCK"

    async def query(
        self, policy: PolicySnapshot, query: str, *, market: str, language: str, max_results: int
    ) -> SourceResult:
        urls = self.web.search.get(query) or self.web.search.get("default", [])
        hits = [SourceHit(url=u, title=None, snippet=None) for u in urls][:max_results]
        return SourceResult("OK", hits) if hits else SourceResult("NO_RESULTS")


@dataclass
class MockPageFetcher:
    web: MockWeb
    data_origin: Literal["REAL", "MOCK"] = "MOCK"
    requested: list[str] = field(default_factory=list)

    async def fetch(self, url: str, *, timeout_s: float) -> RawPage:
        self.requested.append(url)
        page = self.web.pages.get(url)
        if page is None:
            return RawPage(404, "text/html", "<html>not found</html>", url)
        return RawPage(page.status, "text/html; charset=utf-8", page.html, url, page.retry_after)

    async def fetch_robots(self, domain: str, *, timeout_s: float) -> RawPage:
        body = self.web.robots.get(domain)
        if body is None:
            return RawPage(404, "text/plain", "", f"https://{domain}/robots.txt")
        return RawPage(200, "text/plain", body, f"https://{domain}/robots.txt")


def mock_published_at(web: MockWeb, url: str) -> str | None:
    page = web.pages.get(url)
    return page.published_at if page else None


def domain_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()
