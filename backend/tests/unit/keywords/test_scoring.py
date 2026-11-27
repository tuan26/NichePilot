"""T024 – Keyword Opportunity/Coverage/Confidence theo ví dụ tính tay của scoring-rubric (FR-017…FR-020)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from nichepilot.modules.keywords.scoring import criteria as cr
from nichepilot.modules.keywords.scoring.confidence import ConfidenceInputs, compute_confidence
from nichepilot.modules.keywords.scoring.opportunity import compute_opportunity, validate_weights

pytestmark = [pytest.mark.keywords]

W = {"fit": 30, "intent_value": 20, "competition": 20, "content_gap": 15, "demand": 15}
FIT = {"level": 75, "reason": "solves the stock-out pain", "evidence_ids": ["e1"]}
SERP = [
    {"url": "https://forum.example/t/1", "page_type": "forum"},
    {"url": "https://qa.example/q/2", "page_type": "qa"},
    {"url": "https://blog.example/a", "page_type": "article"},
    {"url": "https://review.example/b", "page_type": "review"},
    {"url": "https://shop.example/pricing", "page_type": "product"},
]


def _full() -> dict[str, cr.Criterion]:
    return {
        "fit": cr.fit(FIT, has_valid_origin=True, allowed_evidence={"e1"}),
        "intent_value": cr.intent_value("INFORMATIONAL", "PROBLEM"),
        "competition": cr.competition(SERP),
        "content_gap": cr.content_gap(["p1", "p2"], [["p1"]]),
        "demand": cr.demand(3, 0),
    }


def test_TC_E3_FR017_01_rubric_example_full_coverage() -> None:
    crit = _full()
    assert [crit[k].level for k in W] == [75, 75, 75, 75, 50]
    res = compute_opportunity(crit, W, 60)
    assert (res.opportunity, res.coverage, res.scoring_status) == (Decimal("71.25"), Decimal("100.00"), "SCORED")


def test_TC_E3_FR017_02_rubric_example_without_serp() -> None:
    crit = {
        "fit": cr.fit(FIT, has_valid_origin=True, allowed_evidence={"e1"}),
        "intent_value": cr.intent_value("INFORMATIONAL", "PROBLEM"),
        "competition": cr.competition(None),
        "content_gap": cr.content_gap(["p1"], None),
        "demand": cr.demand(2, 0),
    }
    res = compute_opportunity(crit, W, 60)
    assert res.coverage == Decimal("65.00") and res.opportunity == Decimal("63.46")
    assert set(res.missing) == {"competition", "content_gap"}


def test_TC_E3_FR018_01_insufficient_when_low_coverage_or_no_fit() -> None:
    crit = _full()
    crit["fit"] = cr.fit(None, has_valid_origin=True, allowed_evidence={"e1"})
    res = compute_opportunity(crit, W, 60)
    assert res.opportunity is None and res.scoring_status == "INSUFFICIENT_SCORING_DATA"
    low = {k: cr.Criterion(None, "UNKNOWN") for k in W}
    low["fit"] = _full()["fit"]
    low["intent_value"] = cr.intent_value("TRANSACTIONAL", "PRODUCT")
    assert compute_opportunity(low, W, 60).scoring_status == "INSUFFICIENT_SCORING_DATA"  # coverage 50 < 60


def test_TC_E3_FR018_02_unknown_criteria_never_scored() -> None:
    assert (
        cr.fit(
            {"level": 75, "reason": "x", "evidence_ids": ["zzz"]}, has_valid_origin=True, allowed_evidence={"e1"}
        ).level
        is None
    )
    assert (
        cr.fit(
            {"level": 70, "reason": "x", "evidence_ids": ["e1"]}, has_valid_origin=True, allowed_evidence={"e1"}
        ).level
        is None
    )
    assert cr.fit(FIT, has_valid_origin=False, allowed_evidence={"e1"}).level is None
    assert cr.demand(0, 0).level is None
    assert cr.content_gap([], [["p1"]]).level is None


def test_TC_E3_FR017_03_intent_value_problem_not_below_transactional() -> None:
    problem = cr.intent_value("INFORMATIONAL", "PROBLEM").level
    trans = cr.intent_value("TRANSACTIONAL", "PRODUCT").level
    generic = cr.intent_value("INFORMATIONAL", "INFORMATIONAL").level
    assert problem == trans == 75 and generic == 25
    assert cr.intent_value("COMMERCIAL_INVESTIGATION", "PRODUCT").level == 100
    assert cr.intent_value("NAVIGATIONAL", "PRODUCT").level == 0


def test_TC_E3_FR019_01_confidence_independent_of_opportunity() -> None:
    conf, comp = compute_confidence(
        ConfidenceInputs(has_serp=True, source_domains=3, ages_days=[36.0], observed_criteria=3, coverage=100.0)
    )
    assert conf == Decimal("92.00") and comp["F"] == 0.8
    import inspect

    assert "opportunity" not in inspect.signature(compute_confidence).parameters
    assert "opportunity" not in ConfidenceInputs.__dataclass_fields__


def test_TC_E3_FR020_01_deterministic_and_weights_validated() -> None:
    assert compute_opportunity(_full(), W) == compute_opportunity(_full(), W)
    with pytest.raises(ValueError):
        validate_weights({**W, "fit": 31})
    with pytest.raises(ValueError):
        validate_weights({"fit": 100})


def test_TC_E3_FR015_01_competition_weak_share() -> None:
    c = cr.competition(SERP, uncovering_urls=["https://blog.example/a"])
    assert c.inputs["weak"] == 3 and c.level == 100  # 3/5 = 0.6
    assert cr.competition([{"url": "u", "page_type": "article"}]).level == 0
    assert cr.competition([]).level is None
