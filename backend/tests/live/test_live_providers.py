"""T126 – Tích hợp provider THẬT (SC-003). KHÔNG chạy trong CI hay `make test`; chỉ `make test-live` khi được cho phép.

Kết quả ghi vào `live-results.jsonl` để đưa vào mục "Tích hợp provider thật" của báo cáo. Không có kết quả = chưa kiểm chứng.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from nichepilot.ai.providers.anthropic_api import AnthropicAPIProvider
from nichepilot.ai.providers.base import LLMMessage, LLMRequest

pytestmark = pytest.mark.live
RESULTS = Path(os.environ.get("NICHEPILOT_LIVE_RESULTS", "live-results.jsonl"))
MODEL = os.environ.get("NICHEPILOT_LIVE_MODEL", "claude-haiku-5-5")
# Giá tham khảo cho trần chi phí; phải trùng bản giá đã xác minh trong DB trước khi bật (enable-real-api.md §3).
REF_IN, REF_OUT = (
    Decimal(os.environ.get("NICHEPILOT_LIVE_IN_PER_MTOK", "0.10")),
    Decimal(os.environ.get("NICHEPILOT_LIVE_OUT_PER_MTOK", "0.50")),
)
MAX_OUTPUT = 64


def _record(**row: object) -> None:
    row["at"] = datetime.now(UTC).isoformat()
    with RESULTS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, default=str) + "\n")


async def test_TC_SC003_L1_anthropic_connection(anthropic_key: str) -> None:
    result = await AnthropicAPIProvider(anthropic_key).check_connection()  # Models API – không tính phí
    _record(test="anthropic_connection", result=result.result)
    assert result.result == "OK"


async def test_TC_SC003_L2_anthropic_minimal_call_cost(anthropic_key: str, live_guard: Decimal) -> None:
    worst = (Decimal(2000) * REF_IN + Decimal(MAX_OUTPUT) * REF_OUT) / Decimal(1_000_000)
    if worst > live_guard:
        pytest.skip(f"BLOCKED: chi phí tối đa ước tính {worst} > NICHEPILOT_LIVE_MAX_USD {live_guard}")
    provider = AnthropicAPIProvider(anthropic_key)
    req = LLMRequest(
        task_type="system.diagnostic",
        model=MODEL,
        system="Reply with the single word OK.",
        messages=[LLMMessage(role="user", content="ping")],
        max_output_tokens=MAX_OUTPUT,
        timeout_s=60,
        effort="low",
    )
    resp = await provider.generate(req)
    cost = (Decimal(resp.usage.input_tokens) * REF_IN + Decimal(resp.usage.output_tokens) * REF_OUT) / Decimal(
        1_000_000
    )
    _record(
        test="anthropic_minimal_call",
        model=MODEL,
        outcome=resp.outcome,
        request_id=resp.provider_request_id,
        input_tokens=resp.usage.input_tokens,
        output_tokens=resp.usage.output_tokens,
        estimated_cost_usd=str(cost),
        note="Đối chiếu với trang usage của Anthropic (SC-003: lệch ≤ 1%)",
    )
    assert resp.outcome == "SUCCESS"
    assert cost <= live_guard
