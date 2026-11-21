"""E1 (X6, chủ sở hữu duyệt 2026-11-20) – JobContext.call_ai(task_type=…) (FR-028).

- Không truyền task_type → giữ nguyên hành vi E0 (task type của agent).
- Chỉ chấp nhận task type agent đã đăng ký (`AgentDefinition.extra_task_types`) – khác → TASK_TYPE_NOT_ALLOWED, không gọi gateway.
- Mọi lời gọi vẫn qua AIGateway (Model Task Profile, xác minh giá, giữ chỗ ngân sách) và tính vào max_ai_calls.
"""

from __future__ import annotations

import dataclasses
import uuid
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from nichepilot.core.errors import AppError
from nichepilot.jobs.agents.diagnostic import DEFINITION
from nichepilot.jobs.agents.niche_discovery import DEFINITION as DISCOVERY
from nichepilot.jobs.runtime import JobContext

pytestmark = pytest.mark.discovery


class _Gateway:
    def __init__(self) -> None:
        self.task_types: list[str] = []

    async def call(self, task_type: str, **_kw: Any) -> Any:
        self.task_types.append(task_type)
        usage = SimpleNamespace(input_tokens=1, output_tokens=1)
        return SimpleNamespace(response=SimpleNamespace(usage=usage), cost_usd=Decimal(0), data_origin="MOCK")


def _ctx(definition: Any, gw: _Gateway) -> JobContext:
    return JobContext(uuid.uuid4(), "MOCK", {}, definition, gw, None, None, None)  # type: ignore[arg-type]


async def test_TC_E1_FR028_03_default_task_type_unchanged_for_e0_agents() -> None:
    gw = _Gateway()
    ctx = _ctx(DEFINITION, gw)
    await ctx.call_ai(system="s", messages=[])
    assert gw.task_types == ["system.diagnostic"] and DEFINITION.extra_task_types == ()
    with pytest.raises(AppError) as exc:  # agent E0 không đăng ký task type phụ
        await ctx.call_ai(system="s", messages=[], task_type="discovery.extract")
    assert exc.value.code == "TASK_TYPE_NOT_ALLOWED" and gw.task_types == ["system.diagnostic"]


async def test_TC_E1_FR028_04_registered_task_types_only_and_counted() -> None:
    gw = _Gateway()
    ctx = _ctx(DISCOVERY, gw)
    await ctx.call_ai(system="s", messages=[], task_type="discovery.extract")
    await ctx.call_ai(system="s", messages=[], task_type="discovery.assess")
    with pytest.raises(AppError) as exc:
        await ctx.call_ai(system="s", messages=[], task_type="reason.complex")  # có profile nhưng agent không đăng ký
    assert exc.value.code == "TASK_TYPE_NOT_ALLOWED"
    assert gw.task_types == ["discovery.extract", "discovery.assess"] and ctx.ai_call_count == 2
    limited = _ctx(dataclasses.replace(DISCOVERY, max_ai_calls=1), _Gateway())
    await limited.call_ai(system="s", messages=[], task_type="discovery.extract")
    with pytest.raises(AppError) as exc2:  # giới hạn lời gọi AI áp dụng cho mọi task type
        await limited.call_ai(system="s", messages=[], task_type="discovery.assess")
    assert exc2.value.code == "MAX_AI_CALLS_EXCEEDED"
