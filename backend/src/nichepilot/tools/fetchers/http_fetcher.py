"""PageFetcher mặc định: httpx (FR-005, FR-031; research R-03, R-04).

Chỉ tải: không chạy JavaScript, không gửi cookie/đăng nhập, User-Agent nhận diện được (không giả trình duyệt). Giới
hạn kích thước
và loại nội dung. Kiểm tra robots/khoảng cách do agent (modules/discovery/access.py) làm TRƯỚC khi gọi.
Nội dung trả về là HTML thô – chỉ tồn tại trong handler của tool `page.fetch`, được trích + che PII trước khi ra khỏi
tool.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

import httpx


@dataclass(frozen=True)
class RawPage:
    http_status: int | None
    content_type: str | None
    body: str | None
    final_url: str | None
    retry_after_s: float | None = None
    error: str | None = None  # NETWORK_ERROR | TIMEOUT | TOO_LARGE


class PageFetcher(Protocol):
    data_origin: Literal["REAL", "MOCK"]

    async def fetch(self, url: str, *, timeout_s: float) -> RawPage: ...

    async def fetch_robots(self, domain: str, *, timeout_s: float) -> RawPage: ...


def _retry_after(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return 86400.0  # dạng ngày giờ → coi là rất dài (không chờ)


@dataclass
class HttpPageFetcher:
    user_agent: str
    max_bytes: int = 3 * 1024 * 1024
    client_factory: Callable[[], httpx.AsyncClient] = lambda: httpx.AsyncClient(follow_redirects=True)
    data_origin: Literal["REAL", "MOCK"] = "REAL"

    async def fetch(self, url: str, *, timeout_s: float) -> RawPage:
        headers = {"User-Agent": self.user_agent, "Accept": "text/html,application/xhtml+xml"}
        try:
            async with (
                self.client_factory() as client,
                client.stream("GET", url, headers=headers, timeout=timeout_s) as r,
            ):
                ctype = r.headers.get("content-type", "")
                retry = _retry_after(r.headers.get("retry-after"))
                if r.status_code != 200 or "html" not in ctype.lower():
                    text = (await r.aread())[:20000].decode(r.encoding or "utf-8", errors="replace")
                    return RawPage(r.status_code, ctype, text, str(r.url), retry)
                chunks: list[bytes] = []
                size = 0
                async for chunk in r.aiter_bytes():
                    size += len(chunk)
                    if size > self.max_bytes:
                        return RawPage(r.status_code, ctype, None, str(r.url), error="TOO_LARGE")
                    chunks.append(chunk)
                body = b"".join(chunks).decode(r.encoding or "utf-8", errors="replace")
                return RawPage(r.status_code, ctype, body, str(r.url), retry)
        except httpx.TimeoutException:
            return RawPage(None, None, None, None, error="TIMEOUT")
        except httpx.TransportError:
            return RawPage(None, None, None, None, error="NETWORK_ERROR")

    async def fetch_robots(self, domain: str, *, timeout_s: float) -> RawPage:
        headers = {"User-Agent": self.user_agent}
        try:
            async with self.client_factory() as client:
                r = await client.get(f"https://{domain}/robots.txt", headers=headers, timeout=timeout_s)
                return RawPage(r.status_code, r.headers.get("content-type"), r.text[:65536], str(r.url))
        except httpx.TimeoutException:
            return RawPage(None, None, None, None, error="TIMEOUT")
        except httpx.TransportError:
            return RawPage(None, None, None, None, error="NETWORK_ERROR")
