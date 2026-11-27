"""Truy vấn tìm kiếm xác định cho E2 (research R-02; FR-011) – không dùng AI, mẫu lấy từ phiên bản trọng số
(`query_templates`)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

DEFAULT_TEMPLATES: dict[str, Any] = {
    "max_pain_points": 3,
    "niche": ["{pain_point} {segment} tool", "best {kind} for {segment}"],
    "product": ["{product} pricing", "{product} affiliate program"],
}
_MOCK_PREFIXES = ("[MOCK DEMO]", "[MOCK]")


@dataclass(frozen=True)
class PainPointInput:
    id: str
    title: str
    severity: int | None


def clean(text: str | None) -> str:
    out = (text or "").strip()
    for p in _MOCK_PREFIXES:
        out = out.replace(p, " ")
    return " ".join(out.split())


def _dedupe(items: Sequence[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for q in items:
        q = " ".join(q.split())
        if q and q.lower() not in seen:
            seen.add(q.lower())
            out.append(q)
    return out


def niche_queries(
    pain_points: Sequence[PainPointInput], segment: str | None, kind: str | None, templates: Mapping[str, Any] | None
) -> list[str]:
    t = {**DEFAULT_TEMPLATES, **dict(templates or {})}
    top = sorted(pain_points, key=lambda p: (-(p.severity or 0), p.title))[: int(t["max_pain_points"])]
    seg = clean(segment) or "small business"
    knd = clean(kind) or "software"
    out: list[str] = []
    for tpl in t["niche"]:
        if "{pain_point}" in tpl:
            out += [tpl.format(pain_point=clean(p.title), segment=seg, kind=knd) for p in top]
        else:
            out.append(tpl.format(segment=seg, kind=knd, pain_point=""))
    return _dedupe(out)


def product_queries(product_name: str, templates: Mapping[str, Any] | None) -> list[str]:
    t = {**DEFAULT_TEMPLATES, **dict(templates or {})}
    return _dedupe([tpl.format(product=clean(product_name)) for tpl in t["product"]])
