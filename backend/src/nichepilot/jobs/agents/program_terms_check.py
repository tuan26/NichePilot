"""Agent `products.terms_check` (FR-040, Should; research R-09) và `products.recompute` (không AI; FR-027).

terms_check: tải lại `terms_url` của chương trình đang được theo dõi qua PageCollector (robots/tốc độ/che PII), trích
lại thuộc tính
(AI `products.program_extract`, kiểm số liệu), so ảnh chụp gộp với phiên bản gần nhất → phiên bản mới + `changes` khi
khác.
Lỗi truy cập → ghi `last_check_error`, KHÔNG xóa giá trị cũ. Không có thao tác đăng ký/đăng nhập (FR-025).
"""

from __future__ import annotations

import json
import time
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from nichepilot.ai.gateway import LLMMessage
from nichepilot.ai.sanitize import wrap_untrusted
from nichepilot.core.errors import AppError
from nichepilot.discovery_wiring import current_discovery
from nichepilot.jobs.agents import _collector as collector
from nichepilot.jobs.agents.product_discovery import SYSTEM_PROGRAM, ProductDiscoveryAgent
from nichepilot.jobs.runtime import AgentDefinition, JobContext, StepOutcome
from nichepilot.modules.products import evaluation, store
from nichepilot.modules.products.attributes import PROGRAM_KEYS, resolve_all
from nichepilot.modules.products.extraction import validate_program_extract
from nichepilot.modules.products.programs import diff_snapshots, terms_snapshot
from nichepilot.modules.products.schemas import (
    ProgramExtractOutput,
    RecomputeParams,
    RecomputeResult,
    TermsCheckParams,
    TermsCheckResult,
)


def _acceptance(result: dict[str, Any]) -> list[str]:
    return (
        []
        if result.get("run_id") and result.get("outcome") in ("COMPLETED", "PARTIAL_COMPLETED")
        else ["kết quả thiếu"]
    )


TERMS_DEFINITION = AgentDefinition(
    job_type="products.terms_check",
    description="E2 – Kiểm tra lại điều khoản chương trình affiliate đang theo dõi (FR-040)",
    task_type="products.program_extract",
    input_model=TermsCheckParams,
    output_model=TermsCheckResult,
    allowed_tools=["page.fetch", "robots.fetch"],
    max_steps=20,
    max_ai_calls=3,
    timeout_s=900,
    token_budget=150_000,
    paid=True,
    acceptance=_acceptance,
)
RECOMPUTE_DEFINITION = AgentDefinition(
    job_type="products.recompute",
    description="E2 – Tính lại điểm sản phẩm theo trọng số/bằng chứng hiện tại (không AI)",
    task_type="products.extract",
    input_model=RecomputeParams,
    output_model=RecomputeResult,
    allowed_tools=[],
    max_steps=50,
    max_ai_calls=1,  # ràng buộc agent_jobs của E0 yêu cầu ≥ 1; agent KHÔNG gọi AI (như discovery.recompute của E1)
    timeout_s=600,
    token_budget=1,
    paid=False,
    acceptance=_acceptance,
)


