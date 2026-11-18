---

description: "Danh sách công việc triển khai E0 — Foundation & AI Infrastructure"
---

# Tasks: E0 — Foundation & AI Infrastructure

**Input**: Tài liệu thiết kế trong `/specs/001-foundation-ai-infrastructure/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (openapi.yaml, internal-interfaces.md,
configuration.md), quickstart.md

**Tests**: BẮT BUỘC (Constitution IX – Test-Driven, truy vết yêu cầu). Trong mỗi story, task test được viết trước và phải
FAIL trước khi triển khai. Test tự động KHÔNG gọi API có phí, KHÔNG gọi mạng tới provider thật; test dùng
`MockAIProvider`/`FakeLLMProvider` không được tính là đã kiểm thử provider thật (FR-018h).

**Organization**: Nhóm theo user story của spec.md. E0 là feature hạ tầng nên US2 → US3 → US4 có phụ thuộc tuần tự (xem
"Dependencies"); US1, US6, US7 độc lập tương đối sau Phase 2.

**Truy vết**: mỗi task ghi FR/SC liên quan trong ngoặc; test case đặt mã `TC-<REQ-ID>-<nn>` trong docstring/tên test; task
T118 sinh báo cáo truy vết tự động. Field có ràng buộc được trích dẫn dạng `data-model.md Entity.field`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Chạy song song được (khác file, không phụ thuộc task chưa xong)
- **[Story]**: User story (US1…US7)
- Đường dẫn theo cấu trúc web app trong plan.md: `backend/`, `frontend/`, `deploy/`, `docs/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Khởi tạo repo, công cụ, CI – chưa có nghiệp vụ.

- [ ] T001 Tạo cấu trúc thư mục theo plan.md (`backend/src/nichepilot/{core,ai,tools,jobs,modules,api}`, `backend/tests/{unit,integration,contract,live,fakes}`, `frontend/`, `deploy/`, `docs/operations/`)
- [ ] T002 Khởi tạo backend bằng uv: `backend/pyproject.toml` (Python 3.13, dependency + phiên bản theo research.md R-02/R-03/R-09, nhóm dev: pytest, pytest-asyncio, testcontainers, httpx, respx, ruff, mypy, detect-secrets) và `backend/uv.lock`
- [ ] T003 [P] Khởi tạo frontend Vite + React + TypeScript trong `frontend/` (Tailwind 4, shadcn init, i18next, react-i18next, i18next-browser-languagedetector, TanStack Query, React Router, Zod, Vitest, Playwright) với `frontend/package-lock.json` (R-10)
- [ ] T004 [P] Cấu hình lint/format/type check: `backend/pyproject.toml` (ruff, mypy strict cho `core/`, `ai/`, `jobs/`), `frontend/eslint.config.js`, `frontend/tsconfig.json`
- [ ] T005 [P] Tạo `.gitattributes` (LF cho `*.sh`, `*.py`, `Makefile`) và cập nhật `.gitignore` cho `backups/`, `deploy/env/.env` (FR-054, FR-071)
- [ ] T006 [P] Tạo `deploy/env/.env.example` theo contracts/configuration.md (không chứa secret thật; `AI_PROVIDER_OVERRIDE=mock`, `AI_PAID_CALLS_ENABLED=false`, `APP_ENV=development`) (FR-019, FR-054)
- [ ] T007 Tạo `backend/Dockerfile` multi-stage (user không phải root, không GPU) và `frontend/Dockerfile` (build SPA → Caddy) (FR-070, NFR-02)
- [ ] T008 Tạo `deploy/docker-compose.yml` (postgres:17-alpine, migrate one-shot, api, worker, web; healthcheck; `mem_limit`/`cpus` theo system-architecture §8; profile `ops` cho backup) và `deploy/caddy/Caddyfile` (FR-070)
- [ ] T009 [P] Tạo `deploy/docker-compose.dev.yml` (mount mã nguồn, `uvicorn --reload`, worker tự khởi động lại bằng watchfiles, Vite HMR) (FR-074)
- [ ] T010 [P] Tạo `Makefile` với các target `up`, `down`, `dev`, `migrate`, `test`, `test-e2e`, `test-live`, `lint`, `backup`, `restore` (quickstart.md)
- [ ] T011 [P] Tạo `.github/workflows/ci.yml`: lint, type check, unit, integration (Docker trên runner), contract, E2E với Compose, detect-secrets; KHÔNG chạy marker `live` (FR-072, SC-008)

**Checkpoint**: `make lint` chạy được trên khung rỗng; CI chạy được.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Hạ tầng lõi mà MỌI user story cần. Không story nào bắt đầu trước khi xong phase này.

### Tests cho Phase 2 (viết trước)

- [ ] T012 [P] Unit test cấu hình: đọc env/.env/Docker secret theo thứ tự ưu tiên, `SecretStr`, fail-fast `MOCK_NOT_ALLOWED` khi `APP_ENV=production` + override mock, bỏ qua `ANTHROPIC_AUTH_TOKEN`/`ANTHROPIC_PROFILE` kèm cảnh báo trong `backend/tests/unit/core/test_config.py` (FR-018f, FR-019b, FR-054)
- [ ] T013 [P] Unit test redaction log: secret đã nạp và mẫu `sk-ant-…`, `sk-…`, `Bearer …` bị che; context `request_id/job_id/step_id` có mặt trong `backend/tests/unit/core/test_logging.py` (FR-050, SC-008)
- [ ] T014 [P] Unit test định dạng lỗi problem+json với `code` ổn định, không lộ stack trace trong `backend/tests/unit/core/test_errors.py` (FR-061)
- [ ] T015 [P] Integration test migration: `alembic upgrade head` rồi `downgrade base` sạch trên PostgreSQL 17 thật (testcontainers), mọi bảng có UUID PK + timestamps theo quy ước data-model.md trong `backend/tests/integration/test_migrations.py` (FR-004, FR-005)
- [ ] T016 [P] Integration test audit append-only: UPDATE/DELETE trên `audit_logs` bị trigger từ chối (data-model.md audit_logs.actor_type, ràng buộc bất biến) trong `backend/tests/integration/test_audit_immutable.py` (FR-051)
- [ ] T017 [P] Contract test `GET /health` công khai, không lộ chi tiết, đối chiếu `contracts/openapi.yaml` trong `backend/tests/contract/test_health.py` (FR-002)

