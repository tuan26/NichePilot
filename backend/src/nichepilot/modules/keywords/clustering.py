"""Gom cluster keyword (Clarification (b); FR-016) – mã thuần, xác định.

Cluster = cùng nguồn gốc chính + cùng intent. Nguồn gốc chính ưu tiên pain point → sản phẩm → thuộc tính persona (chọn
id nhỏ nhất khi
có nhiều). Điểm cluster = trung bình Opportunity của keyword `SCORED`; Confidence = trung bình; không có keyword
`SCORED` → None.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from nichepilot.modules.keywords.scoring.opportunity import q2

_PRIORITY = (
    ("PAIN_POINT", "pain_point_id", "pp"),
    ("PRODUCT", "product_id", "pr"),
    ("PERSONA", "persona_attribute", "pe"),
)


def primary_origin(origins: Iterable[Mapping[str, Any]]) -> tuple[str, str]:
    """(loại, id) nguồn gốc chính."""
    items = list(origins)
    for kind, key, _ in _PRIORITY:
        ids = sorted(str(o[key]) for o in items if o.get("origin_type") == kind and o.get(key))
        if ids:
            return kind, ids[0]
    raise ValueError("keyword has no origin")


def cluster_key(origins: Iterable[Mapping[str, Any]], intent: str) -> str:
    kind, ref = primary_origin(origins)
    prefix = {k: p for k, _, p in _PRIORITY}[kind]
    return f"{prefix}:{ref}|{intent}"


@dataclass(frozen=True)
class Member:
    keyword_id: str
    text: str
    length_class: str
    opportunity: Decimal | None
    confidence: Decimal | None


def choose_primary(members: Sequence[Member]) -> str:
    """Keyword chính: Opportunity cao nhất (SCORED trước), hòa → Confidence, hòa → LONG_TAIL trước, hòa → chữ cái."""
    if not members:
        raise ValueError("empty cluster")

    def key(m: Member) -> tuple[Any, ...]:
        return (
            m.opportunity is None,
            -(m.opportunity or Decimal(0)),
            -(m.confidence or Decimal(0)),
            m.length_class != "LONG_TAIL",
            m.text.lower(),
        )

    return sorted(members, key=key)[0].keyword_id


def cluster_scores(members: Sequence[Member]) -> tuple[Decimal | None, Decimal | None, int]:
    scored = [m for m in members if m.opportunity is not None]
    if not scored:
        return None, None, 0
    opp = sum((m.opportunity or Decimal(0) for m in scored), Decimal(0)) / len(scored)
    conf = sum((m.confidence or Decimal(0) for m in scored), Decimal(0)) / len(scored)
    return q2(opp), q2(conf), len(scored)
