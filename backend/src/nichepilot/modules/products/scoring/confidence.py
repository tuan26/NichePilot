"""Product Confidence (scoring-rubric §3; FR-029; BR-04) – tách biệt Opportunity (không nhận Opportunity làm đầu vào).

A = #thuộc tính bắt buộc VERIFIED / #bắt buộc; D = min(1, #tên miền nguồn / domain_target); F = trung bình max(0, 1 −
tuổi/freshness_days);
K = 1 − #CONFLICTING / #thuộc tính có dữ liệu hoặc CONFLICTING (không có → 0); V = Coverage/100. Confidence =
round(100 × Σ C·w, 2).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from nichepilot.modules.products.scoring.opportunity import q2

DEFAULT_WEIGHTS = {"A": 0.30, "D": 0.20, "F": 0.15, "K": 0.15, "V": 0.20}


@dataclass(frozen=True)
class ConfidenceInputs:
    required_total: int
    required_verified: int
    source_domains: int
    ages_days: list[float]
    conflicting: int
    with_data_or_conflicting: int
    coverage: float


def compute_confidence(
    inp: ConfidenceInputs, params: Mapping[str, Any] | None = None
) -> tuple[Decimal, dict[str, Any]]:
    p = dict(params or {})
    w = {**DEFAULT_WEIGHTS, **dict(p.get("weights") or {})}
    target = float(p.get("domain_target", 4))
    fresh = float(p.get("freshness_days", 365))
    a = inp.required_verified / inp.required_total if inp.required_total else 0.0
    d = min(1.0, inp.source_domains / target) if target > 0 else 0.0
    f = sum(max(0.0, 1 - x / fresh) for x in inp.ages_days) / len(inp.ages_days) if inp.ages_days else 0.0
    k = 1 - inp.conflicting / inp.with_data_or_conflicting if inp.with_data_or_conflicting > 0 else 0.0
    v = max(0.0, min(1.0, inp.coverage / 100))
    comp = {"A": a, "D": d, "F": f, "K": k, "V": v}
    total = sum(Decimal(str(comp[x])) * Decimal(str(w[x])) for x in comp) * 100
    return q2(total), {**{x: round(val, 6) for x, val in comp.items()}, "weights": w}
