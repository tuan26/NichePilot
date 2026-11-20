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
    status: Status
    evidence_ids: list[str] = Field(default_factory=list)


class ExtractOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pain_points: list[PainPointOut] = Field(default_factory=list, max_length=20)
