"""WeightsService (T096; FR-018, FR-036): phiên bản trọng số mới (tổng 100, đủ 6 tiêu chí) trở thành active; phiên
bản cũ và
mọi đánh giá cũ KHÔNG bị sửa; audit `scoring.weights_version_created`."""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nichepilot.core.errors import AppError
from nichepilot.modules.audit.service import record_audit
from nichepilot.modules.discovery.scoring.opportunity import validate_weights


def weights_dto(r: Any) -> dict[str, Any]:
    return {
        "id": str(r["id"]),
        "version": r["version"],
        "weights": r["weights"],
        "coverage_threshold": float(r["coverage_threshold"]),
        "is_active": r["is_active"],
        "created_at": r["created_at"].isoformat(),
    }


async def list_versions(session: AsyncSession) -> list[dict[str, Any]]:
    rows = (
        (await session.execute(text("SELECT * FROM scoring_weights_versions ORDER BY version DESC"))).mappings().all()
    )
    return [weights_dto(r) for r in rows]


async def create_version(
    session: AsyncSession,
    *,
    weights: Mapping[str, float],
    coverage_threshold: float | None,
    actor_id: uuid.UUID,
    request_id: str | None,
) -> dict[str, Any]:
    try:
        validate_weights(weights)
    except ValueError as exc:
        raise AppError("WEIGHTS_INVALID", params={"detail": str(exc)}) from None
    if coverage_threshold is not None and not 0 < coverage_threshold <= 100:
        raise AppError("WEIGHTS_INVALID", params={"detail": "coverage_threshold"})
    current = (
        (await session.execute(text("SELECT * FROM scoring_weights_versions WHERE is_active FOR UPDATE")))
        .mappings()
        .one()
    )
    await session.execute(
        text("UPDATE scoring_weights_versions SET is_active = false WHERE id = :i"), {"i": current["id"]}
    )
    row = (
        (
            await session.execute(
                text(
                    "INSERT INTO scoring_weights_versions (version, weights, coverage_threshold, evidence_rules,"
                    " confidence_params, dedup_params, is_active, created_by) SELECT max(version) + 1, CAST(:w AS"
                    " jsonb),"
                    " :ct, CAST(:er AS jsonb), CAST(:cp AS jsonb), CAST(:dp AS jsonb), true, :u FROM"
                    " scoring_weights_versions RETURNING *"
                ),
                {
                    "w": json.dumps({k: weights[k] for k in sorted(weights)}),
                    "ct": coverage_threshold if coverage_threshold is not None else current["coverage_threshold"],
                    "er": json.dumps(current["evidence_rules"]),
                    "cp": json.dumps(current["confidence_params"]),
                    "dp": json.dumps(current["dedup_params"]),
                    "u": actor_id,
                },
            )
        )
        .mappings()
        .one()
    )
    await record_audit(
        session,
        action="scoring.weights_version_created",
        actor_type="USER",
        actor_id=actor_id,
        entity_type="scoring_weights_version",
        entity_id=row["id"],
        before={"version": current["version"], "weights": current["weights"]},
        after={
            "version": row["version"],
            "weights": row["weights"],
            "coverage_threshold": float(row["coverage_threshold"]),
        },
        request_id=request_id,
    )
    return weights_dto(row)
