"""Keyword Confidence (scoring-rubric §3; FR-019; BR-04) – tách biệt Opportunity (không nhận Opportunity làm đầu vào).

S = 1 nếu có quan sát SERP; D = min(1, #tên miền bằng chứng / domain_target); F = trung bình max(0, 1 −
tuổi/freshness_days);
O = #tiêu chí quan sát (competition, content_gap, demand từ SERP) / 3; V = Coverage/100. Confidence = round(100 × Σ
C·w, 2).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from nichepilot.modules.keywords.scoring.opportunity import q2

DEFAULT_WEIGHTS = {"S": 0.25, "D": 0.20, "F": 0.15, "O": 0.20, "V": 0.20}


@dataclass(frozen=True)
class ConfidenceInputs:
    has_serp: bool
    source_domains: int
    ages_days: list[float]
    observed_criteria: int
    coverage: float


def compute_confidence(
    inp: ConfidenceInputs, params: Mapping[str, Any] | None = None
) -> tuple[Decimal, dict[str, Any]]:
    p = dict(params or {})
    w = {**DEFAULT_WEIGHTS, **dict(p.get("weights") or {})}
    target = float(p.get("domain_target", 4))
    fresh = float(p.get("freshness_days", 180))
    s = 1.0 if inp.has_serp else 0.0
    d = min(1.0, inp.source_domains / target) if target > 0 else 0.0
    f = sum(max(0.0, 1 - x / fresh) for x in inp.ages_days) / len(inp.ages_days) if inp.ages_days else 0.0
    o = max(0.0, min(1.0, inp.observed_criteria / 3))
    v = max(0.0, min(1.0, inp.coverage / 100))
    comp = {"S": s, "D": d, "F": f, "O": o, "V": v}
    total = sum(Decimal(str(comp[x])) * Decimal(str(w[x])) for x in comp) * 100
    return q2(total), {**{x: round(val, 6) for x, val in comp.items()}, "weights": w}
