"""Ba danh sách xếp hạng (T097; scoring-rubric §4; FR-013d, FR-019b, FR-024, FR-016).

- research: EVIDENCE_SUFFICIENT ∧ SCORED ∧ decision ∉ {HIDDEN, REJECTED} – xếp Opportunity giảm dần, hòa → Confidence.
- affiliate: research ∧ SIGNALS_FOUND ∧ không MONETIZATION_RISK.
- needs_research: INSUFFICIENT_EVIDENCE ∨ INSUFFICIENT_SCORING_DATA ∨ chưa có đánh giá – không có thứ hạng Opportunity.
MOCK mặc định bị loại (chỉ hiện khi `include_mock` – luôn kèm `data_origin`). Ngách đã gộp không xuất hiện.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

ListName = Literal["research", "affiliate", "needs_research"]
SortName = Literal["opportunity_desc", "confidence_desc", "created_desc"]
DISCLAIMER_KEY = "discovery.opportunity.disclaimer"
VERIFICATION_KEYS = ("VERIFIED", "INFERRED", "UNKNOWN", "CONFLICTING")

RESEARCH = (
    "n.evidence_status = 'EVIDENCE_SUFFICIENT' AND e.scoring_status = 'SCORED'"
    " AND n.decision_status NOT IN ('HIDDEN', 'REJECTED')"
)
WHERE = {
    "research": RESEARCH,
    "affiliate": RESEARCH
    + " AND n.monetization_status = 'SIGNALS_FOUND' AND NOT ('MONETIZATION_RISK' = ANY(n.risk_flags))",
    "needs_research": (
        "(n.evidence_status = 'INSUFFICIENT_EVIDENCE' OR e.id IS NULL OR e.scoring_status ="
        " 'INSUFFICIENT_SCORING_DATA')"
        " AND n.decision_status <> 'HIDDEN'"
    ),
}
ORDER = {
    "opportunity_desc": (
        "e.opportunity_score DESC NULLS LAST, e.confidence_score DESC NULLS LAST, n.created_at DESC, n.id"
    ),
    "confidence_desc": (
        "e.confidence_score DESC NULLS LAST, e.opportunity_score DESC NULLS LAST, n.created_at DESC, n.id"
    ),
    "created_desc": "n.created_at DESC, n.id",
}


def _f(v: Any) -> float | None:
    return float(v) if v is not None else None


def summary_dto(r: Any) -> dict[str, Any]:
    summary = {k: 0 for k in VERIFICATION_KEYS}
    for c in dict(r["criteria"] or {}).values():
        summary[c.get("status", "UNKNOWN")] = summary.get(c.get("status", "UNKNOWN"), 0) + 1
    return {
        "id": str(r["id"]),
        "name": r["name"],
        "micro_niche": r["micro_niche"],
        "country": r["country"],
        "opportunity_score": _f(r["opportunity_score"]),
        "confidence_score": _f(r["confidence_score"]),
        "coverage": _f(r["coverage"]),
        "scoring_status": r["scoring_status"],
        "evidence_status": r["evidence_status"],
        "verification_summary": summary,
        "monetization_status": r["monetization_status"],
        "risk_flags": list(r["risk_flags"] or []),
        "ai_recommendation": r["ai_recommendation"],
        "decision_status": r["decision_status"],
        "has_possible_duplicate": bool(r["has_possible_duplicate"]),
        "data_origin": r["data_origin"],
    }


async def list_niches(
    session: AsyncSession,
    *,
    list_name: ListName = "research",
    run_id: uuid.UUID | None = None,
    country: str | None = None,
    decision_status: list[str] | None = None,
    include_mock: bool = False,
    sort: SortName | None = None,
    limit: int = 50,
    offset: int = 0,
    min_opportunity: float | None = None,
    min_confidence: float | None = None,
) -> tuple[list[dict[str, Any]], int | None]:
    clauses = ["n.merged_into_id IS NULL", WHERE[list_name]]
    params: dict[str, Any] = {"l": limit + 1, "o": offset}
    if not include_mock:
        clauses.append("n.data_origin = 'REAL'")
    if run_id is not None:
        clauses.append("EXISTS (SELECT 1 FROM niche_run_links rl WHERE rl.niche_id = n.id AND rl.run_id = :run)")
        params["run"] = run_id
    if country:
        clauses.append("n.country = :country")
        params["country"] = country
    if decision_status:
        clauses.append("n.decision_status = ANY(:ds)")
        params["ds"] = decision_status
    if min_opportunity is not None:
        clauses.append("e.opportunity_score >= :mo")
        params["mo"] = min_opportunity
    if min_confidence is not None:
        clauses.append("e.confidence_score >= :mc")
        params["mc"] = min_confidence
    order = ORDER[sort or ("confidence_desc" if list_name == "needs_research" else "opportunity_desc")]
    sql = (
        "SELECT n.*, e.opportunity_score, e.confidence_score, e.coverage, e.scoring_status, e.criteria,"  # noqa: S608 – chỉ hằng, giá trị qua tham số
        " EXISTS (SELECT 1 FROM niche_similarity s WHERE s.status = 'POSSIBLE' AND (s.niche_a_id = n.id OR"
        " s.niche_b_id = n.id)) AS has_possible_duplicate FROM niches n LEFT JOIN niche_evaluations e"
        f" ON e.id = n.latest_evaluation_id WHERE {' AND '.join(clauses)} ORDER BY {order} LIMIT :l OFFSET :o"
    )
    # chỉ ghép các mệnh đề hằng (WHERE/ORDER) – mọi giá trị người dùng đi qua tham số ràng buộc
    rows = (await session.execute(text(sql), params)).mappings().all()
    items = [summary_dto(r) for r in rows[:limit]]
    return items, (offset + limit if len(rows) > limit else None)
