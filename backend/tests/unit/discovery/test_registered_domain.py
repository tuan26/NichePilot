"""T027 – eTLD+1 và SimHash không gọi mạng (FR-015; research R-06). Rào chắn socket E0 đang bật trong mọi test."""

from __future__ import annotations

import pytest

from nichepilot.modules.discovery.fingerprint import content_hash, hamming, registered_domain, simhash64

pytestmark = pytest.mark.discovery


def test_TC_E1_FR015_01_registered_domain_offline_and_simhash_detects_copies() -> None:
    assert registered_domain("https://forum.example.co.uk/t/1") == "example.co.uk"
    assert registered_domain("https://Sub.Reviews.Example.com/x") == "example.com"
    assert registered_domain("http://localhost:8080/x") == "localhost"
    a = "I run a two-person bakery and every week we run out of flour or butter without warning."
    b = "I run a two person bakery, and every week we run out of flour or butter without warning!"
    c = "Our grooming salon double-books appointments every Saturday and clients get angry."
    assert hamming(simhash64(a), simhash64(b)) <= 3  # bản sao chỉ khác dấu câu
    assert hamming(simhash64(a), simhash64(c)) > 3
    assert -(2**63) <= simhash64(a) < 2**63  # vừa BIGINT
    assert len(content_hash("x")) == 64 and content_hash("x") == content_hash("x")
