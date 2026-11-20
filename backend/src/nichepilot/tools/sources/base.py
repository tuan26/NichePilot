"""SourceAdapter chung (FR-006, FR-006c…g; research R-13; internal-interfaces §1).

Loại adapter (code) tách khỏi nguồn (dữ liệu cấu hình `source_policies`). Cấu hình KHÔNG chứa credential: khóa bị cấm
ở mọi
cấp lồng nhau và giá trị có dạng credential bị từ chối (§1.1). Xác thực chỉ qua `auth_env_var` = TÊN biến môi trường.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict

from nichepilot.core.source_config import (  # tái xuất cho lớp tools
    ADAPTER_CONFIG_MODELS,
    DatasetConfig,
    HttpJsonApiConfig,
    SearxngEngineConfig,
    SourceConfigError,
    validate_source_config,
)

__all__ = [
    "ADAPTER_CONFIG_MODELS",
    "DatasetConfig",
    "HttpJsonApiConfig",
    "PolicySnapshot",
    "RateLimiter",
    "SearxngEngineConfig",
    "Sleep",
    "SourceAdapter",
    "SourceConfigError",
    "SourceHit",
    "SourceResult",
    "validate_source_config",
]

SourceStatus = Literal["OK", "NO_RESULTS", "UNAVAILABLE", "RATE_LIMITED", "ACCESS_RESTRICTED"]
ComplianceStatus = Literal["ALLOWED", "UNVERIFIED", "PROHIBITED"]
Sleep = Callable[[float], Awaitable[None]]


class PolicySnapshot(BaseModel):
    """Ảnh chụp policy truyền cho tool. Tool từ chối mọi trạng thái khác ALLOWED (phòng thủ lớp 2 – A1)."""

    model_config = ConfigDict(extra="forbid")
    policy_id: uuid.UUID
    source_key: str
    adapter_type: str
    config: dict[str, Any]
    compliance_status: ComplianceStatus
    verified_at: date | None = None


@dataclass(frozen=True)
class SourceHit:
    url: str
    title: str | None = None
    snippet: str | None = None
    published_at: str | None = None


@dataclass
class SourceResult:
    status: SourceStatus
    hits: list[SourceHit] = field(default_factory=list)
    reason: str | None = None


class SourceAdapter(Protocol):
    adapter_type: str
    data_origin: Literal["REAL", "MOCK"]

    async def query(
        self, policy: PolicySnapshot, query: str, *, market: str, language: str, max_results: int
    ) -> SourceResult: ...


class RateLimiter:
    """Giới hạn tần suất theo nguồn (`rate_limit_per_minute`) trong một tiến trình."""

    def __init__(self, sleep: Sleep | None = None, clock: Callable[[], float] = time.monotonic) -> None:
        self.sleep = sleep or asyncio.sleep
        self.clock = clock
        self._last: dict[str, float] = {}

    async def wait(self, key: str, per_minute: int) -> None:
        interval = 60.0 / per_minute
        last = self._last.get(key)
        now = self.clock()
        if last is not None and now - last < interval:
            await self.sleep(interval - (now - last))
        self._last[key] = self.clock()
