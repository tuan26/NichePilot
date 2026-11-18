# Hợp đồng Interface Nội bộ: E0

**Ngày**: 2026-11-18 | Liên quan: [research.md](../research.md), [data-model.md](../data-model.md)

Các interface dưới đây là ranh giới ổn định mà E1–E8 dựa vào (Constitution VIII). Chữ ký viết dạng Python để rõ kiểu;
đây là **hợp đồng**, không phải mã triển khai. Thay đổi phá vỡ hợp đồng cần cập nhật tài liệu này và test hợp đồng.

---

## 1. `LLMProvider` — AI Gateway (FR-010, FR-011, FR-018)

Ba triển khai: `AnthropicAPIProvider`, `OpenAIAPIProvider`, `MockAIProvider`. Business logic **không bao giờ** gọi
provider trực tiếp; nó gọi `AIGateway`, gateway chọn provider từ `ModelTaskProfile` + `AI_PROVIDER_OVERRIDE`.

```python
class LLMProvider(Protocol):
    name: Literal["anthropic", "openai", "mock"]
    data_origin: Literal["REAL", "MOCK"]

    async def count_input_tokens(self, req: LLMRequest) -> int: ...          # không tính phí; lỗi → ProviderError
    async def generate(self, req: LLMRequest) -> LLMResponse: ...            # một lượt gọi model
    async def check_connection(self) -> ConnectionCheckResult: ...           # không tính phí (models.list hoặc tương đương)
```

```python
class LLMRequest(BaseModel):
    task_type: str
    model: str
    system: str                                   # đã qua sanitize_for_llm()
    messages: list[LLMMessage]                    # nội dung tool/web bọc trong khối untrusted_content
    tools: list[ToolSpec] = []                    # lấy từ Tool Registry theo quyền agent
    output_schema: type[BaseModel] | None = None  # yêu cầu structured output
    effort: str | None
    max_output_tokens: int
    timeout_s: int
    mock_scenario: str | None = None              # chỉ MockAIProvider đọc; provider thật từ chối nếu có giá trị

class LLMResponse(BaseModel):
    outcome: AiOutcome                            # SUCCESS | SCHEMA_INVALID | ... | REFUSED | TRUNCATED
    stop_reason: str | None
    content_text: str | None
    tool_calls: list[ToolCall]                    # input đã parse JSON (không so khớp chuỗi thô)
    parsed_output: dict | None                    # chưa được coi là hợp lệ cho tới khi gateway validate
    refusal_category: str | None
    refusal_explanation: str | None
    usage: TokenUsage                             # input, output, cache_read, cache_write
    provider_request_id: str | None
    raw_model: str                                # model provider thực sự báo cáo
    latency_ms: int
    data_origin: Literal["REAL", "MOCK"]
```

**Lỗi chuẩn hóa** (provider ném, gateway phân loại – FR-014):

| Exception | outcome | Retry ở Job Runtime |
|---|---|---|
| `ProviderTimeout` | TIMEOUT | Có (backoff) |
| `ProviderRateLimited(retry_after_s)` | RATE_LIMITED | Có, chờ `retry_after_s` |
| `ProviderUnavailable` (5xx, 529) | PROVIDER_ERROR | Có; hết lượt → fallback nếu cấu hình |
| `ProviderNetworkError` | NETWORK_ERROR | Có |
| `ProviderAuthError` (401/403) | AUTH_ERROR | Không |
| `ProviderBadRequest` (400/404/422) | BAD_REQUEST | Không |
| — (`stop_reason=refusal`) | REFUSED | Không; không fallback |
| — (`stop_reason=max_tokens`) | TRUNCATED | Không tự động |
| — (parse/validate thất bại) | SCHEMA_INVALID | Có, tối đa `schema_retry_max` |

**Bất biến của `AIGateway.call(task_type, request, job_ctx)`** – thứ tự bắt buộc:

