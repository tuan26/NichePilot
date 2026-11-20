"""E1 (X6) – JobContext.call_ai nhận task type tùy chọn để mỗi bước dùng Model Task Profile riêng (FR-028).

Mặc định vẫn là task type của agent (hành vi E0 không đổi). Không gọi provider – gateway giả.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from nichepilot.jobs.agents.diagnostic import DEFINITION
from nichepilot.jobs.runtime import JobContext

pytestmark = pytest.mark.discovery


class _Gateway:
    def __init__(self) -> None:
        self.task_types: list[str] = []

    async def call(self, task_type: str, **_kw: Any) -> Any:
        self.task_types.append(task_type)
        usage = SimpleNamespace(input_tokens=1, output_tokens=1)
        return SimpleNamespace(response=SimpleNamespace(usage=usage), cost_usd=Decimal(0), data_origin="MOCK")


async def test_TC_E1_FR028_03_call_ai_task_type_override_keeps_default() -> None:
    gw = _Gateway()
    ctx = JobContext(uuid.uuid4(), "MOCK", {}, DEFINITION, gw, None, None, None)  # type: ignore[arg-type]
    await ctx.call_ai(system="s", messages=[])
    await ctx.call_ai(system="s", messages=[], task_type="discovery.extract")
    assert gw.task_types == ["system.diagnostic", "discovery.extract"]
    assert ctx.ai_call_count == 2  # giới hạn lời gọi AI của agent vẫn áp dụng cho mọi task type
