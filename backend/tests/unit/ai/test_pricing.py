"""T063 – Tính chi phí theo bảng giá có phiên bản (FR-040, FR-041, SC-003)."""

from __future__ import annotations

from decimal import Decimal

from nichepilot.ai.pricing import PriceSheet, compute_cost, max_cost
from nichepilot.ai.providers.base import TokenUsage

D = Decimal


def _price(**kw: object) -> PriceSheet:
    base: dict[str, object] = {
        "id": None,
        "provider": "anthropic",
        "model": "m",
        "input_per_mtok": D("2.00"),
        "output_per_mtok": D("10.00"),
        "cache_read_per_mtok": D("0.10"),
        "cache_write_per_mtok": None,
        "long_context_threshold_tokens": None,
        "long_input_per_mtok": None,
        "long_output_per_mtok": None,
        "verified": True,
    }
    base.update(kw)
    return PriceSheet(**base)  # type: ignore[arg-type]


def test_TC_FR040_01_cost_matches_hand_calculation() -> None:
    usage = TokenUsage(input_tokens=1_000, output_tokens=500, cache_read_tokens=2_000, cache_write_tokens=0)
    # 1000*2/1e6 + 500*10/1e6 + 2000*0.10/1e6 = 0.002 + 0.005 + 0.0002 = 0.0072
    assert compute_cost(_price(), usage) == D("0.007200")


def test_TC_FR040_02_unknown_cache_write_price_charged_conservatively_at_input_rate() -> None:
    usage = TokenUsage(input_tokens=0, output_tokens=0, cache_write_tokens=1_000_000)
    assert compute_cost(_price(), usage) == D("2.000000")


def test_TC_FR041_01_long_context_tier_applies_above_threshold() -> None:
    price = _price(
        input_per_mtok=D("0.10"),
        output_per_mtok=D("0.50"),
        long_context_threshold_tokens=100_000,
        long_input_per_mtok=D("0.50"),
        long_output_per_mtok=D("2.50"),
    )
    small = compute_cost(price, TokenUsage(input_tokens=100_000, output_tokens=1_000_000))
    big = compute_cost(price, TokenUsage(input_tokens=100_001, output_tokens=1_000_000))
    assert small == D("0.510000")
    assert big == D("2.550001")


def test_TC_SC003_01_deviation_within_one_percent() -> None:
    usage = TokenUsage(input_tokens=2_000, output_tokens=500)
    expected = D(2_000) * D("2.00") / D(1_000_000) + D(500) * D("10.00") / D(1_000_000)
    actual = compute_cost(_price(), usage)
    assert abs(actual - expected) / expected <= D("0.01")


def test_TC_FR043_06_max_cost_assumes_all_output_tokens_and_rounds_up() -> None:
    assert max_cost(_price(), input_tokens=1, max_output_tokens=1) == D("0.000012")
    assert max_cost(_price(), input_tokens=0, max_output_tokens=0) == D("0.000001")  # luôn > 0 để giữ chỗ
