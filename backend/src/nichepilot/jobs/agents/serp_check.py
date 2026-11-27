"""Agent `keywords.serp_check` (FR-031, Should; research R-09) và `keywords.recompute` (không AI; FR-017).

serp_check: chạy lại `source.query` (nguồn `ALLOWED`) cho keyword chính của cluster được theo dõi, so với phiên bản
gần nhất → phiên bản
mới + `changes` khi khác (cảnh báo trong ứng dụng). Lỗi/không nguồn → ghi `last_check_error`, KHÔNG xóa quan sát cũ.
Không gọi AI.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

from sqlalchemy import text

from nichepilot.discovery_wiring import current_discovery
from nichepilot.jobs.runtime import AgentDefinition, JobContext, StepOutcome
from nichepilot.modules.discovery.sources.policy import SourcePolicyService
from nichepilot.modules.keywords import evaluation, store
from nichepilot.modules.keywords.analysis import channels
from nichepilot.modules.keywords.schemas import RecomputeParams, RecomputeResult, SerpCheckParams, SerpCheckResult
from nichepilot.modules.keywords.serp import results_from_hits

SERP_RESULTS = 10


def _acceptance(result: dict[str, Any]) -> list[str]:
    ok = result.get("run_id") and result.get("outcome") in ("COMPLETED", "PARTIAL_COMPLETED")
    return [] if ok else ["kết quả thiếu"]


SERP_DEFINITION = AgentDefinition(
    job_type="keywords.serp_check",
    description="E3 – Kiểm tra lại SERP của cluster đang theo dõi (FR-031, không AI)",
    task_type="keywords.analyze",
    input_model=SerpCheckParams,
    output_model=SerpCheckResult,
    allowed_tools=["source.query"],
    max_steps=10,
    max_ai_calls=1,  # ràng buộc agent_jobs của E0 yêu cầu ≥ 1; agent KHÔNG gọi AI
    timeout_s=600,
    token_budget=1,
    paid=False,
    acceptance=_acceptance,
)
RECOMPUTE_DEFINITION = AgentDefinition(
    job_type="keywords.recompute",
    description="E3 – Tính lại điểm keyword theo trọng số/bằng chứng hiện tại (không AI)",
    task_type="keywords.generate",
    input_model=RecomputeParams,
    output_model=RecomputeResult,
    allowed_tools=[],
    max_steps=50,
    max_ai_calls=1,
    timeout_s=600,
    token_budget=1,
    paid=False,
    acceptance=_acceptance,
)


class SerpCheckAgent:
    definition = SERP_DEFINITION

    async def run_step(self, seq: int, state: dict[str, Any], ctx: JobContext) -> StepOutcome:
        ds = current_discovery()
        await ds.require_ledger_ok(force=True)
        p = SerpCheckParams.model_validate({k: v for k, v in ctx.params.items() if k in SerpCheckParams.model_fields})
        cluster_id = uuid.UUID(p.cluster_id)
        async with ctx.sessionmaker() as s:
            c = (
                await s.execute(
                    text(
                        "SELECT c.niche_id, c.primary_keyword_id, c.data_origin, k.text, n.country FROM"
                        " keyword_clusters c"
                        " JOIN niches n ON n.id = c.niche_id LEFT JOIN keywords k ON k.id = c.primary_keyword_id WHERE"
                        " c.id = :c"
                    ),
                    {"c": cluster_id},
                )
            ).first()
        if c is None:
            missing = SerpCheckResult(
                run_id=str(ctx.job_id), outcome="PARTIAL_COMPLETED", stop_reason="KEYWORD_CLUSTER_NOT_FOUND"
            ).model_dump()
            return StepOutcome(
                name="finalize", step_type="LOGIC", output=missing, state=state, done=True, result=missing
            )
        async with ctx.sessionmaker() as s, s.begin():
            run_id = await store.ensure_run(
                s,
                job_id=ctx.job_id,
                niche_id=c.niche_id,
                params=p.model_dump(exclude_none=True),
                origin=ds.backends.data_origin,
            )
        async with ctx.sessionmaker() as s:
            usable = await SourcePolicyService(s).usable_for_run()
        version: int | None = None
        error: str | None = None
        reason = "CHECKED"
        if c.primary_keyword_id is None:
            reason, error = "NO_PRIMARY_KEYWORD", "NO_PRIMARY_KEYWORD"
        elif not usable:
            reason, error = "NO_COMPLIANT_SEARCH_SOURCE", "NO_COMPLIANT_SEARCH_SOURCE"
        else:
            hits: list[dict[str, Any]] = []
            policy_id: str | None = None
            out: dict[str, Any] = {}
            for policy in usable:
                out = await ctx.call_tool(
                    "source.query",
                    {
                        "policy": policy.tool_input(),
                        "query": c.text,
                        "market": c.country,
                        "language": "en",
                        "max_results": SERP_RESULTS,
                    },
                )
                if out["hits"] and policy_id is None:
                    policy_id = str(policy.policy_id)
                hits += list(out["hits"])
            results = results_from_hits(hits)
            if not results:
                reason, error = "NO_RESULTS", str(out.get("status") or "NO_RESULTS")
            else:
                origin = "MOCK" if "MOCK" in (c.data_origin, out.get("data_origin")) else "REAL"
                async with ctx.sessionmaker() as s, s.begin():
                    v, created = await store.record_serp(
                        s,
                        keyword_id=c.primary_keyword_id,
                        results=results,
                        source_policy_id=uuid.UUID(policy_id) if policy_id else None,
                        job_id=ctx.job_id,
                        origin=origin,
                    )
                    version = v if created else None
                    if created:
                        await store.merge_insights(s, cluster_id, {"channels": channels(results)})
                        kids = (
                            (await s.execute(text("SELECT id FROM keywords WHERE cluster_id = :c"), {"c": cluster_id}))
                            .scalars()
                            .all()
                        )
                        await evaluation.evaluate_keywords(s, list(kids), run_id=run_id)
                        await evaluation.refresh_clusters(s, [cluster_id])
        outcome = "COMPLETED" if error is None else "PARTIAL_COMPLETED"
        async with ctx.sessionmaker() as s, s.begin():
            await s.execute(
                text("UPDATE keyword_clusters SET last_checked_at = now(), last_check_error = :e WHERE id = :c"),
                {"e": error, "c": cluster_id},
            )
            await s.execute(
                text(
                    "UPDATE keyword_runs SET outcome = :o, stop_reason = :r, metrics = CAST(:m AS jsonb) WHERE id = :i"
                ),
                {"o": outcome, "r": reason, "m": json.dumps({"new_version": version, "ai_calls": 0}), "i": run_id},
            )
        result = SerpCheckResult(
            run_id=str(run_id), outcome=outcome, stop_reason=reason, new_version=version
        ).model_dump()
        return StepOutcome(name="finalize", step_type="LOGIC", output=result, state=state, done=True, result=result)


class KeywordRecomputeAgent:
    definition = RECOMPUTE_DEFINITION

    async def run_step(self, seq: int, state: dict[str, Any], ctx: JobContext) -> StepOutcome:
        p = RecomputeParams.model_validate({k: v for k, v in ctx.params.items() if k in RecomputeParams.model_fields})
        async with ctx.sessionmaker() as s, s.begin():
            ids = (
                (
                    await s.execute(
                        text("SELECT id FROM keywords WHERE CAST(:n AS uuid) IS NULL OR niche_id = CAST(:n AS uuid)"),
                        {"n": p.niche_id},
                    )
                )
                .scalars()
                .all()
            )
            outs = await evaluation.evaluate_keywords(s, list(ids))
            clusters = (
                (await s.execute(text("SELECT DISTINCT cluster_id FROM keywords WHERE cluster_id IS NOT NULL")))
                .scalars()
                .all()
            )
            await evaluation.refresh_clusters(s, list(clusters))
        result = RecomputeResult(
            run_id=str(ctx.job_id),
            outcome="COMPLETED",
            stop_reason="RECOMPUTED",
            recomputed=sum(1 for o in outs if o.created),
        ).model_dump()
        return StepOutcome(name="recompute", step_type="LOGIC", output=result, state=state, done=True, result=result)