1. Chọn profile → provider (override, rào chắn production cho mock).
2. Từ chối nếu `mock_scenario` được truyền mà provider không phải mock.
3. Bảng giá model phải tồn tại và `verified` (mock: bảng giá giả lập) → nếu không: `PRICING_MISSING`.
4. Ước tính chi phí tối đa → `BudgetService.reserve()` (theo `data_origin`) → `BudgetExceeded` nếu không đủ.
5. Nếu provider có phí và `AI_PAID_CALLS_ENABLED=false` → `PaidCallsDisabled` (giải phóng đặt chỗ).
6. Kiểm tra `cancel_requested` của job.
7. Gọi provider với timeout.
8. Ghi `ai_usage_logs` (luôn, kể cả lỗi có usage) → `settle()` đặt chỗ.
9. Validate `parsed_output` bằng `output_schema` (Pydantic) → `SCHEMA_INVALID` nếu sai.
10. Trả kết quả cho agent.

**Hành vi `MockAIProvider`** (R-14): không I/O mạng; xác định theo seed; mọi chuỗi sinh ra có tiền tố `[MOCK]`; usage
giả lập (mặc định 2 000 vào / 500 ra; `budget_heavy`: 2 000 000 vào); kịch bản: `success`, `timeout`, `rate_limit`,
`schema_invalid`, `provider_error`, `auth_error`, `refusal`, `truncated`, `budget_heavy`,
`fail_n_then_success:<kịch bản>:<n>`. Khi có `tools`, kịch bản `success` trả một lời gọi tool hợp lệ ở lượt đầu rồi output
cuối ở lượt sau.

## 2. Tool Registry (FR-020, FR-022, FR-023)

```python
class ToolDefinition(BaseModel):
    name: str                         # dạng "namespace.action", ví dụ "system.runtime_info"
    version: str
    description: str                  # mô tả cho model
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    timeout_s: int = 30
    external_effect: bool = False     # True → bị vô hiệu hóa trong MVP
    rate_limit_per_min: int | None = None
    handler: Callable[[BaseModel, ToolContext], Awaitable[BaseModel]]

class ToolRegistry(Protocol):
    def register(self, tool: ToolDefinition) -> None: ...                    # trùng name+version → lỗi khởi động
    def specs_for(self, allowed: Sequence[str]) -> list[ToolSpec]: ...       # schema gửi cho model
    async def execute(self, name: str, raw_input: dict, ctx: ToolContext) -> ToolResult: ...
```

`execute` bất biến: tool phải thuộc `ctx.allowed_tools` (nếu không: `DENIED/NOT_PERMITTED`) → `external_effect` phải false
trong MVP (nếu không: `DENIED/EXTERNAL_EFFECT_DISABLED`) → validate input → chạy với timeout → validate output → ghi
`tool_executions` (redaction) → trả kết quả đã đánh dấu `untrusted_content` cho agent.

Tool có sẵn trong E0: `system.runtime_info` (trả phiên bản ứng dụng, thời gian máy chủ, múi giờ – không tác động bên ngoài,
không đọc secret).

## 3. Định nghĩa Agent (FR-021, AI-08)

```python
class AgentDefinition(BaseModel):
    job_type: str                     # ví dụ "system.diagnostic"
    description: str
    task_type: str                    # khóa tới ModelTaskProfile – KHÔNG có tên model
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    allowed_tools: list[str]
    max_steps: int
    max_ai_calls: int
    timeout_s: int
    token_budget: int                 # tổng token vào+ra tối đa của job
    retry_policy: RetryPolicy         # max_attempts, base_delay_s, max_delay_s, jitter
    paid: bool                        # có thể phát sinh chi phí AI thật
    acceptance: Callable[[BaseModel], list[str]]   # trả danh sách vi phạm; rỗng = đạt

class Agent(Protocol):
    definition: AgentDefinition
    async def step(self, state: AgentState, ctx: JobContext) -> StepOutcome: ...   # một bước; idempotent theo (job_id, seq)
```

Job Runtime (không phải agent) chịu trách nhiệm: vòng lặp, giới hạn bước/lời gọi/token/timeout, checkpoint sau mỗi bước,
kiểm tra pause/cancel giữa các bước, chuyển trạng thái job.

