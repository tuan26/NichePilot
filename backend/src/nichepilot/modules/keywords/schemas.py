"""Schema E3 – đầu ra AI (bắt buộc, `extra="forbid"` – Constitution V, FR-029) và tham số/kết quả lượt.

Đầu ra AI **không có** trường Search Volume / CPC / Keyword Difficulty: AI trả thêm số liệu thì cả đầu ra bị loại
(research R-02).
AI chỉ ĐỀ XUẤT keyword/intent/tóm tắt có dẫn nguồn gốc/bằng chứng; điểm, cluster, gap do mã quyết định (FR-020).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Level = Literal[0, 25, 50, 75, 100]
KeywordType = Literal["PROBLEM", "SOLUTION", "PRODUCT", "COMPARISON", "INFORMATIONAL"]
Intent = Literal["INFORMATIONAL", "COMMERCIAL_INVESTIGATION", "TRANSACTIONAL", "NAVIGATIONAL"]
OriginType = Literal["PAIN_POINT", "PERSONA", "PRODUCT"]
ContentType = Literal["GUIDE", "COMPARISON", "REVIEW", "LIST", "FAQ"]
PERSONA_ATTRIBUTES = ("segment", "goals", "budget", "frustrations", "buying_criteria", "channels", "knowledge_level")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OriginOut(_Strict):
    origin_type: OriginType
    pain_point_id: str | None = None
    product_id: str | None = None
    persona_attribute: str | None = Field(default=None, max_length=60)
    reason: str = Field(default="", max_length=300)


class LevelOut(_Strict):
    level: Level | None = None
    reason: str = Field(default="", max_length=600)
    evidence_ids: list[str] = Field(default_factory=list, max_length=12)


class KeywordOut(_Strict):
    text: str = Field(min_length=2, max_length=150)
    keyword_type: KeywordType
    intent: Intent
    intent_reason: str = Field(default="", max_length=300)
    origins: list[OriginOut] = Field(min_length=1, max_length=5)
    fit: LevelOut = Field(default_factory=LevelOut)


class KeywordsGenerateOutput(_Strict):
    keywords: list[KeywordOut] = Field(default_factory=list, max_length=40)


class PageSummaryOut(_Strict):
    url: str = Field(min_length=8, max_length=500)
    headings: list[str] = Field(default_factory=list, max_length=10)
    topics: list[str] = Field(default_factory=list, max_length=15)
    has_comparison: bool = False
    has_pricing: bool = False
    has_experience_evidence: bool = False
    covered_pain_point_ids: list[str] = Field(default_factory=list, max_length=20)
    evidence_ids: list[str] = Field(min_length=1, max_length=6)


class KeywordsAnalyzeOutput(_Strict):
    pages: list[PageSummaryOut] = Field(default_factory=list, max_length=12)


class CitedText(_Strict):
    value: str = Field(min_length=1, max_length=400)
    evidence_ids: list[str] = Field(min_length=1, max_length=8)


class PersonaOut(_Strict):
    goals: CitedText | None = None
    barriers: CitedText | None = None
    knowledge_level: CitedText | None = None
    typical_questions: CitedText | None = None


class StrategyOut(_Strict):
    content_type: ContentType
    angle: str = Field(min_length=1, max_length=400)
    pain_point_ids: list[str] = Field(default_factory=list, max_length=10)
    product_ids: list[str] = Field(default_factory=list, max_length=10)
    primary_keyword_id: str | None = None
    secondary_keyword_ids: list[str] = Field(default_factory=list, max_length=20)
    gap_refs: list[str] = Field(default_factory=list, max_length=10)


class ClusterStrategyOut(_Strict):
    cluster_id: str
    persona: PersonaOut = Field(default_factory=PersonaOut)
    strategy: StrategyOut | None = None


class KeywordsStrategyOutput(_Strict):
    clusters: list[ClusterStrategyOut] = Field(default_factory=list, max_length=10)


class KeywordRunParams(_Strict):
    """`data-model.md keyword_runs.params`."""

    niche_id: str
    max_keywords: int = Field(default=60, ge=5, le=200)
    serp_keywords: int = Field(default=10, ge=0, le=30)
    competitor_pages: int = Field(default=3, ge=0, le=5)
    page_limit: int = Field(default=60, ge=5, le=200)
    time_limit_s: int = Field(default=1800, ge=60, le=5400)
    per_domain_interval_s: float = Field(default=2.0, ge=2.0, le=60.0)
    mock_scenario: str | None = None


class KeywordRunResult(_Strict):
    run_id: str
    outcome: Literal["COMPLETED", "PARTIAL_COMPLETED"]
    stop_reason: str
    keywords_found: int = 0


class SerpCheckParams(_Strict):
    cluster_id: str
    mock_scenario: str | None = None


class SerpCheckResult(_Strict):
    run_id: str
    outcome: Literal["COMPLETED", "PARTIAL_COMPLETED"]
    stop_reason: str
    new_version: int | None = None


class RecomputeParams(_Strict):
    niche_id: str | None = None
    mock_scenario: str | None = None


class RecomputeResult(_Strict):
    run_id: str
    outcome: Literal["COMPLETED", "PARTIAL_COMPLETED"]
    stop_reason: str
    recomputed: int = 0
