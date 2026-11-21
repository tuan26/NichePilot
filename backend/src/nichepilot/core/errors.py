"""Lỗi chuẩn hóa dạng problem+json (T026 – FR-061; danh mục: contracts/internal-interfaces.md §8).

Frontend dịch thông báo theo `code`; `title` chỉ là mô tả ngắn tiếng Anh. Không bao giờ trả stack trace.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from nichepilot.core.logging import get_logger

PROBLEM_JSON = "application/problem+json"
log = get_logger(__name__)


@dataclass(frozen=True)
class ErrorSpec:
    status: int
    title: str


ERROR_CATALOG: dict[str, ErrorSpec] = {
    "AUTH_REQUIRED": ErrorSpec(401, "Authentication required"),
    "AUTH_INVALID_CREDENTIALS": ErrorSpec(401, "Invalid username or password"),
    "AUTH_LOCKED": ErrorSpec(423, "Account temporarily locked"),
    "ALREADY_SETUP": ErrorSpec(409, "Owner account already exists"),
    "CSRF_INVALID": ErrorSpec(403, "Missing or invalid CSRF token"),
    "VALIDATION_ERROR": ErrorSpec(422, "Validation error"),
    "NOT_FOUND": ErrorSpec(404, "Not found"),
    "VERSION_CONFLICT": ErrorSpec(409, "Resource was modified concurrently"),
    "MODEL_EXISTS": ErrorSpec(409, "Model already exists in catalog"),
    "SCHEDULE_NAME_EXISTS": ErrorSpec(409, "A schedule with this name already exists"),
    "INVALID_JOB_TRANSITION": ErrorSpec(409, "Invalid job state transition"),
    "MODEL_NOT_VERIFIED": ErrorSpec(409, "Model is not verified for paid calls"),
    "PRICING_NOT_VERIFIED": ErrorSpec(409, "Model pricing is not verified"),
    "RESERVATION_NOT_UNCERTAIN": ErrorSpec(409, "Reservation is not in UNCERTAIN state"),
    "UNCERTAIN_RESERVATION_LIMIT": ErrorSpec(409, "Job reached the uncertain reservation limit"),
    "UNCERTAIN_RESERVATIONS_UNRESOLVED": ErrorSpec(423, "Job has unresolved uncertain reservations"),
    "BUDGET_DAILY_EXCEEDED": ErrorSpec(402, "Daily AI budget exceeded"),
    "BUDGET_MONTHLY_EXCEEDED": ErrorSpec(402, "Monthly AI budget exceeded"),
    "BUDGET_JOB_EXCEEDED": ErrorSpec(402, "Job AI budget exceeded"),
    "BUDGET_STILL_INSUFFICIENT": ErrorSpec(402, "Budget is still insufficient"),
    "BUDGET_NOT_CONFIGURED": ErrorSpec(422, "Budget is not configured"),
    "PAID_CALLS_DISABLED": ErrorSpec(409, "Paid API calls are disabled"),
    "PRICING_MISSING": ErrorSpec(409, "No pricing for model"),
    "COST_ESTIMATE_UNAVAILABLE": ErrorSpec(409, "Cannot safely estimate the cost of a paid call"),
    "PROVIDER_NOT_CONFIGURED": ErrorSpec(409, "Provider is not configured"),
    "PROVIDER_AUTH_ERROR": ErrorSpec(502, "Provider rejected the credentials"),
    "PROVIDER_TIMEOUT": ErrorSpec(504, "Provider timed out"),
    "PROVIDER_RATE_LIMITED": ErrorSpec(429, "Provider rate limited the request"),
    "PROVIDER_UNAVAILABLE": ErrorSpec(502, "Provider unavailable"),
    "PROVIDER_NETWORK_ERROR": ErrorSpec(502, "Network error reaching provider"),
    "PROVIDER_BAD_REQUEST": ErrorSpec(502, "Provider rejected the request"),
    "AI_REFUSED": ErrorSpec(422, "The AI provider refused the request"),
    "AI_TRUNCATED": ErrorSpec(422, "The AI output was truncated"),
    "AI_SCHEMA_INVALID": ErrorSpec(422, "The AI output did not match the schema"),
    "MAX_STEPS_EXCEEDED": ErrorSpec(409, "Maximum agent steps exceeded"),
    "MAX_AI_CALLS_EXCEEDED": ErrorSpec(409, "Maximum AI calls exceeded"),
    "JOB_TOKEN_BUDGET_EXCEEDED": ErrorSpec(409, "Job token budget exceeded"),
    "JOB_CANCELLED": ErrorSpec(409, "Job was cancelled"),
    "JOB_TIMEOUT": ErrorSpec(504, "Job timed out"),
    "TOOL_NOT_PERMITTED": ErrorSpec(403, "Tool not permitted for this agent"),
    "TOOL_EXTERNAL_EFFECT_DISABLED": ErrorSpec(403, "Tools with external effects are disabled"),
    "MOCK_NOT_ALLOWED": ErrorSpec(409, "Mock provider is not allowed in production"),
    # E1 – Autonomous Niche Discovery (X5, specs/002-niche-discovery/contracts/openapi.yaml)
    "NO_COMPLIANT_SEARCH_SOURCE": ErrorSpec(409, "No ALLOWED data source is enabled"),
    "SOURCE_NOT_ALLOWED": ErrorSpec(409, "Only ALLOWED sources can be enabled"),
    "SOURCE_VERIFICATION_INCOMPLETE": ErrorSpec(422, "Source verification evidence is incomplete"),
    "SOURCE_CONFIG_INVALID": ErrorSpec(422, "Source configuration is invalid"),
    "SOURCE_EXISTS": ErrorSpec(409, "Source already exists"),
    "SOURCE_NOT_FOUND": ErrorSpec(404, "Source not found"),
    "RUN_BUDGET_EXCEEDS_DAILY_LIMIT": ErrorSpec(409, "Run budget exceeds the daily budget"),
    "WEIGHTS_INVALID": ErrorSpec(422, "Scoring weights are invalid"),
    "DISCOVERY_RUN_NOT_FOUND": ErrorSpec(404, "Discovery run not found"),
    "NICHE_NOT_FOUND": ErrorSpec(404, "Niche not found"),
    "EVIDENCE_NOT_FOUND": ErrorSpec(404, "Evidence not found"),
    "EVIDENCE_ALREADY_ERASED": ErrorSpec(409, "Evidence was already erased"),
    "ERASURE_LEDGER_NOT_APPLIED": ErrorSpec(503, "Evidence erasure ledger has not been fully applied"),
    "ERASURE_LEDGER_WRITE_FAILED": ErrorSpec(
        503, "The evidence erasure ledger could not be written; nothing was erased"
    ),
    "PII_ENGINE_NOT_APPROVED": ErrorSpec(409, "PII engine is not approved for this environment"),
    "TASK_TYPE_NOT_ALLOWED": ErrorSpec(409, "Task type is not registered for this agent"),
    "SERVICE_UNAVAILABLE": ErrorSpec(503, "Service temporarily unavailable"),
    "INTERNAL_ERROR": ErrorSpec(500, "Internal error"),
}


class AppError(Exception):
    """Lỗi nghiệp vụ có mã ổn định."""

    def __init__(
        self,
        code: str,
        *,
        detail: str | None = None,
        params: dict[str, Any] | None = None,
        errors: list[dict[str, str]] | None = None,
    ) -> None:
        spec = ERROR_CATALOG[code]  # KeyError nếu mã không có trong danh mục
        super().__init__(code)
        self.code = code
        self.status = spec.status
        self.title = spec.title
        self.detail = detail
        self.params = params or {}
        self.errors = errors or []


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def problem_response(
    request: Request,
    code: str,
    *,
    detail: str | None = None,
    params: dict[str, Any] | None = None,
    errors: list[dict[str, str]] | None = None,
    status: int | None = None,
) -> JSONResponse:
    spec = ERROR_CATALOG[code]
    body: dict[str, Any] = {
        "type": f"https://nichepilot.local/problems/{code.lower()}",
        "title": spec.title,
        "status": status or spec.status,
        "code": code,
    }
    if detail:
        body["detail"] = detail
    if params:
        body["params"] = params
    if errors:
        body["errors"] = errors
    rid = _request_id(request)
    if rid:
        body["request_id"] = rid
    return JSONResponse(body, status_code=body["status"], media_type=PROBLEM_JSON)


def _is_db_unavailable(exc: BaseException) -> bool:
    from sqlalchemy.exc import DBAPIError, OperationalError

    if isinstance(exc, OperationalError):
        return True
    if isinstance(exc, DBAPIError) and exc.connection_invalidated:
        return True
    try:
        import psycopg

        if isinstance(exc, psycopg.OperationalError):
            return True
    except ImportError:  # pragma: no cover
        pass
    return isinstance(exc, (ConnectionRefusedError, OSError)) and "connect" in str(exc).lower()


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return problem_response(request, exc.code, detail=exc.detail, params=exc.params, errors=exc.errors)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"field": ".".join(str(p) for p in e.get("loc", ())), "code": str(e.get("type", "invalid"))}
            for e in exc.errors()
        ]
        return problem_response(request, "VALIDATION_ERROR", errors=errors)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            return problem_response(request, "NOT_FOUND")
        if exc.status_code == 401:
            return problem_response(request, "AUTH_REQUIRED")
        return problem_response(request, "INTERNAL_ERROR", status=exc.status_code)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        if _is_db_unavailable(exc):
            log.warning("database unavailable", error_type=type(exc).__name__)
            return problem_response(request, "SERVICE_UNAVAILABLE")
        log.error("unhandled error", error_type=type(exc).__name__, exc_info=exc)
        return problem_response(request, "INTERNAL_ERROR")
