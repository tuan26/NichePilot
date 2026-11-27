"""T022 – truy vấn xác định, không AI (research R-02; FR-011)."""

from __future__ import annotations

import pytest

from nichepilot.modules.products.queries import PainPointInput, niche_queries, product_queries

pytestmark = pytest.mark.products


def test_TC_E2_FR011_01_deterministic_queries() -> None:
    pps = [
        PainPointInput("1", "[MOCK DEMO] Ingredients run out", 4),
        PainPointInput("2", "Spreadsheets too slow", 3),
        PainPointInput("3", "Dairy expires", 5),
        PainPointInput("4", "Minor issue", 1),
    ]
    q = niche_queries(pps, "[MOCK DEMO] micro bakery owners", None, None)
    assert q == niche_queries(list(reversed(pps)), "[MOCK DEMO] micro bakery owners", None, None)
    assert q[0] == "Dairy expires micro bakery owners tool" and "Minor issue micro bakery owners tool" not in q
    assert q[-1] == "best software for micro bakery owners" and all("[MOCK" not in x for x in q)
    assert product_queries("StockPal", None) == ["StockPal pricing", "StockPal affiliate program"]
    assert product_queries("X", {"product": ["{product} partners"]}) == ["X partners"]
