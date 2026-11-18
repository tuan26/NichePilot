# Data Model (Phase 1): E0 — Foundation & AI Infrastructure

**Ngày**: 2026-11-18 | **Spec**: [spec.md](./spec.md) | **Research**: [research.md](./research.md)

Quy ước chung (DATA-01, FR-005):

- Khóa chính `id UUID` (sinh bằng `uuid7` phía ứng dụng để có thứ tự thời gian; DB default `gen_random_uuid()`).
- Mọi bảng có `created_at timestamptz NOT NULL DEFAULT now()` và `updated_at timestamptz NOT NULL` (cập nhật tự động);
  **ngoại lệ**: `audit_logs` và `ai_usage_logs` là bất biến nên chỉ có `created_at`.
- Thời gian lưu UTC (`timestamptz`); quy đổi ngày/tháng ngân sách theo múi giờ cấu hình.
- Tiền: `NUMERIC(14,6)` USD. Token: `BIGINT`.
- Enum lưu dạng `TEXT` + `CHECK` (dễ migration hơn enum PostgreSQL).
- `data_origin TEXT NOT NULL CHECK (data_origin IN ('REAL','MOCK'))` trên mọi bảng chứa kết quả AI/tool/nghiên cứu (R-14).
- Bảng `procrastinate_*` do thư viện quản lý, được tạo trong migration Alembic, không mô tả ở đây.

## Sơ đồ quan hệ

```mermaid
erDiagram
  users ||--o{ auth_sessions : has
  projects ||--o{ agent_jobs : scopes
  projects ||--o{ job_schedules : scopes
  projects ||--o{ research_sources : scopes
  job_schedules ||--o{ agent_jobs : triggers
  agent_jobs ||--o{ job_steps : contains
  agent_jobs ||--o{ tool_executions : records
  agent_jobs ||--o{ ai_usage_logs : records
  agent_jobs ||--o{ budget_reservations : holds
  job_steps ||--o{ ai_usage_logs : records
  job_steps ||--o{ tool_executions : records
  model_pricing ||--o{ ai_usage_logs : prices
  budget_reservations |o--o| ai_usage_logs : settles
  research_sources ||--o{ research_evidence : supports
  agent_jobs ||--o{ research_evidence : collects
```

---

## 1. `users` — chủ sở hữu (FR-052, FR-053)

| Cột | Kiểu | Ràng buộc / Ghi chú |
|---|---|---|
| id | UUID | PK |
| username | TEXT | UNIQUE, 3–64 ký tự `[a-z0-9._-]` |
| password_hash | TEXT | Argon2id (không bao giờ trả qua API) |
| ui_locale | TEXT | `vi` \| `en`, mặc định `vi` |
| failed_login_count | INT | ≥ 0, reset khi đăng nhập thành công |
| locked_until | timestamptz | NULL = không khóa; = now + 15 phút sau 5 lần sai |
| last_login_at | timestamptz | NULL được |

Quy tắc: MVP tối đa 1 bản ghi (API khởi tạo từ chối nếu đã có user). Mật khẩu ≥ 12 ký tự.

## 2. `auth_sessions` — phiên đăng nhập phía server (R-07)

| Cột | Kiểu | Ràng buộc / Ghi chú |
|---|---|---|
| id | UUID | PK |
| user_id | UUID | FK → users, ON DELETE CASCADE |
| token_hash | TEXT | UNIQUE, SHA-256 của token cookie |
| last_seen_at | timestamptz | cập nhật tối đa mỗi 60 s |
| expires_at | timestamptz | last_seen + 12 giờ (cấu hình) |
| revoked_at | timestamptz | NULL = còn hiệu lực |
| ip, user_agent | TEXT | phục vụ audit |

## 3. `projects` — phạm vi dữ liệu (FR-006, BR-10)

| Cột | Kiểu | Ràng buộc / Ghi chú |
|---|---|---|
| id | UUID | PK |
| slug | TEXT | UNIQUE |
| name | TEXT | |
| is_default | BOOL | partial UNIQUE (chỉ một `true`) |
| target_market | TEXT | ISO 3166-1 alpha-2, mặc định `US` |
| research_language | TEXT | `auto` (theo thị trường) hoặc mã BCP 47; mặc định `auto` |
| content_language | TEXT | BCP 47, mặc định `en` |

Seed: một project mặc định `default`.

## 4. `settings` — cấu hình không bí mật (FR-055)

| Cột | Kiểu | Ràng buộc / Ghi chú |
|---|---|---|
| id | UUID | PK |
| key | TEXT | UNIQUE; CHECK không chứa `key`/`secret`/`token`/`password` (R-08) |
| value | JSONB | validate theo schema đăng ký của key |
| version | INT | tăng mỗi lần sửa (optimistic locking) |
| updated_by | UUID | FK → users, NULL = hệ thống |

