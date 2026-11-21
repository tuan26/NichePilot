"""Confidence (T094; scoring-rubric §3; FR-020) – tách biệt Opportunity (không nhận Opportunity làm đầu vào).

N = min(1, nhóm độc lập / 6); Q = quality trung bình của bằng chứng hợp lệ; D = min(1, số loại nguồn / 3);
F = trung bình max(0, 1 − tuổi/freshness_days); K = 1 − #CONFLICTING / #tiêu chí có dữ liệu hoặc CONFLICTING (không
có → 0);
V = Coverage / 100. Confidence = round(100 × Σ C·w, 2); INSUFFICIENT_EVIDENCE → min(·, insufficient_cap).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit

from nichepilot.modules.discovery.scoring.opportunity import q2

DEFAULT_WEIGHTS = {"N": 0.25, "Q": 0.20, "D": 0.15, "F": 0.15, "K": 0.15, "V": 0.10}


@dataclass(frozen=True)
class ConfidenceInputs:
    independent_groups: int
    qualities: list[float]
    source_kinds: set[str]
    ages_days: list[float]
    conflicting: int
    criteria_with_data: int
    coverage: float
    evidence_status: str


def source_kind(url: str) -> str:
    """Loại nguồn (diễn đàn, đánh giá, hỏi-đáp, video, bài viết, khác) – heuristic xác định theo tên miền/đường dẫn."""
    parts = urlsplit(url.lower())
    host, path = parts.hostname or "", parts.path
    if any(h in host for h in ("youtube.", "youtu.be", "vimeo.")):
        return "video"
    if any(h in host for h in ("stackoverflow.", "stackexchange.", "quora.", "superuser.", "serverfault.")):
        return "qa"
    if "reddit." in host or "forum" in host or "community" in host or "/t/" in path or "/thread" in path:
        return "forum"
    if "review" in host or "review" in path or "trustpilot." in host or "g2." in host or "capterra." in host:
        return "review"
    if "blog" in host or "/blog" in path or "/post" in path or "/article" in path or "news" in host:
        return "article"
    return "other"


def compute_confidence(
    inp: ConfidenceInputs, params: Mapping[str, Any] | None = None
) -> tuple[Decimal, dict[str, Any]]:
    p = dict(params or {})
    w = {**DEFAULT_WEIGHTS, **dict(p.get("weights") or {})}
    fresh_days = float(p.get("freshness_days", 730))
    cap = float(p.get("insufficient_cap", 30))
    n = min(1.0, inp.independent_groups / 6)
    q = sum(inp.qualities) / len(inp.qualities) if inp.qualities else 0.0
    d = min(1.0, len(inp.source_kinds) / 3)
    f = sum(max(0.0, 1 - a / fresh_days) for a in inp.ages_days) / len(inp.ages_days) if inp.ages_days else 0.0
    k = 1 - inp.conflicting / inp.criteria_with_data if inp.criteria_with_data > 0 else 0.0
    v = max(0.0, min(1.0, inp.coverage / 100))
    comp = {"N": n, "Q": q, "D": d, "F": f, "K": k, "V": v}
    total = sum(Decimal(str(comp[x])) * Decimal(str(w[x])) for x in comp) * 100
    score = q2(total)
    if inp.evidence_status != "EVIDENCE_SUFFICIENT":
        score = min(score, q2(cap))
    return score, {
        **{x: round(val, 6) for x, val in comp.items()},
        "weights": w,
        "freshness_days": fresh_days,
        "insufficient_cap": cap,
    }
