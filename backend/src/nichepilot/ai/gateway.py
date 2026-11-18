"""AI Gateway (T076 – FR-012…FR-019c, FR-040, FR-047; contracts/internal-interfaces.md §1).

Điểm DUY NHẤT gọi LLM. Thứ tự bất biến cho mỗi lần thử:
 1. chọn provider (profile + AI_PROVIDER_OVERRIDE) + rào chắn runtime cho mock ở production
 2. từ chối mock_scenario với provider thật/production
 3. provider có phí: model + khả năng + giá phải đã xác minh; mock: bảng giá giả lập riêng
 4. công tắc AI_PAID_CALLS_ENABLED (chưa giữ chỗ)
 5. giữ chỗ ngân sách nguyên tử (BudgetService.reserve)
 6. kiểm tra hủy job  7. mark_sent  8. gọi provider với timeout
 9. ghi ai_usage_logs + xử lý reservation (SETTLED / RELEASED / UNCERTAIN)
10. validate output theo schema  11. trả kết quả
Refusal: KHÔNG retry, KHÔNG fallback, KHÔNG đổi model. Dự phòng chỉ khi được cấu hình và chỉ cho PROVIDER_UNAVAILABLE.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nichepilot.ai.budget import BudgetService, UncertainLimitReachedError
from nichepilot.ai.catalog import check_paid_call_allowed, require_price
from nichepilot.ai.pricing import PriceSheet, compute_cost, max_cost
from nichepilot.ai.providers.base import (
    LLMMessage,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    ProviderError,
    ProviderNetworkError,
    ProviderRateLimitedError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ToolSpec,
)
from nichepilot.ai.providers.mock import MOCK_MODEL, validate_scenario
from nichepilot.ai.sanitize import UNTRUSTED_GUARD, sanitize_for_llm
from nichepilot.core.config import Settings
from nichepilot.core.errors import AppError
from nichepilot.core.logging import get_logger

log = get_logger(__name__)

# Agent dùng các kiểu này qua gateway – không import gói providers trực tiếp (FR-025, hợp đồng import-linter).
__all__ = ["AIGateway", "CallContext", "GatewayResult", "JobCancelledError", "LLMMessage", "ToolSpec"]

OUTCOME_TO_CODE = {
    "TIMEOUT": "PROVIDER_TIMEOUT",
    "RATE_LIMITED": "PROVIDER_RATE_LIMITED",
    "PROVIDER_ERROR": "PROVIDER_UNAVAILABLE",
    "NETWORK_ERROR": "PROVIDER_NETWORK_ERROR",
    "AUTH_ERROR": "PROVIDER_AUTH_ERROR",
    "BAD_REQUEST": "PROVIDER_BAD_REQUEST",
}


class JobCancelledError(Exception):
    """Job bị hủy trước khi gửi lời gọi – không phát sinh chi phí."""


@dataclass(frozen=True)
class CallContext:
    job_id: uuid.UUID
    step_id: uuid.UUID | None = None
    mock_scenario: str | None = None
    seed: str | None = None
    is_cancelled: Callable[[], Awaitable[bool]] | None = None


@dataclass(frozen=True)
class GatewayResult:
    response: LLMResponse
    parsed: dict[str, Any] | None
    usage_log_id: uuid.UUID
    cost_usd: Decimal
    data_origin: str
    provider: str
    model: str
    is_fallback: bool
    schema_valid: bool = True


@dataclass(frozen=True)
class Profile:
    task_type: str
    provider: str
    model: str
    effort: str | None
    max_output_tokens: int
    timeout_s: int
    schema_retry_max: int
    fallback_provider: str | None
    fallback_model: str | None
    fallback_on: list[str]


class AIGateway:
    def __init__(
        self,
        settings: Settings,
        sessionmaker: async_sessionmaker[AsyncSession],
        providers: dict[str, LLMProvider],
        *,
        budget: BudgetService | None = None,
        retry_attempts: int = 3,
        backoff_base_s: float = 0.5,
        backoff_max_s: float = 8.0,
    ) -> None:
        self.settings = settings
        self.sessionmaker = sessionmaker
        self.providers = providers
        self.budget = budget or BudgetService(sessionmaker)
        self.retry_attempts = retry_attempts
        self.backoff_base_s = backoff_base_s
        self.backoff_max_s = backoff_max_s

    @classmethod
    def from_settings(cls, settings: Settings, sessionmaker: async_sessionmaker[AsyncSession]) -> AIGateway:
        from nichepilot.ai.providers.anthropic_api import AnthropicAPIProvider
        from nichepilot.ai.providers.mock import MockAIProvider
        from nichepilot.ai.providers.openai_api import OpenAIAPIProvider

        providers: dict[str, LLMProvider] = {}
        if not settings.is_production:
            providers["mock"] = MockAIProvider(settings.mock_ai_default_scenario)
        if settings.anthropic_api_key:
            providers["anthropic"] = AnthropicAPIProvider(settings.anthropic_api_key.get_secret_value())
        if settings.openai_api_key:
            providers["openai"] = OpenAIAPIProvider(settings.openai_api_key.get_secret_value())
        return cls(settings, sessionmaker, providers)

    # ------------------------------------------------------------------ cấu hình
    async def load_profile(self, task_type: str) -> Profile:
        async with self.sessionmaker() as s:
            row = (
                (
                    await s.execute(
                        text("SELECT * FROM model_task_profiles WHERE task_type = :t AND enabled"), {"t": task_type}
                    )
                )
                .mappings()
                .first()
            )
        if row is None:
            raise AppError("PROVIDER_NOT_CONFIGURED", params={"task_type": task_type})
        return Profile(
            task_type=row["task_type"],
            provider=row["provider"],
            model=row["model"],
            effort=row["effort"],
            max_output_tokens=row["max_output_tokens"],
            timeout_s=row["timeout_s"],
            schema_retry_max=row["schema_retry_max"],
            fallback_provider=row["fallback_provider"],
            fallback_model=row["fallback_model"],
            fallback_on=list(row["fallback_on"] or []),
        )

    def resolve_provider_name(self, profile_provider: str) -> str:
        name = self.settings.ai_provider_override or profile_provider
        if name == "mock" and self.settings.is_production:
            raise AppError("MOCK_NOT_ALLOWED")  # rào chắn runtime (bổ sung cho kiểm tra lúc khởi động)
        return name

    async def resolve_data_origin(self, task_type: str) -> str:
        profile = await self.load_profile(task_type)
        return "MOCK" if self.resolve_provider_name(profile.provider) == "mock" else "REAL"

    async def _error_policy_verified(self, provider: str) -> bool:
        async with self.sessionmaker() as s:
            value = (
                await s.execute(
                    text("SELECT value FROM settings WHERE key = 'billing.error_responses_not_billed_verified'")
                )
            ).scalar_one_or_none()
        policy = value if isinstance(value, dict) else {}
        # MockAIProvider không bao giờ tính phí – mặc định coi là đã xác minh trừ khi cấu hình khác.
        return bool(policy.get(provider, provider == "mock"))

    # ------------------------------------------------------------------ gọi
    async def call(
        self,
        task_type: str,
        *,
        system: str,
        messages: Sequence[LLMMessage],
        tools: Sequence[ToolSpec] = (),
        output_model: type[BaseModel] | None = None,
        ctx: CallContext,
    ) -> GatewayResult:
        profile = await self.load_profile(task_type)
        name = self.resolve_provider_name(profile.provider)
        if ctx.mock_scenario is not None:
            if name != "mock" or self.settings.is_production:
                raise AppError("MOCK_NOT_ALLOWED")
            validate_scenario(ctx.mock_scenario)
        provider = self.providers.get(name)
        if provider is None:
            raise AppError("PROVIDER_NOT_CONFIGURED", params={"provider": name})
        model = MOCK_MODEL if name == "mock" else profile.model
        secrets = self.settings.secret_values()
        req = LLMRequest(
            task_type=task_type,
            model=model,
            system=sanitize_for_llm(f"{system}\n\n{UNTRUSTED_GUARD}", secrets),
            messages=[
                LLMMessage(
                    role=m.role,
                    content=sanitize_for_llm(m.content, secrets) if isinstance(m.content, str) else m.content,
                )
                for m in messages
            ],
            tools=list(tools),
            output_schema=output_model.model_json_schema() if output_model else None,
            effort=None if name == "mock" else profile.effort,
            max_output_tokens=profile.max_output_tokens,
            timeout_s=profile.timeout_s,
            mock_scenario=ctx.mock_scenario if name == "mock" else None,
            seed=ctx.seed or str(ctx.job_id),
        )
        needs = {"effort"} if req.effort else set()
        if req.output_schema:
            needs.add("structured_output")
        if req.tools:
            needs.add("tools")

        for schema_attempt in range(profile.schema_retry_max + 1):
            result = await self._call_with_retry(provider, req, needs, ctx, profile, output_model)
            response = result.response
            if response.outcome == "REFUSED":
                raise AppError(
                    "AI_REFUSED",
                    params={
                        "refusal_category": response.refusal_category or "",
                        "refusal_explanation": response.refusal_explanation or "",
                    },
                )
            if response.outcome == "TRUNCATED":
                raise AppError("AI_TRUNCATED")
            if not result.schema_valid:
                log.warning("ai.schema_invalid", task_type=task_type, attempt=schema_attempt + 1)
                continue
            return result
        raise AppError("AI_SCHEMA_INVALID")

    async def _call_with_retry(
        self,
        provider: LLMProvider,
        req: LLMRequest,
        needs: set[str],
        ctx: CallContext,
        profile: Profile,
        output_model: type[BaseModel] | None,
    ) -> GatewayResult:
        last: ProviderError | None = None
        for attempt in range(self.retry_attempts):
            try:
                return await self._attempt(provider, req, needs, ctx, output_model, is_fallback=False)
            except ProviderError as exc:
                last = exc
                if not exc.retryable:
                    break
                if attempt + 1 < self.retry_attempts:
                    await asyncio.sleep(self._backoff(attempt, exc))
        assert last is not None
        if (
            isinstance(last, ProviderUnavailableError)
            and profile.fallback_provider
            and profile.fallback_model
            and "PROVIDER_UNAVAILABLE" in profile.fallback_on
            and profile.fallback_provider in self.providers
        ):
            fallback = self.providers[profile.fallback_provider]
            log.warning("ai.fallback", from_provider=provider.name, to_provider=fallback.name)
            fb_req = req.model_copy(update={"model": profile.fallback_model})
            try:
                return await self._attempt(fallback, fb_req, needs, ctx, output_model, is_fallback=True)
            except ProviderError as exc:
                last = exc
        raise AppError(OUTCOME_TO_CODE.get(last.outcome, "PROVIDER_UNAVAILABLE"))

    def _backoff(self, attempt: int, exc: ProviderError) -> float:
        if isinstance(exc, ProviderRateLimitedError) and exc.retry_after_s is not None:
            return float(min(exc.retry_after_s, self.backoff_max_s))
        return float(min(self.backoff_base_s * (2**attempt), self.backoff_max_s))

    async def _price_for(self, provider: LLMProvider, model: str, needs: set[str]) -> PriceSheet:
        async with self.sessionmaker() as s:
            if provider.paid:
                return await check_paid_call_allowed(s, provider.name, model, needs)
            return await require_price(s, provider.name, model)

    async def _attempt(
        self,
        provider: LLMProvider,
        req: LLMRequest,
        needs: set[str],
        ctx: CallContext,
        output_model: type[BaseModel] | None,
        *,
        is_fallback: bool,
    ) -> GatewayResult:
        price = await self._price_for(provider, req.model, needs)
        if provider.paid and not self.settings.ai_paid_calls_enabled:
            raise AppError("PAID_CALLS_DISABLED")
        try:
            input_tokens = await provider.count_input_tokens(req)
        except ProviderError:
            input_tokens = (len(req.system) + sum(len(str(m.content)) for m in req.messages)) // 3 + 1
        amount = max_cost(price, input_tokens=input_tokens, max_output_tokens=req.max_output_tokens)
        origin = provider.data_origin
        reservation = await self.budget.reserve(
            ctx.job_id, amount, origin, call_timeout_s=req.timeout_s, step_id=ctx.step_id
        )
        if ctx.is_cancelled is not None and await ctx.is_cancelled():
            await self.budget.release(reservation.id, "NOT_SENT")
            raise JobCancelledError
        await self.budget.mark_sent(reservation.id)

        base_log: dict[str, Any] = {
            "job_id": ctx.job_id,
            "step_id": ctx.step_id,
            "provider": provider.name,
            "model": req.model,
            "task_type": req.task_type,
            "data_origin": origin,
            "is_fallback": is_fallback,
            "pricing_id": price.id,
        }
        try:
            async with asyncio.timeout(req.timeout_s + 5):
                response = await provider.generate(req)
        except TimeoutError:
            exc: ProviderError = ProviderTimeoutError("gateway timeout", sent=True)
            await self._handle_failure(exc, reservation.id, base_log)
            raise exc from None
        except ProviderError as err:
            await self._handle_failure(err, reservation.id, base_log)
            raise

        cost = compute_cost(price, response.usage)
        # Validate schema TRƯỚC khi ghi usage log (bảng bất biến) để outcome được ghi đúng ngay từ đầu.
        parsed: dict[str, Any] | None = response.parsed_output
        schema_valid = True
        if output_model is not None and response.outcome == "SUCCESS":
            try:
                parsed = output_model.model_validate(response.parsed_output or {}).model_dump(mode="json")
            except ValidationError:
                parsed, schema_valid = None, False
        usage_id = await self._insert_usage(
            {
                **base_log,
                "outcome": response.outcome if schema_valid else "SCHEMA_INVALID",
                "billing_status": "BILLED",
                "sent": True,
                "stop_reason": response.stop_reason,
                "refusal_category": response.refusal_category,
                "refusal_explanation": response.refusal_explanation,
                "provider_request_id": response.provider_request_id,
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "cache_read_tokens": response.usage.cache_read_tokens,
                "cache_write_tokens": response.usage.cache_write_tokens,
                "cost_usd": cost,
                "latency_ms": response.latency_ms,
            }
        )
        await self.budget.settle(reservation.id, usage_id, cost)
        return GatewayResult(
            response, parsed, usage_id, cost, origin, provider.name, req.model, is_fallback, schema_valid
        )

    async def _handle_failure(self, exc: ProviderError, reservation_id: uuid.UUID, base_log: dict[str, Any]) -> None:
        """Phân loại chi phí của lời gọi lỗi (FR-047) và xử lý reservation tương ứng."""
        if not exc.sent:
            billing, action, reason = "NOT_BILLED", "release", "NOT_SENT"
        elif isinstance(exc, ProviderTimeoutError):
            billing, action, reason = "UNCERTAIN", "uncertain", "TIMEOUT_AFTER_SEND"
        elif isinstance(exc, ProviderNetworkError):
            billing, action, reason = "UNCERTAIN", "uncertain", "CONNECTION_LOST"
        elif await self._error_policy_verified(str(base_log["provider"])):
            billing, action, reason = "NOT_BILLED", "release", "ERROR_RESPONSE_NOT_BILLED"
        else:
            billing, action, reason = "UNCERTAIN", "uncertain", "ERROR_BILLING_UNVERIFIED"
        await self._insert_usage(
            {**base_log, "outcome": exc.outcome, "billing_status": billing, "sent": exc.sent, "cost_usd": Decimal(0)}
        )
        if action == "release":
            await self.budget.release(reservation_id, reason)
            return
        count = await self.budget.mark_uncertain(reservation_id, reason)
        limits = await self._max_uncertain()
        if count >= limits:
            raise UncertainLimitReachedError(base_log["job_id"], count, limits) from exc

    async def _max_uncertain(self) -> int:
        async with self.sessionmaker() as s:
            return int(
                (
                    await s.execute(text("SELECT value FROM settings WHERE key = 'budget.max_uncertain_per_job'"))
                ).scalar_one()
            )

    async def _insert_usage(self, row: dict[str, Any]) -> uuid.UUID:
        usage_id = uuid.uuid4()
        cols = {"id": usage_id, **row}
        names = ", ".join(cols)
        params = ", ".join(f":{k}" for k in cols)
        async with self.sessionmaker() as s, s.begin():
            await s.execute(text(f"INSERT INTO ai_usage_logs ({names}) VALUES ({params})"), cols)  # noqa: S608
        return usage_id
