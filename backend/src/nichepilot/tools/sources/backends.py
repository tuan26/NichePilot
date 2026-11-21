"""Lắp ráp backend nguồn theo cấu hình (thật hoặc giả lập) – fail-closed ở production (FR-016)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from nichepilot.core.discovery_config import DiscoverySettings, validate_discovery_settings
from nichepilot.tools.fetchers.http_fetcher import HttpPageFetcher, PageFetcher
from nichepilot.tools.mock_sources import MockPageFetcher, MockSourceAdapter, MockWeb
from nichepilot.tools.sources.base import ADAPTER_CONFIG_MODELS, SourceAdapter
from nichepilot.tools.sources.dataset import DatasetAdapter
from nichepilot.tools.sources.http_json_api import HttpJsonApiAdapter
from nichepilot.tools.sources.searxng_engine import SearxngEngineAdapter


@dataclass
class SourceBackends:
    data_origin: Literal["REAL", "MOCK"]
    adapters: dict[str, SourceAdapter]
    fetcher: PageFetcher
    mock_web: MockWeb | None = None


def build_source_backends(settings: DiscoverySettings, *, mock_web_path: Path | None = None) -> SourceBackends:
    validate_discovery_settings(settings)  # MOCK_NOT_ALLOWED ở production
    if settings.discovery_source_mode == "mock":
        web = MockWeb.from_json(mock_web_path) if mock_web_path else MockWeb.builtin()
        adapters: dict[str, SourceAdapter] = {t: MockSourceAdapter(web, adapter_type=t) for t in ADAPTER_CONFIG_MODELS}
        return SourceBackends("MOCK", adapters, MockPageFetcher(web), web)
    ua = settings.discovery_user_agent
    adapters = {
        "searxng_engine": SearxngEngineAdapter(base_url=settings.searxng_url, user_agent=ua),
        "http_json_api": HttpJsonApiAdapter(user_agent=ua),
        "open_dataset": DatasetAdapter("open_dataset"),
        "licensed_data": DatasetAdapter("licensed_data"),
    }
    if settings.page_fetcher == "browser":  # profile tùy chọn – mặc định HTTP thường
        from nichepilot.tools.fetchers.playwright_fetcher import PlaywrightPageFetcher

        browser = PlaywrightPageFetcher(
            user_agent=ua,
            max_bytes=settings.fetch_max_bytes,
            ws_endpoint=settings.browser_ws_endpoint,
            executable_path=settings.browser_executable_path,
        )
        return SourceBackends("REAL", adapters, browser)
    return SourceBackends("REAL", adapters, HttpPageFetcher(user_agent=ua, max_bytes=settings.fetch_max_bytes))