Khóa seed:

| key | Giá trị mặc định |
|---|---|
| `budget.daily_usd` | 3.00 |
| `budget.monthly_usd` | 30.00 |
| `budget.per_job_default_usd` | 2.00 |
| `budget.warning_threshold` | 0.80 |
| `system.timezone` | `Asia/Ho_Chi_Minh` |
| `agent.default_max_steps` | 20 |
| `agent.default_max_ai_calls` | 30 |
| `agent.default_job_timeout_s` | 1800 |
| `worker.max_concurrent_jobs` | 1 |
| `schedule.misfire_policy_default` | `RUN_ONCE` |
| `ui.default_locale` | `vi` |

Ràng buộc chéo: `per_job_default_usd ≤ daily_usd ≤ monthly_usd`; giá trị > 0.

## 5. `model_pricing` — bảng giá có phiên bản (FR-041)

| Cột | Kiểu | Ràng buộc / Ghi chú |
|---|---|---|
| id | UUID | PK |
| provider | TEXT | `anthropic` \| `openai` \| `mock` |
| model | TEXT | |
| version | INT | UNIQUE(provider, model, version) |
| effective_from | timestamptz | bản có hiệu lực = version lớn nhất có effective_from ≤ now |
| input_per_mtok, output_per_mtok | NUMERIC | ≥ 0 |
| cache_read_per_mtok, cache_write_per_mtok | NUMERIC | NULL = chưa xác minh → model bị chặn nếu dùng cache |
| long_context_threshold_tokens | BIGINT | NULL = không phân tầng |
| long_input_per_mtok, long_output_per_mtok | NUMERIC | áp dụng khi prompt > ngưỡng |
| source_note | TEXT | nguồn giá + ngày xác minh (Evidence-First) |
| verified | BOOL | `false` → không cho chạy job có phí với model này |

Bản ghi chỉ thêm, không sửa (đổi giá = thêm version mới).

## 6. `model_task_profiles` — model theo tác vụ (FR-012, R-04)

| Cột | Kiểu | Ràng buộc / Ghi chú |
|---|---|---|
| id | UUID | PK |
| task_type | TEXT | UNIQUE (ví dụ `system.diagnostic`) |
| provider | TEXT | `anthropic` \| `openai` \| `mock` |
| model | TEXT | phải có trong `model_pricing` |
| effort | TEXT | `low`\|`medium`\|`high`\|`xhigh`\|`max`\|NULL (provider không hỗ trợ) |
| max_output_tokens | INT | 1–128 000 |
| timeout_s | INT | 5–900, mặc định 120 |
| schema_retry_max | INT | 0–5, mặc định 2 |
| fallback_provider, fallback_model | TEXT | NULL = không dự phòng; không được là `mock`; không cùng provider chính |
| fallback_on | TEXT[] | tập con của `{PROVIDER_UNAVAILABLE}` (mặc định rỗng) |
| enabled | BOOL | |

Seed theo bảng R-04 (`system.diagnostic`, `extract.simple`, `analyze.standard`, `reason.complex`).

## 7. `agent_jobs` — job (FR-030…FR-038)

| Cột | Kiểu | Ràng buộc / Ghi chú |
|---|---|---|
| id | UUID | PK |
| project_id | UUID | FK → projects |
| job_type | TEXT | phải là loại đã đăng ký (E0: `system.diagnostic`) |
| params | JSONB | validate theo input schema của agent |
| idempotency_key | TEXT | UNIQUE (FR-037) |
| status | TEXT | xem state machine |
| trigger | TEXT | `MANUAL` \| `SCHEDULE` \| `RETRY` |
| schedule_id | UUID | FK → job_schedules, NULL được |
| scheduled_for | timestamptz | thời điểm lịch (job từ lịch) |
| data_origin | TEXT | `REAL`/`MOCK` theo provider thực tế đã dùng; `MOCK` nếu bất kỳ bước nào dùng mock |
| budget_limit_usd | NUMERIC | ≤ ngân sách ngày; mặc định `budget.per_job_default_usd` |
| cost_accumulated_usd | NUMERIC | tổng chi phí thực (hoặc giả lập nếu MOCK) |
| max_steps, max_ai_calls, timeout_s | INT | snapshot giới hạn khi tạo job |
| step_count, ai_call_count | INT | bộ đếm |
| last_completed_seq | INT | checkpoint: bước cuối hoàn tất (0 = chưa) |
| checkpoint | JSONB | trạng thái agent đã tuần tự hóa (không chứa secret) |
| pause_requested, cancel_requested | BOOL | cờ yêu cầu từ người dùng |
| attempt | INT | số lượt thực thi đã chạy |
| max_attempts | INT | mặc định 3 (retry tự động lỗi tạm thời) |
| status_reason_code | TEXT | ví dụ `BUDGET_DAILY_EXCEEDED`, `PAID_CALLS_DISABLED`, `REFUSED`, `MAX_STEPS` |
| status_reason_detail | JSONB | số liệu kèm (ngân sách bị chạm, ước tính, phần còn lại…) |
| result | JSONB | output đã validate theo output schema |
| queue_job_id | BIGINT | id lượt thực thi Procrastinate hiện tại |
| heartbeat_at | timestamptz | worker cập nhật khi RUNNING |
| started_at, finished_at | timestamptz | |

