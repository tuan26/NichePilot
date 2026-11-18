"""Tool Registry (T077 – FR-020, FR-022, FR-023; contracts/internal-interfaces.md §2).

Quyền tool được quyết định ở mã nguồn: chỉ tool trong `allowed_tools` của agent, và mọi tool có tác động bên ngoài
bị vô hiệu hóa trong MVP. Mỗi lần thực thi (kể cả bị từ chối) đều được ghi lại.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

from nichepilot.ai.providers.base import ToolSpec
from nichepilot.core.logging import redact_payload

Recorder = Callable[[dict[str, Any]], Awaitable[None]]


@dataclass(frozen=True)
class ToolContext:
    job_id: uuid.UUID
    step_id: uuid.UUID | None
    allowed_tools: frozenset[str]
    data_origin: Literal["REAL", "MOCK"]
    record: Recorder
    extras: dict[str, Any] = field(default_factory=dict)


Handler = Callable[[BaseModel, ToolContext], Awaitable[BaseModel]]


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    version: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Handler
    timeout_s: int = 30
    external_effect: bool = False


class ToolDeniedError(Exception):
    def __init__(self, code: str, tool: str) -> None:
        super().__init__(f"{code}: {tool}")
        self.code = code
        self.tool = tool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool đã đăng ký: {tool.name}")
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def specs_for(self, allowed: list[str] | frozenset[str]) -> list[ToolSpec]:
        """Schema gửi cho model – chỉ tool được phép và không có tác động bên ngoài."""
        return [
            ToolSpec(name=t.name, description=t.description, input_schema=t.input_model.model_json_schema())
            for name in allowed
            if (t := self._tools.get(name)) is not None and not t.external_effect
        ]

    def list_info(self) -> list[dict[str, Any]]:
        return [
            {
                "name": t.name,
                "version": t.version,
                "description": t.description,
                "external_effect": t.external_effect,
                "enabled": not t.external_effect,
                "timeout_s": t.timeout_s,
                "input_schema": t.input_model.model_json_schema(),
                "output_schema": t.output_model.model_json_schema(),
            }
            for t in self._tools.values()
        ]

    async def execute(self, name: str, raw_input: dict[str, Any], ctx: ToolContext) -> dict[str, Any]:
        started = time.monotonic()
        tool = self._tools.get(name)
        row: dict[str, Any] = {
            "job_id": ctx.job_id,
            "step_id": ctx.step_id,
            "tool_name": name,
            "tool_version": tool.version if tool else "unknown",
            "input": redact_payload(raw_input),
            "output": None,
            "data_origin": ctx.data_origin,
            "denial_reason": None,
        }

        async def finish(status: str, **extra: Any) -> None:
            row.update(status=status, duration_ms=int((time.monotonic() - started) * 1000), **extra)
            await ctx.record(row)

        if tool is None or name not in ctx.allowed_tools:
            await finish("DENIED", denial_reason="NOT_PERMITTED")
            raise ToolDeniedError("TOOL_NOT_PERMITTED", name)
        if tool.external_effect:
            await finish("DENIED", denial_reason="EXTERNAL_EFFECT_DISABLED")
            raise ToolDeniedError("TOOL_EXTERNAL_EFFECT_DISABLED", name)
        try:
            parsed = tool.input_model.model_validate(raw_input)
        except ValidationError as exc:
            await finish("FAILED")
            raise ValueError(f"Input tool không hợp lệ: {name}") from exc
        try:
            async with asyncio.timeout(tool.timeout_s):
                result = await tool.handler(parsed, ctx)
            output = tool.output_model.model_validate(result.model_dump()).model_dump(mode="json")
        except TimeoutError:
            await finish("TIMEOUT")
            raise
        except Exception:
            await finish("FAILED")
            raise
        await finish("SUCCEEDED", output=redact_payload(output))
        return output
