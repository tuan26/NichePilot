"""T085 – compute_opportunity (scoring-rubric §2–§3; FR-017, FR-019, FR-019a, SC-005, SC-005a). Logic xác định, không AI."""

from __future__ import annotations

from decimal import Decimal

import pytest

from nichepilot.modules.discovery.scoring.opportunity import CRITERIA, Criterion, compute_opportunity

pytestmark = pytest.mark.discovery

W = {
    "problem_severity": 25,
    "monetization": 20,
    "market_gap": 20,
    "reachability": 15,
    "competition_opportunity": 10,
    "demand_stability": 10,
}


def c(score: int | None, status: str = "VERIFIED") -> Criterion:
    return Criterion(score=score, status=status, reason="r", evidence_ids=("e1",) if score is not None else ())


UNKNOWN = Criterion(score=None, status="UNKNOWN", reason="no data")


def example() -> dict[str, Criterion]:
    return {
        "problem_severity": c(75),
        "monetization": UNKNOWN,
        "market_gap": c(50, "INFERRED"),
        "reachability": c(75),
        "competition_opportunity": c(25),
        "demand_stability": UNKNOWN,
    }


def test_TC_E1_FR019_01_hand_example_60_71() -> None:
    r = compute_opportunity(example(), W)
    assert r.coverage == Decimal("70.00") and r.scoring_status == "SCORED"
    assert r.opportunity == Decimal("60.71")
    assert r.criteria["monetization"]["score"] is None and r.criteria["monetization"]["normalized_weight"] is None
    assert r.criteria["problem_severity"]["normalized_weight"] == pytest.approx(25 / 70, abs=1e-4)


def test_TC_E1_FR017_01_all_six_criteria() -> None:
    crit = {k: c(100) for k in CRITERIA}
    crit["demand_stability"] = c(0)
    r = compute_opportunity(crit, W)
    assert r.coverage == Decimal("100.00") and r.opportunity == Decimal("90.00")


def test_TC_E1_FR019_02_unknown_never_scored_as_zero_or_hundred() -> None:
    base = compute_opportunity(example(), W).opportunity
    as_zero = {**example(), "monetization": c(0)}
    as_hundred = {**example(), "monetization": c(100)}
    assert compute_opportunity(as_zero, W).opportunity != base != compute_opportunity(as_hundred, W).opportunity
    # thiếu khóa = UNKNOWN (không mặc định)
    missing = {k: v for k, v in example().items() if k != "monetization"}
    assert compute_opportunity(missing, W).opportunity == base


def test_TC_E1_FR019a_01_coverage_threshold_exactly_60_and_below() -> None:
    at60 = {k: UNKNOWN for k in CRITERIA} | {"problem_severity": c(50), "monetization": c(50), "reachability": c(50)}
    r = compute_opportunity(at60, W)
    assert r.coverage == Decimal("60.00") and r.scoring_status == "SCORED" and r.opportunity == Decimal("50.00")
    below = {**example(), "reachability": UNKNOWN}  # 55
    r2 = compute_opportunity(below, W)
    assert (
        r2.coverage == Decimal("55.00") and r2.scoring_status == "INSUFFICIENT_SCORING_DATA" and r2.opportunity is None
    )
    assert compute_opportunity(below, W, coverage_threshold=50).scoring_status == "SCORED"


def test_TC_E1_FR019_03_conflicting_and_invalid_treated_as_unknown() -> None:
    conflicting = {
        **example(),
        "problem_severity": Criterion(score=None, status="CONFLICTING", reason="sources disagree"),
    }
    r = compute_opportunity(conflicting, W)
    assert r.coverage == Decimal("45.00") and r.opportunity is None
    # điểm ngoài thang, CONFLICTING kèm điểm, VERIFIED/INFERRED không bằng chứng hoặc không lý do → coi như UNKNOWN
    for bad in (
        Criterion(score=60, status="VERIFIED", reason="r", evidence_ids=("e",)),
        Criterion(score=75, status="CONFLICTING", reason="r", evidence_ids=("e",)),
        Criterion(score=75, status="VERIFIED", reason="r", evidence_ids=()),
        Criterion(score=75, status="INFERRED", reason="", evidence_ids=("e",)),
    ):
        r3 = compute_opportunity({**example(), "monetization": bad}, W)
        assert r3.coverage == Decimal("70.00") and r3.criteria["monetization"]["score"] is None
    with pytest.raises(ValueError):
        compute_opportunity(example(), {**W, "extra": 0})


def test_TC_E1_SC005_01_SC005a_01_deterministic_and_weights_version_driven() -> None:
    w2 = {**W, "problem_severity": 35, "market_gap": 10}
    a = compute_opportunity(example(), w2)
    # (75·35 + 50·10 + 75·15 + 25·10) / 70 = 4500/70 = 64.29
    assert a.opportunity == Decimal("64.29")
    assert compute_opportunity(example(), w2) == a  # tính lại cho cùng kết quả
