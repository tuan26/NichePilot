"""T009 – kiểm chứng đầu ra AI chống bịa số liệu (research R-03; FR-009, FR-024)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nichepilot.modules.products.extraction import numbers_in, supported, validate_products, validate_program_extract
from nichepilot.modules.products.schemas import ProductsExtractOutput, ProgramExtractOutput

pytestmark = pytest.mark.products

EX = {
    "a": "[MOCK] StockPal Micro costs $1,299.00 per year or $19 per month.",
    "b": "[MOCK] Earn 30% recurring commission for 12 months with a 60-day cookie. Minimum payout $50.",
}


def test_TC_E2_FR009_00_number_normalisation() -> None:
    assert {1299, 19} <= {int(x) for x in numbers_in(EX["a"]) if x == int(x)}
    assert supported(1299.0, ["a"], EX) and supported(30, ["b"], EX) and not supported(45, ["b"], EX)


def test_TC_E2_FR009_01_unknown_evidence_id_rejects_whole_product() -> None:
    out = ProductsExtractOutput.model_validate(
        {
            "products": [
                {
                    "name": "StockPal",
                    "prices": [{"plan": "Micro", "amount": 19, "period": "month", "evidence_ids": ["a"]}],
                },
                {"name": "Ghost", "features": [{"text": "x", "evidence_ids": ["zzz"]}]},
            ]
        }
    )
    kept, v = validate_products(out, EX, pain_point_ids=set())
    assert [p.name for p in kept] == ["StockPal"] and v.rejected_items == 1


def test_TC_E2_FR009_02_number_not_in_excerpt_becomes_unknown() -> None:
    out = ProductsExtractOutput.model_validate(
        {"products": [{"name": "StockPal", "prices": [{"plan": "Pro", "amount": 49, "evidence_ids": ["a"]}]}]}
    )
    kept, v = validate_products(out, EX, pain_point_ids=set())
    assert kept[0].prices == [] and v.rejected_values == 1
    prog = ProgramExtractOutput.model_validate(
        {
            "programs": [
                {
                    "name": "StockPal Partners",
                    "commission": {"kind": "recurring", "value": 45, "evidence_ids": ["b"]},
                    "cookie": {"days": 60, "evidence_ids": ["b"]},
                    "payment": {"methods": ["PayPal"], "min_payout": 100, "evidence_ids": ["b"]},
                }
            ]
        }
    )
    _, programs, v2 = validate_program_extract(prog, EX)
    p = programs[0]
    assert p.commission is None and p.cookie is not None and p.cookie.days == 60
    assert p.payment is not None and p.payment.min_payout is None and v2.rejected_values == 2


def test_TC_E2_FR009_03_codes_outside_catalogue_rejected() -> None:
    with pytest.raises(ValidationError):
        ProgramExtractOutput.model_validate(
            {"programs": [{"name": "X", "ad_restrictions": {"codes": ["NO_TIKTOK"], "evidence_ids": ["b"]}}]}
        )
    prog = ProgramExtractOutput.model_validate(
        {"programs": [{"name": "X", "promotion_regions": {"include": ["USA"], "evidence_ids": ["b"]}}]}
    )
    _, programs, v = validate_program_extract(prog, EX)
    assert programs[0].promotion_regions is None and v.rejected_values == 1


def test_TC_E2_FR024_00_extra_keys_forbidden() -> None:
    with pytest.raises(ValidationError):
        ProductsExtractOutput.model_validate({"products": [{"name": "X", "rating": 5}]})
