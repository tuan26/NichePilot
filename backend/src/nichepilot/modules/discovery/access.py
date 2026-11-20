"""DomainAccessService – robots.txt và tốc độ truy cập theo tên miền (FR-005, FR-030, FR-030a, FR-031; research R-04).

- robots.txt phân tích bằng protego (wildcard + ưu tiên khớp dài nhất RFC 9309). Cache 24 giờ trong
`domain_access_state`.
- robots 4xx (`NOT_FOUND`) → không có giới hạn; 5xx/mạng (`UNREACHABLE`) → KHÔNG thu thập tên miền đó (thận trọng).
- Khoảng cách tối thiểu = max(mức trần của lượt, Crawl-delay, Retry-After gần nhất). Trạng thái lưu DB → đúng cả sau khi
  worker khởi động lại.
- Agent gọi `permit()` TRƯỚC mỗi lần gọi tool `page.fetch` và `record_request()` ngay khi gửi.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit

from protego import Protego
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

ROBOTS_TTL = timedelta(hours=24)
USER_AGENT_TOKEN = "NichePilotResearchBot"  # noqa: S105 – tên User-Agent trong robots.txt, không phải secret
MAX_ROBOTS_CHARS = 65536

DecisionReason = Literal["OK", "WAIT", "ROBOTS_PENDING", "ROBOTS_DISALLOWED", "ROBOTS_UNREACHABLE", "BLOCKED"]


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    reason: DecisionReason
    wait_s: float = 0.0
    domain: str = ""


def domain_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def _now() -> datetime:
    return datetime.now(UTC)


class DomainAccessService:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession], *, clock: Callable[[], datetime] = _now) -> None:
        self.sessionmaker = sessionmaker
        self.clock = clock

    async def _state(self, s: AsyncSession, domain: str) -> dict[str, object] | None:
        row = (
            (await s.execute(text("SELECT * FROM domain_access_state WHERE domain = :d"), {"d": domain}))
            .mappings()
            .first()
        )
        return dict(row) if row else None

    async def permit(self, url: str, *, interval_ceiling_s: float) -> AccessDecision:
        domain = domain_of(url)
        now = self.clock()
        async with self.sessionmaker() as s:
            st = await self._state(s, domain)
        if st is None or st["robots_status"] == "PENDING" or st["robots_fetched_at"] is None:
            return AccessDecision(False, "ROBOTS_PENDING", domain=domain)
        fetched_at = st["robots_fetched_at"]
        assert isinstance(fetched_at, datetime)
        if now - fetched_at > ROBOTS_TTL:
            return AccessDecision(False, "ROBOTS_PENDING", domain=domain)
        if st["robots_status"] == "UNREACHABLE":
            return AccessDecision(False, "ROBOTS_UNREACHABLE", domain=domain)
        if st["robots_status"] == "OK" and st["robots_rules"]:
            rp = Protego.parse(str(st["robots_rules"]))
            if not rp.can_fetch(url, USER_AGENT_TOKEN):
                return AccessDecision(False, "ROBOTS_DISALLOWED", domain=domain)
        blocked_until = st["blocked_until"]
        if isinstance(blocked_until, datetime) and blocked_until > now:
            return AccessDecision(False, "WAIT", (blocked_until - now).total_seconds(), domain)
        interval = max(
            float(interval_ceiling_s),
            float(st["min_interval_s"] or 0),  # type: ignore[arg-type]
            float(st["crawl_delay_s"] or 0),  # type: ignore[arg-type]
        )
        last = st["last_request_at"]
        if isinstance(last, datetime):
            elapsed = (now - last).total_seconds()
            if elapsed < interval:
                return AccessDecision(False, "WAIT", interval - elapsed, domain)
        return AccessDecision(True, "OK", domain=domain)

    async def record_robots(self, domain: str, status: Literal["OK", "NOT_FOUND", "UNREACHABLE"], content: str) -> None:
        crawl_delay: Decimal | None = None
        rules = content[:MAX_ROBOTS_CHARS] if status == "OK" else None
        if rules:
            delay = Protego.parse(rules).crawl_delay(USER_AGENT_TOKEN)
            crawl_delay = Decimal(str(delay)) if delay is not None else None
        async with self.sessionmaker() as s, s.begin():
            await s.execute(
                text(
                    "INSERT INTO domain_access_state (domain, robots_status, robots_fetched_at, robots_rules,"
                    " crawl_delay_s) VALUES (:d, :st, :at, :r, :cd) ON CONFLICT (domain) DO UPDATE SET"
                    " robots_status = EXCLUDED.robots_status, robots_fetched_at = EXCLUDED.robots_fetched_at,"
                    " robots_rules = EXCLUDED.robots_rules, crawl_delay_s = EXCLUDED.crawl_delay_s, updated_at = now()"
                ),
                {"d": domain, "st": status, "at": self.clock(), "r": rules, "cd": crawl_delay},
            )

    async def record_request(self, domain: str) -> None:
        async with self.sessionmaker() as s, s.begin():
            await s.execute(
                text(
                    "INSERT INTO domain_access_state (domain, last_request_at) VALUES (:d, :t)"
                    " ON CONFLICT (domain) DO UPDATE SET last_request_at = EXCLUDED.last_request_at, updated_at = now()"
                ),
                {"d": domain, "t": self.clock()},
            )

    async def record_retry_after(
        self, domain: str, seconds: float, reason: Literal["RATE_LIMITED", "ACCESS_RESTRICTED"] = "RATE_LIMITED"
    ) -> None:
        until = self.clock() + timedelta(seconds=max(0.0, seconds))
        async with self.sessionmaker() as s, s.begin():
            await s.execute(
                text(
                    "INSERT INTO domain_access_state (domain, blocked_until, block_reason) VALUES (:d, :u, :r)"
                    " ON CONFLICT (domain) DO UPDATE SET blocked_until = EXCLUDED.blocked_until,"
                    " block_reason = EXCLUDED.block_reason, updated_at = now()"
                ),
                {"d": domain, "u": until, "r": reason},
            )