### Implementation cho Phase 2

- [ ] T018 Hạ tầng test: fixture PostgreSQL testcontainers + transaction rollback, client httpx, chặn mạng ra ngoài mặc định (respx), marker `mock`/`live` trong `backend/tests/conftest.py` và `backend/pytest.ini` (FR-072, SC-003b)
- [ ] T019 [P] Cấu hình ứng dụng bằng pydantic-settings (env > .env > secrets file; validator fail-fast production+mock; không dò hồ sơ OAuth) trong `backend/src/nichepilot/core/config.py` (FR-018f, FR-019b, FR-054)
- [ ] T020 [P] Structured logging structlog JSON + processor redaction + contextvars trong `backend/src/nichepilot/core/logging.py` (FR-050)
- [ ] T021 [P] Lỗi chuẩn hóa (exception → problem+json, danh mục mã lỗi theo contracts/internal-interfaces.md §8) trong `backend/src/nichepilot/core/errors.py` (FR-061)
- [ ] T022 [P] Database: engine/session async SQLAlchemy + psycopg 3, retry kết nối, trả `SERVICE_UNAVAILABLE` khi DB mất kết nối trong `backend/src/nichepilot/core/db.py` (FR-003, QA-08)
- [ ] T023 [P] Lớp model cơ sở (UUID PK, `created_at`/`updated_at` tự cập nhật, mixin `data_origin` với CHECK REAL/MOCK) trong `backend/src/nichepilot/core/models_base.py` (FR-005, data-model.md quy ước chung)
- [ ] T024 Thiết lập Alembic (`backend/alembic.ini`, `backend/alembic/env.py` async) và migration `0001_core`: bảng `projects`, `settings`, `audit_logs` (+ trigger chặn UPDATE/DELETE) theo data-model.md projects.slug, projects.is_default, projects.target_market, projects.research_language, projects.content_language, settings.key, settings.value, settings.version, audit_logs.actor_type trong `backend/alembic/versions/0001_core.py` (FR-004, FR-006, FR-051, FR-055)
- [ ] T025 Migration `0002_procrastinate`: áp dụng SQL schema của Procrastinate 3.11 (đã pin) trong `backend/alembic/versions/0002_procrastinate.py` (R-01)
- [ ] T026 [P] Seed project mặc định + khóa `settings` mặc định (budget.*, auth.*, agent.*, worker.*, schedule.*, ui.*, billing.*) theo data-model.md §4 trong `backend/alembic/versions/0003_seed_core.py` (FR-006, FR-042, FR-053)
- [ ] T027 [P] Audit service ghi trong cùng transaction, redaction before/after trong `backend/src/nichepilot/modules/audit/service.py` (FR-051)
- [ ] T028 FastAPI app factory: middleware `request_id`, xử lý lỗi problem+json, router `/health`, mount `/api/v1`, Swagger tại `/api/docs` trong `backend/src/nichepilot/main.py` và `backend/src/nichepilot/api/v1/__init__.py` (FR-002)
- [ ] T029 [P] Danh mục mã lỗi dùng chung cho frontend (xuất từ backend thành `frontend/src/api/error-codes.json`) – script `backend/scripts/export_error_codes.py` (FR-061, XII)

**Checkpoint**: `make up` khởi động postgres/migrate/api; `/health` = ok; test Phase 2 pass.

---

## Phase 3: User Story 1 – Khởi động hệ thống và đăng nhập an toàn (Priority: P1) 🎯 MVP

**Goal**: Khởi động một lệnh, tạo tài khoản lần đầu, đăng nhập/đăng xuất, khóa tạm, trang trạng thái, chuyển VI/EN.

**Independent Test**: Quickstart §1–§2 trên máy sạch, không cần API key.

### Tests cho User Story 1 ⚠️ (viết trước, phải FAIL)

- [ ] T030 [P] [US1] Contract test `GET /auth/setup-status`, `POST /auth/setup` (409 khi đã có user, 422 mật khẩu < 12) trong `backend/tests/contract/test_auth_setup.py` (FR-052)
- [ ] T031 [P] [US1] Contract test `POST /auth/login`, `/logout`, `GET/PATCH /auth/me`, 401 khi chưa đăng nhập, CSRF thiếu/sai → `CSRF_INVALID` trong `backend/tests/contract/test_auth_session.py` (FR-052, FR-053)
- [ ] T032 [P] [US1] Integration test khóa tài khoản sau `auth.lockout_threshold` lần sai trong `auth.lockout_minutes`, hết hạn phiên theo `auth.session_idle_timeout_hours`, thu hồi phiên khi logout, audit `auth.*` trong `backend/tests/integration/test_auth_lockout.py` (FR-051, FR-053)
- [ ] T033 [P] [US1] Contract test `GET /api/v1/system/status` (database, worker, providers chưa cấu hình ≠ lỗi, `paid_calls_enabled`, `provider_override`) trong `backend/tests/contract/test_system_status.py` (FR-002)
- [ ] T034 [P] [US1] Vitest: mọi khóa trong `frontend/src/i18n/locales/vi.json` có trong `en.json` và ngược lại; không chuỗi UI hard-code trong `frontend/tests/unit/i18n-keys.test.ts` (FR-060, SC-010)
- [ ] T035 [P] [US1] Playwright E2E: khởi tạo tài khoản → trang trạng thái tiếng Việt → chuyển EN ngay không tải lại → tải lại vẫn EN → đăng xuất → khóa sau 5 lần sai trong `frontend/tests/e2e/us1-auth-i18n.spec.ts` (US1 kịch bản 1–6)

