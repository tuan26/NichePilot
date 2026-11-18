"""T065 – Tool Registry: quyền, tác động bên ngoài, validate, timeout (FR-020, FR-022, FR-023).

Dùng recorder trong bộ nhớ thay cho DB (test double) để kiểm tra bản ghi tool_executions.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from pydantic import BaseModel

from nichepilot.tools.registry import ToolContext, ToolDefinition, ToolDeniedError, ToolRegistry


class In(BaseModel):
    n: int = 0


class Out(BaseModel):
    doubled: int


async def _double(inp: BaseModel, _ctx: ToolContext) -> BaseModel:
    assert isinstance(inp, In)
    return Out(doubled=inp.n * 2)


async def _slow(_inp: BaseModel, _ctx: ToolContext) -> BaseModel:
    await asyncio.sleep(5)
    return Out(doubled=0)


class MemoryRecorder:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    async def __call__(self, row: dict[str, Any]) -> None:
        self.rows.append(row)


def _registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(ToolDefinition("math.double", "1", "Double n", In, Out, _double))
    reg.register(ToolDefinition("math.slow", "1", "Slow", In, Out, _slow, timeout_s=1))
    reg.register(ToolDefinition("web.publish", "1", "Publish", In, Out, _double, external_effect=True))
    return reg


def _ctx(rec: MemoryRecorder, allowed: set[str]) -> ToolContext:
    return ToolContext(
        job_id=uuid.uuid4(), step_id=uuid.uuid4(), allowed_tools=frozenset(allowed), data_origin="MOCK", record=rec
    )


async def test_TC_FR020_01_execute_validates_and_records() -> None:
    rec = MemoryRecorder()
    result = await _registry().execute("math.double", {"n": 21}, _ctx(rec, {"math.double"}))
    assert result == {"doubled": 42}
    assert rec.rows[-1]["status"] == "SUCCEEDED" and rec.rows[-1]["tool_name"] == "math.double"
    assert rec.rows[-1]["data_origin"] == "MOCK"


async def test_TC_FR022_01_tool_not_in_allowed_list_denied() -> None:
    rec = MemoryRecorder()
    with pytest.raises(ToolDeniedError) as exc:
        await _registry().execute("math.double", {"n": 1}, _ctx(rec, set()))
    assert exc.value.code == "TOOL_NOT_PERMITTED"
    assert rec.rows[-1]["status"] == "DENIED" and rec.rows[-1]["denial_reason"] == "NOT_PERMITTED"


async def test_TC_FR023_01_external_effect_tools_disabled_in_mvp() -> None:
    rec = MemoryRecorder()
    with pytest.raises(ToolDeniedError) as exc:
        await _registry().execute("web.publish", {"n": 1}, _ctx(rec, {"web.publish"}))
    assert exc.value.code == "TOOL_EXTERNAL_EFFECT_DISABLED"
    assert rec.rows[-1]["denial_reason"] == "EXTERNAL_EFFECT_DISABLED"
    assert next(t for t in _registry().list_info() if t["name"] == "web.publish")["enabled"] is False


async def test_TC_FR020_02_invalid_input_and_timeout_fail() -> None:
    rec = MemoryRecorder()
    with pytest.raises(ValueError):
        await _registry().execute("math.double", {"n": "abc"}, _ctx(rec, {"math.double"}))
    assert rec.rows[-1]["status"] == "FAILED"
    with pytest.raises(TimeoutError):
        await _registry().execute("math.slow", {}, _ctx(rec, {"math.slow"}))
    assert rec.rows[-1]["status"] == "TIMEOUT"


def test_TC_FR020_03_duplicate_registration_and_specs() -> None:
    reg = _registry()
    with pytest.raises(ValueError):
        reg.register(ToolDefinition("math.double", "1", "dup", In, Out, _double))
    specs = reg.specs_for(["math.double", "web.publish", "unknown"])
    assert [s.name for s in specs] == ["math.double"]  # tool tác động bên ngoài không được gửi cho model
