"""T111 – Phát hiện trùng trên bộ ≥ 40 cặp có nhãn (FR-022, SC-010): độ chính xác ≥ 90%, 0 cặp "không trùng" bị tự gộp."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nichepilot.modules.discovery.dedup import DedupParams, classify, normalize, similarity

pytestmark = pytest.mark.discovery
PAIRS = json.loads((Path(__file__).resolve().parents[2] / "fixtures" / "discovery" / "dedup_pairs.json").read_text())[
    "pairs"
]


def test_TC_E1_FR022_01_TC_E1_SC010_01_labelled_pairs_accuracy_and_no_false_merge() -> None:
    assert len(PAIRS) >= 40 and {p["duplicate"] for p in PAIRS} == {True, False}
    params = DedupParams()
    correct = false_merges = 0
    for p in PAIRS:
        verdict = classify(similarity(p["a"], p["b"], params), params)
        merged = verdict == "DUPLICATE"
        correct += merged == p["duplicate"]
        false_merges += merged and not p["duplicate"]
    assert correct / len(PAIRS) >= 0.90, correct
    assert false_merges == 0


def test_TC_E1_FR022_03_same_problem_different_customers_never_auto_merged() -> None:
    a = {"customer_group": "freelance designers", "core_problem": "clients pay invoices late"}
    b = {"customer_group": "freelance photographers", "core_problem": "clients pay invoices late"}
    sim = similarity(a, b)
    assert sim.score >= 0.85 and classify(sim) == "POSSIBLE"  # chờ chủ sở hữu, không tự gộp
    assert normalize("Owners of the small bakeries") == "owner small bakeri"
    assert classify(similarity(a, a)) == "DUPLICATE"
