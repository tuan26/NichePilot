"""Phiên bản trọng số sản phẩm (FR-027, FR-028; data-model `product_scoring_weights`) – cấu hình được, có version,
đúng 1 bản active."""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nichepilot.core.errors import AppError
from nichepilot.modules.products.scoring.opportunity import validate_weights


@dataclass(frozen=True)
class WeightsVersion:
    id: uuid.UUID
    version: int
    weights: dict[str, float]
    rubric: dict[str, Any]
    coverage_min: Decimal
    confidence_params: dict[str, Any]
    query_templates: dict[str, Any]
    non_official_domains: list[str]


_COLS = "id, version, weights, rubric, coverage_min, confidence_params, query_templates, non_official_domains"


def _row(r: Any) -> WeightsVersion:
    return WeightsVersion(
        r[0], r[1], dict(r[2]), dict(r[3] or {}), Decimal(r[4]), dict(r[5] or {}), dict(r[6] or {}), list(r[7] or [])
    )


async def active(session: AsyncSession) -> WeightsVersion:
    r = (await session.execute(text(f"SELECT {_COLS} FROM product_scoring_weights WHERE is_active"))).one()  # noqa: S608
    return _row(r)


async def history(session: AsyncSession) -> list[WeightsVersion]:
    rows = (await session.execute(text(f"SELECT {_COLS} FROM product_scoring_weights ORDER BY version DESC"))).all()  # noqa: S608
    return [_row(r) for r in rows]


async def create_version(
    session: AsyncSession, weights: Mapping[str, float], *, coverage_min: float | None, actor_id: uuid.UUID | None
) -> WeightsVersion:
    try:
        validate_weights(weights)
    except ValueError as exc:
        raise AppError("PRODUCT_WEIGHTS_INVALID", detail=str(exc)) from None
    if coverage_min is not None and not 0 <= float(coverage_min) <= 100:
        raise AppError("PRODUCT_WEIGHTS_INVALID", detail="coverage_min must be within 0..100")
    cur = await active(session)
    await session.execute(text("UPDATE product_scoring_weights SET is_active = false WHERE is_active"))
    new_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO product_scoring_weights (id, version, weights, rubric, coverage_min, confidence_params,"
            " query_templates, non_official_domains, is_active, created_by) VALUES (:id,"
            " (SELECT max(version) + 1 FROM product_scoring_weights), CAST(:w AS jsonb), CAST(:r AS jsonb), :cm,"
            " CAST(:c AS jsonb), CAST(:q AS jsonb), :n, true, :u)"
        ),
        {
            "id": new_id,
            "w": json.dumps({k: float(v) for k, v in weights.items()}),
            "r": json.dumps(cur.rubric),
            "cm": coverage_min if coverage_min is not None else cur.coverage_min,
            "c": json.dumps(cur.confidence_params),
            "q": json.dumps(cur.query_templates),
            "n": cur.non_official_domains,
            "u": actor_id,
        },
    )
    return await active(session)
