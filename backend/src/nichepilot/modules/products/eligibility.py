"""Ngách đủ điều kiện cho Product Discovery (FR-001; Clarification Q1 2026-11-27; data-model §1).

Đủ điều kiện ⇔ `evidence_status = EVIDENCE_SUFFICIENT` (ngưỡng bằng chứng E1: ≥ 2 bằng chứng pain point hợp lệ từ ≥ 2
nhóm nguồn độc lập)
∧ `decision_status ∈ {CANDIDATE, WATCH, PURSUE}` (CANDIDATE = chưa có quyết định) ∧ chưa bị gộp. Chỉ đọc bảng E1.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from nichepilot.core.errors import AppError
from nichepilot.modules.discovery.models import Niche

ELIGIBLE_DECISIONS = ("CANDIDATE", "WATCH", "PURSUE")


@dataclass(frozen=True)
class EligibleNiche:
    id: uuid.UUID
    project_id: uuid.UUID
    country: str
    data_origin: str


def ineligibility_reason(niche: Niche) -> str | None:
    if niche.merged_into_id is not None:
        return "MERGED"
    if niche.evidence_status != "EVIDENCE_SUFFICIENT":
        return "INSUFFICIENT_EVIDENCE"
    if niche.decision_status not in ELIGIBLE_DECISIONS:
        return str(niche.decision_status)  # REJECTED | HIDDEN
    return None


async def check_niche_eligible(session: AsyncSession, niche_id: uuid.UUID) -> EligibleNiche:
    niche = (await session.execute(select(Niche).where(Niche.id == niche_id))).scalar_one_or_none()
    if niche is None:
        raise AppError("NICHE_NOT_FOUND")
    reason = ineligibility_reason(niche)
    if reason is not None:
        raise AppError("NICHE_NOT_ELIGIBLE", params={"reason": reason})
    return EligibleNiche(niche.id, niche.project_id, niche.country, niche.data_origin)