### Implementation cho User Story 1

- [ ] T036 [US1] Migration `0004_identity`: bảng `users`, `auth_sessions` theo data-model.md users.username, users.password_hash, users.ui_locale, users.failed_login_count, users.locked_until, auth_sessions.token_hash, auth_sessions.expires_at, auth_sessions.revoked_at trong `backend/alembic/versions/0004_identity.py` (FR-052)
- [ ] T037 [P] [US1] Model SQLAlchemy `User`, `AuthSession` trong `backend/src/nichepilot/modules/identity/models.py`
- [ ] T038 [US1] Dịch vụ xác thực: Argon2id, giới hạn 1 user, khóa tạm đọc `auth.lockout_threshold`/`auth.lockout_minutes`, phiên server-side (SHA-256 token), hết hạn theo `auth.session_idle_timeout_hours` trong `backend/src/nichepilot/modules/identity/service.py` (FR-052, FR-053)
- [ ] T039 [US1] Dependency xác thực + CSRF double-submit (`np_session`, `np_csrf`, `X-CSRF-Token`) trong `backend/src/nichepilot/core/security.py` (FR-052)
- [ ] T040 [US1] Router `auth` (setup-status, setup, login, logout, me GET/PATCH) có audit trong `backend/src/nichepilot/api/v1/auth.py` (FR-051, FR-052)
- [ ] T041 [US1] Router `system/status`: kiểm tra DB, heartbeat worker (bảng `procrastinate_workers`), trạng thái provider (configured + `key_hint`), `paid_calls_enabled`, `provider_override` trong `backend/src/nichepilot/api/v1/system.py` (FR-002, FR-054)
- [ ] T042 [P] [US1] i18n frontend: `frontend/src/i18n/index.ts` (vi mặc định, lưu localStorage, đồng bộ `PATCH /auth/me`), `locales/vi.json`, `locales/en.json`, định dạng ngày/số qua `Intl` (FR-060, E4-06)
- [ ] T043 [P] [US1] API client frontend: fetch + CSRF header, ánh xạ `code` → thông báo i18n, xử lý 401 → về trang đăng nhập trong `frontend/src/api/client.ts` (FR-061)
- [ ] T044 [US1] Layout + router + `LanguageSwitcher` + `MockBadge` trong `frontend/src/app/` và `frontend/src/components/` (FR-060)
- [ ] T045 [US1] Trang `SetupPage`, `LoginPage` (thông báo khóa kèm thời gian còn lại) trong `frontend/src/pages/` (US1 kịch bản 2–4)
- [ ] T046 [US1] Trang `StatusPage` (thành phần, chế độ AI MOCK/REAL, "Gọi API có phí: TẮT/BẬT", loading/error/empty states) trong `frontend/src/pages/StatusPage.tsx` (FR-002, UI-05)

**Checkpoint**: Quickstart §1–§2 đạt; US1 kiểm thử độc lập được.

---

## Phase 4: User Story 2 – Gọi AI có kiểm soát, có cấu trúc, ghi nhận chi phí (Priority: P1)

**Goal**: AI Gateway + 3 provider + Tool Registry + Job Runtime tối thiểu chạy được job chẩn đoán bằng MockAIProvider; provider thật chỉ được kiểm thử ở mức HTTP giả lập.

**Independent Test**: Quickstart §3–§4 (không cần API key).

### Tests cho User Story 2 ⚠️

- [ ] T047 [P] [US2] Unit test MockAIProvider: không I/O mạng, xác định theo seed, tiền tố `[MOCK]`, đủ kịch bản `success`, `timeout`, `timeout_after_send`, `rate_limit`, `schema_invalid`, `provider_error`, `auth_error`, `refusal`, `truncated`, `budget_heavy`, `fail_n_then_success` trong `backend/tests/unit/ai/test_mock_provider.py` (FR-018)
- [ ] T048 [P] [US2] Unit test rào chắn mock runtime: gateway, cập nhật profile, tham số `mock_scenario` đều từ chối khi `APP_ENV=production`; `mock_scenario` bị từ chối với provider thật trong `backend/tests/unit/ai/test_mock_guard.py` (FR-018f)
- [ ] T049 [P] [US2] Contract test adapter Anthropic bằng respx (payload mẫu theo tài liệu): structured output, tool_use, `stop_reason` refusal/max_tokens, usage có cache tokens, ánh xạ 401/400/429/5xx/timeout; client tạo với `api_key` tường minh; không gửi `temperature`/prefill trong `backend/tests/contract/test_anthropic_adapter.py` (FR-010, FR-014, FR-017, FR-019b)
- [ ] T050 [P] [US2] Contract test adapter OpenAI bằng respx (ánh xạ lỗi, usage, structured output) trong `backend/tests/contract/test_openai_adapter.py` (FR-011)
- [ ] T051 [P] [US2] Unit test AIGateway: thứ tự bất biến 1–11 (contracts/internal-interfaces.md §1), refusal → `REFUSED` không fallback/không retry, fallback chỉ `PROVIDER_UNAVAILABLE` khi cấu hình, không bao giờ fallback sang mock, `SCHEMA_INVALID` retry tối đa `schema_retry_max`, công tắc `PAID_CALLS_DISABLED` chặn trước khi gửi trong `backend/tests/unit/ai/test_gateway.py` (FR-013, FR-014, FR-017, FR-019, AI-07)
- [ ] T052 [P] [US2] Unit test xác minh model/giá: provider có phí với `ai_models.verified=false` → `MODEL_NOT_VERIFIED`; giá chưa xác minh → `PRICING_NOT_VERIFIED`; model thiếu khả năng tác vụ cần → chặn; từ chối model_id chứa `latest` trong `backend/tests/unit/ai/test_catalog.py` (FR-019c)
- [ ] T053 [P] [US2] Unit test pricing: chi phí từ usage × bảng giá có phiên bản, giá phân tầng theo ngưỡng prompt, cache read/write, lệch ≤ 1% so với tính tay trong `backend/tests/unit/ai/test_pricing.py` (FR-040, FR-041, SC-003)
- [ ] T054 [P] [US2] Unit test sanitize: secret và mẫu khóa bị loại khỏi prompt; kết quả tool bọc `untrusted_content`; chỉ thị trong nội dung tool không đổi quyền tool trong `backend/tests/unit/ai/test_sanitize.py` (FR-015, FR-016)
- [ ] T055 [P] [US2] Unit test Tool Registry: tool ngoài `allowed_tools` → `DENIED/NOT_PERMITTED`, `external_effect=true` → `DENIED/EXTERNAL_EFFECT_DISABLED`, validate input/output, timeout, ghi `tool_executions` trong `backend/tests/unit/tools/test_registry.py` (FR-020, FR-022, FR-023)
- [ ] T056 [P] [US2] Unit test Job Runtime tối thiểu: dừng ở `max_steps`/`max_ai_calls`/`token_budget`/timeout job; acceptance của agent được kiểm tra trước `SUCCEEDED` trong `backend/tests/unit/jobs/test_runtime_limits.py` (FR-021, FR-024)
- [ ] T057 [US2] Integration test job chẩn đoán với MockAIProvider qua API: `POST /jobs` → `SUCCEEDED`, 3 bước, `data_origin=MOCK` trên job/steps/usage/tool, usage `provider=mock`, sổ chi tiêu REAL = 0; xác nhận 0 lời gọi mạng tới provider thật; mỗi kịch bản lỗi ở quickstart §4 cho đúng trạng thái/mã lỗi trong `backend/tests/integration/test_diagnostic_job_mock.py` (FR-018, FR-026, SC-003b, QA-01, QA-02, QA-15)

