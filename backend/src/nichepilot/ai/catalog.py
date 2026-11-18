"""Catalog model & điều kiện gọi có phí (T074 – FR-019c).

Lời gọi có phí chỉ được phép khi: model đã xác minh từ nguồn chính thức, có đủ khả năng tác vụ cần, và bảng giá đã
xác minh. Không dùng alias tự nâng cấp (`latest`); không tự chọn model khác.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nichepilot.ai.pricing import PriceSheet, load_price
from nichepilot.core.errors import AppError

CAPABILITY_COLUMNS = {
    "structured_output": "supports_structured_output",
    "tools": "supports_tools",
    "effort": "supports_effort",
}


def validate_model_id(model_id: str) -> None:
    if not model_id or "latest" in model_id.lower():
        raise ValueError("model_id phải là ID chính xác, không dùng alias kiểu 'latest'")


async def require_price(session: AsyncSession, provider: str, model: str) -> PriceSheet:
    price = await load_price(session, provider, model)
    if price is None:
        raise AppError("PRICING_MISSING", params={"provider": provider, "model": model})
    return price


async def check_paid_call_allowed(session: AsyncSession, provider: str, model: str, needs: set[str]) -> PriceSheet:
    validate_model_id(model)
    row = (
        (
            await session.execute(
                text("SELECT * FROM ai_models WHERE provider = :p AND model_id = :m AND status = 'ACTIVE'"),
                {"p": provider, "m": model},
            )
        )
        .mappings()
        .first()
    )
    if row is None or not row["verified"]:
        raise AppError("MODEL_NOT_VERIFIED", params={"provider": provider, "model": model})
    missing = [cap for cap in sorted(needs) if row[CAPABILITY_COLUMNS[cap]] is not True]
    if missing:
        raise AppError(
            "MODEL_NOT_VERIFIED", params={"provider": provider, "model": model, "missing": ",".join(missing)}
        )
    price = await require_price(session, provider, model)
    if not price.verified:
        raise AppError("PRICING_NOT_VERIFIED", params={"provider": provider, "model": model})
    return price
