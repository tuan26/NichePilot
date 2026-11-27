"""T031 – thuộc tính chương trình có cấu trúc và mức hấp dẫn (FR-019…FR-024; scoring-rubric §2.2–2.3)."""

from __future__ import annotations

import pytest

from nichepilot.modules.products.readiness import market_ok
from nichepilot.modules.products.scoring import criteria as cr
from tests.unit.products._attrs import attr

pytestmark = pytest.mark.products
NO_COOKIE = attr("cookie_days", None)


def _aff(
    c: dict[str, object] | None, cookie: dict[str, object] | None = None, cheapest: float | None = None
) -> int | None:
    return cr.affiliate(attr("commission", c), attr("cookie_days", cookie), cheapest=cheapest).level


def test_TC_E2_FR019_01_commission_shapes() -> None:
    assert _aff({"kind": "percent", "value": 30}) == 100
    assert _aff({"kind": "percent", "value": 12}) == 50
    assert _aff({"kind": "percent", "min": 5, "max": 40}) == 25  # khoảng → cận dưới
    assert _aff({"kind": "percent", "value": 30, "up_to": True}) == 75  # "lên tới" → −25
    assert _aff({"kind": "recurring", "value": 20}) == 100
    assert _aff({"kind": "fixed", "value": 30}, cheapest=100) == 100  # 30% giá
    assert _aff({"kind": "fixed", "value": 30}) == 50  # không có giá → theo số tiền
    assert _aff(None) is None


def test_TC_E2_FR020_01_cookie_adjustment() -> None:
    assert _aff({"kind": "percent", "value": 20}, {"days": 7}) == 50
    assert _aff({"kind": "percent", "value": 20}, {"session": True}) == 50
    assert _aff({"kind": "percent", "value": 20}, {"days": 90}) == 75


def test_TC_E2_FR021_01_payment_is_attribute_not_score() -> None:
    p = attr("payment", {"methods": ["PayPal"], "min_payout": 50, "currency": "USD"})
    assert p.has_data and p.value == {"methods": ["PayPal"], "min_payout": 50, "currency": "USD"}


def _elig(
    vn: dict[str, object] | None,
    regions: dict[str, object] | None,
    codes: list[str] | None,
    country: str = "US",
    status: str = "VERIFIED",
) -> cr.Criterion:
    return cr.eligibility(
        attr("vn_eligibility", vn, status),
        attr("promotion_regions", regions, status),
        attr("ad_restrictions", {"codes": codes} if codes is not None else None, status),
        country=country,
    )


def test_TC_E2_FR022_01_silence_is_unknown_not_allowed() -> None:
    c = _elig(None, None, None)
    assert c.level is None and c.status == "UNKNOWN"
    assert _elig(None, {"global": True}, None).level == 50  # chỉ biết thị trường → 50, không coi là cho phép VN
    assert _elig({"status": "NOT_ALLOWED"}, {"global": True}, None).level == 0


def test_TC_E2_FR023_01_market_comparison() -> None:
    assert market_ok({"include": ["US", "CA"]}, "US") is True
    assert market_ok({"global": True, "exclude": ["US"]}, "US") is False
    assert market_ok(None, "US") is None
    assert _elig({"status": "ALLOWED"}, {"include": ["GB"]}, None).level == 0


def test_TC_E2_FR024_01_restrictions_affect_level_unknown_not_none() -> None:
    assert _elig({"status": "ALLOWED"}, {"global": True}, ["NO_BRAND_BIDDING"]).level == 100
    assert _elig({"status": "ALLOWED"}, {"global": True}, ["NO_PPC", "NO_EMAIL"]).level == 75
    assert _elig({"status": "ALLOWED"}, {"global": True}, None).level == 75  # UNKNOWN ≠ "không có giới hạn"
    assert _elig({"status": "ALLOWED"}, {"global": True}, ["NO_PPC"], status="INFERRED").level == 50