### Implementation cho User Story 2

- [ ] T058 [US2] Migration `0005_ai_jobs`: bảng `ai_models`, `model_pricing`, `model_task_profiles`, `agent_jobs`, `job_steps`, `tool_executions`, `ai_usage_logs` theo data-model.md ai_models.provider, ai_models.model_id, ai_models.verified, ai_models.verification_source, ai_models.status, model_pricing.provider, model_pricing.version, model_pricing.effective_from, model_pricing.input_per_mtok, model_pricing.output_per_mtok, model_pricing.cache_read_per_mtok, model_pricing.cache_write_per_mtok, model_pricing.long_context_threshold_tokens, model_pricing.verified, model_pricing.source_note, model_task_profiles.task_type, model_task_profiles.provider, model_task_profiles.model, model_task_profiles.effort, model_task_profiles.max_output_tokens, model_task_profiles.timeout_s, model_task_profiles.schema_retry_max, model_task_profiles.fallback_provider, model_task_profiles.fallback_on, agent_jobs.job_type, agent_jobs.params, agent_jobs.idempotency_key, agent_jobs.status, agent_jobs.trigger, agent_jobs.data_origin, agent_jobs.budget_limit_usd, agent_jobs.last_completed_seq, agent_jobs.max_attempts, job_steps.seq, job_steps.step_type, job_steps.status, tool_executions.status, tool_executions.denial_reason, ai_usage_logs.outcome, ai_usage_logs.billing_status, ai_usage_logs.data_origin trong `backend/alembic/versions/0005_ai_jobs.py` (FR-030, FR-031, FR-040, FR-041, FR-019c)
- [ ] T059 [US2] Seed catalog + profile + giá: model R-04 với `ai_models.verified=false`, giá tham khảo với `model_pricing.verified=false` và `source_note` ghi nguồn tài liệu; model/giá `mock` riêng `verified=true`; 4 profile R-04 trong `backend/alembic/versions/0006_seed_ai.py` (FR-012, FR-019c, R-04)
- [ ] T060 [P] [US2] Model SQLAlchemy cho các bảng ở T058 trong `backend/src/nichepilot/ai/models.py` và `backend/src/nichepilot/jobs/models.py`
- [ ] T061 [P] [US2] Kiểu và interface `LLMProvider`, `LLMRequest`, `LLMResponse`, `TokenUsage`, exception chuẩn hóa trong `backend/src/nichepilot/ai/providers/base.py` (contracts/internal-interfaces.md §1)
- [ ] T062 [P] [US2] `MockAIProvider` (kịch bản, seed, sinh output từ JSON Schema, usage giả lập, `data_origin=MOCK`) trong `backend/src/nichepilot/ai/providers/mock.py` (FR-018)
- [ ] T063 [P] [US2] `AnthropicAPIProvider` (SDK anthropic 2.x – đối chiếu tài liệu SDK chính thức, `api_key` tường minh, `max_retries=0`, structured output, tools `strict`, `tool_choice=auto`, effort, prompt caching, count_tokens, `models.list` cho kiểm tra kết nối) trong `backend/src/nichepilot/ai/providers/anthropic_api.py` (FR-010, FR-019b, R-03)
- [ ] T064 [P] [US2] `OpenAIAPIProvider` cùng interface trong `backend/src/nichepilot/ai/providers/openai_api.py` (FR-011, R-05)
- [ ] T065 [P] [US2] Pricing service (bảng giá hiệu lực theo version/effective_from, phân tầng, cache) trong `backend/src/nichepilot/ai/pricing.py` (FR-040, FR-041)
- [ ] T066 [P] [US2] Catalog service: kiểm tra `ai_models.verified` + khả năng + `model_pricing.verified` trước lời gọi có phí; từ chối alias `latest` trong `backend/src/nichepilot/ai/catalog.py` (FR-019c)
- [ ] T067 [P] [US2] `sanitize_for_llm` + bọc `untrusted_content` trong `backend/src/nichepilot/ai/sanitize.py` (FR-015, FR-016)
- [ ] T068 [US2] `AIGateway.call` theo thứ tự bất biến (chọn provider + override + rào chắn runtime mock, catalog, công tắc phí, gọi BudgetService – interface, `mark_sent`, timeout, ghi usage + `billing_status`, validate schema, phân loại lỗi, fallback có cấu hình) trong `backend/src/nichepilot/ai/gateway.py` (FR-012…FR-019c, FR-040)
- [ ] T069 [P] [US2] Tool Registry + tool `system.runtime_info` trong `backend/src/nichepilot/tools/registry.py` và `backend/src/nichepilot/tools/builtin/system_runtime_info.py` (FR-020, FR-022, FR-023)
- [ ] T070 [US2] `AgentDefinition`, `Agent` protocol, `JobContext` và Job Runtime tối thiểu (vòng lặp bước, giới hạn, ghi `job_steps`, kết quả validate) trong `backend/src/nichepilot/jobs/runtime.py` (FR-021, FR-024, FR-025, FR-031)
- [ ] T071 [US2] Agent `system.diagnostic` (AI → tool → AI có structured output, acceptance) trong `backend/src/nichepilot/jobs/agents/diagnostic.py` (FR-026)
- [ ] T072 [US2] `JobQueue` interface + `ProcrastinateJobQueue` (`queueing_lock`/`lock` theo job_id) + entrypoint worker trong `backend/src/nichepilot/jobs/queue.py` và `backend/src/nichepilot/worker.py` (R-01, FR-037)
- [ ] T073 [US2] Router `jobs` (POST tạo job + idempotency, GET danh sách/chi tiết/steps, `GET /job-types`) và `tools` (GET) trong `backend/src/nichepilot/api/v1/jobs.py`, `backend/src/nichepilot/api/v1/tools.py` (FR-032)
- [ ] T074 [US2] Router `costs/usage` (lọc `data_origin`, mặc định REAL) trong `backend/src/nichepilot/api/v1/costs.py` (FR-040, FR-044, FR-018g)

