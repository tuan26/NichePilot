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

from nichepilot.discovery_wiring import current_discovery
from nichepilot.jobs.runtime import AgentDefinition, JobContext, StepOutcome
from nichepilot.modules.discovery import evaluation


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
