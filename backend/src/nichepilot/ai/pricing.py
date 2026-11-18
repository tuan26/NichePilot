"""Tính chi phí theo bảng giá có phiên bản (T073 – FR-040, FR-041). Giá chỉ lấy từ dữ liệu, không hard-code."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, ROUND_UP, Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nichepilot.ai.providers.base import TokenUsage

MTOK = Decimal(1_000_000)
QUANT = Decimal("0.000001")
MIN_RESERVATION = Decimal("0.000001")


@dataclass(frozen=True)
class PriceSheet:
    id: uuid.UUID | None
    provider: str
    model: str
    input_per_mtok: Decimal
    output_per_mtok: Decimal
    cache_read_per_mtok: Decimal | None
    cache_write_per_mtok: Decimal | None
    long_context_threshold_tokens: int | None
    long_input_per_mtok: Decimal | None
    long_output_per_mtok: Decimal | None
    verified: bool


# Khi chưa có giá cache write: 2× giá input của bậc áp dụng (= giá ghi cache 1 giờ, mức cao nhất theo trang giá chính
# thức; ≥ yêu cầu tối thiểu 1.25×). Không bao giờ dùng giá input thường cho cache write (C3).
CACHE_WRITE_FALLBACK_MULTIPLIER = Decimal(2)


class CostEstimateError(ValueError):
    """Không thể ước tính chi phí an toàn → lời gọi có phí phải bị chặn (fail closed)."""


@dataclass(frozen=True)
class _Rates:
    input: Decimal
    output: Decimal
    cache_read: Decimal
    cache_write: Decimal


def _rates(price: PriceSheet, prompt_tokens: int) -> _Rates:
    """Giá theo bậc. Độ dài prompt = input + cache read + cache write (theo trang giá chính thức)."""
    threshold = price.long_context_threshold_tokens
    if threshold is not None and prompt_tokens > threshold and price.long_input_per_mtok and price.long_output_per_mtok:
        long_in = price.long_input_per_mtok
        # Schema chưa có giá cache cho bậc cao → bảo thủ: cache read = giá input bậc cao, cache write = 2× giá đó.
        return _Rates(long_in, price.long_output_per_mtok, long_in, long_in * CACHE_WRITE_FALLBACK_MULTIPLIER)
    in_rate = price.input_per_mtok
    # Giá cache read chưa có → tính bằng giá input (cache read chính thức luôn rẻ hơn input → bảo thủ).
    cache_read = price.cache_read_per_mtok if price.cache_read_per_mtok is not None else in_rate
    cache_write = (
        price.cache_write_per_mtok
        if price.cache_write_per_mtok is not None
        else in_rate * CACHE_WRITE_FALLBACK_MULTIPLIER
    )
    return _Rates(in_rate, price.output_per_mtok, cache_read, cache_write)


def _raw_cost(price: PriceSheet, usage: TokenUsage) -> Decimal:
    prompt = usage.input_tokens + usage.cache_read_tokens + usage.cache_write_tokens
    r = _rates(price, prompt)
    total = (
        Decimal(usage.input_tokens) * r.input
        + Decimal(usage.output_tokens) * r.output
        + Decimal(usage.cache_read_tokens) * r.cache_read
        + Decimal(usage.cache_write_tokens) * r.cache_write
    )
    return total / MTOK


def compute_cost(price: PriceSheet, usage: TokenUsage) -> Decimal:
    return _raw_cost(price, usage).quantize(QUANT, rounding=ROUND_HALF_UP)


def max_cost(price: PriceSheet, *, input_tokens: int, max_output_tokens: int) -> Decimal:
    """Chi phí tối đa có thể có của một lời gọi – dùng để giữ chỗ ngân sách (làm tròn lên, luôn > 0).

    Mỗi token prompt được tính theo mức cao nhất trong input / cache read / cache write của bậc áp dụng, nên giữ chỗ
    không bao giờ thấp hơn chi phí thực dù provider tính một phần prompt là cache.
    """
    r = _rates(price, input_tokens)
    per_prompt_token = max(r.input, r.cache_read, r.cache_write)
    raw = (Decimal(input_tokens) * per_prompt_token + Decimal(max_output_tokens) * r.output) / MTOK
    return max(raw.quantize(QUANT, rounding=ROUND_UP), MIN_RESERVATION)


def ensure_billable(price: PriceSheet) -> None:
    """Fail closed cho provider có phí: giá input/output phải > 0 (giá 0 là dữ liệu sai, không thể ước tính an toàn)."""
    if price.input_per_mtok <= 0 or price.output_per_mtok <= 0:
        raise CostEstimateError(f"giá không hợp lệ cho {price.provider}/{price.model}")


async def load_price(session: AsyncSession, provider: str, model: str) -> PriceSheet | None:
    row = (
        (
            await session.execute(
                text(
                    "SELECT * FROM model_pricing WHERE provider = :p AND model = :m AND effective_from <= now() "
                    "ORDER BY version DESC LIMIT 1"
                ),
                {"p": provider, "m": model},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return PriceSheet(
        id=row["id"],
        provider=row["provider"],
        model=row["model"],
        input_per_mtok=row["input_per_mtok"],
        output_per_mtok=row["output_per_mtok"],
        cache_read_per_mtok=row["cache_read_per_mtok"],
        cache_write_per_mtok=row["cache_write_per_mtok"],
        long_context_threshold_tokens=row["long_context_threshold_tokens"],
        long_input_per_mtok=row["long_input_per_mtok"],
        long_output_per_mtok=row["long_output_per_mtok"],
        verified=row["verified"],
    )
