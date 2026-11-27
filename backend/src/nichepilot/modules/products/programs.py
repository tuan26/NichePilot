"""Trạng thái chương trình affiliate, chọn chương trình tốt nhất, ảnh chụp/so sánh điều khoản (data-model §4; FR-018,
FR-040).

Mã thuần, không I/O.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from nichepilot.modules.products.attributes import PROGRAM_KEYS, ResolvedAttribute

STATUS_RANK = {"VERIFIED": 3, "PARTIAL": 2, "UNVERIFIED": 1, "CLOSED": 0}


@dataclass(frozen=True)
class ProgramView:
    id: str
    name: str
    status: str
    attrs: Mapping[str, ResolvedAttribute] = field(default_factory=dict)
    affiliate_level: int | None = None


def program_status(attrs: Mapping[str, ResolvedAttribute], *, has_operator_source: bool) -> str:
    """CLOSED (có bằng chứng) > VERIFIED (đọc được trang của đơn vị vận hành ∧ hoa hồng/cookie VERIFIED) > PARTIAL >
    UNVERIFIED."""
    st = attrs.get("program_status")
    if st is not None and st.has_data and (st.value or {}).get("status") == "CLOSED":
        return "CLOSED"
    core_verified = any(attrs.get(k) is not None and attrs[k].verified for k in ("commission", "cookie_days"))
    if has_operator_source and core_verified:
        return "VERIFIED"
    if any(a.has_data for a in attrs.values()):
        return "PARTIAL"
    return "UNVERIFIED"


def best_program(programs: Sequence[ProgramView]) -> ProgramView | None:
    if not programs:
        return None
    return max(
        programs,
        key=lambda p: (STATUS_RANK.get(p.status, 0), p.affiliate_level if p.affiliate_level is not None else -1, p.id),
    )


def terms_snapshot(attrs: Mapping[str, ResolvedAttribute]) -> dict[str, Any]:
    return {
        k: {
            "status": attrs[k].status,
            "value": attrs[k].value,
            "evidence_ids": [v.evidence_id for v in attrs[k].values],
        }
        for k in PROGRAM_KEYS
        if k in attrs
    }


def diff_snapshots(old: Mapping[str, Any] | None, new: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Thay đổi giá trị/trạng thái giữa hai ảnh chụp; thuộc tính mới UNKNOWN không xóa giá trị cũ (lỗi đọc ≠ thay
    đổi)."""
    old = old or {}
    changes: list[dict[str, Any]] = []
    for k in PROGRAM_KEYS:
        o, n = old.get(k) or {}, new.get(k) or {}
        if n.get("status", "UNKNOWN") == "UNKNOWN":
            continue
        if (o.get("value"), o.get("status")) != (n.get("value"), n.get("status")):
            changes.append(
                {
                    "claim_key": k,
                    "old": o.get("value"),
                    "new": n.get("value"),
                    "old_status": o.get("status"),
                    "new_status": n.get("status"),
                }
            )
    return changes
