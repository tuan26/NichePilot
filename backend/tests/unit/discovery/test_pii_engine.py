"""T022 – RegexPhonePiiEngine (FR-012a, FR-012b, SC-016; research R-05, quyết định I2).

Bộ mẫu PII là dữ liệu GIẢ tự soạn (không thuộc người thật). Regex KHÔNG được coi là đủ cho mọi loại PII: đoạn có nguy cơ chứa
tên người phải là NEEDS_REVIEW.
"""

from __future__ import annotations

import pytest

from nichepilot.tools.privacy.pii import RegexPhonePiiEngine

pytestmark = pytest.mark.discovery
ENGINE = RegexPhonePiiEngine()


@pytest.mark.parametrize(
    ("text", "label", "secret"),
    [
        ("Contact me at owner.fake@example.com for details.", "[EMAIL]", "owner.fake@example.com"),
        ("Write to a.b-c+tag@sub.example.org today.", "[EMAIL]", "a.b-c+tag@sub.example.org"),
        ("Call +1 202-555-0143 after 5pm.", "[PHONE]", "202-555-0143"),
        ("Call (202) 555-0143 after 5pm.", "[PHONE]", "555-0143"),
        ("My handle is @groomfixer99 on the forum.", "[USER]", "groomfixer99"),
        ("Ask u/bakerguy_77 in that subreddit.", "[USER]", "bakerguy_77"),
        ("See https://forum.example/user/groomfixer99 for my posts.", "[USER]", "groomfixer99"),
        ("Posted by Taylor Brennan", "[PERSON]", "Taylor Brennan"),
    ],
)
def test_TC_E1_FR012a_01_structured_pii_is_replaced(text: str, label: str, secret: str) -> None:
    r = ENGINE.redact(text, language="en", country="US")
    assert label in r.text
    assert secret not in r.text
    assert r.status in {"REDACTED", "NEEDS_REVIEW"}
    assert sum(r.counts.values()) >= 1


def test_TC_E1_FR012a_02_vietnamese_phone_uses_market_region() -> None:
    r = ENGINE.redact("Gọi cho tôi số 0912 345 678 nhé.", language="vi", country="VN")
    assert "0912 345 678" not in r.text and "[PHONE]" in r.text


@pytest.mark.parametrize(
    "text",
    [
        "Last week Priya Raman told me rescheduling takes days.",  # tên trong câu, không theo mẫu
        "Thanks, Morgan",  # chữ ký
        "Hi Jordan, did you find a fix?",  # lời chào
        "Priya Raman runs a tutoring centre and loses students.",  # tên ở đầu câu
    ],
)
def test_TC_E1_FR012a_03_person_name_risk_needs_review(text: str) -> None:
    r = ENGINE.redact(text, language="en", country="US")
    assert r.status == "NEEDS_REVIEW", r.text


def test_TC_E1_FR012a_04_clean_text_redacted_and_unknown_language_needs_review() -> None:
    clean = (
        "I run a two-person bakery and every week we run out of flour. Spreadsheets take too long to update. "
        "Is there a simple tool that works on a phone? StockPal is built for restaurant chains."
    )
    r = ENGINE.redact(clean, language="en", country="US")
    assert r.status == "REDACTED" and r.text == clean and r.counts == {}
    # Ngôn ngữ chưa hiệu chỉnh: cụm viết hoa nghi ngờ → NEEDS_REVIEW (không coi regex là đủ)
    de = ENGINE.redact("Gestern hat Anna Schmidt gesagt, dass die Planung schwierig ist.", language="de", country="DE")
    assert de.status == "NEEDS_REVIEW"


def test_TC_E1_SC016_01_residual_pii_is_unsafe_never_redacted() -> None:
    # Email bị làm rối để lọt qua regex chính nhưng vẫn khớp kiểm tra lại → UNSAFE (đoạn bị bỏ)
    r = ENGINE.redact("mail me: owner (at) example.com or owner@example .com", language="en", country="US")
    assert r.status in {"UNSAFE", "NEEDS_REVIEW"}
    assert ENGINE.name == "regex-phone/1"
