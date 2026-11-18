"""Tool `system.runtime_info` (T077): thông tin runtime vô hại – không tác động bên ngoài, không đọc secret."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict

from nichepilot.tools.registry import ToolContext, ToolDefinition, ToolRegistry


class RuntimeInfoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RuntimeInfoOutput(BaseModel):
    app_version: str
    server_time_utc: str
    timezone: str


async def runtime_info(_inp: BaseModel, ctx: ToolContext) -> BaseModel:
    return RuntimeInfoOutput(
        app_version=str(ctx.extras.get("app_version", "unknown")),
        server_time_utc=datetime.now(UTC).isoformat(timespec="seconds"),
        timezone=str(ctx.extras.get("timezone", "UTC")),
    )


RUNTIME_INFO = ToolDefinition(
    name="system.runtime_info",
    version="1",
    description="Return the NichePilot application version, server time (UTC) and configured timezone.",
    input_model=RuntimeInfoInput,
    output_model=RuntimeInfoOutput,
    handler=runtime_info,
    timeout_s=5,
)


def build_tool_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(RUNTIME_INFO)
    return registry