Chỉ mục: `(status)`, `(project_id, created_at DESC)`, `(schedule_id, scheduled_for)`.

### State machine

```mermaid
stateDiagram-v2
  [*] --> QUEUED
  QUEUED --> RUNNING : worker nhận
  QUEUED --> CANCELLED : hủy
  RUNNING --> SUCCEEDED
  RUNNING --> FAILED : lỗi không retry / hết max_attempts / REFUSED / MAX_STEPS / PAID_CALLS_DISABLED
  RUNNING --> RETRY_SCHEDULED : lỗi tạm thời / worker stalled
  RUNNING --> PAUSED : pause_requested (sau bước hiện tại)
  RUNNING --> PAUSED_BUDGET : ngân sách không đủ
  RUNNING --> CANCELLED : cancel_requested
  RETRY_SCHEDULED --> RUNNING
  RETRY_SCHEDULED --> CANCELLED
  PAUSED --> QUEUED : resume
  PAUSED --> CANCELLED
  PAUSED_BUDGET --> QUEUED : resume (chỉ khi chủ sở hữu yêu cầu và ngân sách đủ)
  PAUSED_BUDGET --> CANCELLED
  FAILED --> QUEUED : retry thủ công (tiếp tục từ checkpoint)
```

Trạng thái kết thúc: `SUCCEEDED`, `CANCELLED` (không chuyển tiếp); `FAILED` chỉ chuyển qua retry thủ công.
Mọi chuyển trạng thái do `JobStateMachine` kiểm tra; chuyển không hợp lệ → lỗi `INVALID_JOB_TRANSITION` (409).

## 8. `job_steps` — bước của job (FR-031, FR-036)

| Cột | Kiểu | Ràng buộc / Ghi chú |
|---|---|---|
| id | UUID | PK |
| job_id | UUID | FK → agent_jobs ON DELETE CASCADE |
| seq | INT | UNIQUE(job_id, seq) – đảm bảo chạy lại không tạo bước trùng |
| step_type | TEXT | `AI_CALL` \| `TOOL_CALL` \| `LOGIC` |
| name | TEXT | |
| status | TEXT | `RUNNING`\|`SUCCEEDED`\|`FAILED`\|`REFUSED`\|`TRUNCATED`\|`SKIPPED`\|`BLOCKED` |
| attempt | INT | số lần thử của bước |
| data_origin | TEXT | REAL/MOCK |
| input_summary | JSONB | đã redaction, giới hạn kích thước |
| output | JSONB | đã validate |
| error_code, error_message | TEXT | mã ổn định + mô tả an toàn |
| cost_usd | NUMERIC | |
| started_at, finished_at | timestamptz | |

## 9. `tool_executions` (FR-020, FR-022)

| Cột | Kiểu | Ràng buộc / Ghi chú |
|---|---|---|
| id | UUID | PK |
| job_id / step_id | UUID | FK |
| tool_name, tool_version | TEXT | |
| status | TEXT | `SUCCEEDED`\|`FAILED`\|`DENIED`\|`TIMEOUT` |
| denial_reason | TEXT | ví dụ `NOT_PERMITTED`, `EXTERNAL_EFFECT_DISABLED` |
| input, output | JSONB | đã redaction |
| data_origin | TEXT | |
| duration_ms | INT | |

## 10. `ai_usage_logs` — mỗi lời gọi AI (FR-040, FR-017) — bất biến

| Cột | Kiểu | Ràng buộc / Ghi chú |
|---|---|---|
| id | UUID | PK |
| job_id, step_id | UUID | FK, NULL được (kiểm tra kết nối không thuộc job) |
| provider, model, task_type | TEXT | |
| data_origin | TEXT | `MOCK` khi provider = mock |
| is_fallback | BOOL | lời gọi tới provider dự phòng |
| provider_request_id | TEXT | |
| outcome | TEXT | `SUCCESS`\|`SCHEMA_INVALID`\|`TIMEOUT`\|`RATE_LIMITED`\|`AUTH_ERROR`\|`NETWORK_ERROR`\|`PROVIDER_ERROR`\|`BAD_REQUEST`\|`REFUSED`\|`TRUNCATED` |
| stop_reason | TEXT | từ provider |
| refusal_category, refusal_explanation | TEXT | khi REFUSED |
| input_tokens, output_tokens, cache_read_tokens, cache_write_tokens | BIGINT | |
| cost_usd | NUMERIC | tính từ usage × pricing |
| pricing_id | UUID | FK → model_pricing |
| latency_ms | INT | |

