"""T008 – trạng thái xác minh theo tên miền và gộp thuộc tính (research R-04; FR-008, FR-012)."""

from __future__ import annotations

import pytest

from nichepilot.modules.products.attributes import resolve, verification_for
from tests.unit.products._attrs import ev

pytestmark = pytest.mark.products


def test_TC_E2_FR008_01_verified_only_from_authority_domain() -> None:
    assert verification_for("stockpal.example", "stockpal.example") == "VERIFIED"
    assert verification_for("reviews.example", "stockpal.example") == "INFERRED"
    assert verification_for("stockpal.example", None) == "INFERRED"  # TC_E2_FR012: không rõ website chính thức


def test_TC_E2_FR008_02_third_party_only_is_inferred() -> None:
    a = resolve("commission", [ev("commission", {"kind": "percent", "value": 25}, "INFERRED", "blog.example")])
    assert (a.status, a.value) == ("INFERRED", {"kind": "percent", "value": 25})


def test_TC_E2_FR008_03_conflicting_keeps_every_value() -> None:
    off = ev("commission", {"kind": "percent", "value": 30})
    third = ev("commission", {"kind": "percent", "value": 25}, "INFERRED", "blog.example")
    a = resolve("commission", [off, third])
    assert a.status == "CONFLICTING" and a.value == {"kind": "percent", "value": 30}
    assert "THIRD_PARTY_DISAGREES" in a.flags and {v.evidence_id for v in a.values} == {
        off.evidence_id,
        third.evidence_id,
    }
    two_official = resolve("commission", [off, ev("commission", {"kind": "percent", "value": 20})])
    assert two_official.status == "CONFLICTING" and two_official.value is None and not two_official.has_data


def test_TC_E2_FR008_04_unknown_without_evidence_and_multi_values() -> None:
    assert resolve("cookie_days", []).status == "UNKNOWN"
    feats = resolve(
        "feature",
        [
            ev("feature", {"text": "Alerts"}),
            ev("feature", {"text": "alerts"}),
            ev("feature", {"text": "App"}, "INFERRED", "b.example"),
        ],
    )
    assert feats.status == "VERIFIED" and len(feats.value or []) == 2
    prices = resolve(
        "price", [ev("price", {"plan": "Micro", "amount": 19}), ev("price", {"plan": "micro", "amount": 29})]
    )
    assert prices.status == "CONFLICTING"
