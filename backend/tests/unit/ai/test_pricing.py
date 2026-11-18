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


def test_TC_FR040_02_unknown_cache_write_price_charged_conservatively() -> None:
    # C3: giá cache write chưa có (NULL) KHÔNG được tính bằng giá input thường (thấp hơn thực tế 1.25×/2×).
    usage = TokenUsage(input_tokens=0, output_tokens=0, cache_write_tokens=1_000_000)
    cost = compute_cost(_price(), usage)
    assert cost >= D("2.00") * D("1.25")
    assert cost == D("4.000000")  # chính sách: 2× giá input = mức ghi cache 1 giờ (cao nhất) theo trang giá chính thức


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
    # C3: token prompt giữ chỗ theo mức cao nhất input/cache read/cache write (cache write chưa có giá → 2× input = 4.00)
    assert max_cost(_price(), input_tokens=1, max_output_tokens=1) == D("0.000014")
    assert max_cost(_price(), input_tokens=0, max_output_tokens=0) == D("0.000001")  # luôn > 0 để giữ chỗ


# --- C3: an toàn giá -----------------------------------------------------------------------------------------------
# Bảng giá dạng Haiku 5.5 (giá theo độ dài prompt, ngưỡng 100K). DỮ LIỆU TEST – chỉ để kiểm tra công thức.
def _tiered(**kw: object) -> PriceSheet:
    base: dict[str, object] = {
        "input_per_mtok": D("0.10"),
        "output_per_mtok": D("0.50"),
        "cache_read_per_mtok": D("0.01"),
        "cache_write_per_mtok": D("0.125"),
        "long_context_threshold_tokens": 100_000,
        "long_input_per_mtok": D("0.50"),
        "long_output_per_mtok": D("2.50"),
    }
    base.update(kw)
    return _price(**base)


def test_TC_FR040_10_verified_cache_write_price_used() -> None:
    usage = TokenUsage(input_tokens=0, output_tokens=0, cache_write_tokens=80_000)  # ≤ 100K → bậc thường
    assert compute_cost(_tiered(), usage) == D("0.010000")  # 80K × 0.125 / 1M


def test_TC_FR041_10_prompt_under_threshold_counts_cache_tokens() -> None:
    # Độ dài prompt = input + cache read + cache write = 90K ≤ 100K → bậc thường.
    usage = TokenUsage(input_tokens=50_000, output_tokens=1_000, cache_read_tokens=30_000, cache_write_tokens=10_000)
    expected = (D(50_000) * D("0.10") + D(1_000) * D("0.50") + D(30_000) * D("0.01") + D(10_000) * D("0.125")) / D(
        1_000_000
    )
    assert compute_cost(_tiered(), usage) == expected.quantize(D("0.000001"))


def test_TC_FR041_11_prompt_over_threshold_uses_long_tier_including_cache() -> None:
    # 60K input + 50K cache read = 110K > 100K → bậc cao áp dụng cho CẢ request, kể cả phần cache.
    usage = TokenUsage(input_tokens=60_000, output_tokens=1_000, cache_read_tokens=50_000, cache_write_tokens=0)
    cost = compute_cost(_tiered(), usage)
    official_long = (D(60_000) * D("0.50") + D(1_000) * D("2.50") + D(50_000) * D("0.05")) / D(1_000_000)
    assert cost >= official_long  # không thấp hơn giá chính thức bậc > 100K (cache read 0.05)
    # Chính sách bảo thủ: không có giá cache bậc cao trong schema → cache read tính bằng giá input bậc cao.
    assert cost == ((D(60_000) * D("0.50") + D(1_000) * D("2.50") + D(50_000) * D("0.50")) / D(1_000_000)).quantize(
        D("0.000001")
    )


def test_TC_FR041_12_cache_write_over_threshold_conservative() -> None:
    usage = TokenUsage(input_tokens=100_000, output_tokens=0, cache_write_tokens=1_000_000)
    assert compute_cost(_tiered(), usage) == D("1.050000")  # 0.1M×0.50 + 1M×(2×0.50)


def test_TC_FR043_10_reservation_never_below_any_actual_split() -> None:
    """Giữ chỗ cho N token prompt + M token output ≥ chi phí thực của MỌI cách chia N thành input/cache read/write."""
    for price in (_tiered(), _price(), _tiered(cache_write_per_mtok=None, cache_read_per_mtok=None)):
        for n in (1_000, 99_999, 100_000, 100_001, 150_000):
            reserved = max_cost(price, input_tokens=n, max_output_tokens=2_000)
            for frac_write in (0, 0.3, 1):
                for frac_read in (0, 0.5):
                    w = int(n * frac_write)
                    r = min(int(n * frac_read), n - w)
                    actual = compute_cost(
                        price,
                        TokenUsage(
                            input_tokens=n - w - r, output_tokens=2_000, cache_read_tokens=r, cache_write_tokens=w
                        ),
                    )
                    assert reserved >= actual, (price.cache_write_per_mtok, n, w, r, reserved, actual)


def test_TC_FR043_11_paid_price_must_be_usable() -> None:
    from nichepilot.ai.pricing import CostEstimateError, ensure_billable

    ensure_billable(_tiered())
    for bad in (_price(input_per_mtok=D(0)), _price(output_per_mtok=D(0))):
        try:
            ensure_billable(bad)
        except CostEstimateError:
            continue
        raise AssertionError("giá 0 cho provider có phí phải bị từ chối (fail closed)")


# --- C3 (quyết định chủ sở hữu 2026-11-18): bộ test bắt buộc ---------------------------------------------------------
def test_TC_FR040_11_cache_write_null_below_threshold_is_2x_input() -> None:
    usage = TokenUsage(input_tokens=0, output_tokens=0, cache_write_tokens=50_000)  # ≤ 100K
    assert compute_cost(_tiered(cache_write_per_mtok=None), usage) == (
        D(50_000) * D("0.10") * 2 / D(1_000_000)
    ).quantize(D("0.000001"))


def test_TC_FR040_12_cache_write_null_above_threshold_is_2x_long_input() -> None:
    usage = TokenUsage(input_tokens=60_000, output_tokens=0, cache_write_tokens=50_000)  # 110K > 100K
    expected = (D(60_000) * D("0.50") + D(50_000) * D("0.50") * 2) / D(1_000_000)
    assert compute_cost(_tiered(cache_write_per_mtok=None), usage) == expected.quantize(D("0.000001"))


def test_TC_FR040_13_verified_cache_read_used_without_multiplier() -> None:
    usage = TokenUsage(input_tokens=0, output_tokens=0, cache_read_tokens=90_000)  # ≤ 100K, giá cache read đã có
    assert compute_cost(_tiered(), usage) == D("0.000900")  # 90K × 0.01 / 1M – không nhân 2×, không dùng giá input
