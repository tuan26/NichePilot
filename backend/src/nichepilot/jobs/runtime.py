"""Job Runtime (T078 – FR-021, FR-024, FR-025, FR-031; contracts/internal-interfaces.md §3).

Runtime (không phải agent) chịu trách nhiệm: vòng lặp bước, giới hạn bước/lời gọi AI/token/timeout, ghi `job_steps`,
checkpoint sau mỗi bước, chuyển trạng thái job. Agent chỉ dùng AI Gateway, Tool Registry và JobContext dùng chung.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal, Protocol

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nichepilot.ai.budget import BudgetExceededError, UncertainLimitReachedError
from nichepilot.ai.gateway import AIGateway, CallContext, GatewayResult, JobCancelledError
from nichepilot.ai.providers.base import LLMMessage, ToolSpec
from nichepilot.core.config import Settings
from nichepilot.core.errors import AppError
from nichepilot.core.logging import bind_context, get_logger, unbind_context
from nichepilot.tools.registry import ToolContext, ToolDeniedError, ToolRegistry

log = get_logger(__name__)
RETRYABLE_CODES = frozenset(
    {"PROVIDER_TIMEOUT", "PROVIDER_RATE_LIMITED", "PROVIDER_UNAVAILABLE", "PROVIDER_NETWORK_ERROR"}
)
Requeue = Callable[[uuid.UUID, int], Awaitable[object]]
StepType = Literal["AI_CALL", "TOOL_CALL", "LOGIC"]
RUNNABLE = ("QUEUED", "RETRY_SCHEDULED")


@dataclass(frozen=True)
class AgentDefinition:
    job_type: str
    description: str
    task_type: str  # khóa tới Model Task Profile – KHÔNG có tên model
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    allowed_tools: list[str]
    max_steps: int
    max_ai_calls: int
    timeout_s: int
    token_budget: int
    paid: bool
    acceptance: Callable[[dict[str, Any]], list[str]]
    retry_max_attempts: int = 3


@dataclass
class StepOutcome:
    name: str
    step_type: StepType
    output: dict[str, Any]
    state: dict[str, Any]
    done: bool = False
    result: dict[str, Any] | None = None


class Agent(Protocol):
    definition: AgentDefinition

    async def run_step(self, seq: int, state: dict[str, Any], ctx: JobContext) -> StepOutcome: ...


@dataclass
class JobContext:
    job_id: uuid.UUID
    data_origin: str
    params: dict[str, Any]
    definition: AgentDefinition
    gateway: AIGateway
    tools: ToolRegistry
    sessionmaker: async_sessionmaker[AsyncSession]
    settings: Settings
    ai_call_count: int = 0
    tokens_used: int = 0
    step_id: uuid.UUID | None = None
    seq: int = 0
    step_cost: Decimal = field(default_factory=lambda: Decimal(0))
    step_origin: str | None = None

    async def is_cancelled(self) -> bool:
        async with self.sessionmaker() as s:
            return bool(
                (
                    await s.execute(text("SELECT cancel_requested FROM agent_jobs WHERE id = :j"), {"j": self.job_id})
                ).scalar()
            )

    async def call_ai(
        self,
        *,
        system: str,
        messages: Sequence[LLMMessage],
        tools: Sequence[ToolSpec] = (),
        output_model: type[BaseModel] | None = None,
        task_type: str | None = None,
    ) -> GatewayResult:
        # E1 (X6): task_type tùy chọn để mỗi bước dùng Model Task Profile riêng; mặc định = task type của agent (E0).
        if self.ai_call_count >= self.definition.max_ai_calls:
            raise AppError("MAX_AI_CALLS_EXCEEDED")
        if self.tokens_used >= self.definition.token_budget:
            raise AppError("JOB_TOKEN_BUDGET_EXCEEDED")
        self.ai_call_count += 1
        result = await self.gateway.call(
            task_type or self.definition.task_type,
            system=system,
            messages=messages,
            tools=tools,
            output_model=output_model,
            ctx=CallContext(
                job_id=self.job_id,
                step_id=self.step_id,
                mock_scenario=self.params.get("mock_scenario"),
                seed=f"{self.job_id}:{self.seq}",
                is_cancelled=self.is_cancelled,
            ),
        )
        usage = result.response.usage
        self.tokens_used += usage.input_tokens + usage.output_tokens
        self.step_cost += result.cost_usd
        self.step_origin = result.data_origin
        return result

    def tool_specs(self) -> list[ToolSpec]:
        return self.tools.specs_for(self.definition.allowed_tools)

    async def call_tool(self, name: str, raw_input: dict[str, Any]) -> dict[str, Any]:
        tz = await self._setting("system.timezone")
        ctx = ToolContext(
            job_id=self.job_id,
            step_id=self.step_id,
            allowed_tools=frozenset(self.definition.allowed_tools),
            data_origin="MOCK" if self.data_origin == "MOCK" else "REAL",
            record=self._record_tool,
            extras={"app_version": self.settings.app_version, "timezone": tz},
        )
        return await self.tools.execute(name, raw_input, ctx)

    async def _setting(self, key: str) -> Any:
        async with self.sessionmaker() as s:
            return (await s.execute(text("SELECT value FROM settings WHERE key = :k"), {"k": key})).scalar_one()

    async def _record_tool(self, row: dict[str, Any]) -> None:
        import json

        params = {**row, "input": json.dumps(row.get("input")), "output": json.dumps(row.get("output"))}
        async with self.sessionmaker() as s, s.begin():
            await s.execute(
                text(
                    "INSERT INTO tool_executions (job_id, step_id, tool_name, tool_version, status, denial_reason,"
                    " input,"
                    " output, data_origin, duration_ms) VALUES (:job_id, :step_id, :tool_name, :tool_version, :status,"
                    " :denial_reason, CAST(:input AS jsonb), CAST(:output AS jsonb), :data_origin, :duration_ms)"
                ),
                params,
            )
        log.info(
            "tool.executed",
            job_id=str(row["job_id"]),
            step_id=str(row["step_id"]) if row.get("step_id") else None,
            tool_name=row.get("tool_name"),
            status=row.get("status"),
            denial_reason=row.get("denial_reason"),
            duration_ms=row.get("duration_ms"),
        )


def _now() -> datetime:
    return datetime.now(UTC)


class JobRuntime:
    def __init__(
        self,
        sessionmaker: async_sessionmaker[AsyncSession],
        gateway: AIGateway,
        tools: ToolRegistry,
        agents: dict[str, Agent],
        settings: Settings,
        *,
        requeue: Requeue | None = None,
        heartbeat_interval_s: float = 15.0,
    ) -> None:
        self.sessionmaker = sessionmaker
        self.gateway = gateway
        self.tools = tools
        self.agents = agents
        self.settings = settings
        self.requeue = requeue  # hàng đợi để retry tự động (None = không retry tự động)
        self.heartbeat_interval_s = heartbeat_interval_s

    async def _exec(self, sql: str, **params: Any) -> Any:
        async with self.sessionmaker() as s, s.begin():
            return await s.execute(text(sql), params)

    async def _claim(self, job_id: uuid.UUID) -> dict[str, Any] | None:
        """Chuyển QUEUED/RETRY_SCHEDULED → RUNNING một cách nguyên tử (một job – một worker)."""
        result = await self._exec(
            "UPDATE agent_jobs SET status = 'RUNNING', attempt = attempt + 1, started_at = COALESCE(started_at, now()),"
            " heartbeat_at = now(), status_reason_code = NULL, status_reason_detail = NULL, updated_at = now()"
            " WHERE id = :j AND status IN ('QUEUED', 'RETRY_SCHEDULED') RETURNING *",
            j=job_id,
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def _finish(
        self, job_id: uuid.UUID, status: str, code: str | None = None, detail: Any = None, result: Any = None
    ) -> None:
        import json

        terminal = status in ("SUCCEEDED", "FAILED", "CANCELLED")
        await self._exec(
            "UPDATE agent_jobs SET status = :st, status_reason_code = :c, status_reason_detail = CAST(:d AS jsonb),"
            " result = COALESCE(CAST(:r AS jsonb), result), finished_at = CASE WHEN :t THEN now() ELSE finished_at END,"
            " updated_at = now() WHERE id = :j",
            j=job_id,
            st=status,
            c=code,
            d=json.dumps(detail) if detail is not None else None,
            r=json.dumps(result) if result is not None else None,
            t=terminal,
        )
        log.info("job.finished", job_id=str(job_id), status=status, reason=code)

    async def _start_step(self, job_id: uuid.UUID, seq: int, origin: str) -> uuid.UUID:
        row = await self._exec(
            "INSERT INTO job_steps (job_id, seq, step_type, name, status, data_origin, started_at)"
            " VALUES (:j, :s, 'LOGIC', 'pending', 'RUNNING', :o, now())"
            " ON CONFLICT (job_id, seq) DO UPDATE SET attempt = job_steps.attempt + 1, status = 'RUNNING',"
            " error_code = NULL, error_message = NULL, started_at = now(), finished_at = NULL, updated_at = now()"
            " RETURNING id",
            j=job_id,
            s=seq,
            o=origin,
        )
        step_id = uuid.UUID(str(row.scalar_one()))
        log.info("step.started", job_id=str(job_id), step_id=str(step_id), seq=seq)
        return step_id

    async def _end_step(
        self,
        step_id: uuid.UUID,
        *,
        status: str,
        ctx: JobContext,
        name: str | None = None,
        step_type: str | None = None,
        output: Any = None,
        error_code: str | None = None,
    ) -> None:
        import json

        await self._exec(
            "UPDATE job_steps SET status = :st, name = COALESCE(:n, name), step_type = COALESCE(:ty, step_type),"
            " output = CAST(:o AS jsonb), error_code = :ec, error_message = :em, cost_usd = cost_usd + :c,"
            " data_origin = COALESCE(:org, data_origin), finished_at = now(), updated_at = now() WHERE id = :id",
            id=step_id,
            st=status,
            n=name,
            ty=step_type,
            o=json.dumps(output) if output is not None else None,
            ec=error_code,
            em=error_code,
            c=ctx.step_cost,
            org=ctx.step_origin,
        )
        log.info(
            "step.finished",
            job_id=str(ctx.job_id),
            step_id=str(step_id),
            seq=ctx.seq,
            status=status,
            name=name,
            error_code=error_code,
            cost_usd=str(ctx.step_cost),
        )
        await self._exec(
            "UPDATE agent_jobs SET cost_accumulated_usd = cost_accumulated_usd + :c, ai_call_count = :a,"
            " heartbeat_at = now(), updated_at = now() WHERE id = :j",
            j=ctx.job_id,
            c=ctx.step_cost,
            a=ctx.ai_call_count,
        )

    async def run(self, job_id: uuid.UUID) -> str | None:

        job = await self._claim(job_id)
        if job is None:
            return None  # đã chạy/đã xong/không tồn tại – idempotent
        bind_context(job_id=str(job_id))
        try:
            return await self._run_claimed(job_id, job)
        finally:
            unbind_context("job_id")  # log của worker sau khi job kết thúc không gắn nhầm job_id

    async def _run_claimed(self, job_id: uuid.UUID, job: dict[str, Any]) -> str | None:
        import asyncio

        log.info(
            "job.started",
            job_id=str(job_id),
            job_type=job["job_type"],
            attempt=int(job["attempt"]),
            data_origin=job["data_origin"],
            resume_from_seq=int(job["last_completed_seq"]) + 1,
        )
        agent = self.agents.get(job["job_type"])
        if agent is None:
            await self._finish(job_id, "FAILED", "VALIDATION_ERROR", {"reason": "unknown job_type"})
            return "FAILED"
        ctx = JobContext(
            job_id=job_id,
            data_origin=job["data_origin"],
            params=dict(job["params"] or {}),
            definition=agent.definition,
            gateway=self.gateway,
            tools=self.tools,
            sessionmaker=self.sessionmaker,
            settings=self.settings,
            ai_call_count=int(job["ai_call_count"]),
        )
        state: dict[str, Any] = dict(job["checkpoint"] or {})
        seq = int(job["last_completed_seq"]) + 1
        heartbeat = asyncio.create_task(self._heartbeat(job_id))
        try:
            return await self._loop(job, agent, ctx, state, seq)
        finally:
            heartbeat.cancel()

    async def _heartbeat(self, job_id: uuid.UUID) -> None:
        """Heartbeat nền khi job RUNNING – để phân biệt bước chạy lâu với worker đã chết (SC-006)."""
        import asyncio

        while True:
            await asyncio.sleep(self.heartbeat_interval_s)
            await self._exec(
                "UPDATE agent_jobs SET heartbeat_at = now() WHERE id = :j AND status = 'RUNNING'", j=job_id
            )

    async def _has_uncertain(self, job_id: uuid.UUID) -> bool:
        result = await self._exec(
            "SELECT COUNT(*) FROM budget_reservations WHERE job_id = :j AND status = 'UNCERTAIN'", j=job_id
        )
        return int(result.scalar_one()) > 0

    async def _loop(
        self, job: dict[str, Any], agent: Agent, ctx: JobContext, state: dict[str, Any], seq: int
    ) -> str | None:
        import asyncio
        import json

        job_id = ctx.job_id
        step_id: uuid.UUID | None = None
        try:
            async with asyncio.timeout(int(job["timeout_s"])):
                while True:
                    if seq > int(job["max_steps"]):
                        await self._finish(job_id, "FAILED", "MAX_STEPS_EXCEEDED")
                        return "FAILED"
                    flags = (
                        await self._exec(
                            "SELECT cancel_requested, pause_requested FROM agent_jobs WHERE id = :j", j=job_id
                        )
                    ).one()
                    if flags.cancel_requested:
                        await self._finish(job_id, "CANCELLED", "JOB_CANCELLED")
                        return "CANCELLED"
                    if flags.pause_requested:
                        await self._finish(job_id, "PAUSED")
                        return "PAUSED"
                    step_id = await self._start_step(job_id, seq, job["data_origin"])
                    ctx.step_id, ctx.seq, ctx.step_cost, ctx.step_origin = step_id, seq, Decimal(0), None
                    outcome = await agent.run_step(seq, state, ctx)
                    await self._end_step(
                        step_id,
                        status="SUCCEEDED",
                        ctx=ctx,
                        name=outcome.name,
                        step_type=outcome.step_type,
                        output=outcome.output,
                    )
                    state = outcome.state
                    await self._exec(
                        "UPDATE agent_jobs SET last_completed_seq = :s, step_count = :s,"
                        " checkpoint = CAST(:c AS jsonb),"
                        " updated_at = now() WHERE id = :j",
                        j=job_id,
                        s=seq,
                        c=json.dumps(state),
                    )
                    step_id = None
                    if outcome.done:
                        result = outcome.result or {}
                        violations = agent.definition.acceptance(result)
                        if violations:
                            await self._finish(job_id, "FAILED", "VALIDATION_ERROR", {"acceptance": violations})
                            return "FAILED"
                        await self._finish(job_id, "SUCCEEDED", result=result)
                        return "SUCCEEDED"
                    seq += 1
        except TimeoutError:
            return await self._fail(job_id, step_id, ctx, "FAILED", "JOB_TIMEOUT")
        except (BudgetExceededError, UncertainLimitReachedError) as exc:
            return await self._fail(
                job_id, step_id, ctx, "PAUSED_BUDGET", exc.code, exc.detail(), step_status="BLOCKED"
            )
        except JobCancelledError:
            return await self._fail(job_id, step_id, ctx, "CANCELLED", "JOB_CANCELLED", step_status="SKIPPED")
        except ToolDeniedError as exc:
            return await self._fail(job_id, step_id, ctx, "FAILED", exc.code, {"tool": exc.tool})
        except AppError as exc:
            if (
                exc.code in RETRYABLE_CODES
                and self.requeue is not None
                and int(job["attempt"]) < int(job["max_attempts"])
                and not await self._has_uncertain(job_id)  # không gọi lại API khi chi phí chưa xác định
            ):
                status = await self._fail(job_id, step_id, ctx, "RETRY_SCHEDULED", exc.code, exc.params or None)
                await self.requeue(job_id, self.settings.job_retry_delay_s)
                return status
            step_status = {"AI_REFUSED": "REFUSED", "AI_TRUNCATED": "TRUNCATED"}.get(exc.code, "FAILED")
            return await self._fail(
                job_id, step_id, ctx, "FAILED", exc.code, exc.params or None, step_status=step_status
            )

    async def _fail(
        self,
        job_id: uuid.UUID,
        step_id: uuid.UUID | None,
        ctx: JobContext,
        status: str,
        code: str,
        detail: Any = None,
        *,
        step_status: str = "FAILED",
    ) -> str:
        if step_id is not None:
            await self._end_step(step_id, status=step_status, ctx=ctx, error_code=code)
        await self._finish(job_id, status, code, detail)
        return status
