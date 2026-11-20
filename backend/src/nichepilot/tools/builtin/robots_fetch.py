"""Tool `robots.fetch` (FR-005, FR-030a; research R-04): tải robots.txt của một tên miền (nội dung ≤ 64 KB)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from nichepilot.core.discovery_config import DiscoverySettings
from nichepilot.tools.fetchers.http_fetcher import PageFetcher
from nichepilot.tools.registry import ToolContext, ToolDefinition

TOOL_NAME = "robots.fetch"


class RobotsFetchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    domain: str = Field(pattern=r"^[a-z0-9.-]{1,253}$")


class RobotsFetchOutput(BaseModel):
    status: Literal["OK", "NOT_FOUND", "UNREACHABLE"]
    http_status: int | None
    content: str


def build_robots_fetch_tool(settings: DiscoverySettings, *, fetcher: PageFetcher) -> ToolDefinition:
    async def handler(inp: BaseModel, ctx: ToolContext) -> BaseModel:
        assert isinstance(inp, RobotsFetchInput)
        raw = await fetcher.fetch_robots(inp.domain, timeout_s=settings.fetch_timeout_s)
        if raw.error or raw.http_status is None or raw.http_status >= 500:
            return RobotsFetchOutput(status="UNREACHABLE", http_status=raw.http_status, content="")
        if raw.http_status >= 400:
            return RobotsFetchOutput(status="NOT_FOUND", http_status=raw.http_status, content="")
        return RobotsFetchOutput(status="OK", http_status=raw.http_status, content=(raw.body or "")[:65536])

    return ToolDefinition(
        name=TOOL_NAME,
        version="1",
        description="Fetch robots.txt of a domain so crawl rules can be honoured.",
        input_model=RobotsFetchInput,
        output_model=RobotsFetchOutput,
        handler=handler,
        timeout_s=30,
    )
