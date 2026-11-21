"""Schema E1 (T055): tham số job, đầu ra AI bắt buộc (FR-013, FR-014, FR-019), DTO API.

Đầu ra AI chỉ được chấp nhận khi khớp schema; `evidence_ids` phải thuộc tập bằng chứng đã cung cấp (chống bịa nguồn)
– kiểm
tra ở agent. Mức tiêu chí ∈ {0,25,50,75,100} hoặc null (scoring-rubric §2).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Status = Literal["VERIFIED", "INFERRED", "UNKNOWN", "CONFLICTING"]
Level = Literal[0, 25, 50, 75, 100]


class DiscoveryRunParams(BaseModel):
    """Tham số job `discovery.run` (data-model `discovery_runs`). Không có trường chọn nguồn chưa xác minh (A1)."""

    model_config = ConfigDict(extra="forbid")
    market: str = Field(pattern=r"^[A-Z]{2}$")
    research_language: str = Field(default="en", pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
    seed_topic: str | None = Field(default=None, max_length=200)
    max_candidates: int = Field(default=20, ge=1, le=50)
    time_limit_s: int = Field(default=5400, ge=300, le=14400)
    page_limit: int = Field(default=300, ge=10, le=2000)
    per_domain_interval_s: float = Field(default=2.0, ge=1)
    mock_scenario: str | None = None


class DiscoveryRunResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    run_id: str
    outcome: Literal["COMPLETED", "PARTIAL_COMPLETED"]
    stop_reason: str


class CandidateOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    micro_niche: str = Field(min_length=1, max_length=200)
    domain: str = Field(min_length=1, max_length=100, description="Lĩnh vực rộng (để kiểm tra đa dạng ≥ 3 lĩnh vực)")
    customer_group: str = Field(min_length=1, max_length=300)
    core_problem: str = Field(min_length=1, max_length=500)
    queries: list[str] = Field(min_length=1, max_length=5)


class CandidatesOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    candidates: list[CandidateOut] = Field(max_length=50)


class PainPointOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(max_length=2000)
    severity: int | None = Field(default=None, ge=1, le=5)
    severity_reason: str | None = Field(default=None, max_length=500)
    status: Status
    evidence_ids: list[str] = Field(default_factory=list, max_length=50)


class ConflictValue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str | int | float | bool | list[str] | dict[str, str]
    evidence_ids: list[str] = Field(min_length=1, max_length=50)


class FindingOut(BaseModel):
    """Một kết luận có trạng thái xác minh (FR-014): UNKNOWN không có giá trị; CONFLICTING lưu MỌI giá trị kèm nguồn
    (QA-05)."""

    model_config = ConfigDict(extra="forbid")
    value: str | int | float | bool | list[str] | dict[str, str] | None = None
    status: Status
    evidence_ids: list[str] = Field(default_factory=list, max_length=50)
    conflicting_values: list[ConflictValue] = Field(default_factory=list, max_length=10)


class PersonaOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    segment: FindingOut | None = None
    context: FindingOut | None = None
    goals: FindingOut | None = None
    obstacles: FindingOut | None = None
    ability_to_pay: FindingOut | None = None


class FindingsOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    CURRENT_SOLUTIONS: FindingOut | None = None
    MARKET_GAPS: FindingOut | None = None
    POTENTIAL_PRODUCTS: FindingOut | None = None
    MONETIZATION: FindingOut | None = None
    CHANNELS: FindingOut | None = None
    RISKS: FindingOut | None = None


class CompetitorOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    kind: Literal["PRODUCT", "SERVICE", "MANUAL_WORKAROUND"]
    url: str | None = Field(default=None, max_length=2000, pattern=r"^https?://")
    strengths: list[str] = Field(default_factory=list, max_length=10)
    weaknesses: list[str] = Field(default_factory=list, max_length=10)
    evidence_ids: list[str] = Field(default_factory=list, max_length=50)


class ExtractOutput(BaseModel):
    """Đầu ra `discovery.extract`. `extra=forbid`: trường lạ (vd. search_volume, CPC) → đầu ra bị loại (FR-011,
    SC-004)."""

    model_config = ConfigDict(extra="forbid")
    pain_points: list[PainPointOut] = Field(default_factory=list, max_length=20)
    persona: PersonaOut | None = None
    findings: FindingsOut | None = None
    competitors: list[CompetitorOut] = Field(default_factory=list, max_length=20)


class EvidenceAssessmentOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    evidence_id: str
    relevance: float = Field(ge=0, le=1)
    quality: float = Field(ge=0, le=1)
    copy_suspected: bool = False
    reason: str = Field(min_length=1, max_length=500)


class CriterionOut(BaseModel):
    """AI ĐỀ XUẤT mức tiêu chí (scoring-rubric §2); mức ngoài thang → đầu ra bị loại. Tổng điểm do mã tính (FR-017,
    FR-019)."""

    model_config = ConfigDict(extra="forbid")
    level: Level | None = None
    status: Status
    reason: str = Field(default="", max_length=500)
    evidence_ids: list[str] = Field(default_factory=list, max_length=50)


class CriteriaOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    problem_severity: CriterionOut | None = None
    monetization: CriterionOut | None = None
    market_gap: CriterionOut | None = None
    reachability: CriterionOut | None = None
    competition_opportunity: CriterionOut | None = None
    demand_stability: CriterionOut | None = None


class RecommendationOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["PURSUE", "REJECT", "UNKNOWN"]
    reason: str = Field(min_length=1, max_length=1000)


class AssessOutput(BaseModel):
    """Đầu ra `discovery.assess`: đánh giá từng bằng chứng (US2) + mức đề xuất cho 6 tiêu chí và đề xuất tiếp
    tục/loại bỏ (US3).

    Mọi phần là nhận định INFERRED – đầu vào cho logic xác định (ngưỡng, Opportunity, Confidence). Không có search
    volume/CPC."""

    model_config = ConfigDict(extra="forbid")
    evidence: list[EvidenceAssessmentOut] = Field(default_factory=list, max_length=50)
    criteria: CriteriaOut | None = None
    recommendation: RecommendationOut | None = None
