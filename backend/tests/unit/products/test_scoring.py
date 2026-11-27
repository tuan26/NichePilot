"""T038 – Opportunity/Coverage/Confidence (scoring-rubric §3 ví dụ tính tay; FR-027…FR-030)."""

from __future__ import annotations

import ast
import inspect
from decimal import Decimal

import pytest

from nichepilot.modules.products.scoring import confidence, opportunity
from nichepilot.modules.products.scoring.confidence import ConfidenceInputs, compute_confidence
from nichepilot.modules.products.scoring.criteria import Criterion
from nichepilot.modules.products.scoring.opportunity import compute_opportunity, validate_weights

pytestmark = pytest.mark.products
W = {"fit": 25, "affiliate": 25, "eligibility": 20, "quality": 15, "price_fit": 15}


def crit(**levels: int | None) -> dict[str, Criterion]:
    return {k: Criterion(v, "INFERRED" if v is not None else "UNKNOWN") for k, v in levels.items()}


def test_TC_E2_FR027_06_worked_example() -> None:
    r = compute_opportunity(crit(fit=75, affiliate=100, eligibility=100, quality=75, price_fit=None), W)
    assert (r.opportunity, r.coverage, r.scoring_status) == (Decimal("88.24"), Decimal("85.00"), "SCORED")


def test_TC_E2_FR028_01_at_threshold() -> None:
    r = compute_opportunity(crit(fit=75, affiliate=None, eligibility=100, quality=75, price_fit=None), W)
    assert (r.opportunity, r.coverage) == (Decimal("83.33"), Decimal("60.00"))


def test_TC_E2_FR028_02_below_threshold() -> None:
    r = compute_opportunity(crit(fit=75, affiliate=None, eligibility=100, quality=None, price_fit=None), W)
    assert (r.opportunity, r.coverage, r.scoring_status) == (None, Decimal("45.00"), "INSUFFICIENT_SCORING_DATA")


def test_TC_E2_FR028_03_fit_required() -> None:
    r = compute_opportunity(crit(fit=None, affiliate=100, eligibility=100, quality=75, price_fit=50), W)
    assert r.coverage == Decimal("75.00") and r.scoring_status == "INSUFFICIENT_SCORING_DATA"
    with pytest.raises(ValueError):
        validate_weights({**W, "fit": 30})
    with pytest.raises(ValueError):
        validate_weights({"fit": 100})


def test_TC_E2_FR029_01_confidence_worked_example() -> None:
    score, comp = compute_confidence(
        ConfidenceInputs(
            required_total=10,
            required_verified=7,
            source_domains=3,
            ages_days=[73.0],
            conflicting=0,
            with_data_or_conflicting=8,
            coverage=85,
        )
    )
    assert score == Decimal("80.00") and comp["A"] == 0.7


def test_TC_E2_FR029_02_confidence_independent_of_opportunity() -> None:
    src = inspect.signature(compute_confidence)
    assert "opportunity" not in str(src)
    tree = ast.parse(inspect.getsource(confidence))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
        a.attr for a in ast.walk(tree) if isinstance(a, ast.Attribute)
    }
    assert "compute_opportunity" not in names and "opportunity_score" not in names


def test_TC_E2_FR030_02_scoring_has_no_ai() -> None:
    for mod in (opportunity, confidence):
        text = inspect.getsource(mod)
        assert "gateway" not in text.lower() and "call_ai" not in text
