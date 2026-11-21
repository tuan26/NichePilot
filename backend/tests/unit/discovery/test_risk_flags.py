"""T090 – Cờ rủi ro tuân thủ cho lĩnh vực nhạy cảm (FR-035): gắn cờ, KHÔNG tự loại ngách."""

from __future__ import annotations

import pytest

from nichepilot.modules.discovery.risk import compliance_sensitive, risk_flags

pytestmark = pytest.mark.discovery


def test_TC_E1_FR035_01_sensitive_domains_flagged_not_excluded() -> None:
    for text in (
        "weight loss supplements for new mothers",
        "payday loan comparison for gig workers",
        "online casino bonus tracking",
        "CBD oil dosage for anxiety",
        "crypto trading signals for beginners",
        "prescription medication reminders for seniors",
    ):
        assert compliance_sensitive(text), text
    for text in ("flour inventory for micro bakeries", "dog grooming appointment scheduling"):
        assert not compliance_sensitive(text), text
    flags = risk_flags(
        texts=["payday loan comparison"], monetization_status="SIGNALS_FOUND", freshness=0.9, has_evidence=True
    )
    assert flags == ["COMPLIANCE_SENSITIVE"]
    flags2 = risk_flags(
        texts=["bakery"], monetization_status="MONETIZATION_UNVERIFIED", freshness=0.1, has_evidence=True
    )
    assert flags2 == ["LOW_EVIDENCE_FRESHNESS", "MONETIZATION_RISK"]
    assert risk_flags(texts=["bakery"], monetization_status="SIGNALS_FOUND", freshness=0.0, has_evidence=False) == []
    # chưa có tín hiệu affiliate (kể cả khi chưa có bằng chứng) → vẫn gắn cờ rủi ro monetization (FR-010)
    assert risk_flags(
        texts=["bakery"], monetization_status="MONETIZATION_UNVERIFIED", freshness=0.0, has_evidence=False
    ) == ["MONETIZATION_RISK"]
