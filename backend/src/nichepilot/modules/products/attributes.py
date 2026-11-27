"""Trạng thái xác minh và gộp thuộc tính (research R-04; FR-008, FR-012; data-model §3).

- `verification_for`: `VERIFIED` chỉ khi tên miền nguồn (eTLD+1) = tên miền có thẩm quyền (website chính thức của sản
phẩm hoặc
  `operator_domain` của chương trình); ngược lại `INFERRED`. Không có tên miền thẩm quyền → `INFERRED`.
- `resolve`: gộp các bằng chứng ACTIVE của một `claim_key` thành một thuộc tính: `VERIFIED` / `INFERRED` /
`CONFLICTING` / `UNKNOWN`.
  Nguồn mâu thuẫn → `CONFLICTING`, giữ MỌI giá trị kèm nguồn (QA-05); `value` của thuộc tính CONFLICTING là giá trị
  VERIFIED nếu
  chỉ có một giá trị VERIFIED (bên thứ ba ghi khác), ngược lại `None`.
Mã thuần, không I/O.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

AttrStatus = Literal["VERIFIED", "INFERRED", "CONFLICTING", "UNKNOWN"]
PRODUCT_KEYS = ("official_website", "price", "feature", "target_customer", "third_party_mention")
PROGRAM_KEYS = (
    "commission",
    "cookie_days",
    "payment",
    "vn_eligibility",
    "promotion_regions",
    "ad_restrictions",
    "program_status",
)
MULTI_KEYS = frozenset({"price", "feature", "third_party_mention"})
# thuộc tính bắt buộc dùng cho Coverage "missing" và Confidence A (scoring-rubric §3)
REQUIRED_PRODUCT = ("official_website", "price", "feature", "target_customer")
REQUIRED_PROGRAM = ("commission", "cookie_days", "payment", "vn_eligibility", "promotion_regions", "ad_restrictions")


@dataclass(frozen=True)
class AttrEvidence:
    evidence_id: str
    claim_key: str
    value: dict[str, Any]
    status: str  # VERIFIED | INFERRED (bằng chứng đơn lẻ)
    source_url: str | None = None
    registered_domain: str | None = None
    excerpt: str | None = None
    collected_at: datetime | None = None
    verified_at: datetime | None = None


@dataclass(frozen=True)
class ResolvedAttribute:
    key: str
    status: AttrStatus
    value: Any | None
    values: tuple[AttrEvidence, ...] = field(default_factory=tuple)
    flags: tuple[str, ...] = ()

    @property
    def has_data(self) -> bool:
        """Có dữ liệu dùng được cho chấm điểm (scoring-rubric: VERIFIED/INFERRED, CONFLICTING có giá trị VERIFIED duy
        nhất)."""
        return self.value is not None and self.status != "UNKNOWN"

    @property
    def verified(self) -> bool:
        return self.status == "VERIFIED"


def verification_for(source_domain: str | None, authority_domain: str | None) -> Literal["VERIFIED", "INFERRED"]:
    if source_domain and authority_domain and source_domain.lower() == authority_domain.lower():
        return "VERIFIED"
    return "INFERRED"


def _canon(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def _identity(key: str, value: dict[str, Any]) -> str:
    """Khóa nhóm cho thuộc tính nhiều giá trị: giá theo tên gói, tính năng theo văn bản, mention theo bằng chứng."""
    if key == "price":
        return str(value.get("plan", "")).strip().lower()
    if key == "feature":
        return " ".join(str(value.get("text", "")).lower().split())
    return _canon(value)


def _value_key(key: str, value: dict[str, Any]) -> str:
    """Khóa so sánh giá trị: tính năng so theo văn bản chuẩn hóa (khác hoa/thường không phải mâu thuẫn)."""
    return _identity(key, value) if key == "feature" else _canon(value)


def _resolve_single(key: str, rows: Sequence[AttrEvidence]) -> ResolvedAttribute:
    verified = {_value_key(key, r.value): r.value for r in rows if r.status == "VERIFIED"}
    inferred = {_value_key(key, r.value): r.value for r in rows if r.status != "VERIFIED"}
    if verified:
        if len(verified) > 1:
            return ResolvedAttribute(key, "CONFLICTING", None, tuple(rows))
        ((vkey, vval),) = verified.items()
        if any(k != vkey for k in inferred):
            return ResolvedAttribute(key, "CONFLICTING", vval, tuple(rows), ("THIRD_PARTY_DISAGREES",))
        return ResolvedAttribute(key, "VERIFIED", vval, tuple(rows))
    if len(inferred) > 1:
        return ResolvedAttribute(key, "CONFLICTING", None, tuple(rows))
    ((_, ival),) = inferred.items()
    return ResolvedAttribute(key, "INFERRED", ival, tuple(rows))


def resolve(key: str, rows: Iterable[AttrEvidence]) -> ResolvedAttribute:
    items = [r for r in rows if r.claim_key == key]
    if not items:
        return ResolvedAttribute(key, "UNKNOWN", None)
    if key not in MULTI_KEYS:
        return _resolve_single(key, items)
    groups: dict[str, list[AttrEvidence]] = {}
    for r in items:
        groups.setdefault(_identity(key, r.value), []).append(r)
    parts = [_resolve_single(key, g) for g in groups.values()]
    values = [p.value for p in parts if p.value is not None]
    if any(p.status == "CONFLICTING" for p in parts):
        status: AttrStatus = "CONFLICTING"
    elif any(p.status == "VERIFIED" for p in parts):
        status = "VERIFIED"
    else:
        status = "INFERRED"
    return ResolvedAttribute(key, status, values or None, tuple(items))


def resolve_all(keys: Sequence[str], rows: Sequence[AttrEvidence]) -> dict[str, ResolvedAttribute]:
    return {k: resolve(k, rows) for k in keys}
