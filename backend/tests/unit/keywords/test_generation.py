"""T014 – keyword phải có nguồn gốc hợp lệ; keyword commercial theo mẫu (FR-002, FR-005, FR-007)."""

from __future__ import annotations

import pytest

from nichepilot.modules.keywords.generation import (
    GenerationInputs,
    PainPointInput,
    PersonaInput,
    ProductInput,
    commercial_keywords,
    display_name,
    validate_generated,
)
from nichepilot.modules.keywords.schemas import KeywordsGenerateOutput

pytestmark = [pytest.mark.keywords]

TEMPLATES = ["best {product} alternatives", "{product} review", "{product} pricing", "{product} vs {other}"]


def _inputs(**over: object) -> GenerationInputs:
    base: dict[str, object] = {
        "niche_id": "n1",
        "micro_niche": "micro bakery stock",
        "segment": "[MOCK DEMO] micro bakery owners",
        "country": "US",
        "niche_compliance_sensitive": False,
        "pain_points": {"p1": PainPointInput("p1", "Ingredients run out", frozenset({"e1"}), 2)},
        "persona": {"segment": PersonaInput("segment", "micro bakery owners", frozenset({"e2"}))},
        "products": {
            "pr1": ProductInput(
                "pr1", "[MOCK DEMO] ShelfAlert", 75, "fits", frozenset({"e3"}), frozenset({"p1"}), True, False
            ),
            "pr2": ProductInput("pr2", "[MOCK DEMO] CrumbCount", None, "", frozenset(), frozenset(), False, False),
        },
    }
    base.update(over)
    return GenerationInputs(**base)  # type: ignore[arg-type]


def _kw(text: str, origins: list[dict[str, object]], kt: str = "PROBLEM") -> dict[str, object]:
    return {
        "text": text,
        "keyword_type": kt,
        "intent": "INFORMATIONAL",
        "origins": origins,
        "fit": {"level": 75, "reason": "r", "evidence_ids": ["e1"]},
    }


def test_TC_E3_FR005_01_invalid_or_foreign_origin_rejected() -> None:
    out = KeywordsGenerateOutput.model_validate(
        {
            "keywords": [
                _kw(
                    "how to stop running out of flour",
                    [{"origin_type": "PAIN_POINT", "pain_point_id": "p-other-niche"}],
                ),
                _kw("flour budget tips", [{"origin_type": "PERSONA", "persona_attribute": "income"}]),
                _kw("bakery stock tool", [{"origin_type": "PAIN_POINT", "pain_point_id": "p1", "product_id": "pr1"}]),
                _kw("shelfalert setup", [{"origin_type": "PAIN_POINT", "pain_point_id": "p1"}], kt="PRODUCT"),
            ]
        }
    )
    v = validate_generated(out, _inputs())
    assert v.kept == [] and v.rejected == 4
    assert v.reasons == {"invalid_origin": 3, "product_type_without_product": 1}


def test_TC_E3_FR005_02_valid_origins_kept_with_flags() -> None:
    out = KeywordsGenerateOutput.model_validate(
        {
            "keywords": [
                _kw(
                    "how to stop running out of flour in a micro bakery",
                    [{"origin_type": "PAIN_POINT", "pain_point_id": "p1"}],
                ),
                _kw("shelfalert low stock alerts", [{"origin_type": "PRODUCT", "product_id": "pr1"}], kt="PRODUCT"),
                _kw("stock tips for micro bakery owners", [{"origin_type": "PERSONA", "persona_attribute": "segment"}]),
            ]
        }
    )
    v = validate_generated(out, _inputs())
    assert len(v.kept) == 3 and v.rejected == 0
    assert v.kept[0].length_class == "LONG_TAIL"
    assert v.kept[1].risk_flags == ["BRAND_TERM"]  # chương trình cấm brand bidding
    assert v.kept[0].risk_flags == []


def test_TC_E3_FR007_01_commercial_templates_for_every_product() -> None:
    kws = commercial_keywords(_inputs(), TEMPLATES)
    by_product: dict[str, list[str]] = {}
    for k in kws:
        by_product.setdefault(k.origins[0]["product_id"], []).append(k.text)
    assert set(by_product) == {"pr1", "pr2"}
    assert "ShelfAlert vs CrumbCount" in by_product["pr1"] and "CrumbCount pricing" in by_product["pr2"]
    assert all("[MOCK" not in k.text for k in kws)
    shelf = [k for k in kws if k.origins[0]["product_id"] == "pr1"]
    assert all(k.fit and k.fit["level"] == 75 and k.fit["evidence_ids"] == ["e3"] for k in shelf)
    assert all(
        k.fit is None for k in kws if k.origins[0]["product_id"] == "pr2"
    )  # không có mức E2 → UNKNOWN, không bịa
    assert {k.intent for k in kws if k.text.endswith("pricing")} == {"TRANSACTIONAL"}
    assert {k.keyword_type for k in kws if " vs " in k.text} == {"COMPARISON"}
    one = _inputs(products={"pr1": _inputs().products["pr1"]})
    assert all(" vs " not in k.text for k in commercial_keywords(one, TEMPLATES))


def test_TC_E3_FR002_01_display_name_strips_labels() -> None:
    assert display_name("[MOCK DEMO] ShelfAlert") == "ShelfAlert"
    assert display_name("StockPal") == "StockPal"
