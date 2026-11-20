"""Adapter `searxng_engine` (FR-006, FR-006a, FR-006f; research R-02).

Chỉ truy vấn engine của policy ALLOWED (tham số `engines=`) – SearXNG cũng chỉ nạp engine của nguồn đang bật (`keep_only`).
429/503: thử lại tối đa `max_retries` lần theo Retry-After; Retry-After quá dài → dừng. CAPTCHA/chặn → ACCESS_RESTRICTED,
không thử vượt.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

import httpx

from nichepilot.tools.sources.base import PolicySnapshot, RateLimiter, SearxngEngineConfig, SourceHit, SourceResult, Sleep

CAPTCHA_MARKERS = ("captcha", "verify you are human", "unusual traffic", "access denied")
MAX_RETRY_AFTER_S = 60.0


def _retry_after(resp: httpx.Response) -> float:
    try:
        return float(resp.headers.get("Retry-After", "1"))
    except ValueError:
        return MAX_RETRY_AFTER_S + 1  # dạng ngày giờ → coi là dài, không chờ


def looks_like_challenge(text: str) -> bool:
    low = text[:5000].lower()
    return any(m in low for m in CAPTCHA_MARKERS)


@dataclass
class SearxngEngineAdapter:
    base_url: str
    user_agent: str
    client_factory: Callable[[], httpx.AsyncClient] = httpx.AsyncClient
    sleep: Sleep = asyncio.sleep
    limiter: RateLimiter = field(default_factory=RateLimiter)
    adapter_type: str = "searxng_engine"
    data_origin: Literal["REAL", "MOCK"] = "REAL"

    async def query(
        self, policy: PolicySnapshot, query: str, *, market: str, language: str, max_results: int
    ) -> SourceResult:
        cfg = SearxngEngineConfig.model_validate(policy.config)
        params = {
            "q": query,
            "format": "json",
            "engines": cfg.engine_name,
            "language": f"{language}-{market}" if market else language,
            "pageno": "1",
        }
        headers = {"User-Agent": self.user_agent, "X-Real-IP": "127.0.0.1", "X-Forwarded-For": "127.0.0.1"}
        attempts = cfg.max_retries + 1
        last_reason = "UNKNOWN"
        async with self.client_factory() as client:
            for attempt in range(attempts):
                await self.limiter.wait(policy.source_key, cfg.rate_limit_per_minute)
                try:
                    resp = await client.get(
                        f"{self.base_url.rstrip('/')}/search", params=params, headers=headers, timeout=cfg.timeout_s
                    )
                except (httpx.TimeoutException, httpx.TransportError):
                    last_reason = "NETWORK_ERROR"
                    continue
                if resp.status_code in (429, 503):
                    wait = _retry_after(resp)
                    if wait > MAX_RETRY_AFTER_S or attempt == attempts - 1:
                        return SourceResult("RATE_LIMITED", reason="RETRY_AFTER")
                    await self.sleep(wait)
                    continue
                if resp.status_code in (401, 403) or looks_like_challenge(resp.text if resp.status_code != 200 else ""):
                    return SourceResult("ACCESS_RESTRICTED", reason=f"HTTP_{resp.status_code}")
                if resp.status_code != 200:
                    last_reason = f"HTTP_{resp.status_code}"
                    continue
                return self._parse(resp.json(), max_results)
        return SourceResult("UNAVAILABLE", reason=last_reason)

    @staticmethod
    def _parse(data: dict[str, object], max_results: int) -> SourceResult:
        results = data.get("results") or []
        hits = [
            SourceHit(
                url=str(r["url"]),
                title=str(r.get("title") or "") or None,
                snippet=str(r.get("content") or "") or None,
                published_at=str(r["publishedDate"]) if r.get("publishedDate") else None,
            )
            for r in results  # type: ignore[union-attr]
            if isinstance(r, dict) and str(r.get("url", "")).startswith(("http://", "https://"))
        ][:max_results]
        if hits:
            return SourceResult("OK", hits)
        unresponsive = " ".join(str(x) for x in (data.get("unresponsive_engines") or [])).lower()  # type: ignore[union-attr]
        if "captcha" in unresponsive or "access denied" in unresponsive:
            return SourceResult("ACCESS_RESTRICTED", reason="UPSTREAM_CAPTCHA")
        if unresponsive:
            return SourceResult("UNAVAILABLE", reason="ENGINE_UNRESPONSIVE")
        return SourceResult("NO_RESULTS")
