"""T030 – trạng thái chương trình và chương trình tốt nhất (data-model §4; FR-018)."""

from __future__ import annotations

import pytest

from nichepilot.modules.products.programs import ProgramView, best_program, diff_snapshots, program_status
from tests.unit.products._attrs import attr

pytestmark = pytest.mark.products


def test_TC_E2_FR018_01_status_rules() -> None:
    com = attr("commission", {"kind": "percent", "value": 30})
    assert program_status({"commission": com}, has_operator_source=True) == "VERIFIED"
    assert program_status({"commission": com}, has_operator_source=False) == "PARTIAL"
    inf = attr("commission", {"kind": "percent", "value": 30}, "INFERRED", "b.example")
    assert program_status({"commission": inf}, has_operator_source=True) == "PARTIAL"
    assert program_status({}, has_operator_source=True) == "UNVERIFIED"
    closed = attr("program_status", {"status": "CLOSED"})
    assert program_status({"commission": com, "program_status": closed}, has_operator_source=True) == "CLOSED"


def test_TC_E2_FR018_02_best_program_and_terms_diff() -> None:
    a = ProgramView("a", "A", "PARTIAL", {}, 100)
    b = ProgramView("b", "B", "VERIFIED", {}, 25)
    c = ProgramView("c", "C", "VERIFIED", {}, 75)
    assert best_program([a, b, c]) is c and best_program([]) is None
    old = {"commission": {"status": "VERIFIED", "value": {"kind": "percent", "value": 30}}}
    new = {
        "commission": {"status": "VERIFIED", "value": {"kind": "percent", "value": 20}},
        "cookie_days": {"status": "UNKNOWN", "value": None},
    }
    changes = diff_snapshots(old, new)
    assert [c["claim_key"] for c in changes] == ["commission"] and diff_snapshots(new, new) == []
