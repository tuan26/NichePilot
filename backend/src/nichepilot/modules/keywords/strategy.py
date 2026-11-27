"""Kiểm tra persona cấp cluster và content strategy do AI đề xuất (research R-08; FR-022, FR-024; BR-11).

- Thuộc tính persona không có bằng chứng thuộc cluster → `UNKNOWN`.
- Câu chứa tuyên bố trải nghiệm ("we tested", "đã dùng thử"…) bị loại khi không có bằng chứng trải nghiệm (BR-11) –
đếm `rejected_claims`.
- id pain point/sản phẩm/keyword ngoài cluster bị bỏ; loại nội dung ngoài danh mục đã bị schema chặn.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from nichepilot.modules.keywords.schemas import CitedText, ClusterStrategyOut

PERSONA_KEYS = ("goals", "barriers", "knowledge_level", "typical_questions")
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class ClusterContext:
    cluster_id: str
    evidence_ids: frozenset[str]
    pain_point_ids: frozenset[str]
    product_ids: frozenset[str]
    keyword_ids: frozenset[str]
    gap_pain_point_ids: frozenset[str]
    has_experience_evidence: bool = False


@dataclass
class StrategyValidation:
    insights: dict[str, dict[str, Any]] = field(default_factory=dict)
    rejected_claims: int = 0
    rejected_items: int = 0


def strip_claims(text: str, terms: Iterable[str]) -> tuple[str, int]:
    """Bỏ câu chứa tuyên bố trải nghiệm; trả (văn bản còn lại, số câu bị bỏ)."""
    low_terms = [t.lower() for t in terms if t]
    kept, dropped = [], 0
    for sentence in _SENTENCE.split(text.strip()):
        if any(t in sentence.lower() for t in low_terms):
            dropped += 1
            continue
        if sentence:
            kept.append(sentence)
    return " ".join(kept).strip(), dropped


def _persona_attr(
    item: CitedText | None, ctx: ClusterContext, terms: Iterable[str], v: StrategyValidation
) -> dict[str, Any]:
    if item is None or not set(item.evidence_ids) <= ctx.evidence_ids:
        return {"status": "UNKNOWN", "value": None, "evidence_ids": []}
    value, dropped = strip_claims(item.value, [] if ctx.has_experience_evidence else terms)
    v.rejected_claims += dropped
    if not value:
        return {"status": "UNKNOWN", "value": None, "evidence_ids": []}
    return {"status": "INFERRED", "value": value, "evidence_ids": list(item.evidence_ids)}


def validate_strategy(
    clusters: Iterable[ClusterStrategyOut], contexts: Mapping[str, ClusterContext], claim_terms: Iterable[str]
) -> StrategyValidation:
    terms = list(claim_terms)
    v = StrategyValidation()
    for c in clusters:
        ctx = contexts.get(c.cluster_id)
        if ctx is None:
            v.rejected_items += 1
            continue
        persona = {k: _persona_attr(getattr(c.persona, k), ctx, terms, v) for k in PERSONA_KEYS}
        strategy: dict[str, Any] = {"status": "UNKNOWN"}
        if c.strategy is not None:
            s = c.strategy
            angle, dropped = strip_claims(s.angle, [] if ctx.has_experience_evidence else terms)
            v.rejected_claims += dropped
            if angle:
                primary = s.primary_keyword_id if s.primary_keyword_id in ctx.keyword_ids else None
                strategy = {
                    "status": "INFERRED",
                    "content_type": s.content_type,
                    "angle": angle,
                    "pain_point_ids": [x for x in s.pain_point_ids if x in ctx.pain_point_ids],
                    "product_ids": [x for x in s.product_ids if x in ctx.product_ids],
                    "primary_keyword_id": primary,
                    "secondary_keyword_ids": [
                        x for x in s.secondary_keyword_ids if x in ctx.keyword_ids and x != primary
                    ],
                    "gap_refs": [x for x in s.gap_refs if x in ctx.gap_pain_point_ids],
                }
        v.insights[c.cluster_id] = {"persona": persona, "strategy": strategy}
    return v
