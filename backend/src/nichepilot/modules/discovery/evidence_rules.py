"""Ngưỡng bằng chứng + nhóm nguồn độc lập – logic xác định, thuần, không I/O (T079; scoring-rubric §1).

- Bằng chứng **hợp lệ** (FR-013a, FR-013b): đủ URL nguồn, trích đoạn (đã che), thời điểm thu thập, trạng thái
  xác minh (VERIFIED/INFERRED/CONFLICTING – không phải UNKNOWN); `purpose = PAIN_POINT`; `ACTIVE`; `REDACTED`;
  relevance ≥ ngưỡng; quality ≥ ngưỡng; không `copy_suspected`; cùng `data_origin` với ngách (MOCK tính riêng).
- **Nhóm độc lập** (FR-013b, FR-015): hai bằng chứng cùng nhóm nếu cùng eTLD+1 **hoặc** SimHash trích đoạn ≤ d
  **hoặc** SimHash toàn nguồn ≤ d **hoặc** cùng `content_hash` **hoặc** tỉ lệ chứa shingle 3 từ ≥ 0,5 (bản gần giống
  mà SimHash bỏ sót). Nhóm = thành phần liên thông (union-find) trên MỌI bằng chứng ACTIVE của ngách (thận trọng:
  bằng chứng không hợp lệ vẫn nối được các bản sao) – chỉ đếm nhóm có bằng chứng hợp lệ.
- Đánh giá của AI (relevance, quality, copy_suspected) chỉ là đầu vào `INFERRED`; đếm và so ngưỡng nằm ở đây.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from nichepilot.modules.discovery.fingerprint import (
    hamming,
    normalize,
    registered_domain,
    shingle_containment,
    simhash64,
)

EvidenceStatus = Literal["EVIDENCE_SUFFICIENT", "INSUFFICIENT_EVIDENCE"]
COUNTABLE_STATUSES = ("VERIFIED", "INFERRED", "CONFLICTING")


@dataclass(frozen=True)
class EvidenceRules:
    min_items: int = 2
    min_independent_groups: int = 2
    min_relevance: float = 0.6
    min_quality: float = 0.5
    simhash_max_distance: int = 3
    # Bổ sung (phát hiện bản gần giống mà SimHash 64-bit bỏ sót khi sửa vài từ): tỉ lệ chứa shingle 3 từ ≥ ngưỡng →
    # cùng nhóm.
    # Chỉ áp dụng cho trích đoạn ≥ min_tokens_for_overlap từ (tránh trùng ngẫu nhiên ở câu ngắn). Thận trọng: chỉ GỘP
    # thêm nhóm.
    shingle_overlap_min: float = 0.5
    min_tokens_for_overlap: int = 12

    @classmethod
    def from_json(cls, data: Mapping[str, Any] | None) -> EvidenceRules:
        d = dict(data or {})
        rules = cls(
            min_items=int(d.get("min_items", cls.min_items)),
            min_independent_groups=int(d.get("min_independent_groups", cls.min_independent_groups)),
            min_relevance=float(d.get("min_relevance", cls.min_relevance)),
            min_quality=float(d.get("min_quality", cls.min_quality)),
            simhash_max_distance=int(d.get("simhash_max_distance", cls.simhash_max_distance)),
            shingle_overlap_min=float(d.get("shingle_overlap_min", cls.shingle_overlap_min)),
            min_tokens_for_overlap=int(d.get("min_tokens_for_overlap", cls.min_tokens_for_overlap)),
        )
        if rules.min_items < 1 or rules.min_independent_groups < 1:
            raise ValueError("min_items/min_independent_groups phải ≥ 1")
        if not (0 <= rules.min_relevance <= 1 and 0 <= rules.min_quality <= 1):
            raise ValueError("min_relevance/min_quality phải trong [0, 1]")
        if not 0 <= rules.simhash_max_distance <= 16:
            raise ValueError("simhash_max_distance phải trong [0, 16]")
        if not 0 < rules.shingle_overlap_min <= 1 or rules.min_tokens_for_overlap < 3:
            raise ValueError("shingle_overlap_min phải trong (0, 1], min_tokens_for_overlap ≥ 3")
        return rules


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    source_url: str | None
    excerpt: str | None
    collected_at: datetime | None
    verification_status: str | None
    redaction_status: str | None = "REDACTED"
    lifecycle_status: str = "ACTIVE"
    purpose: str | None = "PAIN_POINT"
    relevance: float | None = None
    quality: float | None = None
    copy_suspected: bool = False
    data_origin: str = "REAL"
    registered_domain: str | None = None
    source_simhash: int | None = None
    excerpt_simhash: int | None = None
    content_hash: str | None = None


@dataclass(frozen=True)
class ThresholdResult:
    status: EvidenceStatus
    counted_ids: set[str]
    independent_groups: int
    groups: dict[str, str]
    invalid_reasons: dict[str, list[str]] = field(default_factory=dict)

    @property
    def valid_count(self) -> int:
        return len(self.counted_ids)


def invalid_reasons(item: EvidenceItem, *, origin: str, rules: EvidenceRules) -> list[str]:
    """Lý do bằng chứng KHÔNG được tính (rỗng = hợp lệ)."""
    reasons: list[str] = []
    if not (item.source_url or "").strip() or not _domain(item):
        reasons.append("MISSING_SOURCE_URL")
    if not (item.excerpt or "").strip():
        reasons.append("MISSING_EXCERPT")
    if item.collected_at is None:
        reasons.append("MISSING_COLLECTED_AT")
    if item.verification_status not in COUNTABLE_STATUSES:
        reasons.append("MISSING_VERIFICATION_STATUS" if not item.verification_status else "UNKNOWN_STATUS")
    if item.lifecycle_status != "ACTIVE":
        reasons.append("ERASED")
    if item.redaction_status != "REDACTED":
        reasons.append("NOT_REDACTED")
    if item.purpose != "PAIN_POINT":
        reasons.append("NOT_PAIN_POINT")
    if item.relevance is None or item.relevance < rules.min_relevance:
        reasons.append("LOW_RELEVANCE")
    if item.quality is None or item.quality < rules.min_quality:
        reasons.append("LOW_QUALITY")
    if item.copy_suspected:
        reasons.append("COPY_SUSPECTED")
    if item.data_origin != origin:
        reasons.append("ORIGIN_MISMATCH")
    return reasons


def _domain(item: EvidenceItem) -> str | None:
    if item.registered_domain:
        return item.registered_domain.lower()
    if item.source_url and item.source_url.strip():
        dom = registered_domain(item.source_url.strip())
        return dom or None
    return None


def _excerpt_hash(item: EvidenceItem) -> int | None:
    if item.excerpt_simhash is not None:
        return item.excerpt_simhash
    text = (item.excerpt or "").strip()
    return simhash64(text) if text else None


def _close(a: int | None, b: int | None, d: int) -> bool:
    return a is not None and b is not None and hamming(a, b) <= d


def independence_groups(items: Iterable[EvidenceItem], rules: EvidenceRules) -> dict[str, str]:
    """evidence_id → nhãn nhóm ổn định (không phụ thuộc thứ tự đầu vào)."""
    lst = sorted(items, key=lambda i: i.evidence_id)
    parent = list(range(len(lst)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    domains = [_domain(i) for i in lst]
    ex_hashes = [_excerpt_hash(i) for i in lst]
    long_text = [len(normalize(i.excerpt or "")) >= rules.min_tokens_for_overlap for i in lst]
    d = rules.simhash_max_distance
    for a in range(len(lst)):
        for b in range(a + 1, len(lst)):
            ia, ib = lst[a], lst[b]
            same = (
                (domains[a] is not None and domains[a] == domains[b])
                or (ia.content_hash is not None and ia.content_hash == ib.content_hash)
                or _close(ex_hashes[a], ex_hashes[b], d)
                or (
                    long_text[a]
                    and long_text[b]
                    and shingle_containment(ia.excerpt or "", ib.excerpt or "") >= rules.shingle_overlap_min
                )
                or _close(ia.source_simhash, ib.source_simhash, d)
            )
            if same:
                union(a, b)
    members: dict[int, list[int]] = {}
    for idx in range(len(lst)):
        members.setdefault(find(idx), []).append(idx)
    labels: dict[str, str] = {}
    for idxs in members.values():
        doms = sorted({dom for i in idxs if (dom := domains[i])})
        if doms:
            label = "domain:" + doms[0]
        else:
            ids = ",".join(sorted(lst[i].evidence_id for i in idxs))
            label = "evidence:" + hashlib.sha256(ids.encode()).hexdigest()[:16]
        for i in idxs:
            labels[lst[i].evidence_id] = label
    return labels


def evaluate_threshold(
    items: Iterable[EvidenceItem], *, origin: str = "REAL", rules: EvidenceRules | None = None
) -> ThresholdResult:
    rules = rules or EvidenceRules()
    lst = list(items)
    groups = independence_groups([i for i in lst if i.lifecycle_status == "ACTIVE"], rules)
    reasons = {i.evidence_id: invalid_reasons(i, origin=origin, rules=rules) for i in lst}
    counted = {eid for eid, r in reasons.items() if not r and eid in groups}
    n_groups = len({groups[e] for e in counted})
    ok = len(counted) >= rules.min_items and n_groups >= rules.min_independent_groups
    return ThresholdResult(
        status="EVIDENCE_SUFFICIENT" if ok else "INSUFFICIENT_EVIDENCE",
        counted_ids=counted,
        independent_groups=n_groups,
        groups=groups,
        invalid_reasons={k: v for k, v in reasons.items() if v},
    )
