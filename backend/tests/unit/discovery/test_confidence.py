"""T086 – compute_confidence (scoring-rubric §3; FR-020): độc lập với Opportunity, ví dụ 66,00, trần 30 khi thiếu bằng chứng."""

from __future__ import annotations

import inspect
from decimal import Decimal

import pytest

from nichepilot.modules.discovery.scoring.confidence import ConfidenceInputs, compute_confidence, source_kind

pytestmark = pytest.mark.discovery

PARAMS = {
    "weights": {"N": 0.25, "Q": 0.20, "D": 0.15, "F": 0.15, "K": 0.15, "V": 0.10},
    "freshness_days": 730,
    "insufficient_cap": 30,
}


def example(**kw: object) -> ConfidenceInputs:
    base: dict[str, object] = {
        "independent_groups": 3,
        "qualities": [0.6, 0.8, 0.7, 0.7],
        "source_kinds": {"forum", "review"},
        "ages_days": [365.0, 365.0],
        "conflicting": 0,
        "criteria_with_data": 4,
        "coverage": 70.0,
        "evidence_status": "EVIDENCE_SUFFICIENT",
    }
    base.update(kw)
    return ConfidenceInputs(**base)  # type: ignore[arg-type]


def test_TC_E1_FR020_01_hand_example_66_00_and_no_opportunity_input() -> None:
    score, comp = compute_confidence(example(), PARAMS)
    assert score == Decimal("66.00")
    assert comp["N"] == 0.5 and comp["Q"] == pytest.approx(0.7) and comp["D"] == pytest.approx(2 / 3, abs=1e-4)
    assert comp["F"] == pytest.approx(0.5) and comp["K"] == 1 and comp["V"] == pytest.approx(0.7)
    names = set(inspect.signature(compute_confidence).parameters) | {f for f in ConfidenceInputs.__dataclass_fields__}
    assert not any("opportunity" in n for n in names)


def test_TC_E1_FR020_02_decreases_with_gaps_conflicts_age_and_cap() -> None:
    base, _ = compute_confidence(example(), PARAMS)
    for worse in (
        example(coverage=55.0),
        example(conflicting=1, criteria_with_data=4),
        example(ages_days=[700.0, 700.0]),
        example(independent_groups=1),
        example(source_kinds={"forum"}),
    ):
        assert compute_confidence(worse, PARAMS)[0] < base
    capped, _ = compute_confidence(example(evidence_status="INSUFFICIENT_EVIDENCE"), PARAMS)
    assert capped == Decimal("30.00")
    empty, comp = compute_confidence(ConfidenceInputs(0, [], set(), [], 0, 0, 0.0, "INSUFFICIENT_EVIDENCE"), PARAMS)
    assert empty == Decimal("0.00") and comp["K"] == 0


def test_TC_E1_FR020_03_source_kind_heuristic() -> None:
    assert source_kind("https://forum.example/t/1") == "forum"
    assert source_kind("https://www.reddit.com/r/x/comments/1") == "forum"
    assert source_kind("https://reviews.example/app") == "review"
    assert source_kind("https://stackoverflow.com/questions/1") == "qa"
    assert source_kind("https://www.youtube.com/watch?v=1") == "video"
    assert source_kind("https://blog.example/post") == "article"
    assert source_kind("https://shop.example/") == "other"
