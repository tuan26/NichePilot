"""T030 – persona cấp cluster, content strategy, loại tuyên bố trải nghiệm (FR-022, FR-024, BR-11)."""

from __future__ import annotations

import pytest

from nichepilot.modules.keywords.schemas import KeywordsStrategyOutput
from nichepilot.modules.keywords.strategy import ClusterContext, strip_claims, validate_strategy

pytestmark = [pytest.mark.keywords]

TERMS = ["we tested", "hands-on", "đã dùng thử"]
CTX = ClusterContext(
    cluster_id="c1",
    evidence_ids=frozenset({"e1", "e2"}),
    pain_point_ids=frozenset({"p1"}),
    product_ids=frozenset({"pr1"}),
    keyword_ids=frozenset({"k1", "k2"}),
    gap_pain_point_ids=frozenset({"p1"}),
)


def _out(**over: object) -> KeywordsStrategyOutput:
    item = {
        "cluster_id": "c1",
        "persona": {
            "goals": {"value": "Never run out of flour", "evidence_ids": ["e1"]},
            "barriers": {"value": "Thin budgets", "evidence_ids": ["e-unknown"]},
        },
        "strategy": {
            "content_type": "GUIDE",
            "angle": "Explain low-stock alerts step by step. We tested five apps hands-on.",
            "pain_point_ids": ["p1", "p-foreign"],
            "product_ids": ["pr1"],
            "primary_keyword_id": "k1",
            "secondary_keyword_ids": ["k2", "k-foreign", "k1"],
            "gap_refs": ["p1"],
        },
    }
    item.update(over)
    return KeywordsStrategyOutput.model_validate({"clusters": [item]})


def test_TC_E3_FR022_01_persona_without_cluster_evidence_unknown() -> None:
    v = validate_strategy(_out().clusters, {"c1": CTX}, TERMS)
    persona = v.insights["c1"]["persona"]
    assert persona["goals"]["status"] == "INFERRED" and persona["goals"]["evidence_ids"] == ["e1"]
    assert persona["barriers"]["status"] == "UNKNOWN"
    assert persona["knowledge_level"]["status"] == "UNKNOWN"


def test_TC_E3_FR024_01_strategy_ids_filtered_to_cluster() -> None:
    s = validate_strategy(_out().clusters, {"c1": CTX}, TERMS).insights["c1"]["strategy"]
    assert s["content_type"] == "GUIDE" and s["pain_point_ids"] == ["p1"]
    assert s["primary_keyword_id"] == "k1" and s["secondary_keyword_ids"] == ["k2"]
    unknown_cluster = validate_strategy(_out(cluster_id="other").clusters, {"c1": CTX}, TERMS)
    assert unknown_cluster.rejected_items == 1 and not unknown_cluster.insights


def test_TC_E3_BR11_01_experience_claims_removed() -> None:
    v = validate_strategy(_out().clusters, {"c1": CTX}, TERMS)
    assert v.insights["c1"]["strategy"]["angle"] == "Explain low-stock alerts step by step."
    assert v.rejected_claims == 1
    assert strip_claims("Chúng tôi đã dùng thử. Hướng dẫn cụ thể.", TERMS) == ("Hướng dẫn cụ thể.", 1)
    only_claim = _out(strategy={"content_type": "REVIEW", "angle": "We tested it hands-on."})
    assert validate_strategy(only_claim.clusters, {"c1": CTX}, TERMS).insights["c1"]["strategy"]["status"] == "UNKNOWN"
