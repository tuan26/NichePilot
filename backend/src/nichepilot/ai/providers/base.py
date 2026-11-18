"""Interface provider AI dùng chung (T037 – FR-011; contracts/internal-interfaces.md §1).

Ba triển khai: `AnthropicAPIProvider` (chính), `OpenAIAPIProvider` (dự phòng), `MockAIProvider` (dev/test).
Business logic không gọi provider trực tiếp mà qua `AIGateway`.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

ProviderName = Literal["anthropic", "openai", "mock"]
DataOrigin = Literal["REAL", "MOCK"]
AiOutcome = Literal[
    "SUCCESS",
    "SCHEMA_INVALID",
    "TIMEOUT",
    "RATE_LIMITED",
    "AUTH_ERROR",
    "NETWORK_ERROR",
    "PROVIDER_ERROR",
    "BAD_REQUEST",
    "REFUSED",
    "TRUNCATED",
]
ConnectionResult = Literal["OK", "INVALID_KEY", "NETWORK_ERROR", "NOT_CONFIGURED", "PROVIDER_ERROR", "MOCK"]


class ToolSpec(BaseModel):
    """Định nghĩa tool gửi cho model (sinh từ Tool Registry)."""

    model_config = ConfigDict(frozen=True)
    name: str
    description: str
    input_schema: dict[str, Any]


class ToolCall(BaseModel):
    id: str
    name: str
    input: dict[str, Any]


class LLMMessage(BaseModel):
    """Một lượt hội thoại. `content` là chuỗi hoặc danh sách block theo định dạng trung lập của NichePilot."""

    role: Literal["user", "assistant"]
    content: str | list[dict[str, Any]]


class TokenUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


class LLMRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    task_type: str
    model: str
    system: str
    messages: list[LLMMessage]
    tools: list[ToolSpec] = Field(default_factory=list)
    output_schema: dict[str, Any] | None = None  # JSON Schema của output có cấu trúc
    effort: str | None = None
    max_output_tokens: int
    timeout_s: int
    mock_scenario: str | None = None  # chỉ MockAIProvider đọc; provider thật phải từ chối nếu có giá trị
    seed: str | None = None  # để MockAIProvider sinh kết quả xác định


class LLMResponse(BaseModel):
    outcome: AiOutcome
    stop_reason: str | None = None
    content_text: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    parsed_output: dict[str, Any] | None = None  # chưa được coi là hợp lệ cho tới khi gateway validate
    refusal_category: str | None = None
    refusal_explanation: str | None = None
    usage: TokenUsage = Field(default_factory=TokenUsage)
    provider_request_id: str | None = None
    raw_model: str
    latency_ms: int = 0
    data_origin: DataOrigin


class ConnectionCheckResult(BaseModel):
    provider: ProviderName
    result: ConnectionResult
    detail: str | None = None


# ---------------------------------------------------------------------------
# Lỗi chuẩn hóa – `sent` cho biết yêu cầu có thể đã rời hệ thống hay chưa (phục vụ phân loại chi phí FR-047)
# ---------------------------------------------------------------------------
class ProviderError(Exception):
    outcome: AiOutcome = "PROVIDER_ERROR"
    retryable: bool = False

    def __init__(self, message: str = "", *, sent: bool, usage: TokenUsage | None = None) -> None:
        super().__init__(message or self.__class__.__name__)
        self.sent = sent
        self.usage = usage


class ProviderTimeoutError(ProviderError):
    outcome: AiOutcome = "TIMEOUT"
    retryable = True


class ProviderRateLimitedError(ProviderError):
    outcome: AiOutcome = "RATE_LIMITED"
    retryable = True

    def __init__(self, message: str = "", *, sent: bool, retry_after_s: float | None = None) -> None:
        super().__init__(message, sent=sent)
        self.retry_after_s = retry_after_s


class ProviderUnavailableError(ProviderError):
    outcome: AiOutcome = "PROVIDER_ERROR"
    retryable = True


class ProviderNetworkError(ProviderError):
    outcome: AiOutcome = "NETWORK_ERROR"
    retryable = True


class ProviderAuthError(ProviderError):
    outcome: AiOutcome = "AUTH_ERROR"
    retryable = False


class ProviderBadRequestError(ProviderError):
    outcome: AiOutcome = "BAD_REQUEST"
    retryable = False


@runtime_checkable
class LLMProvider(Protocol):
    name: ProviderName
    data_origin: DataOrigin
    paid: bool

    async def count_input_tokens(self, req: LLMRequest) -> int: ...

    async def generate(self, req: LLMRequest) -> LLMResponse: ...

    async def check_connection(self) -> ConnectionCheckResult: ...
