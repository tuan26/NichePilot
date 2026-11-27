"""Keyword Opportunity + Coverage (scoring-rubric §3; FR-017, FR-018) – điểm ưu tiên nghiên cứu, KHÔNG phải dự báo
traffic/doanh thu.

V = tiêu chí có mức; Coverage = Σ_{V} w; Opportunity = Σ_{V} level·w / Σ_{V} w nếu Coverage ≥ coverage_min ∧ `fit` ∈ V.
Mã thuần, không AI, không nhận Confidence làm đầu vào.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from nichepilot.modules.keywords.scoring.criteria import CRITERIA_KEYS, Criterion


def q2(x: Decimal | float) -> Decimal:
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class OpportunityResult:
    opportunity: Decimal | None
    coverage: Decimal
    scoring_status: str
    missing: tuple[str, ...]


def validate_weights(weights: Mapping[str, float]) -> dict[str, Decimal]:
    if set(weights) != set(CRITERIA_KEYS):
        raise ValueError("weights must have exactly the 5 keyword criteria")
    w = {k: Decimal(str(v)) for k, v in weights.items()}
    if any(v < 0 or v > 100 for v in w.values()) or sum(w.values()) != Decimal(100):
        raise ValueError("weights must be within 0..100 and sum to 100")
    return w


def compute_opportunity(
    criteria: Mapping[str, Criterion], weights: Mapping[str, float], coverage_min: float | Decimal = 60
) -> OpportunityResult:
    w = validate_weights(weights)
    valid = [k for k in CRITERIA_KEYS if criteria.get(k) is not None and criteria[k].level is not None]
    missing = tuple(k for k in CRITERIA_KEYS if k not in valid)
    coverage = sum((w[k] for k in valid), Decimal(0))
    if coverage == 0 or coverage < Decimal(str(coverage_min)) or "fit" not in valid:
        return OpportunityResult(None, q2(coverage), "INSUFFICIENT_SCORING_DATA", missing)
    total = sum((Decimal(criteria[k].level or 0) * w[k] for k in valid), Decimal(0))
    return OpportunityResult(q2(total / coverage), q2(coverage), "SCORED", missing)
