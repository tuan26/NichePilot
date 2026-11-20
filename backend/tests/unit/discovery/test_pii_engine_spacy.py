"""T024 – SpacyEnPiiEngine: chỉ dev/test khi nhóm tùy chọn pii-ner được cài (quyết định I2)."""

from __future__ import annotations

import importlib.util

import pytest

pytestmark = [pytest.mark.discovery, pytest.mark.pii_ner]


def test_TC_E1_FR012a_06_spacy_engine_marks_names() -> None:
    if importlib.util.find_spec("spacy") is None or importlib.util.find_spec("en_core_web_sm") is None:
        pytest.skip("nhóm tùy chọn pii-ner chưa được cài (chỉ dev/test)")
    from nichepilot.tools.privacy.pii_spacy import SpacyEnPiiEngine

    r = SpacyEnPiiEngine().redact("Last week Priya Raman told me it takes days.", language="en", country="US")
    assert "Priya Raman" not in r.text and "[PERSON]" in r.text
