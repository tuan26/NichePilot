"""T069 – Ngưỡng bằng chứng + nhóm độc lập (scoring-rubric §1; FR-013a, FR-013b, FR-015, SC-003a).

Logic xác định (thuần, không I/O): bằng chứng hợp lệ phải đủ trường; hai nguồn độc lập = khác eTLD+1 **và** không phải bản sao
(SimHash ≤ 3 trên trích đoạn hoặc trên toàn nguồn). Đánh giá AI (relevance/quality/copy_suspected) chỉ là đầu vào.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from pathlib import Path

import pytest

from nichepilot.modules.discovery.evidence_rules import EvidenceItem, EvidenceRules, evaluate_threshold
from nichepilot.modules.discovery.fingerprint import simhash64

pytestmark = pytest.mark.discovery

NOW = datetime(2026, 11, 20, 8, 0, tzinfo=UTC)
FORUM = (
    "I run a two-person bakery and every week we run out of flour or butter without warning. Spreadsheets take too long"
    " to update after a busy morning, and the big restaurant inventory apps are far too expensive for us."
)
REVIEW = (
    "StockPal is fine for restaurants but for a micro bakery it is overkill: the setup took a full weekend and it still"
    " does not warn us before the dairy expires, so we keep throwing away cream every Friday."
)
OTHER = (
    "Our café counts milk and eggs on paper twice a day because no app we tried handles tiny quantities; we waste"
    " roughly forty dollars of dairy each week and nobody has time to update a spreadsheet."
)


def item(eid: str, url: str, excerpt: str | None = FORUM, **kw: object) -> EvidenceItem:
    base: dict[str, object] = {
        "evidence_id": eid,
        "source_url": url,
        "excerpt": excerpt,
        "collected_at": NOW,
        "verification_status": "VERIFIED",
        "redaction_status": "REDACTED",
        "lifecycle_status": "ACTIVE",
        "purpose": "PAIN_POINT",
        "relevance": 0.9,
        "quality": 0.8,
        "copy_suspected": False,
        "data_origin": "REAL",
    }
    base.update(kw)
    return EvidenceItem(**base)  # type: ignore[arg-type]


def test_TC_E1_FR013b_01_two_valid_items_from_two_independent_sources_is_sufficient() -> None:
    res = evaluate_threshold([item("a", "https://forum.example/t/1"), item("b", "https://reviews.example/x", REVIEW)])
    assert res.status == "EVIDENCE_SUFFICIENT"
    assert res.counted_ids == {"a", "b"} and res.independent_groups == 2
    assert res.groups["a"] != res.groups["b"]
    one = evaluate_threshold([item("a", "https://forum.example/t/1")])
    assert one.status == "INSUFFICIENT_EVIDENCE" and one.independent_groups == 1


def test_TC_E1_FR013a_01_items_missing_required_fields_are_not_counted() -> None:
    good = item("ok", "https://reviews.example/x", REVIEW)
    for field, value in (
        ("source_url", None),
        ("source_url", ""),
        ("excerpt", None),
        ("excerpt", "   "),
        ("collected_at", None),
        ("verification_status", None),
        ("verification_status", "UNKNOWN"),
    ):
        broken = item("x", "https://forum.example/t/1", **{field: value})
        res = evaluate_threshold([good, broken])
        assert res.status == "INSUFFICIENT_EVIDENCE", field
        assert "x" not in res.counted_ids and res.invalid_reasons["x"], field


def test_TC_E1_FR013b_02_same_registered_domain_is_one_source_group() -> None:
    res = evaluate_threshold(
        [
            item("a", "https://forum.example/t/1"),
            item("b", "https://community.forum.example/t/2", REVIEW),  # cùng eTLD+1
            item("c", "https://www.forum.example/t/3", OTHER),
        ]
    )
    assert res.status == "INSUFFICIENT_EVIDENCE"
    assert res.independent_groups == 1 and len(set(res.groups.values())) == 1
    multi = evaluate_threshold([item("a", "https://a.blogspot.co.uk/x"), item("b", "https://b.co.uk/y", REVIEW)])
    assert multi.independent_groups == 2  # hậu tố công cộng nhiều cấp (offline PSL)


def test_TC_E1_FR013b_03_cross_domain_copies_are_not_independent() -> None:
    exact = evaluate_threshold([item("a", "https://forum.example/t/1"), item("b", "https://aggregator.example/c")])
    assert exact.status == "INSUFFICIENT_EVIDENCE" and exact.groups["a"] == exact.groups["b"]
    near = FORUM.replace("two-person", "two person").replace("far too", "way too")  # bản gần giống
    assert near != FORUM
    res = evaluate_threshold([item("a", "https://forum.example/t/1"), item("b", "https://mirror.example/p", near)])
    assert res.independent_groups == 1, "bản gần giống khác tên miền phải cùng nhóm"
    # trích đoạn khác nhau nhưng TOÀN BỘ nguồn là bản sao (SimHash nguồn) → vẫn cùng nhóm
    page = simhash64(FORUM + " " + REVIEW)
    src = evaluate_threshold(
        [
            item("a", "https://forum.example/t/1", FORUM, source_simhash=page),
            item("b", "https://scraper.example/z", REVIEW, source_simhash=page),
        ]
    )
    assert src.independent_groups == 1


def test_TC_E1_FR013b_04_ai_assessment_and_status_filters() -> None:
    ok = item("ok", "https://reviews.example/x", REVIEW)
    cases: dict[str, dict[str, object]] = {
        "low_relevance": {"relevance": 0.59},
        "no_relevance": {"relevance": None},
        "low_quality": {"quality": 0.49},
        "no_quality": {"quality": None},
        "copy": {"copy_suspected": True},
        "needs_review": {"redaction_status": "NEEDS_REVIEW"},
        "unredacted": {"redaction_status": None},
        "erased": {"lifecycle_status": "ERASED"},
        "persona_only": {"purpose": "PERSONA"},
        "mock": {"data_origin": "MOCK"},
    }
    for name, kw in cases.items():
        res = evaluate_threshold([ok, item("x", "https://forum.example/t/1", **kw)])
        assert res.status == "INSUFFICIENT_EVIDENCE", name
        assert "x" not in res.counted_ids, name
    edge = evaluate_threshold([ok, item("x", "https://forum.example/t/1", relevance=0.6, quality=0.5)])
    assert edge.status == "EVIDENCE_SUFFICIENT"  # đúng ngưỡng = đạt


def test_TC_E1_FR013b_05_mock_items_counted_separately_for_mock_niches() -> None:
    items = [
        item("a", "https://forum.example/t/1", data_origin="MOCK"),
        item("b", "https://reviews.example/x", REVIEW, data_origin="MOCK"),
    ]
    assert evaluate_threshold(items, origin="MOCK").status == "EVIDENCE_SUFFICIENT"
    assert evaluate_threshold(items, origin="REAL").status == "INSUFFICIENT_EVIDENCE"
    mixed = [items[0], item("c", "https://reviews.example/x", REVIEW)]
    assert evaluate_threshold(mixed, origin="REAL").status == "INSUFFICIENT_EVIDENCE"  # không "mượn" MOCK


def test_TC_E1_FR015_02_duplicates_grouped_transitively_and_counted_once() -> None:
    # a ~ b (bản sao khác miền), b cùng miền c → a, b, c một nhóm; d độc lập
    res = evaluate_threshold(
        [
            item("a", "https://forum.example/t/1"),
            item("b", "https://aggregator.example/c"),
            item("c", "https://news.aggregator.example/d", OTHER),
            item("d", "https://reviews.example/x", REVIEW),
        ]
    )
    assert res.groups["a"] == res.groups["b"] == res.groups["c"] != res.groups["d"]
    assert res.independent_groups == 2 and res.status == "EVIDENCE_SUFFICIENT"
    # nhãn nhóm ổn định, không phụ thuộc thứ tự đầu vào
    items = [
        item("a", "https://forum.example/t/1"),
        item("b", "https://aggregator.example/c"),
        item("d", "https://reviews.example/x", REVIEW),
    ]
    assert evaluate_threshold(items).groups == evaluate_threshold(list(reversed(items))).groups


def test_TC_E1_FR013b_06_rules_come_from_weights_version() -> None:
    rules = EvidenceRules.from_json(
        {
            "min_items": 3,
            "min_independent_groups": 2,
            "min_relevance": 0.7,
            "min_quality": 0.5,
            "simhash_max_distance": 3,
        }
    )
    two = [item("a", "https://forum.example/t/1"), item("b", "https://reviews.example/x", REVIEW)]
    assert evaluate_threshold(two, rules=rules).status == "INSUFFICIENT_EVIDENCE"
    three = [*two, item("c", "https://cafe.example/y", OTHER)]
    assert evaluate_threshold(three, rules=rules).status == "EVIDENCE_SUFFICIENT"
    with pytest.raises(ValueError):
        EvidenceRules.from_json({"min_items": 0})


def test_TC_E1_SC003a_01_labelled_copy_set_counts_zero_copy_pairs_as_independent() -> None:
    """Bộ kiểm thử có nhãn: mọi cặp (bản gốc, bản sao khác tên miền) phải cùng nhóm."""
    fixtures = Path(__file__).resolve().parents[2] / "fixtures" / "discovery"
    original = (fixtures / "forum_bakery.html").read_text(encoding="utf-8")
    copy = (fixtures / "copy_of_forum_bakery.html").read_text(encoding="utf-8")

    def paragraphs(html: str) -> list[str]:
        import re

        return [" ".join(p.split()) for p in re.findall(r"<p>(.*?)</p>", html, flags=re.S)]

    pairs = list(zip(paragraphs(original), paragraphs(copy), strict=True))
    assert len(pairs) == 3
    copies_counted_independent = 0
    for i, (a, b) in enumerate(pairs):
        res = evaluate_threshold(
            [item(f"o{i}", "https://forum.example/t/bakery", a), item(f"c{i}", "https://aggregator.example/copy", b)]
        )
        copies_counted_independent += int(res.groups[f"o{i}"] != res.groups[f"c{i}"])
    assert copies_counted_independent == 0
    # sửa nhẹ (đổi vài từ) vẫn bị coi là bản sao
    tweaked = dataclasses.replace(
        item("t", "https://repost.example/x", pairs[0][1].replace("every week", "each week")),
    )
    res = evaluate_threshold([item("o", "https://forum.example/t/bakery", pairs[0][0]), tweaked])
    assert res.independent_groups == 1