## 11. `budget_reservations` (FR-043, R-06)

| Cột | Kiểu | Ràng buộc / Ghi chú |
|---|---|---|
| id | UUID | PK |
| job_id | UUID | FK |
| data_origin | TEXT | sổ chi tiêu tách REAL/MOCK |
| amount_usd | NUMERIC | chi phí ước tính tối đa |
| status | TEXT | `ACTIVE`\|`SETTLED`\|`RELEASED` |
| usage_log_id | UUID | FK → ai_usage_logs khi SETTLED |
| expires_at | timestamptz | ACTIVE quá hạn → RELEASED bởi tác vụ dọn dẹp |

Chi tiêu kỳ (ngày/tháng/job) = Σ `ai_usage_logs.cost_usd` + Σ `budget_reservations.amount_usd` (ACTIVE), lọc theo
`data_origin` và kỳ theo múi giờ cấu hình.

## 12. `job_schedules` (FR-033, FR-034)

| Cột | Kiểu | Ràng buộc / Ghi chú |
|---|---|---|
| id | UUID | PK |
| project_id | UUID | FK |
| name | TEXT | UNIQUE(project_id, name) |
| job_type, params | TEXT, JSONB | như agent_jobs |
| cron_expr | TEXT | 5 trường, khoảng cách tối thiểu 5 phút |
| timezone | TEXT | IANA, mặc định `system.timezone` |
| enabled | BOOL | không bật được nếu job tốn phí mà ngân sách chưa cấu hình (> 0) |
| misfire_policy | TEXT | `SKIP` \| `RUN_ONCE` |
| budget_limit_usd | NUMERIC | NULL = mặc định |
| last_run_at, next_run_at | timestamptz | |

## 13. `audit_logs` (FR-051) — append-only

| Cột | Kiểu | Ràng buộc / Ghi chú |
|---|---|---|
| id | UUID | PK |
| actor_type | TEXT | `USER` \| `SYSTEM` |
| actor_id | UUID | NULL nếu SYSTEM |
| action | TEXT | ví dụ `auth.login_failed`, `settings.updated`, `job.cancelled`, `provider.connection_tested` |
| entity_type, entity_id | TEXT, UUID | |
| before, after | JSONB | đã redaction |
| request_id, ip, user_agent | TEXT | |

Trigger `BEFORE UPDATE OR DELETE` → `RAISE EXCEPTION`.

## 14. `research_sources` & `research_evidence` — hạ tầng bằng chứng dùng chung (FR-007)

`research_sources`:

| Cột | Kiểu | Ràng buộc / Ghi chú |
|---|---|---|
| id | UUID | PK |
| project_id | UUID | FK |
| source_type | TEXT | `WEB_PAGE`\|`FORUM`\|`REVIEW_SITE`\|`VIDEO`\|`API`\|`DOCUMENT`\|`OTHER` |
| url, canonical_url | TEXT | canonical chuẩn hóa (bỏ tracking params) |
| title, publisher | TEXT | |
| fetched_at | timestamptz | thời điểm thu thập |
| content_hash | TEXT | SHA-256 nội dung đã trích |
| data_origin | TEXT | |

UNIQUE(project_id, canonical_url, content_hash).

`research_evidence`:

| Cột | Kiểu | Ràng buộc / Ghi chú |
|---|---|---|
| id | UUID | PK |
| project_id | UUID | FK |
| source_id | UUID | FK → research_sources, NULL chỉ khi `UNKNOWN` |
| subject_type, subject_id | TEXT, UUID | đối tượng được chứng minh (niche, product… – E1+) |
| claim_key | TEXT | thuộc tính, ví dụ `commission_rate` |
| value | JSONB | NULL khi UNKNOWN |
| excerpt | TEXT | trích đoạn ngắn (giới hạn độ dài, BR-09) |
| verification_status | TEXT | `VERIFIED`\|`INFERRED`\|`UNKNOWN`\|`CONFLICTING` |
| verified_at | timestamptz | |
| collected_by_job_id | UUID | FK → agent_jobs |
| data_origin | TEXT | |

CHECK: `VERIFIED` ⇒ source_id NOT NULL; `UNKNOWN` ⇒ value IS NULL. E0 chỉ tạo bảng + service; không có dữ liệu.

---

## Bảng cố ý chưa tạo trong E0

`approval_requests`, `integration_connections` (chưa có hành động bên ngoài/tích hợp – FR-023); toàn bộ bảng nghiệp vụ
E1–E8 (`niches`, `products`, `keywords`…) – tạo trong feature tương ứng (DATA-02).
