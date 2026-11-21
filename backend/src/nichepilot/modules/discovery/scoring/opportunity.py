"""Opportunity + Coverage (T093; scoring-rubric §2–§3; FR-017, FR-019, FR-019a, FR-021).

`Opportunity = Σ s_i·w_i / Σ w_i` chỉ trên tiêu chí có dữ liệu HỢP LỆ; `Coverage = Σ w_i` (trọng số gốc). Coverage <
ngưỡng →
`INSUFFICIENT_SCORING_DATA`, không có Opportunity. Tiêu chí hợp lệ: điểm ∈ {0,25,50,75,100}, trạng thái
VERIFIED/INFERRED, có lý do
và ≥ 1 bằng chứng. UNKNOWN, CONFLICTING, điểm ngoài thang, thiếu bằng chứng → coi như UNKNOWN (không bao giờ gán
0/100 mặc định).
Không có đầu vào search volume (FR-021).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

CRITERIA = (
    "problem_severity",
    "monetization",
    "market_gap",
    "reachability",
    "competition_opportunity",
    "demand_stability",
)
LEVELS = (0, 25, 50, 75, 100)
TWO = Decimal("0.01")


@dataclass(frozen=True)
class Criterion:
    score: int | None
    status: str
    reason: str = ""
    evidence_ids: tuple[str, ...] = ()

    def is_valid(self) -> bool:
        return (
            self.score in LEVELS
            and self.status in ("VERIFIED", "INFERRED")
            and bool(self.reason.strip())
            and bool(self.evidence_ids)
        )

    @classmethod
    def from_json(cls, d: Mapping[str, Any] | None) -> Criterion:
        if not d:
            return cls(score=None, status="UNKNOWN", reason="")
        return cls(
            score=d.get("score"),
            status=str(d.get("status") or "UNKNOWN"),
            reason=str(d.get("reason") or ""),
            evidence_ids=tuple(str(i) for i in d.get("evidence_ids") or ()),
        )


@dataclass(frozen=True)
class OpportunityResult:
    coverage: Decimal
    scoring_status: str
    opportunity: Decimal | None
    criteria: dict[str, dict[str, Any]] = field(default_factory=dict)


def q2(x: float | Decimal) -> Decimal:
    return Decimal(str(x)).quantize(TWO, rounding=ROUND_HALF_UP)


def validate_weights(weights: Mapping[str, float]) -> None:
    if set(weights) != set(CRITERIA):
        raise ValueError("trọng số phải có đúng 6 tiêu chí")
    if any(float(w) < 0 for w in weights.values()):
        raise ValueError("trọng số không được âm")
    if abs(sum(float(w) for w in weights.values()) - 100) > 1e-9:
        raise ValueError("tổng trọng số phải bằng 100")


def normalize_criterion(c: Criterion) -> Criterion:
    """Chuẩn hóa: tiêu chí không hợp lệ → UNKNOWN/CONFLICTING không điểm (giữ lý do, bằng chứng để hiển thị)."""
    if c.is_valid():
        return c
    status = "CONFLICTING" if c.status == "CONFLICTING" else "UNKNOWN"
    return Criterion(score=None, status=status, reason=c.reason, evidence_ids=c.evidence_ids)


def compute_opportunity(
    criteria: Mapping[str, Criterion], weights: Mapping[str, float], coverage_threshold: float = 60
) -> OpportunityResult:
    validate_weights(weights)
    if set(criteria) - set(CRITERIA):
        raise ValueError("tiêu chí lạ")
    norm = {k: normalize_criterion(criteria.get(k) or Criterion(None, "UNKNOWN")) for k in CRITERIA}
    valid = [k for k in CRITERIA if norm[k].score is not None]
    cov = sum(Decimal(str(weights[k])) for k in valid)
    out: dict[str, dict[str, Any]] = {}
    for k in CRITERIA:
        c = norm[k]
        w = float(weights[k])
        out[k] = {
            "score": c.score,
            "status": c.status,
            "reason": c.reason,
            "evidence_ids": list(c.evidence_ids),
            "weight": w,
            "normalized_weight": round(w / float(cov), 6) if c.score is not None and cov > 0 else None,
        }
    if cov <= 0 or cov < Decimal(str(coverage_threshold)):
        return OpportunityResult(q2(cov), "INSUFFICIENT_SCORING_DATA", None, out)
    total = sum(Decimal(norm[k].score or 0) * Decimal(str(weights[k])) for k in valid)
    return OpportunityResult(q2(cov), "SCORED", q2(total / cov), out)
