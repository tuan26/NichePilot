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
| `ProviderNetworkError` (trước khi gửi: NOT_BILLED; mất kết nối sau khi gửi: UNCERTAIN) | NETWORK_ERROR | Có |
| `ProviderAuthError` (401/403) | AUTH_ERROR | Không |
| `ProviderBadRequest` (400/404/422) | BAD_REQUEST | Không |
| — (`stop_reason=refusal`) | REFUSED | Không; không fallback |
| — (`stop_reason=max_tokens`) | TRUNCATED | Không tự động |
| — (parse/validate thất bại) | SCHEMA_INVALID | Có, tối đa `schema_retry_max` |

**Bất biến của `AIGateway.call(task_type, request, job_ctx)`** – thứ tự bắt buộc:

1. Chọn profile → provider (override). **Rào chắn runtime**: nếu `APP_ENV=production` và provider là `mock` →
   `MockNotAllowed` (bổ sung cho kiểm tra lúc khởi động – FR-018(f)).
2. Từ chối nếu `mock_scenario` được truyền mà provider không phải mock, hoặc đang ở production.
3. Provider có phí: model phải `ai_models.verified` và có khả năng tác vụ cần (`MODEL_NOT_VERIFIED`), bảng giá phải
   tồn tại và `verified` (`PRICING_NOT_VERIFIED`). Mock: dùng bảng giá giả lập riêng.
4. Nếu provider có phí và `AI_PAID_CALLS_ENABLED=false` → `PaidCallsDisabled` (chưa tạo reservation).
5. Ước tính chi phí tối đa → `BudgetService.reserve()` (nguyên tử, theo `data_origin`) → `BudgetExceeded` nếu không đủ.
6. Kiểm tra `cancel_requested` của job → nếu hủy: `release(NOT_SENT)`.
7. `BudgetService.mark_sent(reservation)` (commit riêng) ngay trước khi gửi.
8. Gọi provider với timeout.
9. Ghi `ai_usage_logs` với `billing_status` → xử lý reservation theo bảng dưới.
10. Validate `parsed_output` bằng `output_schema` (Pydantic) → `SCHEMA_INVALID` nếu sai (chi phí vẫn đã `SETTLED`).
11. Trả kết quả cho agent.

**Phân loại chi phí sau lời gọi (FR-047)**:

| Tình huống | billing_status | Reservation |
|---|---|---|
| Phản hồi có usage (thành công, refusal, truncated, sai schema) | BILLED | `settle(actual)` |
| Lỗi trước khi gửi (DNS, connection refused trước khi ghi request, hủy, ngân sách, công tắc phí) | NOT_BILLED | `release(NOT_SENT)` |
| Phản hồi lỗi HTTP đầy đủ (4xx/5xx) **và** `billing.error_responses_not_billed_verified[provider] = true` | NOT_BILLED | `release(ERROR_RESPONSE_NOT_BILLED)` |
| Phản hồi lỗi HTTP khi chính sách tính phí của provider **chưa** được xác minh | UNCERTAIN | `mark_uncertain(ERROR_BILLING_UNVERIFIED)` |
| Timeout sau khi gửi / mất kết nối giữa chừng | UNCERTAIN | `mark_uncertain(TIMEOUT_AFTER_SEND \| CONNECTION_LOST)` |
| Phản hồi không đọc được usage | UNCERTAIN | `mark_uncertain(USAGE_UNREADABLE)` |
| MockAIProvider | theo kịch bản (mô phỏng cả ba loại) | như trên, sổ MOCK |

**Hành vi `MockAIProvider`** (R-14): không I/O mạng; xác định theo seed; mọi chuỗi sinh ra có tiền tố `[MOCK]`; usage
giả lập (mặc định 2 000 vào / 500 ra; `budget_heavy`: 2 000 000 vào); kịch bản: `success`, `timeout`, `rate_limit`,
`schema_invalid`, `provider_error`, `auth_error`, `refusal`, `truncated`, `budget_heavy`, `timeout_after_send`, `network_error`,
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
        # advisory lock; kiểm tra ngày, tháng, job và số UNCERTAIN của job < budget.max_uncertain_per_job;
        # BudgetExceeded(scope, limit, spent, reserved, requested) | UncertainLimitReached(job_id, count, limit)
    async def mark_sent(self, reservation_id: UUID) -> None: ...                  # commit ngay, trước khi gửi
    async def settle(self, reservation_id: UUID, usage_log_id: UUID, actual_usd: Decimal) -> None: ...
        # ghi chênh lệch actual - amount; actual > amount → log cảnh báo BUDGET_RESERVATION_OVERRUN + audit
    async def release(self, reservation_id: UUID, reason: str) -> None: ...     # chỉ khi chắc chắn chưa phát sinh phí
    async def mark_uncertain(self, reservation_id: UUID, reason: str) -> int: ...  # trả số UNCERTAIN hiện tại của job
        # Gateway: nếu kết quả ≥ giới hạn → UncertainLimitReached → Job Runtime chuyển PAUSED_BUDGET (UNCERTAIN_RESERVATION_LIMIT)
    async def resolve(self, reservation_id: UUID, actual_usd: Decimal, note: str, user_id: UUID) -> None: ...  # thủ công, audit
    async def sweep_stale(self) -> SweepResult: ...
        # ACTIVE quá expires_at: sent_at NULL → RELEASED(NOT_SENT); ngược lại → UNCERTAIN(WORKER_LOST); không bao giờ tự giải phóng UNCERTAIN
    async def status(self) -> BudgetStatus: ...
    async def can_resume(self, job_id: UUID) -> ResumeCheck: ...   # OK | BUDGET_STILL_INSUFFICIENT | UNCERTAIN_RESERVATIONS_UNRESOLVED
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
`NOT_FOUND`, `VERSION_CONFLICT`, `INVALID_JOB_TRANSITION`, `MODEL_NOT_VERIFIED`, `PRICING_NOT_VERIFIED`,
`RESERVATION_NOT_UNCERTAIN`, `UNCERTAIN_RESERVATION_LIMIT`, `UNCERTAIN_RESERVATIONS_UNRESOLVED`, `BUDGET_DAILY_EXCEEDED`, `BUDGET_MONTHLY_EXCEEDED`,
`BUDGET_JOB_EXCEEDED`, `BUDGET_STILL_INSUFFICIENT`, `BUDGET_NOT_CONFIGURED`, `PAID_CALLS_DISABLED`, `PRICING_MISSING`,
`PROVIDER_NOT_CONFIGURED`, `PROVIDER_AUTH_ERROR`, `PROVIDER_TIMEOUT`, `PROVIDER_RATE_LIMITED`, `PROVIDER_UNAVAILABLE`,
`PROVIDER_NETWORK_ERROR`, `PROVIDER_BAD_REQUEST`, `AI_REFUSED`, `AI_TRUNCATED`, `AI_SCHEMA_INVALID`, `MAX_STEPS_EXCEEDED`,
`MAX_AI_CALLS_EXCEEDED`, `JOB_TOKEN_BUDGET_EXCEEDED`, `JOB_CANCELLED`, `JOB_TIMEOUT`, `TOOL_NOT_PERMITTED`, `TOOL_EXTERNAL_EFFECT_DISABLED`, `MOCK_NOT_ALLOWED`,
`SERVICE_UNAVAILABLE`, `INTERNAL_ERROR`.
