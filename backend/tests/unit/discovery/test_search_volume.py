"""T087 – Search volume thấp/không có không làm giảm điểm hay loại ngách (FR-021, BR-15)."""

from __future__ import annotations

import inspect

import pytest

from nichepilot.modules.discovery.schemas import AssessOutput
from nichepilot.modules.discovery.scoring.opportunity import Criterion, compute_opportunity

pytestmark = pytest.mark.discovery

W = {
    "problem_severity": 25,
    "monetization": 20,
    "market_gap": 20,
    "reachability": 15,
    "competition_opportunity": 10,
    "demand_stability": 10,
}


def test_TC_E1_FR021_01_no_search_volume_input_and_no_penalty() -> None:
    assert not any("volume" in p for p in inspect.signature(compute_opportunity).parameters)
    crit = {k: Criterion(score=100, status="VERIFIED", reason="r", evidence_ids=("e",)) for k in W}
    # "không có dữ liệu search volume" chỉ làm tiêu chí ổn định nhu cầu UNKNOWN – không thành 0
    crit["demand_stability"] = Criterion(score=None, status="UNKNOWN", reason="no search volume data")
    r = compute_opportunity(crit, W)
    assert r.opportunity == 100 and r.scoring_status == "SCORED"
    with pytest.raises(ValueError):  # AI không được trả search volume
        AssessOutput.model_validate({"evidence": [], "search_volume": 10})
