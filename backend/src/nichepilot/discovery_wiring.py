"""Lắp ráp E1 cho tiến trình api/worker (bổ sung cho services.py của E0 – không đổi hành vi E0).

- Kiểm tra cấu hình E1 lúc khởi động (fail-closed ở production: PII engine chưa phê duyệt, nguồn giả lập → ConfigError).
- Đăng ký tool chỉ đọc `source.query`, `page.fetch`, `robots.fetch` vào Tool Registry dùng chung.
- Cung cấp cổng erasure ledger cho API (cache ngắn) và agent (`preflight`).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nichepilot.core.discovery_config import DiscoverySettings, get_discovery_settings, validate_discovery_settings
from nichepilot.core.errors import AppError
from nichepilot.modules.discovery.erasure import (
    Ledger,
    LedgerApplyResult,
    LedgerHealth,
    apply_erasure_ledger,
    ledger_health,
)
from nichepilot.tools.builtin.page_fetch import build_page_fetch_tool
from nichepilot.tools.builtin.robots_fetch import build_robots_fetch_tool
from nichepilot.tools.builtin.source_query import build_source_query_tool
from nichepilot.tools.privacy.pii import PiiEngine, select_pii_engine
from nichepilot.tools.registry import ToolRegistry
from nichepilot.tools.sources.backends import SourceBackends, build_source_backends

DISCOVERY_TOOLS = ["source.query", "page.fetch", "robots.fetch"]


@dataclass
class DiscoveryServices:
    settings: DiscoverySettings
    sessionmaker: async_sessionmaker[AsyncSession]
    backends: SourceBackends
    pii: PiiEngine
    ledger: Ledger
    _health: LedgerHealth | None = None
    _health_at: float = field(default=0.0)

    async def ledger_health(self, *, force: bool = False) -> LedgerHealth:
        now = time.monotonic()
        if force or self._health is None or now - self._health_at > self.settings.ledger_health_cache_s:
            self._health = await ledger_health(self.sessionmaker, self.ledger)
            self._health_at = now
        return self._health

    async def require_ledger_ok(self, *, force: bool = False) -> None:
        """Cổng dữ liệu nghiên cứu E1 (X4): sổ chưa áp dụng đầy đủ → ERASURE_LEDGER_NOT_APPLIED."""
        if (await self.ledger_health(force=force)).status != "OK":
            raise AppError("ERASURE_LEDGER_NOT_APPLIED")

    async def apply_ledger(self) -> LedgerApplyResult:
        res = await apply_erasure_ledger(self.sessionmaker, self.ledger)
        self._health = None
        return res


_current: DiscoveryServices | None = None


def build_discovery(
    sessionmaker: async_sessionmaker[AsyncSession], tools: ToolRegistry, settings: DiscoverySettings | None = None
) -> DiscoveryServices:
    global _current
    ds = settings or get_discovery_settings()
    validate_discovery_settings(ds)
    pii = select_pii_engine(ds)
    backends = build_source_backends(ds)
    for tool in (
        build_source_query_tool(ds, adapters=backends.adapters, pii=pii),
        build_page_fetch_tool(ds, fetcher=backends.fetcher, pii=pii),
        build_robots_fetch_tool(ds, fetcher=backends.fetcher),
    ):
        if tools.get(tool.name) is None:
            tools.register(tool)
    _current = DiscoveryServices(ds, sessionmaker, backends, pii, Ledger(ds.erasure_ledger_dir))
    return _current


def current_discovery() -> DiscoveryServices:
    if _current is None:
        raise AppError("SERVICE_UNAVAILABLE", detail="E1 chưa được khởi tạo")
    return _current