**Checkpoint**: Quickstart §3–§4 đạt với mock; adapter thật chỉ được kiểm thử bằng respx (ghi rõ "chưa kiểm thử với API thật").

---

## Phase 5: User Story 3 – Giới hạn ngân sách AI (Priority: P1)

**Goal**: Reservation nguyên tử đa worker, đối soát, UNCERTAIN, quét reservation treo, `PAUSED_BUDGET`, API ngân sách.

**Independent Test**: Quickstart §5 (mock, sổ MOCK) + integration test đồng thời.

### Tests cho User Story 3 ⚠️

- [ ] T075 [P] [US3] Unit test công thức chi tiêu `spent`/`held`/`remaining` cho ngày/tháng/job theo múi giờ cấu hình, sổ REAL/MOCK tách biệt trong `backend/tests/unit/ai/test_budget_ledger.py` (FR-042, FR-043, FR-018)
- [ ] T076 [US3] Integration test đồng thời: 2 tiến trình × 10 coroutine reserve tranh chấp trên PostgreSQL thật với ngân sách sát → tổng `spent + held` ≤ mọi giới hạn, số reservation bị từ chối đúng kỳ vọng trong `backend/tests/integration/test_budget_concurrency.py` (FR-043, SC-004)
- [ ] T077 [P] [US3] Integration test vòng đời reservation: thành công → SETTLED theo usage thực (ghi chênh lệch, cảnh báo overrun); lỗi trước gửi → RELEASED(NOT_SENT); `timeout_after_send` → UNCERTAIN không tự giải phóng; phản hồi lỗi khi `billing.error_responses_not_billed_verified=false` → UNCERTAIN; `=true` → RELEASED trong `backend/tests/integration/test_budget_reservation_lifecycle.py` (FR-047, SC-004b)
- [ ] T078 [P] [US3] Integration test `sweep_stale`: ACTIVE quá hạn với `sent_at` NULL → RELEASED; có `sent_at` → UNCERTAIN(WORKER_LOST); không bao giờ chuyển UNCERTAIN → RELEASED trong `backend/tests/integration/test_budget_sweep.py` (FR-048)
- [ ] T079 [P] [US3] Integration test `PAUSED_BUDGET`: vượt job/ngày/tháng → không có usage cho lời gọi bị chặn, `status_reason_detail` đủ số liệu; resume khi chưa đủ → 402 `BUDGET_STILL_INSUFFICIENT`; tăng ngân sách → tiếp tục từ checkpoint, không lặp bước; không tự resume trong `backend/tests/integration/test_paused_budget.py` (FR-045, US3 kịch bản 2–4)
- [ ] T080 [P] [US3] Contract test `GET/PUT /budget` (ràng buộc per_job ≤ daily ≤ monthly, cảnh báo 80% và `UNCERTAIN_RESERVATIONS`), `GET /budget/reservations`, `POST /budget/reservations/{id}/resolve` (409 nếu không UNCERTAIN, audit) trong `backend/tests/contract/test_budget_api.py` (FR-042, FR-044, FR-047)

### Implementation cho User Story 3

- [ ] T081 [US3] Migration `0007_budget`: bảng `budget_reservations` theo data-model.md budget_reservations.amount_usd, budget_reservations.status, budget_reservations.sent_at, budget_reservations.expires_at, budget_reservations.release_reason, budget_reservations.uncertain_reason + chỉ mục trong `backend/alembic/versions/0007_budget.py` (FR-043, FR-047)
- [ ] T082 [US3] `BudgetService` (reserve nguyên tử với `pg_advisory_xact_lock` theo `data_origin`, mark_sent commit riêng, settle, release, mark_uncertain, resolve có audit, status, can_resume) trong `backend/src/nichepilot/ai/budget.py` (FR-042, FR-043, FR-047)
- [ ] T083 [US3] Tác vụ định kỳ `sweep_stale` mỗi phút (Procrastinate periodic) trong `backend/src/nichepilot/jobs/maintenance.py` (FR-048)
- [ ] T084 [US3] Nối `BudgetExceeded` → job `PAUSED_BUDGET` + resume có kiểm tra `can_resume` trong `backend/src/nichepilot/jobs/runtime.py` (FR-045)
- [ ] T085 [US3] Router `budget` (GET/PUT, reservations, resolve) + `costs/summary` (mặc định REAL, MOCK tách riêng) trong `backend/src/nichepilot/api/v1/costs.py` (FR-042, FR-044, FR-047, FR-018g)

