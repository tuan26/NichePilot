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


def _rates(price: PriceSheet, input_tokens: int) -> tuple[Decimal, Decimal]:
    threshold = price.long_context_threshold_tokens
    if threshold is not None and input_tokens > threshold and price.long_input_per_mtok and price.long_output_per_mtok:
        return price.long_input_per_mtok, price.long_output_per_mtok
    return price.input_per_mtok, price.output_per_mtok


def _raw_cost(price: PriceSheet, usage: TokenUsage) -> Decimal:
    in_rate, out_rate = _rates(price, usage.input_tokens)
    # Giá cache chưa xác minh (NULL) → tính bảo thủ bằng giá input thường.
    cache_read = price.cache_read_per_mtok if price.cache_read_per_mtok is not None else in_rate
    cache_write = price.cache_write_per_mtok if price.cache_write_per_mtok is not None else in_rate
    total = (
        Decimal(usage.input_tokens) * in_rate
        + Decimal(usage.output_tokens) * out_rate
        + Decimal(usage.cache_read_tokens) * cache_read
        + Decimal(usage.cache_write_tokens) * cache_write
    )
    return total / MTOK


def compute_cost(price: PriceSheet, usage: TokenUsage) -> Decimal:
    return _raw_cost(price, usage).quantize(QUANT, rounding=ROUND_HALF_UP)


def max_cost(price: PriceSheet, *, input_tokens: int, max_output_tokens: int) -> Decimal:
    """Chi phí tối đa có thể có của một lời gọi – dùng để giữ chỗ ngân sách (làm tròn lên, luôn > 0)."""
    raw = _raw_cost(price, TokenUsage(input_tokens=input_tokens, output_tokens=max_output_tokens))
    return max(raw.quantize(QUANT, rounding=ROUND_UP), MIN_RESERVATION)


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
