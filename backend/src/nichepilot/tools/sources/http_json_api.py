"""Adapter `http_json_api` – khung cho API chính thức (FR-006, FR-006g; research R-13).

Xác thực: giá trị lấy từ `os.environ[auth_env_var]` ngay lúc gọi – không lưu DB, không log, không trả về. Lỗi 401/403 →
UNAVAILABLE lý do AUTH_FAILED, không thử lại. Chưa có nguồn thật nào được bật trong E1.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal
from urllib.parse import quote

import httpx

from nichepilot.tools.sources.base import HttpJsonApiConfig, PolicySnapshot, RateLimiter, SourceHit, SourceResult, Sleep


def _pluck(obj: Any, path: str) -> Any:
    for part in path.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(part)
    return obj


@dataclass
class HttpJsonApiAdapter:
    user_agent: str
    client_factory: Callable[[], httpx.AsyncClient] = httpx.AsyncClient
    sleep: Sleep = asyncio.sleep
    limiter: RateLimiter = field(default_factory=RateLimiter)
    adapter_type: str = "http_json_api"
    data_origin: Literal["REAL", "MOCK"] = "REAL"

    async def query(
        self, policy: PolicySnapshot, query: str, *, market: str, language: str, max_results: int
    ) -> SourceResult:
        cfg = HttpJsonApiConfig.model_validate(policy.config)
        qs = cfg.query_template.format(query=quote(query), language=quote(language), market=quote(market))
        url = f"{cfg.base_url}?{qs}" if "?" not in cfg.base_url else f"{cfg.base_url}&{qs}"
        headers = {"User-Agent": self.user_agent}
        if cfg.auth_env_var:
            value = os.environ.get(cfg.auth_env_var)
            if not value:
                return SourceResult("UNAVAILABLE", reason="AUTH_NOT_CONFIGURED")
            headers[cfg.auth_header_name] = value
        last = "UNKNOWN"
        async with self.client_factory() as client:
            for _ in range(cfg.max_retries + 1):
                await self.limiter.wait(policy.source_key, cfg.rate_limit_per_minute)
                try:
                    resp = await client.get(url, headers=headers, timeout=cfg.timeout_s)
                except (httpx.TimeoutException, httpx.TransportError):
                    last = "NETWORK_ERROR"
                    continue
                if resp.status_code in (401, 403):
                    return SourceResult("UNAVAILABLE", reason="AUTH_FAILED")
                if resp.status_code == 429:
                    return SourceResult("RATE_LIMITED", reason="HTTP_429")
                if resp.status_code != 200:
                    last = f"HTTP_{resp.status_code}"
                    continue
                items = _pluck(resp.json(), cfg.result_mapping.get("items", "items")) or []
                hits = [
                    SourceHit(
                        url=str(_pluck(it, cfg.result_mapping["url"])),
                        title=_pluck(it, cfg.result_mapping.get("title", "title")),
                        snippet=_pluck(it, cfg.result_mapping.get("snippet", "snippet")),
                        published_at=_pluck(it, cfg.result_mapping.get("published_at", "published_at")),
                    )
                    for it in items
                    if isinstance(it, dict)
                ][:max_results]
                return SourceResult("OK", hits) if hits else SourceResult("NO_RESULTS")
        return SourceResult("UNAVAILABLE", reason=last)