**Checkpoint**: Quickstart §5 đạt; SC-004, SC-004b đạt.

---

## Phase 6: User Story 4 – Quản lý vòng đời Agent Job (Priority: P2)

**Goal**: State machine đầy đủ, pause/resume/cancel/retry, checkpoint, phát hiện worker chết, idempotency, concurrency.

**Independent Test**: Quickstart §6.

### Tests cho User Story 4 ⚠️

- [ ] T086 [P] [US4] Unit test `JobStateMachine`: mọi chuyển hợp lệ theo data-model.md §7 và chuyển không hợp lệ → `INVALID_JOB_TRANSITION` trong `backend/tests/unit/jobs/test_state_machine.py` (FR-030)
- [ ] T087 [P] [US4] Integration test cancel giữa chừng (không thêm lời gọi AI; kết quả về sau khi hủy bị bỏ qua nhưng chi phí vẫn ghi), pause sau bước hiện tại → resume từ bước kế trong `backend/tests/integration/test_job_cancel_pause.py` (FR-032, QA-09)
- [ ] T088 [P] [US4] Integration test retry thủ công job FAILED tiếp tục từ `agent_jobs.last_completed_seq`; `fail_n_then_success` qua retry tự động; không có `job_steps.seq` trùng trong `backend/tests/integration/test_job_retry_checkpoint.py` (FR-035, FR-036, QA-10)
- [ ] T089 [P] [US4] Integration test worker chết: kill tiến trình worker khi RUNNING → trong ≤ 5 phút job về `RETRY_SCHEDULED` rồi hoàn tất từ checkpoint; reservation đang dở thành UNCERTAIN/RELEASED đúng quy tắc trong `backend/tests/integration/test_worker_crash.py` (FR-036, FR-048, SC-006)
- [ ] T090 [P] [US4] Integration test idempotency (`agent_jobs.idempotency_key` trùng → trả job cũ) và concurrency (`worker.max_concurrent_jobs`=1 không chạy 2 job cùng lúc; một job không bị 2 worker thực thi) trong `backend/tests/integration/test_job_idempotency.py` (FR-037, FR-038)
- [ ] T091 [P] [US4] Contract test `POST /jobs/{id}/pause|resume|cancel|retry` và 409 trong `backend/tests/contract/test_job_actions.py` (FR-032)

### Implementation cho User Story 4

- [ ] T092 [US4] `JobStateMachine` trong `backend/src/nichepilot/jobs/state_machine.py` (FR-030)
- [ ] T093 [US4] Mở rộng Job Runtime: checkpoint sau mỗi bước, kiểm tra pause/cancel giữa bước và trước lời gọi ngoài, heartbeat `agent_jobs.heartbeat_at`, retry tự động theo `agent_jobs.max_attempts` với backoff + jitter trong `backend/src/nichepilot/jobs/runtime.py` (FR-035, FR-036)
- [ ] T094 [US4] Phát hiện lượt thực thi stalled (Procrastinate heartbeat) → `RETRY_SCHEDULED` + enqueue lại trong `backend/src/nichepilot/jobs/maintenance.py` (FR-036, SC-006)
- [ ] T095 [US4] Giới hạn concurrency (`WORKER_CONCURRENCY`, `worker.max_concurrent_jobs`) trong `backend/src/nichepilot/worker.py` (FR-038)
- [ ] T096 [US4] Endpoint pause/resume/cancel/retry có audit trong `backend/src/nichepilot/api/v1/jobs.py` (FR-032, FR-051)

**Checkpoint**: Quickstart §6 đạt.

---

## Phase 7: User Story 5 – Chạy job theo lịch (Priority: P2)

**Goal**: Lịch cron lưu DB, đúng một job mỗi thời điểm, chính sách chạy bù, chặn khi chưa có ngân sách.

**Independent Test**: Quickstart §7.

### Tests cho User Story 5 ⚠️

- [ ] T097 [P] [US5] Unit test tính thời điểm đến hạn bằng croniter theo `job_schedules.timezone`, `job_schedules.misfire_policy` SKIP/RUN_ONCE, khoảng cách tối thiểu 5 phút của `job_schedules.cron_expr` trong `backend/tests/unit/jobs/test_schedule_calc.py` (FR-033)
- [ ] T098 [P] [US5] Integration test scheduler tick: 2 worker cùng tick → đúng 1 job/thời điểm (unique `agent_jobs.idempotency_key`); lịch tắt → không job; khởi động lại sau thời điểm lỡ → chạy bù tối đa 1 lần trong `backend/tests/integration/test_scheduler_tick.py` (FR-033, FR-037, SC-007)
- [ ] T099 [P] [US5] Contract test CRUD `/schedules`; bật lịch job tốn phí khi ngân sách ngày/tháng = 0 → 422 `BUDGET_NOT_CONFIGURED` trong `backend/tests/contract/test_schedules_api.py` (FR-033, FR-034)

### Implementation cho User Story 5

- [ ] T100 [US5] Migration `0008_schedules`: bảng `job_schedules` theo data-model.md job_schedules.name, job_schedules.cron_expr, job_schedules.timezone, job_schedules.enabled, job_schedules.misfire_policy trong `backend/alembic/versions/0008_schedules.py` (FR-033)
- [ ] T101 [US5] Scheduler tick (periodic mỗi phút, tạo job với `idempotency_key = schedule:{id}:{scheduled_for}`) trong `backend/src/nichepilot/jobs/scheduler.py` (FR-033, FR-034)
- [ ] T102 [US5] Router `schedules` có audit trong `backend/src/nichepilot/api/v1/schedules.py` (FR-033, FR-051)

**Checkpoint**: Quickstart §7 đạt.

---

