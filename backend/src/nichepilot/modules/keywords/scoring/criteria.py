"""Mức 5 tiêu chí Keyword Opportunity (contracts/scoring-rubric.md §2; Clarification Q1 = A).

Mã thuần, xác định. Thiếu dữ liệu → `level = None` (không gán điểm giả – FR-018). Ngưỡng lấy từ `rubric` của phiên bản
trọng số.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

CRITERIA_KEYS = ("fit", "intent_value", "competition", "content_gap", "demand")
VALID_LEVELS = (0, 25, 50, 75, 100)
DEFAULT_RUBRIC: dict[str, Any] = {
    "intent_value": {
        "COMMERCIAL_INVESTIGATION": 100,
        "INFORMATIONAL_PROBLEM": 75,
        "TRANSACTIONAL": 75,
        "INFORMATIONAL": 25,
        "NAVIGATIONAL": 0,
    },
    "competition_levels": [[0.5, 100], [0.3, 75], [0.2, 50], [0.0001, 25]],
    "content_gap_levels": [[0.75, 100], [0.5, 75], [0.25, 50], [0.0001, 25]],
    "demand_levels": [[6, 100], [4, 75], [3, 50], [1, 25]],
    "weak_page_types": ["forum", "qa"],
}


@dataclass(frozen=True)
class Criterion:
    level: int | None
    status: str  # OBSERVED | INFERRED | UNKNOWN
    reason: str = ""
    evidence_ids: tuple[str, ...] = ()
    inputs: dict[str, Any] = field(default_factory=dict)

    def as_json(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "status": self.status,
            "reason": self.reason,
            "evidence_ids": list(self.evidence_ids),
            "inputs": self.inputs,
        }


def _unknown(reason: str, **inputs: Any) -> Criterion:
    return Criterion(None, "UNKNOWN", reason, (), inputs)


def _rubric(rubric: Mapping[str, Any] | None) -> dict[str, Any]:
    return {**DEFAULT_RUBRIC, **dict(rubric or {})}


def level_for(value: float, levels: Sequence[Sequence[float]], below: int = 0) -> int:
    """Mức đầu tiên có `value ≥ ngưỡng` (ngưỡng giảm dần); không đạt ngưỡng nào → `below`."""
    for threshold, lvl in levels:
        if value >= float(threshold):
            return int(lvl)
    return below


def fit(ai: Mapping[str, Any] | None, *, has_valid_origin: bool, allowed_evidence: Iterable[str]) -> Criterion:
    """AI đề xuất mức; hợp lệ khi mức ∈ thang, có lý do, keyword có origin hợp lệ, evidence_ids ⊆ bằng chứng gốc
    ACTIVE."""
    if not ai or ai.get("level") is None:
        return _unknown("no_ai_level")
    level = ai.get("level")
    reason = str(ai.get("reason") or "").strip()
    ids = [str(x) for x in ai.get("evidence_ids") or []]
    allowed = {str(x) for x in allowed_evidence}
    if level not in VALID_LEVELS or not reason or not has_valid_origin:
        return _unknown("invalid_ai_level")
    if not ids or not set(ids) <= allowed:
        return _unknown("evidence_not_allowed")
    return Criterion(int(level), "INFERRED", reason, tuple(ids))


def intent_value(intent: str, keyword_type: str, rubric: Mapping[str, Any] | None = None) -> Criterion:
    table = dict(_rubric(rubric)["intent_value"])
    key = intent
    if intent == "INFORMATIONAL" and keyword_type in ("PROBLEM", "SOLUTION"):
        key = "INFORMATIONAL_PROBLEM"
    if key not in table:
        return _unknown("intent_not_in_rubric", intent=intent)
    return Criterion(int(table[key]), "INFERRED", key, (), {"intent": intent, "keyword_type": keyword_type})


def competition(
    results: Sequence[Mapping[str, Any]] | None,
    *,
    uncovering_urls: Iterable[str] = (),
    rubric: Mapping[str, Any] | None = None,
) -> Criterion:
    """Tỷ lệ kết quả "yếu" (forum/Q&A hoặc trang đối thủ không phủ pain point chính) trong SERP quan sát."""
    if not results:
        return _unknown("no_serp")
    r = _rubric(rubric)
    weak_types = set(r["weak_page_types"])
    uncovering = set(uncovering_urls)
    weak = [x for x in results if x.get("page_type") in weak_types or x.get("url") in uncovering]
    share = len(weak) / len(results)
    return Criterion(
        level_for(share, r["competition_levels"]),
        "OBSERVED",
        f"weak_share={share:.4f}",
        (),
        {"weak": len(weak), "results": len(results), "share": round(share, 4)},
    )


def content_gap(
    origin_pain_point_ids: Iterable[str],
    covered_sets: Sequence[Iterable[str]] | None,
    rubric: Mapping[str, Any] | None = None,
) -> Criterion:
    """Tỷ lệ pain point gốc chưa trang đối thủ nào phủ; không có trang đối thủ/pain point gốc → UNKNOWN."""
    origins = sorted({str(x) for x in origin_pain_point_ids})
    if not covered_sets:
        return _unknown("no_competitor_pages")
    if not origins:
        return _unknown("no_origin_pain_points")
    covered: set[str] = set()
    for s in covered_sets:
        covered |= {str(x) for x in s}
    gaps = [p for p in origins if p not in covered]
    ratio = len(gaps) / len(origins)
    return Criterion(
        level_for(ratio, _rubric(rubric)["content_gap_levels"]),
        "OBSERVED",
        f"gap_ratio={ratio:.4f}",
        (),
        {"gaps": gaps, "origins": len(origins), "pages": len(covered_sets), "ratio": round(ratio, 4)},
    )


def demand(evidence_groups: int, forum_qa_results: int, rubric: Mapping[str, Any] | None = None) -> Criterion:
    """n = nhóm nguồn độc lập của bằng chứng pain point gốc (E1) + kết quả SERP forum/Q&A; n = 0 → UNKNOWN."""
    n = max(0, int(evidence_groups)) + max(0, int(forum_qa_results))
    if n == 0:
        return _unknown("no_demand_evidence")
    status = "OBSERVED" if forum_qa_results > 0 else "INFERRED"
    return Criterion(
        level_for(n, _rubric(rubric)["demand_levels"]),
        status,
        f"n={n}",
        (),
        {"evidence_groups": evidence_groups, "forum_qa_results": forum_qa_results},
    )
