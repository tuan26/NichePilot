"""EvaluationService (T095; data-model `niche_evaluations`, `niches.latest_evaluation_id`; FR-017, FR-019b, FR-020,
FR-035).

`evaluate_and_store` là điểm DUY NHẤT tạo đánh giá ngách:
1. ngưỡng bằng chứng (`analysis.evaluate_niche` – đọc lại bằng chứng hiện tại, bằng chứng đã xóa không được tính);
2. tiêu chí: do AI đề xuất (bước `assess`) hoặc lấy lại từ đánh giá gần nhất (tính lại – 0 lời gọi AI,
`computed_without_ai`);
   bằng chứng đã xóa bị cắt khỏi tiêu chí (hết bằng chứng → UNKNOWN);
3. Opportunity/Coverage và Confidence (thuần, mã xác định) theo phiên bản trọng số ĐANG active;
4. `monetization_status` từ tiêu chí monetization; cờ rủi ro; đề xuất AI (không đủ bằng chứng → UNKNOWN);
5. ghi `niche_evaluations` (bất biến) – bỏ qua nếu kết quả trùng đánh giá gần nhất (chạy lại không tạo bản ghi thừa).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nichepilot.modules.discovery import analysis
from nichepilot.modules.discovery.evidence_rules import EvidenceRules
from nichepilot.modules.discovery.risk import risk_flags
from nichepilot.modules.discovery.scoring.confidence import ConfidenceInputs, compute_confidence, source_kind
from nichepilot.modules.discovery.scoring.opportunity import CRITERIA, Criterion, compute_opportunity


@dataclass(frozen=True)
class EvaluationOutcome:
    evaluation_id: uuid.UUID
    created: bool
    evidence_status: str
    scoring_status: str
    opportunity: Decimal | None
    confidence: Decimal


async def active_weights(session: AsyncSession) -> Any:
    return (
        await session.execute(
            text(
                "SELECT id, version, weights, coverage_threshold, evidence_rules, confidence_params"
                " FROM scoring_weights_versions WHERE is_active"
            )
        )
    ).one()


def monetization_from(criterion: Mapping[str, Any]) -> str:
    """FR-019b: chỉ tiêu chí monetization HỢP LỆ (có bằng chứng) mới xác định trạng thái; null/UNKNOWN →
    MONETIZATION_UNVERIFIED.

    Mức ≥ 50 (tín hiệu affiliate gián tiếp trở lên) → SIGNALS_FOUND; mức 0/25 có bằng chứng → NO_AFFILIATE_FOUND."""
    score = criterion.get("score")
    if score is None:
        return "MONETIZATION_UNVERIFIED"
    return "SIGNALS_FOUND" if int(score) >= 50 else "NO_AFFILIATE_FOUND"


async def _latest(session: AsyncSession, niche_id: uuid.UUID) -> Any:
    return (
        (
            await session.execute(
                text(
                    "SELECT e.* FROM niches n JOIN niche_evaluations e ON e.id = n.latest_evaluation_id WHERE n.id = :n"
                ),
                {"n": niche_id},
            )
        )
        .mappings()
        .first()
    )


def _uuid_or_none(v: str) -> str | None:
    try:
        return str(uuid.UUID(v))
    except ValueError:
        return None


async def _active_evidence_ids(session: AsyncSession, raw_ids: set[str]) -> set[str]:
    """ID không hợp lệ (không phải UUID) bị coi như không tồn tại – không làm hỏng việc tính lại."""
    ids = {u for i in raw_ids if (u := _uuid_or_none(i))}
    if not ids:
        return set()
    rows = (
        await session.execute(
            text("SELECT id FROM research_evidence WHERE id = ANY(CAST(:i AS uuid[])) AND lifecycle_status = 'ACTIVE'"),
            {"i": sorted(ids)},
        )
    ).all()
    return {str(r[0]) for r in rows}


async def evaluate_and_store(
    session: AsyncSession,
    niche_id: uuid.UUID,
    *,
    criteria: Mapping[str, Criterion] | None = None,
    recommendation: tuple[str, str] | None = None,
    run_id: uuid.UUID | None = None,
    computed_without_ai: bool,
) -> EvaluationOutcome:
    wv = await active_weights(session)
    rules = EvidenceRules.from_json(wv.evidence_rules)
    threshold = await analysis.evaluate_niche(session, niche_id, rules=rules)
    latest = await _latest(session, niche_id)
    if criteria is None:  # tính lại không AI: dùng mức tiêu chí đã đề xuất ở đánh giá gần nhất
        prev = dict(latest["criteria"]) if latest else {}
        criteria = {k: Criterion.from_json(prev.get(k)) for k in CRITERIA}
    referenced = {i for c in criteria.values() for i in c.evidence_ids}
    active = await _active_evidence_ids(session, referenced)
    pruned: dict[str, Criterion] = {}
    for k in CRITERIA:
        c = criteria.get(k) or Criterion(None, "UNKNOWN")
        kept = tuple(i for i in c.evidence_ids if i in active)
        if c.evidence_ids and not kept:  # mọi bằng chứng của tiêu chí đã bị xóa → không còn căn cứ
            c = Criterion(None, "UNKNOWN", c.reason, ())
        else:
            c = Criterion(c.score, c.status, c.reason, kept)
        pruned[k] = c
    opp = compute_opportunity(pruned, wv.weights, float(wv.coverage_threshold))

    counted = (
        (
            await session.execute(
                text(
                    "SELECT l.quality, s.url, e.created_at FROM niche_evidence_links l JOIN research_evidence e"
                    " ON e.id = l.evidence_id JOIN research_sources s ON s.id = e.source_id"
                    " WHERE l.niche_id = :n AND l.counted_for_threshold"
                ),
                {"n": niche_id},
            )
        )
        .mappings()
        .all()
    )
    now = datetime.now(UTC)
    ages = [max(0.0, (now - r["created_at"]).total_seconds() / 86400) for r in counted]
    statuses = [opp.criteria[k]["status"] for k in CRITERIA]
    conf_inputs = ConfidenceInputs(
        independent_groups=threshold.independent_groups,
        qualities=[float(r["quality"]) for r in counted if r["quality"] is not None],
        source_kinds={source_kind(r["url"]) for r in counted},
        ages_days=ages,
        conflicting=statuses.count("CONFLICTING"),
        criteria_with_data=sum(1 for k in CRITERIA if opp.criteria[k]["score"] is not None)
        + statuses.count("CONFLICTING"),
        coverage=float(opp.coverage),
        evidence_status=threshold.status,
    )
    confidence, components = compute_confidence(conf_inputs, wv.confidence_params)
    components["formula_version"] = (wv.confidence_params or {}).get("formula_version", 1)

    niche = (
        await session.execute(
            text(
                "SELECT name, micro_niche, customer_group, core_problem, data_origin, ai_recommendation,"
                " ai_recommendation_reason FROM niches WHERE id = :n"
            ),
            {"n": niche_id},
        )
    ).one()
    monetization = monetization_from(opp.criteria["monetization"])
    flags = risk_flags(
        texts=[niche.name, niche.micro_niche, niche.customer_group, niche.core_problem],
        monetization_status=monetization,
        freshness=float(components["F"]),
        has_evidence=bool(counted),
    )
    rec, rec_reason = recommendation if recommendation else (niche.ai_recommendation, niche.ai_recommendation_reason)
    if threshold.status != "EVIDENCE_SUFFICIENT" and rec != "UNKNOWN":
        rec, rec_reason = "UNKNOWN", "INSUFFICIENT_EVIDENCE"  # AI không đề xuất khi chưa đủ bằng chứng
    await session.execute(
        text(
            "UPDATE niches SET monetization_status = :m, risk_flags = CAST(:f AS text[]), ai_recommendation = :r,"
            " ai_recommendation_reason = :rr, updated_at = now() WHERE id = :n"
        ),
        {"m": monetization, "f": flags, "r": rec, "rr": rec_reason, "n": niche_id},
    )

    same = latest is not None and (
        latest["weights_version_id"] == wv.id
        and dict(latest["criteria"]) == json.loads(json.dumps(opp.criteria))
        and latest["opportunity_score"] == opp.opportunity
        and latest["confidence_score"] == confidence
        and latest["evidence_status"] == threshold.status
        and latest["independent_groups"] == threshold.independent_groups
    )
    if same and latest is not None:
        return EvaluationOutcome(
            uuid.UUID(str(latest["id"])), False, threshold.status, opp.scoring_status, opp.opportunity, confidence
        )
    eval_id = (
        await session.execute(
            text(
                "INSERT INTO niche_evaluations (niche_id, run_id, weights_version_id, criteria, coverage,"
                " scoring_status,"
                " opportunity_score, confidence_score, confidence_components, evidence_status, independent_groups,"
                " computed_without_ai, data_origin) VALUES (:n, :r, :w, CAST(:c AS jsonb), :cov, :ss, :o, :conf,"
                " CAST(:cc AS jsonb), :es, :g, :cwa, :origin) RETURNING id"
            ),
            {
                "n": niche_id,
                "r": run_id,
                "w": wv.id,
                "c": json.dumps(opp.criteria),
                "cov": opp.coverage,
                "ss": opp.scoring_status,
                "o": opp.opportunity,
                "conf": confidence,
                "cc": json.dumps(components),
                "es": threshold.status,
                "g": threshold.independent_groups,
                "cwa": computed_without_ai,
                "origin": niche.data_origin,
            },
        )
    ).scalar_one()
    await session.execute(
        text("UPDATE niches SET latest_evaluation_id = :e WHERE id = :n"), {"e": eval_id, "n": niche_id}
    )
    return EvaluationOutcome(
        uuid.UUID(str(eval_id)), True, threshold.status, opp.scoring_status, opp.opportunity, confidence
    )


def evaluation_dto(row: Any) -> dict[str, Any]:
    r = dict(row)
    criteria = dict(r["criteria"])
    missing = [k for k in CRITERIA if criteria.get(k, {}).get("score") is None]
    return {
        "id": str(r["id"]),
        "run_id": str(r["run_id"]) if r["run_id"] else None,
        "weights_version": r.get("weights_version"),
        "criteria": criteria,
        "coverage": float(r["coverage"]),
        "scoring_status": r["scoring_status"],
        "opportunity_score": float(r["opportunity_score"]) if r["opportunity_score"] is not None else None,
        "confidence_score": float(r["confidence_score"]),
        "confidence_components": {k: v for k, v in dict(r["confidence_components"]).items() if k in "NQDFKV"},
        "evidence_status": r["evidence_status"],
        "independent_groups": r["independent_groups"],
        "missing_data": missing,
        "computed_without_ai": r["computed_without_ai"],
        "data_origin": r["data_origin"],
        "created_at": r["created_at"].isoformat(),
    }


async def list_evaluations(session: AsyncSession, niche_id: uuid.UUID) -> list[dict[str, Any]]:
    rows = (
        (
            await session.execute(
                text(
                    "SELECT e.*, w.version AS weights_version FROM niche_evaluations e JOIN scoring_weights_versions w"
                    " ON w.id = e.weights_version_id WHERE e.niche_id = :n ORDER BY e.created_at DESC"
                ),
                {"n": niche_id},
            )
        )
        .mappings()
        .all()
    )
    return [evaluation_dto(r) for r in rows]
