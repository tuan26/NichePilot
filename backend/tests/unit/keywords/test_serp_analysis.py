"""T020 – SERP, phân tích đối thủ, content gap, kênh (FR-011…FR-015, FR-023)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nichepilot.modules.keywords.analysis import channels, content_gaps, validate_page_summaries
from nichepilot.modules.keywords.schemas import KeywordOut, KeywordsAnalyzeOutput, KeywordsGenerateOutput
from nichepilot.modules.keywords.serp import diff_results, page_type, results_from_hits

pytestmark = [pytest.mark.keywords]


def test_TC_E3_FR012_01_page_type_and_results() -> None:
    assert page_type("https://www.reddit.com/r/Baking/comments/x") == "forum"
    assert page_type("https://cooking.stackexchange.com/q/1") == "qa"
    assert page_type("https://youtube.com/watch?v=1") == "video"
    assert page_type("https://stockpal.example/pricing") == "product"
    hits = [
        {"url": "https://bakers-forum.example/t/flour", "title": "x", "redaction_status": "REDACTED"},
        {"url": "https://bakers-forum.example/t/flour", "title": "dup", "redaction_status": "REDACTED"},
        {"url": "https://pii.example/x", "title": "y", "redaction_status": "NEEDS_REVIEW"},
        {"url": "https://blog.example/post/1", "title": None, "redaction_status": "REDACTED"},
    ]
    res = results_from_hits(hits)
    assert [(r["position"], r["page_type"]) for r in res] == [(1, "forum"), (2, "article")]
    assert res[0]["domain"] == "bakers-forum.example"


def test_TC_E3_FR031_02_diff_results() -> None:
    old = [{"url": "a", "position": 1, "page_type": "forum"}, {"url": "b", "position": 2, "page_type": "article"}]
    assert diff_results(old, old) == {}
    new = [{"url": "b", "position": 1, "page_type": "article"}, {"url": "c", "position": 2, "page_type": "qa"}]
    d = diff_results(old, new)
    assert d["added"] == ["c"] and d["removed"] == ["a"] and d["moved"] == [{"url": "b", "from": 2, "to": 1}]
    assert diff_results(None, new) == {}


def test_TC_E3_FR013_01_page_summary_unknown_evidence_or_pain_point_rejected() -> None:
    out = KeywordsAnalyzeOutput.model_validate(
        {
            "pages": [
                {
                    "url": "https://a.example/x",
                    "headings": ["H"],
                    "covered_pain_point_ids": ["p1"],
                    "evidence_ids": ["e1"],
                },
                {"url": "https://a.example/x", "covered_pain_point_ids": [], "evidence_ids": ["e9"]},
                {"url": "https://b.example/y", "covered_pain_point_ids": ["zz"], "evidence_ids": ["e2"]},
                {"url": "https://c.example/never-fetched", "evidence_ids": ["e3"]},
            ]
        }
    )
    v = validate_page_summaries(
        out, page_evidence={"https://a.example/x": {"e1"}, "https://b.example/y": {"e2"}}, pain_point_ids=["p1"]
    )
    assert len(v.kept) == 1 and v.rejected == 3
    assert v.kept[0]["summary"]["covered_pain_point_ids"] == ["p1"]


def test_TC_E3_FR014_01_content_gap_observed_or_unknown() -> None:
    pages = [{"url": "https://a.example/x", "summary": {"covered_pain_point_ids": ["p1"]}}]
    gaps = content_gaps({"p1": "Run out", "p2": "Too pricey"}, pages)
    assert gaps["status"] == "OBSERVED" and [g["pain_point_id"] for g in gaps["items"]] == ["p2"]
    assert gaps["items"][0]["checked_urls"] == ["https://a.example/x"]
    assert content_gaps({"p1": "x"}, [])["status"] == "UNKNOWN"


def test_TC_E3_FR023_01_channels_from_forum_qa_video() -> None:
    res = [
        {"url": "https://f.example/t/1", "domain": "f.example", "page_type": "forum"},
        {"url": "https://f.example/t/2", "domain": "f.example", "page_type": "forum"},
        {"url": "https://v.example/w", "domain": "v.example", "page_type": "video"},
        {"url": "https://b.example/a", "domain": "b.example", "page_type": "article"},
    ]
    ch = channels(res)
    assert ch["status"] == "OBSERVED" and [c["domain"] for c in ch["items"]] == ["f.example", "v.example"]
    assert channels(None)["status"] == "UNKNOWN"


def test_TC_E3_FR011_01_intent_and_metrics_constrained_by_schema() -> None:
    base = {
        "text": "flour stock alerts",
        "keyword_type": "PROBLEM",
        "intent": "INFORMATIONAL",
        "origins": [{"origin_type": "PAIN_POINT", "pain_point_id": "p"}],
    }
    KeywordOut.model_validate(base)
    with pytest.raises(ValidationError):
        KeywordOut.model_validate({**base, "intent": "BUY_NOW"})
    with pytest.raises(ValidationError):  # TC_E3_FR009: AI không được trả chỉ số keyword
        KeywordsGenerateOutput.model_validate({"keywords": [{**base, "search_volume": 1200}]})
    with pytest.raises(ValidationError):
        KeywordOut.model_validate({**base, "origins": []})