## Phase 8: User Story 6 – Cấu hình an toàn và audit (Priority: P3)

**Goal**: API cấu hình không bí mật, project, model profiles, catalog/xác minh model, bảng giá, provider status, test-connection, verify-models, audit log.

**Independent Test**: Quickstart §8 (phần cấu hình/audit) + quét secret.

### Tests cho User Story 6 ⚠️

- [ ] T103 [P] [US6] Contract test `GET/PATCH /settings` (optimistic locking `settings.version`, từ chối khóa bí mật theo `settings.key`, validate ràng buộc chéo, audit before/after), `GET/PATCH /projects/default` theo data-model.md projects.target_market, projects.content_language trong `backend/tests/contract/test_settings_api.py` (FR-055, FR-051)
- [ ] T104 [P] [US6] Contract test `/model-profiles` (provider `mock` bị từ chối khi production), `/models` + `/models/{id}/verification` (bắt buộc `verification_source`), `/model-pricing` (chỉ thêm version, `verified=true` bắt buộc `source_note`) trong `backend/tests/contract/test_model_config_api.py` (FR-012, FR-019c, FR-041, FR-018f)
- [ ] T105 [P] [US6] Contract test `/providers` (không trả giá trị key, chỉ `key_hint`), `test-connection` (OK/INVALID_KEY/NETWORK_ERROR/NOT_CONFIGURED/MOCK, audit, dùng respx), `verify-models` (respx Models API) trong `backend/tests/contract/test_providers_api.py` (FR-054, FR-056)
- [ ] T106 [P] [US6] Security test: quét response của toàn bộ endpoint và log sau bộ test để đảm bảo không xuất hiện giá trị secret đã nạp trong `backend/tests/integration/test_no_secret_leak.py` (FR-054, SC-008)

### Implementation cho User Story 6

- [ ] T107 [US6] Service + router `settings`, `projects/default` (registry schema theo khóa, ràng buộc chéo ngân sách, áp dụng nóng các khóa auth/budget) trong `backend/src/nichepilot/modules/settings/service.py` và `backend/src/nichepilot/api/v1/settings.py` (FR-055)
- [ ] T108 [US6] Router `model-profiles`, `models`, `models/{id}/verification`, `model-pricing` (audit mọi thay đổi model/giá) trong `backend/src/nichepilot/api/v1/settings.py` (FR-012, FR-019c, FR-041)
- [ ] T109 [US6] Router `providers` (status, test-connection, verify-models dùng Models API không tính phí) trong `backend/src/nichepilot/api/v1/providers.py` (FR-056, FR-019c)
- [ ] T110 [US6] Router `audit-logs` (chỉ đọc, lọc, phân trang) trong `backend/src/nichepilot/api/v1/audit.py` (FR-051)

**Checkpoint**: Quickstart §8 (cấu hình/audit) đạt.

---

## Phase 9: User Story 7 – Quan sát, log và backup (Priority: P3)

**Goal**: Log theo job, backup theo lịch, khôi phục có kiểm thử.

**Independent Test**: Quickstart §8 (backup/restore, log).

### Tests cho User Story 7 ⚠️

- [ ] T111 [P] [US7] Integration test lọc log theo `job_id` cho đủ sự kiện theo thứ tự, không secret trong `backend/tests/integration/test_job_logs.py` (FR-050)
- [ ] T112 [P] [US7] Integration test backup → restore vào DB trống → số bản ghi mọi bảng khớp; xoay vòng giữ `BACKUP_RETENTION` bản trong `backend/tests/integration/test_backup_restore.py` (FR-073, SC-012)

### Implementation cho User Story 7

- [ ] T113 [US7] Script `deploy/scripts/backup.sh` (`pg_dump -Fc`, xoay vòng theo `BACKUP_RETENTION`) và `deploy/scripts/restore.sh`; service `backup` (profile `ops`, `BACKUP_CRON`) trong `deploy/docker-compose.yml` (FR-073)
- [ ] T114 [US7] Cấu hình xoay vòng log Docker (kích thước/số file) cho api/worker trong `deploy/docker-compose.yml` (FR-050, R-09)

