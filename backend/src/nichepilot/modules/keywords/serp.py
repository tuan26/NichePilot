"""SERP quan sát được (research R-05, R-09; FR-012, FR-031) – mã thuần.

Loại trang dùng heuristic `source_kind` của E1 (chỉ gọi, không sửa) và bổ sung `product` cho trang giá/sản phẩm. Thứ
hạng là vị trí
quan sát trong kết quả của nguồn `ALLOWED` tại thời điểm thu thập – không phải thứ hạng Google chính thức.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit

from nichepilot.modules.discovery.fingerprint import registered_domain
from nichepilot.modules.discovery.scoring.confidence import source_kind

PAGE_TYPES = ("forum", "qa", "video", "review", "article", "product", "other")


def page_type(url: str, title: str | None = None) -> str:
    kind = source_kind(url)
    if kind != "other":
        return kind
    path = (urlsplit(url.lower()).path or "") + " " + (title or "").lower()
    if any(x in path for x in ("/pricing", "/product", "/plans", " pricing")):
        return "product"
    return "other"


def results_from_hits(hits: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Kết quả SERP từ `source.query` (đã che PII trong tool); bỏ trùng URL, giữ vị trí quan sát."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for h in hits:
        url = str(h.get("url") or "")
        if not url or url in seen or h.get("redaction_status") not in (None, "REDACTED"):
            continue
        seen.add(url)
        title = h.get("title")
        out.append(
            {
                "position": len(out) + 1,
                "url": url,
                "domain": registered_domain(url),
                "title": title,
                "page_type": page_type(url, title),
            }
        )
    return out


def diff_results(old: Sequence[Mapping[str, Any]] | None, new: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Thay đổi giữa hai quan sát: URL vào/ra, đổi vị trí, đổi loại trang. Không đổi → `{}`."""
    if old is None:
        return {}
    o = {str(r["url"]): r for r in old}
    n = {str(r["url"]): r for r in new}
    added = [u for u in n if u not in o]
    removed = [u for u in o if u not in n]
    moved = [
        {"url": u, "from": o[u].get("position"), "to": n[u].get("position")}
        for u in n
        if u in o and o[u].get("position") != n[u].get("position")
    ]
    retyped = [
        {"url": u, "from": o[u].get("page_type"), "to": n[u].get("page_type")}
        for u in n
        if u in o and o[u].get("page_type") != n[u].get("page_type")
    ]
    changes = {"added": added, "removed": removed, "moved": moved, "retyped": retyped}
    return {k: v for k, v in changes.items() if v}


def forum_qa_count(results: Sequence[Mapping[str, Any]] | None) -> int:
    return sum(1 for r in results or [] if r.get("page_type") in ("forum", "qa"))


def intent_signal(
    intent: str, results: Sequence[Mapping[str, Any]] | None, pages: Sequence[Mapping[str, Any]] = ()
) -> bool:
    """Intent có tín hiệu quan sát từ SERP (→ `VERIFIED`) khi loại trang quan sát phù hợp intent; NAVIGATIONAL không
    suy được."""
    if not results:
        return False
    types = {str(r.get("page_type")) for r in results}
    if intent == "INFORMATIONAL":
        return bool(types & {"article", "forum", "qa", "video"})
    if intent == "COMMERCIAL_INVESTIGATION":
        return "review" in types or any((p.get("summary") or {}).get("has_comparison") for p in pages)
    if intent == "TRANSACTIONAL":
        return "product" in types or any((p.get("summary") or {}).get("has_pricing") for p in pages)
    return False
