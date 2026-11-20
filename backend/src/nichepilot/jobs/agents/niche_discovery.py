"""Agent `discovery.run` – NicheDiscoveryAgent (E1; plan.md "Luồng xử lý"; internal-interfaces §6).

Phase 2 (T054): khung agent với bước `preflight` (cổng erasure ledger) và `ensure_run` (tạo `discovery_runs`
idempotent theo
`job_id`, đọc `trigger`/`schedule_id` từ `agent_jobs` của E0 → lượt theo lịch không cần sửa Scheduler/Job Runtime – H1).
Các bước nghiên cứu (plan_queries … finalize) bổ sung ở US1.

Checkpoint chỉ chứa ID/hash/bộ đếm – không chứa văn bản. Không có model ID trong mã (chỉ task type).
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text

from nichepilot.discovery_wiring import DISCOVERY_TOOLS, current_discovery
from nichepilot.jobs.runtime import AgentDefinition, JobContext, StepOutcome
from nichepilot.modules.discovery.schemas import DiscoveryRunParams, DiscoveryRunResult
from nichepilot.modules.discovery.sources.policy import SourcePolicyService

TASK_TYPE = "discovery.candidates"


def _acceptance(result: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if not result.get("run_id"):
        problems.append("thiếu run_id")
    if result.get("outcome") not in ("COMPLETED", "PARTIAL_COMPLETED"):
        problems.append("outcome không hợp lệ")
    if not result.get("stop_reason"):
        problems.append("thiếu stop_reason")
    return problems


DEFINITION = AgentDefinition(
    job_type="discovery.run",
    description="E1 – Tự động khám phá ngách: tìm và thu thập nguồn ALLOWED, phân tích, chấm điểm",
    task_type=TASK_TYPE,
    input_model=DiscoveryRunParams,
    output_model=DiscoveryRunResult,
    allowed_tools=list(DISCOVERY_TOOLS),
    max_steps=240,
    max_ai_calls=120,
    timeout_s=6000,
    token_budget=2_000_000,
    paid=True,
    acceptance=_acceptance,
)


async def ensure_run(ctx: JobContext) -> uuid.UUID:
    """Tạo hoặc lấy `discovery_runs` của job (UNIQUE job_id → idempotent khi job được giao lại/tiếp tục)."""
    ds = current_discovery()
    params = DiscoveryRunParams.model_validate({k: v for k, v in ctx.params.items() if v is not None})
    async with ctx.sessionmaker() as s, s.begin():
        existing = (
            await s.execute(text("SELECT id FROM discovery_runs WHERE job_id = :j"), {"j": ctx.job_id})
        ).scalar_one_or_none()
        if existing is not None:
            return uuid.UUID(str(existing))
        job = (
            (
                await s.execute(
                    text("SELECT project_id, trigger, budget_limit_usd, data_origin FROM agent_jobs WHERE id = :j"),
                    {"j": ctx.job_id},
                )
            )
            .mappings()
            .one()
        )
        weights = (await s.execute(text("SELECT id FROM scoring_weights_versions WHERE is_active"))).scalar_one()
        usable = await SourcePolicyService(s).usable_for_run()
        source_mode = ds.backends.data_origin
        origin = "MOCK" if "MOCK" in (source_mode, job["data_origin"]) else "REAL"
        run_id = (
            await s.execute(
                text(
                    "INSERT INTO discovery_runs (project_id, job_id, market, research_language, seed_topic,"
                    " max_candidates, budget_usd, time_limit_s, page_limit, per_domain_interval_s, trigger,"
                    " source_policy_ids, weights_version_id, source_mode, data_origin, metrics)"
                    " VALUES (:p, :j, :m, :l, :t, :mc, :b, :tl, :pl, :pi, :tr, CAST(:sp AS uuid[]), :w, :sm, :o,"
                    " CAST(:met AS jsonb)) ON CONFLICT (job_id) DO NOTHING RETURNING id"
                ),
                {
                    "p": job["project_id"],
                    "j": ctx.job_id,
                    "m": params.market,
                    "l": params.research_language,
                    "t": params.seed_topic,
                    "mc": params.max_candidates,
                    "b": job["budget_limit_usd"],
                    "tl": params.time_limit_s,
                    "pl": params.page_limit,
                    "pi": params.per_domain_interval_s,
                    "tr": job["trigger"],
                    "sp": [str(u.policy_id) for u in usable],
                    "w": weights,
                    "sm": source_mode,
                    "o": origin,
                    "met": json.dumps({}),
                },
            )
        ).scalar_one_or_none()
        if run_id is None:  # tranh chấp: worker khác vừa tạo
            run_id = (
                await s.execute(text("SELECT id FROM discovery_runs WHERE job_id = :j"), {"j": ctx.job_id})
            ).scalar_one()
        return uuid.UUID(str(run_id))


class NicheDiscoveryAgent:
    definition = DEFINITION

    async def run_step(self, seq: int, state: dict[str, Any], ctx: JobContext) -> StepOutcome:
        if seq == 1 or "run_id" not in state:
            await current_discovery().require_ledger_ok(force=True)  # preflight: không dữ liệu, không AI nếu sổ lỗi
            run_id = await ensure_run(ctx)
            return StepOutcome(
                name="preflight",
                step_type="LOGIC",
                output={"run_id": str(run_id)},
                state={**state, "run_id": str(run_id)},
            )
        return await self._finish(state, ctx)

    async def _finish(self, state: dict[str, Any], ctx: JobContext) -> StepOutcome:
        # Khung Phase 2: chưa có bước nghiên cứu (US1). Không nguồn ALLOWED → kết thúc đúng quy tắc FR-006e.
        run_id = state["run_id"]
        async with ctx.sessionmaker() as s, s.begin():
            await s.execute(
                text(
                    "UPDATE discovery_runs SET outcome = 'PARTIAL_COMPLETED', stop_reason ="
                    " 'NO_COMPLIANT_SEARCH_SOURCE',"
                    " updated_at = now() WHERE id = :r AND outcome IS NULL"
                ),
                {"r": run_id},
            )
        result = {"run_id": run_id, "outcome": "PARTIAL_COMPLETED", "stop_reason": "NO_COMPLIANT_SEARCH_SOURCE"}
        return StepOutcome(name="finalize", step_type="LOGIC", output=result, state=state, done=True, result=result)
