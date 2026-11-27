"""T008 – chuẩn hóa, gộp trùng, độ dài keyword (FR-006, FR-008)."""

from __future__ import annotations

import pytest

from nichepilot.modules.keywords.normalize import dedup_key, length_class, normalize

pytestmark = [pytest.mark.keywords]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("inventory app", "HEAD"),
        ("bakery", "HEAD"),
        ("bakery inventory app", "MID"),
        ("how to track flour stock", "LONG_TAIL"),
        ("best stock alert app for micro bakeries", "LONG_TAIL"),
    ],
)
def test_TC_E3_FR006_01_length_class(text: str, expected: str) -> None:
    assert length_class(text) == expected


def test_TC_E3_FR008_01_dedup_case_accents_plural() -> None:
    assert dedup_key("Bakery Inventory Apps") == dedup_key("bakery inventory app")
    assert dedup_key("Phần mềm quản lý kho") == dedup_key("phan mem quan ly kho")
    assert dedup_key("stock alerts for bakeries") == dedup_key("Stock alert for bakery")
    assert normalize("  Đồ  ăn — nhanh! ") == "do an nhanh"


def test_TC_E3_FR008_02_dedup_word_order_but_not_different_terms() -> None:
    assert dedup_key("bakery stock alerts") == dedup_key("stock alerts bakery")
    assert dedup_key("bakery stock alerts") != dedup_key("bakery stock counts")
    assert dedup_key("glass") == "glass"  # không cắt 'ss'
