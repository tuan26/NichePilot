"""Job `discovery.recompute` (T082; internal-interfaces §6) – tính lại ngưỡng bằng chứng của các ngách sau khi xóa
bằng chứng.

Logic xác định, KHÔNG gọi AI (giới hạn `max_ai_calls = 1` chỉ vì ràng buộc `agent_jobs` của E0 yêu cầu ≥ 1; agent
không bao giờ
gọi `ctx.call_ai`). Bước đầu kiểm tra erasure ledger như mọi job `discovery.*` (X4). Idempotent: chạy lại cho cùng
kết quả.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from nichepilot.discovery_wiring import DISCOVERY_TOOLS, current_discovery
from nichepilot.jobs.agents.niche_discovery import NicheDiscoveryAgent
from nichepilot.jobs.agents.niche_discovery import _acceptance as _run_acceptance
from nichepilot.jobs.runtime import AgentDefinition, JobContext, StepOutcome
from nichepilot.modules.discovery import evaluation
from nichepilot.modules.discovery.schemas import DiscoveryRunResult


class RecomputeParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # chuỗi UUID (params job E0 được lưu dạng JSON)
    niche_ids: list[str] = Field(min_length=1, max_length=500)
    reason: Literal["EVIDENCE_ERASED", "WEIGHTS_CHANGED"]


class RecomputeResult(BaseModel):
    model_config = ConfigDict(extra="allow")
    recomputed: int
    evidence_sufficient: int


def _acceptance(result: dict[str, Any]) -> list[str]:
    return [] if isinstance(result.get("recomputed"), int) else ["thiếu recomputed"]


DEFINITION = AgentDefinition(
    job_type="discovery.recompute",
    description="E1 – Tính lại ngưỡng bằng chứng/trạng thái ngách sau khi xóa bằng chứng (không AI)",
    task_type="discovery.normalize",  # bắt buộc theo AgentDefinition E0; KHÔNG được gọi
    input_model=RecomputeParams,
    output_model=RecomputeResult,
    allowed_tools=[],
    max_steps=10,
    max_ai_calls=1,
    timeout_s=600,
    token_budget=1,
    paid=False,
    acceptance=_acceptance,
)


class NicheRecomputeAgent:
    definition = DEFINITION

    async def run_step(self, seq: int, state: dict[str, Any], ctx: JobContext) -> StepOutcome:
        await current_discovery().require_ledger_ok(force=True)
        params = RecomputeParams.model_validate(ctx.params)
        sufficient = 0
        async with ctx.sessionmaker() as s, s.begin():
            for niche_id in params.niche_ids:  # ngưỡng + Opportunity + Confidence theo trọng số active, 0 lời gọi AI
                res = await evaluation.evaluate_and_store(s, uuid.UUID(niche_id), computed_without_ai=True)
                sufficient += res.evidence_status == "EVIDENCE_SUFFICIENT"
        result = {"recomputed": len(params.niche_ids), "evidence_sufficient": sufficient}
        return StepOutcome(name="recompute", step_type="LOGIC", output=result, state=state, done=True, result=result)


# ---------------------------------------------------------------------------------------------------------------------
# `discovery.reevaluate` (T123; FR-034): thu thập bổ sung + đánh giá lại MỘT ngách; tạo đánh giá mới, giữ lịch sử
# đánh giá cũ.
# Dùng lại pipeline của NicheDiscoveryAgent (nguồn ALLOWED, robots, PII, ledger, ngân sách qua Gateway) với ứng viên
# cố định –
# không gọi AI đề xuất ứng viên; truy vấn tìm kiếm sinh xác định từ nhóm khách hàng + vấn đề cốt lõi.
# ---------------------------------------------------------------------------------------------------------------------


class ReevaluateParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    niche_id: str = Field(pattern=r"^[0-9a-f-]{36}$")
    market: str = Field(pattern=r"^[A-Z]{2}$")
    research_language: str = Field(default="en", pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
    max_candidates: int = 1
    page_limit: int = Field(default=60, ge=10, le=2000)
    time_limit_s: int = Field(default=1800, ge=300, le=14400)
    per_domain_interval_s: float = Field(default=2.0, ge=1)


REEVALUATE_DEFINITION = AgentDefinition(
    job_type="discovery.reevaluate",
    description="E1 – Đánh giá lại một ngách từ nguồn ALLOWED (giữ đánh giá cũ)",
    task_type="discovery.assess",
    input_model=ReevaluateParams,
    output_model=DiscoveryRunResult,
    allowed_tools=list(DISCOVERY_TOOLS),
    max_steps=60,
    max_ai_calls=20,
    timeout_s=3600,
    token_budget=400_000,
    paid=True,
    acceptance=_run_acceptance,
    extra_task_types=("discovery.extract",),
)


class NicheReevaluationAgent(NicheDiscoveryAgent):
    definition = REEVALUATE_DEFINITION

    async def _plan(self, state: dict[str, Any], ctx: JobContext, started: float) -> StepOutcome:
        niche_id = uuid.UUID(str(ctx.params["niche_id"]))
        async with ctx.sessionmaker() as s, s.begin():
            row = (
                await s.execute(
                    text(
                        "SELECT n.customer_group, n.core_problem, e.opportunity_score, e.confidence_score, e.id AS"
                        " eval_id,"
                        " e.evidence_status"
                        " FROM niches n LEFT JOIN niche_evaluations e ON e.id = n.latest_evaluation_id WHERE n.id = :n"
                    ),
                    {"n": niche_id},
                )
            ).one()
            await s.execute(
                text(
                    "INSERT INTO niche_run_links (niche_id, run_id, role) VALUES (:n, :r, 'REEVALUATED')"
                    " ON CONFLICT (niche_id, run_id) DO NOTHING"
                ),
                {"n": niche_id, "r": state["run_id"]},
            )
        query = f"{row.customer_group} {row.core_problem}"[:200]
        state["candidates"] = [{"niche_id": str(niche_id), "queries": [query]}]
        state["before"] = {
            "evaluation_id": str(row.eval_id) if row.eval_id else None,
            "opportunity_score": float(row.opportunity_score) if row.opportunity_score is not None else None,
            "confidence_score": float(row.confidence_score) if row.confidence_score is not None else None,
            "evidence_status": row.evidence_status,
        }
        state["metrics"]["candidates"] = 1
        state["phase"] = "sources"
        return self._outcome("plan_reevaluate", "LOGIC", {"niche_id": str(niche_id)}, state, started)

    async def _finalize(
        self, state: dict[str, Any], ctx: JobContext, started: float, outcome: str, stop_reason: str
    ) -> StepOutcome:
        out = await super()._finalize(state, ctx, started, outcome, stop_reason)
        if state.get("candidates"):
            nid = state["candidates"][0]["niche_id"]
            async with ctx.sessionmaker() as s:
                row = (
                    await s.execute(
                        text(
                            "SELECT e.id, e.opportunity_score, e.confidence_score, e.evidence_status FROM niches n"
                            " JOIN niche_evaluations e"
                            " ON e.id = n.latest_evaluation_id WHERE n.id = :n"
                        ),
                        {"n": nid},
                    )
                ).first()
            after = {
                "evaluation_id": str(row.id) if row else None,
                "opportunity_score": float(row.opportunity_score)
                if row and row.opportunity_score is not None
                else None,
                "confidence_score": float(row.confidence_score) if row else None,
                "evidence_status": row.evidence_status if row else None,
            }
            comparison = {"before": state.get("before"), "after": after}
            out.result = {**(out.result or {}), "comparison": comparison}
            out.output = {**out.output, "comparison": comparison}
        return out
