"""Phiên bản trọng số keyword (FR-017; Clarification Q1 = A; data-model `keyword_scoring_weights`) – cấu hình được, có
version,
đúng 1 bản active. Đổi trọng số = tạo phiên bản mới; đánh giá cũ giữ nguyên (tái lập được – SC-004)."""

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
from nichepilot.modules.keywords.scoring.opportunity import validate_weights


@dataclass(frozen=True)
class WeightsVersion:
    id: uuid.UUID
    version: int
    weights: dict[str, float]
    rubric: dict[str, Any]
    coverage_min: Decimal
    confidence_params: dict[str, Any]
    templates: dict[str, Any]


_COLS = "id, version, weights, rubric, coverage_min, confidence_params, templates"


def _row(r: Any) -> WeightsVersion:
    return WeightsVersion(r[0], r[1], dict(r[2]), dict(r[3] or {}), Decimal(r[4]), dict(r[5] or {}), dict(r[6] or {}))


async def active(session: AsyncSession) -> WeightsVersion:
    r = (await session.execute(text(f"SELECT {_COLS} FROM keyword_scoring_weights WHERE is_active"))).one()  # noqa: S608
    return _row(r)


async def history(session: AsyncSession) -> list[WeightsVersion]:
    rows = (await session.execute(text(f"SELECT {_COLS} FROM keyword_scoring_weights ORDER BY version DESC"))).all()  # noqa: S608
    return [_row(r) for r in rows]


async def create_version(
    session: AsyncSession, weights: Mapping[str, float], *, coverage_min: float | None, actor_id: uuid.UUID | None
) -> WeightsVersion:
    try:
        validate_weights(weights)
    except ValueError as exc:
        raise AppError("KEYWORD_WEIGHTS_INVALID", detail=str(exc)) from None
    if coverage_min is not None and not 0 <= float(coverage_min) <= 100:
        raise AppError("KEYWORD_WEIGHTS_INVALID", detail="coverage_min must be within 0..100")
    cur = await active(session)
    await session.execute(text("UPDATE keyword_scoring_weights SET is_active = false WHERE is_active"))
    await session.execute(
        text(
            "INSERT INTO keyword_scoring_weights (id, version, weights, rubric, coverage_min, confidence_params,"
            " templates,"
            " is_active, created_by) VALUES (:id, (SELECT max(version) + 1 FROM keyword_scoring_weights),"
            " CAST(:w AS jsonb), CAST(:r AS jsonb), :cm, CAST(:c AS jsonb), CAST(:t AS jsonb), true, :u)"
        ),
        {
            "id": uuid.uuid4(),
            "w": json.dumps({k: float(v) for k, v in weights.items()}),
            "r": json.dumps(cur.rubric),
            "cm": coverage_min if coverage_min is not None else cur.coverage_min,
            "c": json.dumps(cur.confidence_params),
            "t": json.dumps(cur.templates, ensure_ascii=False),
            "u": actor_id,
        },
    )
    return await active(session)