**Checkpoint**: Quickstart §8 (backup/log) đạt.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [ ] T115 [P] Kho bằng chứng dùng chung: test ràng buộc CHECK (VERIFIED ⇒ có nguồn; UNKNOWN ⇒ value NULL; unique nguồn) trong `backend/tests/integration/test_evidence_constraints.py`, migration `0009_evidence` theo data-model.md research_sources.source_type, research_sources.canonical_url, research_sources.content_hash, research_evidence.source_id, research_evidence.value, research_evidence.excerpt, research_evidence.verification_status trong `backend/alembic/versions/0009_evidence.py`, và `EvidenceService` (mặc định loại `MOCK`) trong `backend/src/nichepilot/modules/evidence/service.py` (FR-007, FR-018g)
- [ ] T116 [P] Tài liệu vận hành tiếng Việt: `docs/operations/README.md` (cài đặt, cấu hình, khởi động, nâng cấp), `docs/operations/windows-setup.md` (Docker Desktop + WSL2, mã nguồn trong WSL, `.wslconfig`), `docs/operations/troubleshooting.md` (CRLF, cổng, RAM WSL, đồng hồ lệch), `docs/operations/backup-restore.md`, `docs/operations/enable-real-api.md` (quy trình chuyển mock → API thật, xác minh model/giá/chính sách phí, cần chủ sở hữu cho phép) (FR-071, AC-20)
- [ ] T117 [P] Bộ test live tách riêng (chỉ chạy thủ công, từ chối chạy nếu thiếu key + `AI_PAID_CALLS_ENABLED=true` + `NICHEPILOT_LIVE_MAX_USD`; ghi kết quả vào mục "Tích hợp provider thật") trong `backend/tests/live/test_live_providers.py` và target `make test-live` (SC-003, FR-018h) – **không chạy trong E0 khi chưa được cho phép**
- [ ] T118 Script sinh báo cáo truy vết yêu cầu → test (quét mã `TC-<REQ-ID>-nn`, báo FR Must chưa có test, tách kết quả mock và live) trong `backend/scripts/traceability_report.py`, chạy trong CI (SC-011)
- [ ] T119 [P] Smoke test Compose trong CI: `make up` → healthy ≤ 5 phút, đo RAM nghỉ ≤ 3 GB (`docker stats`) ghi vào artifact CI trong `.github/workflows/ci.yml` (SC-001, SC-002)
- [ ] T120 Nghiên cứu (không gọi API có phí) và ghi vào `docs/operations/enable-real-api.md`: chính sách tính phí khi phản hồi lỗi của Anthropic/OpenAI theo tài liệu chính thức, đề xuất giá trị `billing.error_responses_not_billed_verified`; giá chính thức hiện hành của các model R-04 – để chủ sở hữu xác nhận trước khi bật gọi có phí (FR-019c, FR-047)
- [ ] T121 Chạy toàn bộ quickstart §1–§8 và §10, ghi kết quả thực tế (đạt/không đạt) vào `specs/001-foundation-ai-infrastructure/checklists/verification.md`; §9 (API thật) ghi "chưa kiểm chứng" nếu chưa được cho phép (SC-003, Constitution I)
- [ ] T122 Checklist kiểm thử thủ công trên Windows 10/11 cho chủ sở hữu thực hiện (AC-01) trong `specs/001-foundation-ai-infrastructure/checklists/windows-manual.md`
- [ ] T123 Cập nhật `README.md` và `CLAUDE.md` (trạng thái E0, lệnh chạy, cảnh báo API có phí)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 Setup**: không phụ thuộc.
- **Phase 2 Foundational**: phụ thuộc Phase 1; CHẶN mọi user story.
- **US1 (Phase 3)**: sau Phase 2; độc lập với US2–US7.
- **US2 (Phase 4)**: sau Phase 2. Gateway gọi `BudgetService` qua interface; trong US2 lời gọi có phí luôn bị chặn bởi
  `AI_PAID_CALLS_ENABLED=false`, sổ MOCK dùng bản `BudgetService` hoàn chỉnh ở US3 → **US2 và US3 phải hoàn tất cùng nhau
  trước khi coi gateway là xong** (T068 phụ thuộc T082 cho phần reservation; có thể phát triển song song theo interface).
- **US3 (Phase 5)**: sau T058/T061 (bảng + interface của US2).
- **US4 (Phase 6)**: sau US2 + US3 (runtime, reservation khi worker chết).
- **US5 (Phase 7)**: sau US4 (dùng tạo job + idempotency).
- **US6 (Phase 8)**: sau Phase 2; endpoint model/pricing cần bảng của T058.
- **US7 (Phase 9)**: sau Phase 2 (backup); T111 cần job chạy được (US2).
- **Polish (Phase 10)**: sau các story liên quan; T120 có thể làm bất cứ lúc nào (chỉ đọc tài liệu).

### Within Each User Story

- Test viết trước và FAIL → migration/model → service → endpoint → frontend (nếu có) → checkpoint.
- Task [P] trong cùng phase có thể song song; task cùng file (ví dụ `runtime.py`, `costs.py`, `settings.py`, `jobs.py`,
  `docker-compose.yml`) phải tuần tự.

### Parallel Opportunities

- Phase 1: T003–T006, T009–T011 song song sau T001–T002.
- Phase 2: test T012–T017 song song; T019–T023, T026, T027, T029 song song.
- US1: test T030–T035 song song; T042, T043 song song với backend T037–T041.
- US2: test T047–T056 song song; T061–T067, T069 song song.
- US6 có thể làm song song với US4/US5 sau khi có T058.

---

## Parallel Example: User Story 2

```bash
# Viết test trước, song song:
Task: "T047 Unit test MockAIProvider trong backend/tests/unit/ai/test_mock_provider.py"
Task: "T049 Contract test adapter Anthropic bằng respx trong backend/tests/contract/test_anthropic_adapter.py"
Task: "T052 Unit test xác minh model/giá trong backend/tests/unit/ai/test_catalog.py"
Task: "T055 Unit test Tool Registry trong backend/tests/unit/tools/test_registry.py"

# Rồi triển khai song song các thành phần độc lập:
Task: "T062 MockAIProvider trong backend/src/nichepilot/ai/providers/mock.py"
Task: "T063 AnthropicAPIProvider trong backend/src/nichepilot/ai/providers/anthropic_api.py"
Task: "T065 Pricing service trong backend/src/nichepilot/ai/pricing.py"
Task: "T069 Tool Registry trong backend/src/nichepilot/tools/registry.py"
```

---

## Implementation Strategy

### MVP trong E0

1. Phase 1 + Phase 2 → nền tảng khởi động được.
2. US1 → khởi động + đăng nhập + VI/EN (demo được ngay, không cần API key).
3. US2 + US3 → job chẩn đoán với MockAIProvider có ngân sách đầy đủ (lõi AI an toàn chi phí).
4. **Dừng và kiểm chứng**: quickstart §1–§5.

### Incremental Delivery

US4 (vòng đời job) → US5 (lịch) → US6 (cấu hình/audit đầy đủ) → US7 (backup/log) → Polish. Mỗi bước chạy lại toàn bộ test và
quickstart tương ứng; không chuyển sang E1 khi E0 chưa qua T121.

### Ranh giới chi phí

Không task nào trong danh sách này gọi API có phí. T117 (live) chỉ chạy khi chủ sở hữu cho phép rõ ràng; trước đó SC-003 được
báo cáo là "chưa kiểm chứng".

---

## Notes

- [P] = khác file, không phụ thuộc; [USx] = truy vết user story.
- Commit sau mỗi task hoặc nhóm task logic; mỗi commit giữ test xanh.
- Không thêm chức năng ngoài spec; phát hiện thiếu sót → cập nhật spec/plan trước khi code.
- Tổng số task: 123.