Agent E0 `system.diagnostic`: input `{ mock_scenario?: str }`; bước 1 gọi AI với tool `system.runtime_info` được phép;
bước 2 thực thi tool; bước 3 gọi AI yêu cầu output `{ status: "ok", provider: str, model: str, echoed_runtime: {...},
note: str }`; acceptance: `status == "ok"` và `echoed_runtime` khớp output tool.

## 4. `JobQueue` (R-01)

```python
class JobQueue(Protocol):
    async def enqueue_run(self, job_id: UUID) -> int: ...      # queueing_lock = "agent_job:{job_id}"; trả queue_job_id
    async def cancel_run(self, queue_job_id: int) -> None: ...
    async def stalled_runs(self) -> list[UUID]: ...            # job_id có lượt thực thi của worker hết heartbeat
```

Triển khai mặc định: `ProcrastinateJobQueue`. Phương án dự phòng: `PgSkipLockedJobQueue`. Business logic chỉ phụ thuộc
`JobQueue`.

## 5. `BudgetService` (FR-042…FR-045)

```python
class BudgetService(Protocol):
    async def reserve(self, job_id: UUID, amount_usd: Decimal, origin: DataOrigin) -> Reservation: ...
        # advisory lock; kiểm tra ngày, tháng, job; BudgetExceeded(scope, limit, spent, reserved, requested)
    async def settle(self, reservation_id: UUID, usage_log_id: UUID, actual_usd: Decimal) -> None: ...
    async def release(self, reservation_id: UUID) -> None: ...
    async def status(self) -> BudgetStatus: ...
    async def can_resume(self, job_id: UUID) -> bool: ...   # dùng cho POST /jobs/{id}/resume
```

## 6. `EvidenceService` (FR-007) — dùng từ E1

```python
class EvidenceService(Protocol):
    async def upsert_source(self, project_id: UUID, src: SourceInput, origin: DataOrigin) -> UUID: ...
    async def add_evidence(self, ev: EvidenceInput, origin: DataOrigin) -> UUID: ...   # thực thi CHECK VERIFIED/UNKNOWN
    async def evidence_for(self, subject_type: str, subject_id: UUID, *, include_mock: bool = False) -> list[Evidence]: ...
```

## 7. Ghi log & audit

- `get_logger()` trả logger structlog đã gắn context (`request_id`, `job_id`, `step_id`); processor redaction luôn bật.
- `AuditService.record(action, entity_type, entity_id, before, after)` ghi trong cùng transaction với thay đổi.

## 8. Mã lỗi ổn định (frontend dịch theo `code`)

`AUTH_REQUIRED`, `AUTH_INVALID_CREDENTIALS`, `AUTH_LOCKED`, `ALREADY_SETUP`, `CSRF_INVALID`, `VALIDATION_ERROR`,
`NOT_FOUND`, `VERSION_CONFLICT`, `INVALID_JOB_TRANSITION`, `BUDGET_DAILY_EXCEEDED`, `BUDGET_MONTHLY_EXCEEDED`,
`BUDGET_JOB_EXCEEDED`, `BUDGET_STILL_INSUFFICIENT`, `BUDGET_NOT_CONFIGURED`, `PAID_CALLS_DISABLED`, `PRICING_MISSING`,
`PROVIDER_NOT_CONFIGURED`, `PROVIDER_AUTH_ERROR`, `PROVIDER_TIMEOUT`, `PROVIDER_RATE_LIMITED`, `PROVIDER_UNAVAILABLE`,
`PROVIDER_NETWORK_ERROR`, `AI_REFUSED`, `AI_TRUNCATED`, `AI_SCHEMA_INVALID`, `MAX_STEPS_EXCEEDED`,
`MAX_AI_CALLS_EXCEEDED`, `JOB_TIMEOUT`, `TOOL_NOT_PERMITTED`, `TOOL_EXTERNAL_EFFECT_DISABLED`, `MOCK_NOT_ALLOWED`,
`SERVICE_UNAVAILABLE`, `INTERNAL_ERROR`.
