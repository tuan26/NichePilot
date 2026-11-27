"""T025 – gom cluster xác định, keyword chính, điểm cluster (FR-016)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from nichepilot.modules.keywords.clustering import Member, choose_primary, cluster_key, cluster_scores, primary_origin

pytestmark = [pytest.mark.keywords]

PP = {"origin_type": "PAIN_POINT", "pain_point_id": "b-pp"}
PP2 = {"origin_type": "PAIN_POINT", "pain_point_id": "a-pp"}
PR = {"origin_type": "PRODUCT", "product_id": "prod"}
PE = {"origin_type": "PERSONA", "persona_attribute": "goals"}


def test_TC_E3_FR016_01_one_cluster_per_keyword_primary_and_scores() -> None:
    assert primary_origin([PR, PP, PP2]) == ("PAIN_POINT", "a-pp")
    assert primary_origin([PE, PR]) == ("PRODUCT", "prod")
    assert cluster_key([PP], "INFORMATIONAL") == "pp:b-pp|INFORMATIONAL"
    assert cluster_key([PP], "INFORMATIONAL") != cluster_key([PP], "COMMERCIAL_INVESTIGATION")
    assert cluster_key([PE], "INFORMATIONAL") == "pe:goals|INFORMATIONAL"
    members = [
        Member("k1", "stock app", "HEAD", Decimal("60"), Decimal("50")),
        Member("k2", "how to stop running out of flour", "LONG_TAIL", Decimal("80"), Decimal("40")),
        Member("k3", "flour", "HEAD", None, None),
    ]
    assert choose_primary(members) == "k2"
    assert cluster_scores(members) == (Decimal("70.00"), Decimal("45.00"), 2)
    assert cluster_scores([members[2]]) == (None, None, 0)
    with pytest.raises(ValueError):
        primary_origin([])
