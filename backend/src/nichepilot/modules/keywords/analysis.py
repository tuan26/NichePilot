"""Phân tích đối thủ, content gap, kênh tiếp cận (research R-05, R-06; FR-013, FR-014, FR-023) – mã thuần.

AI chỉ trả tóm tắt cấu trúc có dẫn bằng chứng; mã kiểm URL/bằng chứng/pain point. Gap và kênh do mã suy ra từ dữ liệu
quan sát; không có
quan sát → `UNKNOWN` (không dữ liệu thay thế).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from nichepilot.modules.keywords.schemas import KeywordsAnalyzeOutput

CHANNEL_TYPES = ("forum", "qa", "video")


@dataclass
class PageValidation:
    kept: list[dict[str, Any]] = field(default_factory=list)
    rejected: int = 0


def validate_page_summaries(
    out: KeywordsAnalyzeOutput, *, page_evidence: Mapping[str, set[str]], pain_point_ids: Iterable[str]
) -> PageValidation:
    """Giữ tóm tắt khi URL thuộc trang đã tải, mọi evidence_id thuộc trang đó và mọi pain point thuộc ngách; ngược lại
    loại cả trang."""
    known = {str(x) for x in pain_point_ids}
    v = PageValidation()
    for page in out.pages:
        allowed = page_evidence.get(page.url)
        if allowed is None or not set(page.evidence_ids) <= allowed:
            v.rejected += 1
            continue
        if not set(page.covered_pain_point_ids) <= known:
            v.rejected += 1
            continue
        v.kept.append(
            {
                "url": page.url,
                "evidence_id": page.evidence_ids[0],
                "summary": {
                    "headings": [h[:200] for h in page.headings[:10]],
                    "topics": [t[:200] for t in page.topics[:15]],
                    "has_comparison": page.has_comparison,
                    "has_pricing": page.has_pricing,
                    "has_experience_evidence": page.has_experience_evidence,
                    "covered_pain_point_ids": sorted(set(page.covered_pain_point_ids)),
                    "evidence_ids": list(page.evidence_ids),
                },
            }
        )
    return v


def content_gaps(pain_points: Mapping[str, str], pages: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Pain point của cluster mà không trang đối thủ nào phủ → gap (bằng chứng = các trang đã xét)."""
    if not pages:
        return {"status": "UNKNOWN", "items": [], "reason": "no_competitor_pages"}
    covered: set[str] = set()
    for p in pages:
        covered |= {str(x) for x in (p.get("summary") or {}).get("covered_pain_point_ids") or []}
    urls = sorted({str(p["url"]) for p in pages})
    items = [
        {"pain_point_id": pid, "title": title, "checked_urls": urls}
        for pid, title in sorted(pain_points.items())
        if pid not in covered
    ]
    return {"status": "OBSERVED", "items": items, "pages_checked": len(urls)}


def channels(results: Sequence[Mapping[str, Any]] | None) -> dict[str, Any]:
    """Cộng đồng/kênh nơi khách hàng thảo luận = kết quả SERP loại forum/Q&A/video (FR-023)."""
    if not results:
        return {"status": "UNKNOWN", "items": [], "reason": "no_serp"}
    by_domain: dict[str, dict[str, Any]] = {}
    for r in results:
        if r.get("page_type") not in CHANNEL_TYPES:
            continue
        d = str(r.get("domain") or "")
        item = by_domain.setdefault(d, {"domain": d, "kind": r["page_type"], "evidence_urls": []})
        if r["url"] not in item["evidence_urls"]:
            item["evidence_urls"].append(r["url"])
    items = sorted(by_domain.values(), key=lambda x: (-len(x["evidence_urls"]), x["domain"]))
    return {"status": "OBSERVED", "items": items}
