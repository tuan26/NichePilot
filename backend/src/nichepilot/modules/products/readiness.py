"""Trạng thái sẵn sàng affiliate của cặp (sản phẩm, ngách) – scoring-rubric §4; FR-026; Clarification Q2.

`READY_TO_PROMOTE` CHỈ khi điều kiện đăng ký từ Việt Nam `ALLOWED` **VERIFIED** và quyền quảng bá ở thị trường mục
tiêu **VERIFIED**.
Đây là điều kiện tham gia, không phải khuyến nghị quảng bá. Mã thuần.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from nichepilot.modules.products.attributes import ResolvedAttribute
from nichepilot.modules.products.programs import ProgramView, best_program


def market_ok(regions_value: Mapping[str, Any] | None, country: str) -> bool | None:
    """True/False khi có dữ liệu vùng quảng bá; None khi không có."""
    if not regions_value:
        return None
    if country in (regions_value.get("exclude") or []):
        return False
    if regions_value.get("global"):
        return True
    return country in (regions_value.get("include") or [])


def readiness(programs: Sequence[ProgramView], country: str) -> tuple[str, list[str]]:
    if not programs:
        return "NO_PROGRAM", ["MONETIZATION_RISK"]
    if all(p.status == "CLOSED" for p in programs):
        return "PROGRAM_CLOSED", ["MONETIZATION_RISK"]
    usable = [p for p in programs if p.status in ("VERIFIED", "PARTIAL")]
    if not usable:
        return "AFFILIATE_UNVERIFIED", ["MONETIZATION_RISK"]
    best = best_program(usable)
    assert best is not None
    empty = ResolvedAttribute("x", "UNKNOWN", None)
    vn = best.attrs.get("vn_eligibility", empty)
    regions = best.attrs.get("promotion_regions", empty)
    ok = market_ok(regions.value if regions.has_data else None, country)
    flags: list[str] = []
    if ok is None:
        flags.append("MARKET_UNKNOWN")
    elif ok is False:
        flags.append("MARKET_NOT_ALLOWED")
    vn_status = (vn.value or {}).get("status") if vn.has_data else None
    if vn_status == "NOT_ALLOWED" or ok is False:
        status = "NOT_ELIGIBLE"
    elif vn.verified and vn_status == "ALLOWED" and regions.verified and ok is True:
        status = "READY_TO_PROMOTE"
    else:
        status = "ELIGIBILITY_UNVERIFIED"
    if status != "READY_TO_PROMOTE":
        flags.insert(0, "MONETIZATION_RISK")
    return status, flags
