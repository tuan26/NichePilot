"""T039 – trạng thái sẵn sàng affiliate (scoring-rubric §4; FR-026; Clarification Q2)."""

from __future__ import annotations

import pytest

from nichepilot.modules.products.programs import ProgramView
from nichepilot.modules.products.readiness import readiness
from tests.unit.products._attrs import attr

pytestmark = pytest.mark.products


def prog(
    status: str, vn: str | None = "ALLOWED", regions: dict[str, object] | None = None, st: str = "VERIFIED"
) -> ProgramView:
    attrs = {
        "vn_eligibility": attr("vn_eligibility", {"status": vn} if vn else None, st),
        "promotion_regions": attr("promotion_regions", regions, st),
    }
    return ProgramView("p", "P", status, attrs)


def test_TC_E2_FR026_01_no_program() -> None:
    assert readiness([], "US") == ("NO_PROGRAM", ["MONETIZATION_RISK"])


def test_TC_E2_FR026_02_closed() -> None:
    assert readiness([prog("CLOSED")], "US")[0] == "PROGRAM_CLOSED"


def test_TC_E2_FR026_03_unverified() -> None:
    assert readiness([prog("UNVERIFIED")], "US")[0] == "AFFILIATE_UNVERIFIED"


def test_TC_E2_FR026_04_ready_requires_both_verified() -> None:
    assert readiness([prog("VERIFIED", regions={"include": ["US"]})], "US") == ("READY_TO_PROMOTE", [])
    s, flags = readiness([prog("VERIFIED", regions={"include": ["US"]}, st="INFERRED")], "US")
    assert s == "ELIGIBILITY_UNVERIFIED" and "MONETIZATION_RISK" in flags


def test_TC_E2_FR026_05_unknown_vn_or_market_never_ready() -> None:
    s, _ = readiness([prog("VERIFIED", vn=None, regions={"global": True})], "US")
    assert s == "ELIGIBILITY_UNVERIFIED"
    s2, flags2 = readiness([prog("PARTIAL", regions=None)], "US")
    assert s2 == "ELIGIBILITY_UNVERIFIED" and "MARKET_UNKNOWN" in flags2


def test_TC_E2_FR026_06_not_eligible() -> None:
    assert readiness([prog("VERIFIED", vn="NOT_ALLOWED", regions={"global": True})], "US")[0] == "NOT_ELIGIBLE"
    s, flags = readiness([prog("VERIFIED", regions={"include": ["GB"]})], "US")
    assert s == "NOT_ELIGIBLE" and "MARKET_NOT_ALLOWED" in flags
