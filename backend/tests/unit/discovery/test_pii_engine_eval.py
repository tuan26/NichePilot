"""T131 – Đo chất lượng PiiEngine trên tập có nhãn (FR-012a, FR-012b, FR-032, SC-016).

Không nới bảo vệ PII để tăng số ngách đủ bằng chứng: false negative PHẢI bằng 0 trên tập có nhãn. Tỷ lệ cảnh báo sai được đo
và báo cáo (không phải điều kiện đạt) để chủ sở hữu quyết định phương án engine – không tự đổi engine.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from nichepilot.tools.privacy.pii import RegexPhonePiiEngine

pytestmark = pytest.mark.discovery
SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "pii_engine_eval.py"


def _load():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("pii_engine_eval", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pii_engine_eval"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_TC_E1_FR012a_08_no_false_negative_on_labeled_set() -> None:
    res = _load().evaluate(RegexPhonePiiEngine())
    assert res.total >= 30 and res.with_pii >= 15 and res.without_pii >= 10
    assert res.false_negative == 0, f"PII lọt ở mẫu {res.fn_indexes}"


def test_TC_E1_FR032_02_metrics_distinguish_true_and_false_alerts() -> None:
    res = _load().evaluate(RegexPhonePiiEngine())
    s = res.summary()
    assert s["true_positive"] + s["false_negative"] == s["with_pii"]
    assert s["false_positive"] + s["true_negative"] == s["without_pii"]
    assert 0 <= s["needs_review_rate"] <= 1 and 0 <= s["false_positive_rate"] <= 1
    assert "text" not in str(s)  # báo cáo không chứa nội dung mẫu
