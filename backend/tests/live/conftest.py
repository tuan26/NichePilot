"""Bộ test live – gọi API THẬT (T126, SC-003, FR-018h). Chỉ chạy thủ công: `make test-live`.

Từ chối chạy (skip với lý do BLOCKED – không bao giờ tính là PASS) nếu thiếu bất kỳ điều kiện nào:
API key, `AI_PAID_CALLS_ENABLED=true`, `NICHEPILOT_LIVE_MAX_USD` > 0.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from decimal import Decimal, InvalidOperation

import pytest


@pytest.fixture(autouse=True, scope="session")
def _block_outbound_network() -> Iterator[None]:
    """Ghi đè rào chặn mạng của bộ test chính: test live cần gọi provider thật."""
    yield


def live_budget() -> Decimal:
    try:
        value = Decimal(os.environ.get("NICHEPILOT_LIVE_MAX_USD", "0"))
    except InvalidOperation:
        value = Decimal(0)
    return value


@pytest.fixture
def live_guard() -> Decimal:
    if os.environ.get("AI_PAID_CALLS_ENABLED", "false").lower() != "true":
        pytest.skip("BLOCKED: AI_PAID_CALLS_ENABLED khác true – chưa được chủ sở hữu cho phép")
    budget = live_budget()
    if budget <= 0:
        pytest.skip("BLOCKED: thiếu NICHEPILOT_LIVE_MAX_USD > 0")
    return budget


@pytest.fixture
def anthropic_key(live_guard: Decimal) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        pytest.skip("BLOCKED: thiếu ANTHROPIC_API_KEY")
    return key


@pytest.fixture
def openai_key(live_guard: Decimal) -> str:
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        pytest.skip("BLOCKED: thiếu OPENAI_API_KEY")
    return key
