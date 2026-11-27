"""T037 – 5 tiêu chí theo rubric (scoring-rubric §2; FR-027, FR-028a)."""

from __future__ import annotations

import pytest

from nichepilot.modules.products.attributes import resolve
from nichepilot.modules.products.scoring import criteria as cr
from tests.unit.products._attrs import attr, ev

pytestmark = pytest.mark.products
IDS = {"e-fit", "e-price"}


def test_TC_E2_FR027_01_fit_needs_evidence_and_pain_links() -> None:
    ai = {"level": 75, "reason": "[MOCK] solves stock alerts", "evidence_ids": ["e-fit"]}
    assert cr.fit(ai, has_pain_links=True, persona_match="MATCH", active_ids=IDS).level == 75
    assert cr.fit(ai, has_pain_links=False, persona_match="MATCH", active_ids=IDS).level is None
    assert (
        cr.fit({**ai, "evidence_ids": ["erased"]}, has_pain_links=True, persona_match="MATCH", active_ids=IDS).level
        is None
    )
    assert cr.fit({**ai, "level": 60}, has_pain_links=True, persona_match="MATCH", active_ids=IDS).level is None
    assert cr.fit(ai, has_pain_links=True, persona_match="NO_MATCH", active_ids=IDS).level == 25


def test_TC_E2_FR027_02_affiliate_status_follows_commission() -> None:
    v = cr.affiliate(attr("commission", {"kind": "percent", "value": 30}), attr("cookie_days", None), cheapest=None)
    i = cr.affiliate(
        attr("commission", {"kind": "percent", "value": 30}, "INFERRED", "b.example"),
        attr("cookie_days", None),
        cheapest=None,
    )
    assert (v.status, i.status) == ("VERIFIED", "INFERRED")


def test_TC_E2_FR027_03_eligibility_verified_full() -> None:
    c = cr.eligibility(
        attr("vn_eligibility", {"status": "ALLOWED"}),
        attr("promotion_regions", {"include": ["US"]}),
        attr("ad_restrictions", {"codes": ["NO_BRAND_BIDDING"]}),
        country="US",
    )
    assert (c.level, c.status) == (100, "VERIFIED")


def test_TC_E2_FR027_04_quality_points() -> None:
    feats = resolve("feature", [ev("feature", {"text": t}) for t in ("a", "b", "c", "d")])
    c = cr.quality(
        attr("official_website", {"url": "https://v.example"}),
        feats,
        [("blog.example", "positive")],
        official_domain="vendor.example",
    )
    assert c.level == 75
    c2 = cr.quality(attr("official_website", None), attr("feature", None), [], official_domain=None)
    assert c2.level is None
    neg = cr.quality(
        attr("official_website", None),
        attr("feature", None),
        [("a.example", "negative"), ("b.example", "negative")],
        official_domain=None,
    )
    assert neg.level == 0
    own = cr.quality(
        attr("official_website", None),
        attr("feature", None),
        [("vendor.example", "positive")],
        official_domain="vendor.example",
    )
    assert own.level is None  # tự khen trên website chính thức không tính


def test_TC_E2_FR027_05_price_fit_needs_price_and_ability_to_pay() -> None:
    ai = {"level": 50, "reason": "[MOCK] fits a micro budget", "evidence_ids": ["e-price"]}
    assert cr.price_fit(ai, price_has_data=True, ability_to_pay_known=True, active_ids=IDS).level == 50
    assert cr.price_fit(ai, price_has_data=False, ability_to_pay_known=True, active_ids=IDS).level is None
    assert cr.price_fit(ai, price_has_data=True, ability_to_pay_known=False, active_ids=IDS).level is None


def test_TC_E2_FR028a_01_high_commission_alone_never_selects() -> None:
    """Tiêu chí affiliate cao không thay thế được `fit`: Opportunity cần fit (xem test_scoring) và khuyến nghị SELECT
    cần READY + fit."""
    from nichepilot.modules.products.evaluation import final_recommendation

    rec, reason = final_recommendation("SELECT", readiness="READY_TO_PROMOTE", fit_valid=False, scoring_status="SCORED")
    assert (rec, reason) == ("UNKNOWN", "FIT_UNKNOWN")
    assert final_recommendation(
        "SELECT", readiness="ELIGIBILITY_UNVERIFIED", fit_valid=True, scoring_status="SCORED"
    ) == ("UNKNOWN", "NOT_READY_TO_PROMOTE")
    assert (
        final_recommendation(
            "SELECT", readiness="READY_TO_PROMOTE", fit_valid=True, scoring_status="INSUFFICIENT_SCORING_DATA"
        )[0]
        == "UNKNOWN"
    )
    assert final_recommendation("SELECT", readiness="READY_TO_PROMOTE", fit_valid=True, scoring_status="SCORED") == (
        "SELECT",
        None,
    )
    assert final_recommendation("REJECT", readiness="NO_PROGRAM", fit_valid=False, scoring_status="SCORED") == (
        "REJECT",
        None,
    )