class ProgramTermsCheckAgent:
    definition = TERMS_DEFINITION

    async def run_step(self, seq: int, state: dict[str, Any], ctx: JobContext) -> StepOutcome:
        started = time.monotonic()
        p = TermsCheckParams.model_validate({k: v for k, v in ctx.params.items() if k in TermsCheckParams.model_fields})
        program_id = uuid.UUID(p.program_id)
        async with ctx.sessionmaker() as s:
            prog = (
                await s.execute(
                    text(
                        "SELECT ap.project_id, ap.terms_url, ap.operator_domain, ap.data_origin, pn.niche_id,"
                        " pp.product_id"
                        " FROM affiliate_programs ap JOIN product_programs pp ON pp.program_id = ap.id"
                        " JOIN product_niches pn ON pn.product_id = pp.product_id WHERE ap.id = :i"
                        " ORDER BY pn.created_at LIMIT 1"
                    ),
                    {"i": program_id},
                )
            ).first()
        if seq == 1 or "run_id" not in state:
            await current_discovery().require_ledger_ok(force=True)
            if prog is None:
                raise AppError("PROGRAM_NOT_FOUND")
            async with ctx.sessionmaker() as s, s.begin():
                run_id = await store.ensure_run(
                    s,
                    job_id=ctx.job_id,
                    niche_id=prog.niche_id,
                    params=p.model_dump(exclude_none=True),
                    origin=prog.data_origin,
                )
            state = {"run_id": str(run_id), "metrics": {}, "queue": [], "phase": "fetch"}
            if not prog.terms_url:
                return await self._finish(state, ctx, program_id, None, "NO_TERMS_URL", started)
            policy = await self._policy_for(ctx, prog.terms_url)
            if policy is None:
                return await self._finish(state, ctx, program_id, None, "NO_COMPLIANT_SEARCH_SOURCE", started)
            collector.enqueue(state, prog.terms_url, policy, "terms")
            return StepOutcome(name="preflight", step_type="LOGIC", output={"run_id": str(run_id)}, state=state)
        assert prog is not None
        if state["phase"] == "fetch":
            await collector.collect(
                ctx,
                state,
                project_id=prog.project_id,
                run_origin=prog.data_origin,
                run_id=uuid.UUID(state["run_id"]),
                page_limit=3,
                interval_s=2.0,
                language="en",
                country="US",
                time_left=lambda: 600.0,
            )
            if state["queue"]:
                return StepOutcome(name="fetch", step_type="TOOL_CALL", output={}, state=state)
            ids = state.get("pages", {}).get("terms", [])
            if not ids:
                reason = ",".join(sorted(state["metrics"].get("skipped_by_reason", {}))) or "FETCH_FAILED"
                return await self._finish(state, ctx, program_id, reason, "TERMS_UNREACHABLE", started)
            state["phase"] = "extract"
            return StepOutcome(name="fetch", step_type="TOOL_CALL", output={"pages": len(ids)}, state=state)
        async with ctx.sessionmaker() as s:
            pages = await store.page_excerpts(s, uuid.UUID(state["run_id"]), state.get("pages", {}).get("terms", []))
        by_id = {pg.evidence_id: pg for pg in pages}
        prompt = "Extract the affiliate program terms.\n" + wrap_untrusted(
            [{"evidence_id": pg.evidence_id, "url": pg.url, "excerpt": pg.excerpt} for pg in pages],
            source="public_web_excerpts",
        )
        try:
            res = await ctx.call_ai(
                system=SYSTEM_PROGRAM,
                messages=[LLMMessage(role="user", content=prompt)],
                output_model=ProgramExtractOutput,
            )
            out = ProgramExtractOutput.model_validate(res.parsed or {})
        except (AppError, ValueError) as exc:
            if isinstance(exc, AppError) and exc.code != "AI_SCHEMA_INVALID":
                raise
            return await self._finish(state, ctx, program_id, "AI_SCHEMA_INVALID", "EXTRACTION_FAILED", started)
        _, programs, _v = validate_program_extract(out, {k: pg.excerpt for k, pg in by_id.items()})
        if programs:
            agent = ProductDiscoveryAgent()
            async with ctx.sessionmaker() as s, s.begin():
                op = prog.operator_domain
                await agent._store_program_attrs_only(s, ctx, prog.project_id, program_id, op, programs[0], by_id)
        return await self._finish(state, ctx, program_id, None, "CHECKED", started)

    async def _policy_for(self, ctx: JobContext, url: str) -> str | None:
        """Nguồn của trang điều khoản = chính sách nguồn ALLOWED đã đưa URL này vào hệ thống (truy vết
        `source_policy_id`)."""
        async with ctx.sessionmaker() as s:
            row = (
                await s.execute(
                    text(
                        "SELECT rs.source_policy_id FROM research_sources rs JOIN source_policies sp ON sp.id ="
                        " rs.source_policy_id"
                        " WHERE rs.url = :u AND sp.enabled AND sp.compliance_status = 'ALLOWED' ORDER BY rs.created_at"
                        " DESC LIMIT 1"
                    ),
                    {"u": url},
                )
            ).scalar_one_or_none()
        return str(row) if row else None

    async def _finish(
        self,
        state: dict[str, Any],
        ctx: JobContext,
        program_id: uuid.UUID,
        error: str | None,
        reason: str,
        started: float,
    ) -> StepOutcome:
        version: int | None = None
        async with ctx.sessionmaker() as s, s.begin():
            if error is None and reason == "CHECKED":
                ev = await evaluation.load_attr_evidence(s, "affiliate_program", program_id)
                snap = terms_snapshot(resolve_all(PROGRAM_KEYS, ev))
                last = (
                    await s.execute(
                        text(
                            "SELECT version, snapshot FROM program_terms_versions WHERE program_id = :p"
                            " ORDER BY version DESC LIMIT 1"
                        ),
                        {"p": program_id},
                    )
                ).first()
                changes = diff_snapshots(last[1] if last else None, snap)
                if last is None or changes:
                    version = (last[0] + 1) if last else 1
                    origin = (
                        await s.execute(
                            text("SELECT data_origin FROM affiliate_programs WHERE id = :p"), {"p": program_id}
                        )
                    ).scalar_one()
                    await s.execute(
                        text(
                            "INSERT INTO program_terms_versions (program_id, version, snapshot, changes, checked_at,"
                            " job_id,"
                            " data_origin) VALUES (:p, :v, CAST(:s AS jsonb), CAST(:c AS jsonb), now(), :j, :o)"
                        ),
                        {
                            "p": program_id,
                            "v": version,
                            "s": json.dumps(snap, default=str),
                            "c": json.dumps(changes if last else [], default=str),
                            "j": ctx.job_id,
                            "o": origin,
                        },
                    )
                await s.execute(
                    text(
                        "UPDATE affiliate_programs SET last_checked_at = now(), last_check_error = NULL WHERE id = :p"
                    ),
                    {"p": program_id},
                )
                pairs = (
                    (
                        await s.execute(
                            text(
                                "SELECT pn.id FROM product_niches pn JOIN product_programs pp ON pp.product_id ="
                                " pn.product_id"
                                " WHERE pp.program_id = :p"
                            ),
                            {"p": program_id},
                        )
                    )
                    .scalars()
                    .all()
                )
                for pair in pairs:
                    await evaluation.evaluate_pair(s, pair)
            else:
                await s.execute(
                    text("UPDATE affiliate_programs SET last_checked_at = now(), last_check_error = :e WHERE id = :p"),
                    {"e": error or reason, "p": program_id},
                )
            await s.execute(
                text(
                    "UPDATE product_runs SET outcome = :o, stop_reason = :r, metrics = CAST(:m AS jsonb) WHERE id = :i"
                ),
                {
                    "o": "COMPLETED" if error is None and reason == "CHECKED" else "PARTIAL_COMPLETED",
                    "r": reason,
                    "m": json.dumps({**state.get("metrics", {}), "cost_mock_usd": str(Decimal(0))}, default=str),
                    "i": state["run_id"],
                },
            )
        outcome = "COMPLETED" if error is None and reason == "CHECKED" else "PARTIAL_COMPLETED"
        result = TermsCheckResult(
            run_id=state["run_id"], outcome=outcome, stop_reason=reason, new_version=version
        ).model_dump()
        return StepOutcome(name="finalize", step_type="LOGIC", output=result, state=state, done=True, result=result)


class ProductRecomputeAgent:
    definition = RECOMPUTE_DEFINITION

    async def run_step(self, seq: int, state: dict[str, Any], ctx: JobContext) -> StepOutcome:
        p = RecomputeParams.model_validate({k: v for k, v in ctx.params.items() if k in RecomputeParams.model_fields})
        async with ctx.sessionmaker() as s, s.begin():
            pairs = (
                (
                    await s.execute(
                        text(
                            "SELECT id FROM product_niches WHERE CAST(:n AS uuid) IS NULL OR niche_id = CAST(:n AS"
                            " uuid)"
                        ),
                        {"n": p.niche_id},
                    )
                )
                .scalars()
                .all()
            )
            created = 0
            for pair in pairs:
                created += int((await evaluation.evaluate_pair(s, pair)).created)
        result = RecomputeResult(
            run_id=str(ctx.job_id), outcome="COMPLETED", stop_reason="RECOMPUTED", recomputed=created
        ).model_dump()
        return StepOutcome(name="recompute", step_type="LOGIC", output=result, state=state, done=True, result=result)
