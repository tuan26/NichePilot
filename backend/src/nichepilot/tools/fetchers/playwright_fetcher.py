"""PlaywrightPageFetcher – profile TÙY CHỌN `browser-fetcher`, TẮT mặc định (T128; I1; FR-005, FR-006f, FR-031).

Dùng khi trang công khai cần JavaScript để hiển thị nội dung. Quy tắc giống HttpPageFetcher:
- KHÔNG stealth/giả trình duyệt: User-Agent nhận diện được (`discovery_user_agent`), không plugin chống phát hiện, không
  `playwright-stealth`/`patchright`/Crawl4AI; không cookie/đăng nhập (context mới cho mỗi trang); không vượt CAPTCHA.
- Robots + khoảng cách tên miền vẫn do agent kiểm tra TRƯỚC khi gọi (modules/discovery/access.py).
- Giới hạn thời gian, kích thước; chặn tải file; chỉ trả HTML sau khi render → `page.fetch` trích + che PII trong tool.
Kết nối tới trình duyệt từ xa (`browser_ws_endpoint`, container `browser-fetcher`) hoặc chạy Chromium cục bộ (dev/test).
Nhóm tùy chọn `browser` (playwright) phải được cài; thiếu → lỗi cấu hình rõ ràng lúc khởi động.
"""

from __future__ import annotations

from typing import Any, Literal

from nichepilot.tools.fetchers.http_fetcher import RawPage

BLOCKED_RESOURCES = ("media", "font", "image")


class PlaywrightPageFetcher:
    data_origin: Literal["REAL", "MOCK"] = "REAL"

    def __init__(
        self,
        *,
        user_agent: str,
        max_bytes: int,
        ws_endpoint: str | None = None,
        executable_path: str | None = None,
    ) -> None:
        try:
            import playwright.async_api  # noqa: F401
        except ImportError as exc:  # pragma: no cover - phụ thuộc môi trường
            raise RuntimeError("PAGE_FETCHER=browser cần nhóm tùy chọn `browser` (playwright)") from exc
        self.user_agent = user_agent
        self.max_bytes = max_bytes
        self.ws_endpoint = ws_endpoint
        self.executable_path = executable_path

    async def _browser(self, pw: Any) -> Any:
        if self.ws_endpoint:
            return await pw.chromium.connect(self.ws_endpoint)
        kwargs: dict[str, Any] = {"headless": True, "args": ["--no-sandbox"]}
        if self.executable_path:
            kwargs["executable_path"] = self.executable_path
        return await pw.chromium.launch(**kwargs)

    async def fetch(self, url: str, *, timeout_s: float) -> RawPage:
        from playwright.async_api import Error as PlaywrightError
        from playwright.async_api import TimeoutError as PlaywrightTimeout
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await self._browser(pw)
            try:
                context = await browser.new_context(
                    user_agent=self.user_agent, accept_downloads=False, java_script_enabled=True
                )

                async def block_heavy(route: Any) -> None:
                    if route.request.resource_type in BLOCKED_RESOURCES:
                        await route.abort()
                    else:
                        await route.continue_()

                await context.route("**/*", block_heavy)
                page = await context.new_page()
                try:
                    resp = await page.goto(url, timeout=timeout_s * 1000, wait_until="networkidle")
                except PlaywrightTimeout:
                    return RawPage(None, None, None, None, error="TIMEOUT")
                except PlaywrightError:
                    return RawPage(None, None, None, None, error="NETWORK_ERROR")
                if resp is None:
                    return RawPage(None, None, None, None, error="NETWORK_ERROR")
                headers = await resp.all_headers()
                retry_after = headers.get("retry-after")
                html = await page.content()
                if len(html.encode("utf-8")) > self.max_bytes:
                    return RawPage(resp.status, headers.get("content-type"), None, page.url, error="TOO_LARGE")
                return RawPage(
                    resp.status,
                    headers.get("content-type", "text/html"),
                    html,
                    page.url,
                    float(retry_after) if retry_after and retry_after.isdigit() else None,
                )
            finally:
                await browser.close()

    async def fetch_robots(self, domain: str, *, timeout_s: float) -> RawPage:
        """robots.txt không cần JavaScript – tải bằng HTTP thường (không qua trình duyệt)."""
        from nichepilot.tools.fetchers.http_fetcher import HttpPageFetcher

        return await HttpPageFetcher(user_agent=self.user_agent, max_bytes=self.max_bytes).fetch_robots(
            domain, timeout_s=timeout_s
        )
