---

description: "Danh sách công việc triển khai E0 — Foundation & AI Infrastructure"
---

# Tasks: E0 — Foundation & AI Infrastructure

**Input**: Tài liệu thiết kế trong `/specs/001-foundation-ai-infrastructure/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (openapi.yaml, internal-interfaces.md,
configuration.md), quickstart.md

**Tests**: BẮT BUỘC (Constitution IX). Trong mỗi phase, task test viết trước và phải FAIL trước khi triển khai. Test tự động
KHÔNG gọi API có phí, KHÔNG gọi mạng tới provider thật; test dùng `MockAIProvider`/`FakeLLMProvider` không được tính là đã
kiểm thử provider thật (FR-018(h)).

**Organization**: Nhóm theo user story của spec.md. Lõi dùng chung (dữ liệu AI/Job, sổ ngân sách, interface provider) nằm ở
Phase 2 để các story phụ thuộc một chiều, không có phụ thuộc vòng (xem "Dependencies").

**Truy vết**: mỗi task ghi FR/SC/QA liên quan trong ngoặc; test case đặt mã `TC-<REQ-ID>-<nn>` trong docstring/tên test; T127
sinh báo cáo truy vết tự động. Field có ràng buộc được trích dẫn dạng `data-model.md Entity.field`.


> **Quy ước mã yêu cầu**: FR-018 có các mục (a)…(h); tài liệu ghi `FR-018(f)`, `FR-018(g)`, `FR-018(h)`. Trong tên test
> (không dùng được dấu ngoặc) ghi `TC_FR018f_nn` = mục (f) của FR-018; script truy vết tính các mã này cho FR-018.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Chạy song song được (khác file, không phụ thuộc task chưa xong)
- **[Story]**: User story (US1…US7)
- Đường dẫn theo cấu trúc web app trong plan.md: `backend/`, `frontend/`, `deploy/`, `docs/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Khởi tạo repo, công cụ, CI – chưa có nghiệp vụ.

- [X] T001 Tạo cấu trúc thư mục theo plan.md (`backend/src/nichepilot/{core,ai,tools,jobs,modules,api}`, `backend/tests/{unit,integration,contract,live,fakes}`, `backend/scripts/`, `frontend/`, `deploy/`, `docs/operations/`) (FR-001)
- [X] T002 Khởi tạo backend bằng uv: `backend/pyproject.toml` (Python 3.13, dependency + phiên bản theo research.md R-02/R-03/R-09/R-12, nhóm dev: pytest, pytest-asyncio, testcontainers, httpx, respx, ruff, mypy, import-linter, detect-secrets) và `backend/uv.lock`
- [X] T003 [P] Khởi tạo frontend Vite + React + TypeScript trong `frontend/` (Tailwind 4, cấu hình shadcn thủ công – `components.json`, `src/lib/utils.ts` – vì host ui.shadcn.com bị chặn bởi network policy, i18next, react-i18next, i18next-browser-languagedetector, TanStack Query, React Router, Zod, Vitest, Playwright) với `frontend/package-lock.json` (R-10)
- [X] T004 [P] Cấu hình lint/format/type check: `backend/pyproject.toml` (ruff, mypy strict cho `core/`, `ai/`, `jobs/`), `frontend/.oxlintrc.json` (oxlint – linter mặc định của template Vite hiện hành, thay ESLint vì typescript-eslint chưa hỗ trợ TypeScript 7), `frontend/tsconfig.json`
- [X] T005 [P] Tạo `.gitattributes` (LF cho `*.sh`, `*.py`, `Makefile`) và cập nhật `.gitignore` cho `backups/`, `logs/`, `deploy/env/.env` (FR-054, FR-071)
- [X] T006 [P] Tạo `deploy/env/.env.example` theo contracts/configuration.md (không secret thật; `AI_PROVIDER_OVERRIDE=mock`, `AI_PAID_CALLS_ENABLED=false`, `APP_ENV=development`, `LOG_RETENTION_DAYS=90`) (FR-019, FR-054, FR-071)
- [X] T007 Tạo `backend/Dockerfile` multi-stage (user không phải root, không GPU) và `frontend/Dockerfile` (build SPA → Caddy) (FR-070, NFR-02)
- [X] T008 Tạo `deploy/docker-compose.yml` (postgres:17-alpine, migrate one-shot, api, worker, web; healthcheck; `mem_limit`/`cpus` theo system-architecture §8; volume `logs`; profile `ops` cho backup) và `deploy/caddy/Caddyfile` (FR-070)
- [X] T009 [P] Tạo `deploy/docker-compose.dev.yml` (mount mã nguồn, `uvicorn --reload`, worker tự khởi động lại bằng watchfiles, Vite HMR) (FR-074)
- [X] T010 [P] Tạo `Makefile` với các target `up`, `down`, `dev`, `migrate`, `test`, `test-e2e`, `test-live`, `lint`, `backup`, `restore` (quickstart.md)
- [X] T011 [P] Tạo `.github/workflows/ci.yml`: lint, type check, import-linter, unit, integration (Docker trên runner), contract, E2E với Compose, detect-secrets; KHÔNG chạy marker `live` (FR-072, SC-008)

**Checkpoint**: `make lint` chạy được trên khung rỗng; CI chạy được.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Hạ tầng lõi dùng chung: cấu hình, log, lỗi, DB + toàn bộ migration lõi, audit, interface provider, sổ ngân sách
nguyên tử. Không story nào bắt đầu trước khi xong phase này.

### Tests cho Phase 2 (viết trước, phải FAIL)

- [X] T012 [P] Unit test cấu hình: thứ tự ưu tiên env/.env/Docker secret, `SecretStr`, fail-fast `MOCK_NOT_ALLOWED` khi `APP_ENV=production` + override mock, `LOG_RETENTION_DAYS` < 90 bị từ chối, bỏ qua `ANTHROPIC_AUTH_TOKEN`/`ANTHROPIC_PROFILE` kèm cảnh báo trong `backend/tests/unit/core/test_config.py` (FR-018(f), FR-019b, FR-054, FR-057)
- [X] T013 [P] Unit test logging: redaction secret đã nạp và mẫu `sk-ant-…`, `sk-…`, `Bearer …` ở cả stdout và file sink; context `request_id/job_id/step_id`; file theo ngày `app-YYYY-MM-DD.jsonl` trong `backend/tests/unit/core/test_logging.py` (FR-050, FR-057, SC-008)
- [X] T014 [P] Unit test problem+json với `code` ổn định, không lộ stack trace trong `backend/tests/unit/core/test_errors.py` (FR-061)
- [X] T015 [P] Integration test migration trên PostgreSQL 17 thật (testcontainers): `upgrade head` tạo đúng 16 bảng nghiệp vụ + 4 bảng Procrastinate, UUID PK + timestamps theo quy ước data-model.md, `downgrade base` sạch, dữ liệu lưu trong PostgreSQL trong `backend/tests/integration/test_migrations.py` (FR-003, FR-004, FR-005, AC-15)
- [X] T016 [P] Integration test seed: đúng một project mặc định (`is_default`), đủ khóa `settings` mặc định của data-model.md §4 với giá trị đúng (budget 3/30/2, auth 12h/5/15, logging 90) trong `backend/tests/integration/test_seed_defaults.py` (FR-006, FR-042, FR-053, FR-055, FR-057)
- [X] T017 [P] Integration test audit append-only: UPDATE/DELETE trên `audit_logs` bị trigger từ chối trong `backend/tests/integration/test_audit_immutable.py` (FR-051)
- [X] T018 [P] Contract test `GET /health` công khai, không lộ chi tiết, đối chiếu `contracts/openapi.yaml` trong `backend/tests/contract/test_health.py` (FR-002)
- [X] T019 [P] Test kiến trúc: chạy import-linter với hợp đồng `backend/.importlinter` (module `modules.*` chỉ giao tiếp qua service interface; `jobs.agents` không import `ai.providers`, chỉ dùng `ai.gateway`, `tools.registry`, `jobs.runtime`) trong `backend/tests/unit/test_architecture.py` (FR-001, FR-025)
- [X] T020 [P] Unit test công thức sổ ngân sách `spent`/`held`/`remaining` cho ngày/tháng/job theo múi giờ cấu hình; sổ REAL/MOCK tách biệt; `UNCERTAIN` tính vào `held` trong `backend/tests/unit/ai/test_budget_ledger.py` (FR-042, FR-043, FR-018)
- [X] T021 [P] Integration test đồng thời: 2 tiến trình × 10 coroutine `reserve()` tranh chấp trên PostgreSQL thật với ngân sách sát → tổng `spent + held` ≤ mọi giới hạn ngày/tháng/job, số lần bị từ chối đúng kỳ vọng trong `backend/tests/integration/test_budget_concurrency.py` (FR-043, SC-004, SC-009, QA-11)
- [X] T022 [P] Integration test vòng đời reservation lõi: `mark_sent` commit trước khi gửi; `settle` theo chi phí thực (ghi chênh lệch, cảnh báo overrun); `release(NOT_SENT)`; `mark_uncertain` trả số UNCERTAIN của job; không có API nào chuyển UNCERTAIN → RELEASED; `reserve()` từ chối khi job đã có ≥ `budget.max_uncertain_per_job` UNCERTAIN (`UncertainLimitReached`) trong `backend/tests/integration/test_budget_reservation_core.py` (FR-047, FR-049, SC-004b)

### Implementation cho Phase 2

- [X] T023 Hạ tầng test: fixture PostgreSQL testcontainers + rollback, client httpx, chặn mạng ra ngoài mặc định (rào chắn socket), marker `mock`/`live` trong `backend/tests/conftest.py` và `[tool.pytest.ini_options]` của `backend/pyproject.toml` (FR-072, SC-003b)
- [X] T024 [P] Cấu hình bằng pydantic-settings (env > .env > secrets file; validator fail-fast production+mock; `LOG_RETENTION_DAYS ≥ 90`; không dò hồ sơ OAuth) trong `backend/src/nichepilot/core/config.py` (FR-018(f), FR-019b, FR-054, FR-057)
- [X] T025 [P] Structured logging structlog JSON + redaction + contextvars, ghi song song stdout và file sink theo ngày trong `LOG_DIR` trong `backend/src/nichepilot/core/logging.py` (FR-050, FR-057)
- [X] T026 [P] Lỗi chuẩn hóa (exception → problem+json, danh mục mã lỗi contracts/internal-interfaces.md §8) trong `backend/src/nichepilot/core/errors.py` (FR-061)
- [X] T027 [P] Database: engine/session async SQLAlchemy + psycopg 3, retry kết nối, ánh xạ mất kết nối → `SERVICE_UNAVAILABLE` trong `backend/src/nichepilot/core/db.py` (FR-003, QA-08)
- [X] T028 [P] Lớp model cơ sở (UUID PK, `created_at`/`updated_at`, mixin `data_origin` CHECK REAL/MOCK) trong `backend/src/nichepilot/core/models_base.py` (FR-005)
- [X] T029 Thiết lập Alembic (`backend/alembic.ini`, `backend/alembic/env.py` async) và migration `0001_core` gồm `projects`, `users`, `auth_sessions`, `settings`, `audit_logs` (+ trigger chặn UPDATE/DELETE) theo data-model.md projects.slug, projects.is_default, projects.target_market, projects.research_language, projects.content_language, users.username, users.password_hash, users.ui_locale, users.failed_login_count, users.locked_until, users.last_login_at, auth_sessions.user_id, auth_sessions.token_hash, auth_sessions.expires_at, auth_sessions.revoked_at, settings.key, settings.value, settings.version, settings.updated_by, audit_logs.actor_type, audit_logs.actor_id trong `backend/alembic/versions/0001_core.py` (FR-004, FR-006, FR-051, FR-052, FR-055)
- [X] T030 Migration `0002_procrastinate`: áp dụng SQL schema Procrastinate 3.11 (đã pin) trong `backend/alembic/versions/0002_procrastinate.py` (R-01)
- [X] T031 [P] Migration `0003_seed_core`: project mặc định + khóa `settings` mặc định (budget.*, auth.*, agent.*, worker.*, schedule.*, ui.*, billing.*, logging.*) theo data-model.md §4 trong `backend/alembic/versions/0003_seed_core.py` (FR-006, FR-042, FR-049, FR-053, FR-057)
- [X] T032 Migration `0004_ai_jobs` gồm `ai_models`, `model_pricing`, `model_task_profiles`, `job_schedules`, `agent_jobs`, `job_steps`, `tool_executions`, `ai_usage_logs` theo data-model.md ai_models.provider, ai_models.model_id, ai_models.verified, ai_models.verification_source, ai_models.verified_by, ai_models.supports_structured_output, ai_models.supports_tools, ai_models.supports_effort, ai_models.max_input_tokens, ai_models.max_output_tokens, ai_models.status, model_pricing.provider, model_pricing.version, model_pricing.effective_from, model_pricing.input_per_mtok, model_pricing.output_per_mtok, model_pricing.cache_read_per_mtok, model_pricing.cache_write_per_mtok, model_pricing.long_context_threshold_tokens, model_pricing.long_input_per_mtok, model_pricing.long_output_per_mtok, model_pricing.verified, model_pricing.source_note, model_task_profiles.task_type, model_task_profiles.provider, model_task_profiles.model, model_task_profiles.effort, model_task_profiles.max_output_tokens, model_task_profiles.timeout_s, model_task_profiles.schema_retry_max, model_task_profiles.fallback_provider, model_task_profiles.fallback_model, model_task_profiles.fallback_on, job_schedules.project_id, job_schedules.name, job_schedules.cron_expr, job_schedules.timezone, job_schedules.enabled, job_schedules.misfire_policy, job_schedules.budget_limit_usd, agent_jobs.project_id, agent_jobs.job_type, agent_jobs.params, agent_jobs.idempotency_key, agent_jobs.status, agent_jobs.trigger, agent_jobs.schedule_id, agent_jobs.data_origin, agent_jobs.budget_limit_usd, agent_jobs.last_completed_seq, agent_jobs.max_attempts, job_steps.job_id, job_steps.seq, job_steps.step_type, job_steps.status, tool_executions.job_id, tool_executions.step_id, tool_executions.status, tool_executions.denial_reason, ai_usage_logs.job_id, ai_usage_logs.step_id, ai_usage_logs.outcome, ai_usage_logs.billing_status, ai_usage_logs.data_origin, ai_usage_logs.pricing_id trong `backend/alembic/versions/0004_ai_jobs.py` (FR-019c, FR-030, FR-031, FR-033, FR-040, FR-041)
- [X] T033 [P] Migration `0005_seed_ai`: model R-04 với `verified=false`, giá tham khảo `verified=false` kèm `source_note`; model/giá `mock` riêng `verified=true`; 4 Model Task Profile R-04 trong `backend/alembic/versions/0005_seed_ai.py` (FR-012, FR-019c, R-04)
- [X] T034 Migration `0006_budget`: bảng `budget_reservations` + chỉ mục theo data-model.md budget_reservations.job_id, budget_reservations.step_id, budget_reservations.amount_usd, budget_reservations.status, budget_reservations.sent_at, budget_reservations.expires_at, budget_reservations.usage_log_id, budget_reservations.release_reason, budget_reservations.uncertain_reason, budget_reservations.resolved_by trong `backend/alembic/versions/0006_budget.py` (FR-043, FR-047, FR-049)
- [X] T035 [P] Model SQLAlchemy cho các bảng ở T029, T032, T034 trong `backend/src/nichepilot/modules/identity/models.py`, `backend/src/nichepilot/modules/settings/models.py`, `backend/src/nichepilot/modules/audit/models.py`, `backend/src/nichepilot/ai/models.py`, `backend/src/nichepilot/jobs/models.py`
- [X] T036 [P] Audit service ghi trong cùng transaction, redaction before/after trong `backend/src/nichepilot/modules/audit/service.py` (FR-051)
- [X] T037 [P] Interface `LLMProvider`, `LLMRequest`, `LLMResponse`, `TokenUsage`, exception chuẩn hóa (kèm thông tin đã gửi/chưa gửi) trong `backend/src/nichepilot/ai/providers/base.py` (contracts/internal-interfaces.md §1, FR-011)
- [X] T038 `BudgetService` lõi: `reserve` nguyên tử với `pg_advisory_xact_lock` theo `data_origin` + kiểm tra giới hạn UNCERTAIN của job, `mark_sent` commit riêng, `settle`, `release`, `mark_uncertain` (trả số lượng), `status` trong `backend/src/nichepilot/ai/budget.py` (FR-042, FR-043, FR-047, FR-049)
- [X] T039 FastAPI app factory: middleware `request_id`, xử lý lỗi problem+json, `/health`, mount `/api/v1`, Swagger `/api/docs` trong `backend/src/nichepilot/main.py` và `backend/src/nichepilot/api/v1/__init__.py` (FR-002)
- [X] T040 [P] Xuất danh mục mã lỗi cho frontend `frontend/src/api/error-codes.json` bằng `backend/scripts/export_error_codes.py` (FR-061, XII)
- [X] T041 [P] Hợp đồng ranh giới module `backend/.importlinter` (FR-001, FR-025)

**Checkpoint**: `make up` khởi động postgres/migrate/api; `/health` = ok; test Phase 2 pass (gồm SC-004 đồng thời).

---

## Phase 3: User Story 1 – Khởi động hệ thống và đăng nhập an toàn (Priority: P1) 🎯 MVP

**Goal**: Khởi động một lệnh, tạo tài khoản lần đầu, đăng nhập/đăng xuất, khóa tạm, trang trạng thái, chuyển VI/EN.

**Independent Test**: Quickstart §1–§2 trên máy sạch, không cần API key.

### Tests cho User Story 1 ⚠️

- [X] T042 [P] [US1] Contract test `GET /auth/setup-status`, `POST /auth/setup` (409 khi đã có user, 422 mật khẩu < 12) trong `backend/tests/contract/test_auth_setup.py` (FR-052)
- [X] T043 [P] [US1] Contract test `POST /auth/login`, `/logout`, `GET/PATCH /auth/me`, 401 khi chưa đăng nhập, CSRF thiếu/sai → `CSRF_INVALID` trong `backend/tests/contract/test_auth_session.py` (FR-052, FR-053)
- [X] T044 [P] [US1] Integration test khóa sau `auth.lockout_threshold` lần sai trong `auth.lockout_minutes`, hết hạn phiên theo `auth.session_idle_timeout_hours`, thu hồi phiên khi logout, audit `auth.*` trong `backend/tests/integration/test_auth_lockout.py` (FR-051, FR-053)
- [X] T045 [P] [US1] Contract test `GET /api/v1/system/status` (database, worker, providers chưa cấu hình ≠ lỗi, `paid_calls_enabled`, `provider_override`) trong `backend/tests/contract/test_system_status.py` (FR-002)
- [X] T046 [P] [US1] Vitest: mọi khóa của `frontend/src/i18n/locales/vi.json` có trong `en.json` và ngược lại; không chuỗi UI hard-code trong `frontend/tests/unit/i18n-keys.test.ts` (FR-060, SC-010)
- [X] T047 [P] [US1] Playwright E2E: khởi tạo tài khoản → trạng thái tiếng Việt → chuyển EN không tải lại → tải lại vẫn EN → đăng xuất → khóa sau 5 lần sai; thông báo lỗi theo ngôn ngữ, không lộ chi tiết kỹ thuật trong `frontend/tests/e2e/us1-auth-i18n.spec.ts` (FR-060, FR-061, US1 kịch bản 1–6)

### Implementation cho User Story 1

- [X] T048 [US1] Dịch vụ xác thực: Argon2id, giới hạn 1 user, khóa tạm theo `auth.lockout_threshold`/`auth.lockout_minutes`, phiên server-side (lưu SHA-256 token), hết hạn theo `auth.session_idle_timeout_hours` trong `backend/src/nichepilot/modules/identity/service.py` (FR-052, FR-053)
- [X] T049 [US1] Dependency xác thực + CSRF double-submit (`np_session`, `np_csrf`, `X-CSRF-Token`): tiện ích trong `backend/src/nichepilot/core/security.py`, dependency theo request trong `backend/src/nichepilot/api/deps.py` (giữ phân tầng: core không import modules) (FR-052)
- [X] T050 [US1] Router `auth` (setup-status, setup, login, logout, me GET/PATCH) có audit trong `backend/src/nichepilot/api/v1/auth.py` (FR-051, FR-052)
- [X] T051 [US1] Router `system/status`: DB, heartbeat worker (`procrastinate_workers`), provider (configured + `key_hint`), `paid_calls_enabled`, `provider_override` trong `backend/src/nichepilot/api/v1/system.py` (FR-002, FR-054)
- [X] T052 [P] [US1] i18n frontend: `frontend/src/i18n/index.ts` (vi mặc định, localStorage, đồng bộ `PATCH /auth/me`), `locales/vi.json`, `locales/en.json`, định dạng ngày/số qua `Intl` (FR-060, E4-06)
- [X] T053 [P] [US1] API client: CSRF header, ánh xạ `code` → thông báo i18n, 401 → trang đăng nhập trong `frontend/src/api/client.ts` (FR-061)
- [X] T054 [US1] Layout + router + `LanguageSwitcher` + `MockBadge` trong `frontend/src/app/` và `frontend/src/components/` (FR-060)
- [X] T055 [US1] Trang `SetupPage`, `LoginPage` (thông báo khóa kèm thời gian còn lại) trong `frontend/src/pages/` (US1 kịch bản 2–4)
- [X] T056 [US1] Trang `StatusPage` (thành phần, chế độ AI MOCK/REAL, "Gọi API có phí: TẮT/BẬT", cảnh báo dung lượng log, loading/error/empty states) trong `frontend/src/pages/StatusPage.tsx` (FR-002, FR-057, UI-05)

**Checkpoint**: Quickstart §1–§2 đạt.

---

## Phase 4: User Story 2 – Gọi AI có kiểm soát, có cấu trúc, ghi nhận chi phí (Priority: P1)

**Goal**: AI Gateway + 3 provider + catalog xác minh + Tool Registry + Job Runtime tối thiểu chạy job chẩn đoán bằng
MockAIProvider; provider thật chỉ kiểm thử ở mức HTTP giả lập. Dùng `BudgetService` lõi từ Phase 2.

**Independent Test**: Quickstart §3–§4 (không cần API key).

### Tests cho User Story 2 ⚠️

- [X] T057 [P] [US2] Unit test MockAIProvider: không I/O mạng, xác định theo seed, tiền tố `[MOCK]`, đủ kịch bản `success`, `timeout`, `timeout_after_send`, `rate_limit`, `schema_invalid`, `provider_error`, `auth_error`, `network_error`, `refusal`, `truncated`, `budget_heavy`, `fail_n_then_success` trong `backend/tests/unit/ai/test_mock_provider.py` (FR-018)
- [X] T058 [P] [US2] Unit test rào chắn mock runtime: gateway, cập nhật profile, tham số `mock_scenario` từ chối khi `APP_ENV=production`; `mock_scenario` bị từ chối với provider thật trong `backend/tests/integration/test_gateway.py` và `backend/tests/contract/test_anthropic_adapter.py` (FR-018(f))
- [X] T059 [P] [US2] Contract test adapter Anthropic bằng transport giả lập `httpx2.MockTransport` (SDK 2.x dùng gói httpx2 nên respx không áp dụng): structured output, tool_use, `stop_reason` refusal/max_tokens, usage có cache tokens, ánh xạ 401/400/429/5xx/timeout/lỗi kết nối (phân biệt trước/sau khi gửi); client với `api_key` tường minh; không gửi `temperature`/prefill trong `backend/tests/contract/test_anthropic_adapter.py` (FR-010, FR-014, FR-017, FR-019b)
- [X] T060 [P] [US2] Contract test adapter OpenAI bằng `httpx2.MockTransport` (ánh xạ lỗi, usage, structured output) trong `backend/tests/contract/test_openai_adapter.py` (FR-011)
- [X] T061 [P] [US2] Unit test AIGateway: thứ tự bất biến 1–11 (internal-interfaces §1); 100% output sai schema bị từ chối, retry tối đa `schema_retry_max`, không lưu; refusal → `REFUSED` không fallback/không retry; fallback chỉ `PROVIDER_UNAVAILABLE` khi cấu hình, không bao giờ sang mock; `PAID_CALLS_DISABLED` chặn trước khi gửi; bảng phân loại `billing_status` (BILLED/NOT_BILLED/UNCERTAIN) gọi đúng hàm BudgetService trong `backend/tests/integration/test_gateway.py` – PostgreSQL thật (FR-013, FR-014, FR-017, FR-019, FR-047, SC-005, AI-07)
- [X] T062 [P] [US2] Unit test catalog: provider có phí với model chưa xác minh → `MODEL_NOT_VERIFIED`; giá chưa xác minh → `PRICING_NOT_VERIFIED`; thiếu khả năng tác vụ cần → chặn; model_id chứa `latest` bị từ chối trong `backend/tests/integration/test_gateway.py` (FR-019c)
- [X] T063 [P] [US2] Unit test pricing: chi phí từ usage × bảng giá có phiên bản, giá phân tầng, cache read/write, lệch ≤ 1% so với tính tay trong `backend/tests/unit/ai/test_pricing.py` (FR-040, FR-041, SC-003)
- [X] T064 [P] [US2] Unit test sanitize: loại secret/mẫu khóa khỏi prompt; kết quả tool bọc `untrusted_content`; chỉ thị trong nội dung tool không đổi quyền tool trong `backend/tests/unit/ai/test_sanitize.py` (FR-015, FR-016)
- [X] T065 [P] [US2] Unit test Tool Registry: tool ngoài `allowed_tools` → `DENIED/NOT_PERMITTED`, `external_effect=true` → `DENIED/EXTERNAL_EFFECT_DISABLED`, validate input/output, timeout, ghi `tool_executions` trong `backend/tests/unit/tools/test_registry.py` (FR-020, FR-022, FR-023)
- [X] T066 [P] [US2] Unit test Job Runtime tối thiểu: dừng ở `max_steps`/`max_ai_calls`/`token_budget`/timeout; ghi `job_steps` từng bước; acceptance được kiểm tra trước `SUCCEEDED`; agent chỉ dùng gateway/registry/runtime dùng chung trong `backend/tests/unit/jobs/test_runtime_limits.py` (FR-021, FR-024, FR-025, FR-031)
- [X] T067 [US2] Integration test job chẩn đoán với MockAIProvider qua API: `POST /jobs` → `SUCCEEDED`, 3 bước, `data_origin=MOCK` trên job/steps/usage/tool, usage `provider=mock`, sổ REAL = 0, 0 lời gọi mạng tới provider thật; từng kịch bản lỗi ở quickstart §4 (timeout, rate_limit, schema_invalid, auth_error, provider_error, refusal, truncated) ra đúng trạng thái/mã lỗi trong `backend/tests/integration/test_diagnostic_job_mock.py` (FR-018, FR-026, FR-031, SC-003b, SC-005, SC-009, QA-01, QA-02, QA-15)
- [X] T068 [P] [US2] Integration test không có internet (QA-14): kịch bản `network_error` (không kết nối được – lỗi trước khi gửi) → retry rồi `FAILED` với `PROVIDER_NETWORK_ERROR`, mỗi reservation `RELEASED(NOT_SENT)`; trong lúc đó `/health`, đăng nhập, `GET /system/status`, `GET /jobs` vẫn trả 200 trong `backend/tests/integration/test_no_internet.py` (FR-014, FR-018, SC-009, QA-14)
- [X] T069 [P] [US2] Integration test database mất kết nối tạm thời (QA-08): dừng container PostgreSQL giữa chừng → API trả 503 `SERVICE_UNAVAILABLE` không lộ chi tiết; job đang chạy không bị đánh dấu `SUCCEEDED`, không ghi dữ liệu nửa chừng; bật lại DB → hệ thống tự phục hồi, job tiếp tục được trong `backend/tests/integration/test_db_outage.py` (FR-003, FR-061, SC-009, QA-08)

### Implementation cho User Story 2

- [X] T070 [P] [US2] `MockAIProvider` (kịch bản kể cả `network_error`, seed, sinh output từ JSON Schema, usage giả lập, `data_origin=MOCK`) trong `backend/src/nichepilot/ai/providers/mock.py` (FR-018)
- [X] T071 [P] [US2] `AnthropicAPIProvider` (SDK anthropic 2.x – đối chiếu tài liệu SDK chính thức, `api_key` tường minh, `max_retries=0`, structured output, tools `strict`, `tool_choice=auto`, effort, prompt caching, count_tokens, `models.list`, phân loại lỗi trước/sau khi gửi) trong `backend/src/nichepilot/ai/providers/anthropic_api.py` (FR-010, FR-019b, R-03)
- [X] T072 [P] [US2] `OpenAIAPIProvider` cùng interface trong `backend/src/nichepilot/ai/providers/openai_api.py` (FR-011, R-05)
- [X] T073 [P] [US2] Pricing service (giá hiệu lực theo version/effective_from, phân tầng, cache) trong `backend/src/nichepilot/ai/pricing.py` (FR-040, FR-041)
- [X] T074 [P] [US2] Catalog service: kiểm tra model + khả năng + giá đã xác minh trước lời gọi có phí; từ chối alias `latest` trong `backend/src/nichepilot/ai/catalog.py` (FR-019c)
- [X] T075 [P] [US2] `sanitize_for_llm` + bọc `untrusted_content` trong `backend/src/nichepilot/ai/sanitize.py` (FR-015, FR-016)
- [X] T076 [US2] `AIGateway.call` theo thứ tự bất biến (provider + override + rào chắn runtime mock, catalog, công tắc phí, `BudgetService.reserve`/`mark_sent`, timeout, usage + `billing_status`, settle/release/mark_uncertain, validate schema, phân loại lỗi, fallback có cấu hình) trong `backend/src/nichepilot/ai/gateway.py` (FR-012…FR-019c, FR-040, FR-047)
- [X] T077 [P] [US2] Tool Registry + tool `system.runtime_info` trong `backend/src/nichepilot/tools/registry.py` và `backend/src/nichepilot/tools/builtin/system_runtime_info.py` (FR-020, FR-022, FR-023)
- [X] T078 [US2] `AgentDefinition`, `Agent`, `JobContext` và Job Runtime tối thiểu (vòng lặp bước, giới hạn, ghi `job_steps`, validate kết quả) trong `backend/src/nichepilot/jobs/runtime.py` (FR-021, FR-024, FR-025, FR-031)
- [X] T079 [US2] Agent `system.diagnostic` (AI → tool → AI structured output, acceptance) trong `backend/src/nichepilot/jobs/agents/diagnostic.py` (FR-026)
- [X] T080 [US2] `JobQueue` + `ProcrastinateJobQueue` (`queueing_lock`/`lock` theo job_id) + entrypoint worker trong `backend/src/nichepilot/jobs/queue.py` và `backend/src/nichepilot/worker.py` (R-01, FR-037)
- [X] T081 [US2] Router `jobs` (POST + idempotency, GET danh sách/chi tiết/steps, `GET /job-types`) và `tools` (cùng router) trong `backend/src/nichepilot/api/v1/jobs.py` (FR-032)
- [X] T082 [US2] Router `costs/usage` (lọc `data_origin`, mặc định REAL) trong `backend/src/nichepilot/api/v1/costs.py` (FR-040, FR-044, FR-018(g))

**Checkpoint**: Quickstart §3–§4 đạt với mock; adapter thật chỉ kiểm thử bằng transport giả lập `httpx2.MockTransport` (ghi rõ "chưa kiểm thử với API thật").

---

## Phase 5: User Story 3 – Giới hạn ngân sách AI (Priority: P1)

**Goal**: `PAUSED_BUDGET` (vượt ngân sách và giới hạn UNCERTAIN), resume có điều kiện, quét reservation treo, đối soát có
audit, API ngân sách. Dựa trên `BudgetService` lõi (T038) và gateway (T076).

**Independent Test**: Quickstart §5 (mock, sổ MOCK).

### Tests cho User Story 3 ⚠️

> **Ghi nhận tuân thủ (D1, Constitution IX – TDD)**: phần cài đặt US3 (T088–T091) được viết **trước** test T083–T087,
> không đúng quy trình viết test trước. Sai lệch đã được báo cáo cho chủ sở hữu khi kết thúc Phase 5; test US3 được bổ
> sung sau đó và hiện đạt. Không viết lại lịch sử commit, không tạo bằng chứng bổ sung. Từ US4 (Phase 6) trở đi – US4,
> US5, US6, US7, Polish và các bản sửa sau triển khai – đều làm theo TDD: viết test, xác nhận thất bại đúng lý do, rồi
> mới cài đặt.

- [X] T083 [P] [US3] Integration test `PAUSED_BUDGET` do vượt job/ngày/tháng: không có usage cho lời gọi bị chặn, `status_reason_detail` đủ số liệu; resume khi chưa đủ → 402 `BUDGET_STILL_INSUFFICIENT`; tăng ngân sách → tiếp tục từ checkpoint, không lặp bước; không tự resume trong `backend/tests/integration/test_us3_budget.py` (FR-045, SC-009, QA-11, US3 kịch bản 2–4)
- [X] T084 [P] [US3] Integration test giới hạn UNCERTAIN: `timeout_after_send` lặp → reservation UNCERTAIN thứ 3 đưa job về `PAUSED_BUDGET` với `UNCERTAIN_RESERVATION_LIMIT`; không có lời gọi/reservation mới sau đó; resume khi còn UNCERTAIN → 423 `UNCERTAIN_RESERVATIONS_UNRESOLVED`; đối soát hết (mỗi lần có audit) + ngân sách đủ → resume thành công từ checkpoint; đổi `budget.max_uncertain_per_job`=1 có hiệu lực trong `backend/tests/integration/test_us3_budget.py` (FR-047, FR-049, SC-004b)
- [X] T085 [P] [US3] Integration test phân loại phản hồi lỗi: `billing.error_responses_not_billed_verified=false` → UNCERTAIN; `=true` → RELEASED(ERROR_RESPONSE_NOT_BILLED) trong `backend/tests/integration/test_us3_budget.py` (FR-047)
- [X] T086 [P] [US3] Integration test `sweep_stale`: ACTIVE quá hạn với `sent_at` NULL → RELEASED; có `sent_at` → UNCERTAIN(WORKER_LOST); không bao giờ UNCERTAIN → RELEASED tự động trong `backend/tests/integration/test_us3_budget.py` (FR-048)
- [X] T087 [P] [US3] Contract test `GET/PUT /budget` (ràng buộc per_job ≤ daily ≤ monthly, `max_uncertain_per_job` ≥ 1, cảnh báo 80% và `UNCERTAIN_RESERVATIONS`), `GET /budget/reservations`, `POST /budget/reservations/{id}/resolve` (409 nếu không UNCERTAIN, audit), `GET /costs/summary` (mặc định REAL, MOCK tách riêng) trong `backend/tests/integration/test_us3_budget.py` (FR-042, FR-044, FR-047, FR-018(g))

### Implementation cho User Story 3

- [X] T088 [US3] Bổ sung `BudgetService.resolve` (audit), `can_resume` (OK | BUDGET_STILL_INSUFFICIENT | UNCERTAIN_RESERVATIONS_UNRESOLVED), `sweep_stale` trong `backend/src/nichepilot/ai/budget.py` (FR-047, FR-048, FR-049)
- [X] T089 [US3] Tác vụ định kỳ `sweep_stale` mỗi phút (Procrastinate periodic) trong `backend/src/nichepilot/jobs/maintenance.py` (FR-048)
- [X] T090 [US3] Nối `BudgetExceeded`/`UncertainLimitReached` → `PAUSED_BUDGET` (lý do + số liệu), chặn mọi lời gọi có phí khi job tạm dừng, resume qua `can_resume` trong `backend/src/nichepilot/jobs/runtime.py` (FR-045, FR-049)
- [X] T091 [US3] Router `budget` (GET/PUT, reservations, resolve) + `costs/summary` trong `backend/src/nichepilot/api/v1/costs.py`; endpoint `POST /jobs/{id}/resume` tối thiểu (cần cho test US3) trong `backend/src/nichepilot/api/v1/jobs.py` (FR-042, FR-044, FR-047, FR-018(g))

**Checkpoint**: Quickstart §5 đạt; SC-004b đạt.

---

## Phase 6: User Story 4 – Quản lý vòng đời Agent Job (Priority: P2)

**Goal**: State machine đầy đủ, pause/resume/cancel/retry, checkpoint, phát hiện worker chết, idempotency, concurrency.

**Independent Test**: Quickstart §6.

### Tests cho User Story 4 ⚠️

- [X] T092 [P] [US4] Unit test `JobStateMachine`: mọi chuyển hợp lệ theo data-model.md §7, chuyển không hợp lệ → `INVALID_JOB_TRANSITION` trong `backend/tests/unit/jobs/test_state_machine.py` (FR-030)
- [X] T093 [P] [US4] Integration test cancel giữa chừng (không thêm lời gọi AI; kết quả về sau khi hủy bị bỏ qua nhưng chi phí vẫn ghi) và pause → resume từ bước kế trong `backend/tests/integration/test_us4_lifecycle.py` (FR-032, QA-09, SC-009)
- [X] T094 [P] [US4] Integration test retry thủ công job FAILED từ `last_completed_seq`; `fail_n_then_success` qua retry tự động; không có `seq` trùng trong `backend/tests/integration/test_us4_lifecycle.py` (FR-035, FR-036, QA-10, SC-009)
- [X] T095 [P] [US4] Integration test worker chết: kill worker khi RUNNING → ≤ 5 phút job về `RETRY_SCHEDULED` rồi hoàn tất từ checkpoint; reservation dở thành UNCERTAIN/RELEASED đúng quy tắc trong `backend/tests/integration/test_us4_lifecycle.py` (FR-036, FR-048, SC-006)
- [X] T096 [P] [US4] Integration test idempotency (khóa trùng → trả job cũ) và concurrency (`worker.max_concurrent_jobs`=1; một job không bị 2 worker thực thi) trong `backend/tests/integration/test_us4_lifecycle.py` (FR-037, FR-038, QA-10)
- [X] T097 [P] [US4] Contract test `POST /jobs/{id}/pause|resume|cancel|retry` và 409 trong `backend/tests/integration/test_us4_lifecycle.py` (FR-032)

### Implementation cho User Story 4

- [X] T098 [US4] `JobStateMachine` trong `backend/src/nichepilot/jobs/state_machine.py` (FR-030)
- [X] T099 [US4] Mở rộng Job Runtime: checkpoint sau mỗi bước, kiểm tra pause/cancel giữa bước và trước lời gọi ngoài, heartbeat, retry tự động theo `max_attempts` với backoff + jitter trong `backend/src/nichepilot/jobs/runtime.py` (FR-035, FR-036)
- [X] T100 [US4] Phát hiện lượt thực thi stalled → `RETRY_SCHEDULED` + enqueue lại trong `backend/src/nichepilot/jobs/maintenance.py` (FR-036, SC-006)
- [X] T101 [US4] Giới hạn concurrency (`WORKER_CONCURRENCY`, `worker.max_concurrent_jobs`) trong `backend/src/nichepilot/worker.py` (FR-038)
- [X] T102 [US4] Endpoint pause/resume/cancel/retry có audit trong `backend/src/nichepilot/api/v1/jobs.py` (FR-032, FR-051)

**Checkpoint**: Quickstart §6 đạt.

---

## Phase 7: User Story 5 – Chạy job theo lịch (Priority: P2)

**Goal**: Lịch cron lưu DB (bảng đã có từ T032), đúng một job mỗi thời điểm, chạy bù, chặn khi chưa có ngân sách.

**Independent Test**: Quickstart §7.

### Tests cho User Story 5 ⚠️

- [X] T103 [P] [US5] Unit test tính thời điểm đến hạn bằng croniter theo múi giờ lịch, `misfire_policy` SKIP/RUN_ONCE, khoảng cách tối thiểu 5 phút trong `backend/tests/unit/jobs/test_schedule_calc.py` (FR-033)
- [X] T104 [P] [US5] Integration test scheduler tick: 2 worker cùng tick → đúng 1 job/thời điểm; lịch tắt → không job; khởi động lại sau thời điểm lỡ → chạy bù tối đa 1 lần trong `backend/tests/integration/test_scheduler_tick.py` (FR-033, FR-037, SC-007)
- [X] T105 [P] [US5] Contract test CRUD `/schedules`; bật lịch job tốn phí khi ngân sách = 0 → 422 `BUDGET_NOT_CONFIGURED` trong `backend/tests/contract/test_schedules_api.py` (FR-033, FR-034)

### Implementation cho User Story 5

- [X] T106 [US5] Scheduler tick (periodic mỗi phút, `idempotency_key = schedule:{id}:{scheduled_for}`, kiểm tra ngân sách đã cấu hình) trong `backend/src/nichepilot/jobs/scheduler.py` (FR-033, FR-034)
- [X] T107 [US5] Router `schedules` có audit trong `backend/src/nichepilot/api/v1/schedules.py` (FR-033, FR-051)

**Checkpoint**: Quickstart §7 đạt.

---

## Phase 8: User Story 6 – Cấu hình an toàn và audit (Priority: P3)

**Goal**: API cấu hình không bí mật, project, model profiles, catalog/xác minh model, bảng giá, provider status,
test-connection, verify-models, audit log.

**Independent Test**: Quickstart §8 (cấu hình/audit) + quét secret.

### Tests cho User Story 6 ⚠️

- [X] T108 [P] [US6] Contract test `GET/PATCH /settings` (optimistic locking theo version, từ chối khóa bí mật, ràng buộc chéo, `logging.retention_days` < 90 bị từ chối, audit before/after), `GET/PATCH /projects/default` (ngôn ngữ UI/nghiên cứu/nội dung độc lập) trong `backend/tests/contract/test_settings_api.py` (FR-055, FR-051, FR-057)
- [X] T109 [P] [US6] Contract test `/model-profiles` (`mock` bị từ chối khi production), `/models` + `/models/{id}/verification` (bắt buộc `verification_source`), `/model-pricing` (chỉ thêm version; `verified=true` bắt buộc `source_note`) trong `backend/tests/contract/test_model_config_api.py` (FR-012, FR-019c, FR-041, FR-018(f))
- [X] T110 [P] [US6] Contract test `/providers` (không trả giá trị key, chỉ `key_hint`), `test-connection` (OK/INVALID_KEY/NETWORK_ERROR/NOT_CONFIGURED/MOCK, audit, `httpx2.MockTransport`), `verify-models` (Models API giả lập bằng `httpx2.MockTransport`) trong `backend/tests/contract/test_providers_api.py` (FR-054, FR-056)
- [X] T111 [P] [US6] Security test: quét response của toàn bộ endpoint, file log và stdout sau bộ test để đảm bảo không có giá trị secret đã nạp trong `backend/tests/integration/test_no_secret_leak.py` (FR-054, SC-008)

### Implementation cho User Story 6

- [X] T112 [US6] Service + router `settings`, `projects/default` (registry schema theo khóa, ràng buộc chéo, áp dụng nóng khóa auth/budget/logging) trong `backend/src/nichepilot/modules/settings/service.py` và `backend/src/nichepilot/api/v1/settings.py` (FR-055)
- [X] T113 [US6] Router `model-profiles`, `models`, `models/{id}/verification`, `model-pricing` (audit mọi thay đổi model/giá) trong `backend/src/nichepilot/api/v1/models.py` (FR-012, FR-019c, FR-041)
- [X] T114 [US6] Router `providers` (status, test-connection, verify-models dùng Models API không tính phí) trong `backend/src/nichepilot/api/v1/providers.py` (FR-056, FR-019c)
- [X] T115 [US6] Router `audit-logs` (chỉ đọc, lọc, phân trang) trong `backend/src/nichepilot/api/v1/audit.py` (FR-051)

**Checkpoint**: Quickstart §8 (cấu hình/audit) đạt.

---

## Phase 9: User Story 7 – Quan sát, log và backup (Priority: P3)

**Goal**: Log theo job, lưu log ứng dụng ≥ 90 ngày với cảnh báo dung lượng (không xóa sớm), backup theo lịch, khôi phục có
kiểm thử.

**Independent Test**: Quickstart §8 (log, backup/restore).

### Tests cho User Story 7 ⚠️

- [X] T116 [P] [US7] Integration test lọc log theo `job_id` đủ sự kiện theo thứ tự, không secret trong `backend/tests/integration/test_job_logs.py` (FR-050)
- [X] T117 [P] [US7] Integration test retention log: file cũ hơn `logging.retention_days` bị xóa; file 89 ngày giữ nguyên kể cả khi vượt `logging.disk_warn_gb`; vượt ngưỡng → cảnh báo trong log và `system/status.log_storage.warning`; audit log trong DB không bị ảnh hưởng trong `backend/tests/integration/test_log_retention.py` (FR-057)
- [X] T118 [P] [US7] Integration test backup → restore vào DB trống → số bản ghi mọi bảng khớp; xoay vòng giữ `BACKUP_RETENTION` bản trong `backend/tests/integration/test_backup_restore.py` (FR-073, SC-012)

### Implementation cho User Story 7

- [X] T119 [US7] Tác vụ bảo trì log hằng ngày (xóa file quá hạn lưu, đo dung lượng, cảnh báo không xóa) trong `backend/src/nichepilot/jobs/maintenance.py` và trường `log_storage` trong `backend/src/nichepilot/api/v1/system.py` (FR-057)
- [X] T120 [US7] Script `deploy/scripts/backup.sh` (`pg_dump -Fc`, xoay vòng theo `BACKUP_RETENTION`) và `deploy/scripts/restore.sh`; service `backup` (profile `ops`, `BACKUP_CRON`) trong `deploy/docker-compose.yml` (FR-073)
- [X] T121 [US7] Xoay vòng stdout Docker (bản sao xem nhanh; bản lưu chính là file theo ngày) cho api/worker trong `deploy/docker-compose.yml` (FR-050, FR-057, R-09)

**Checkpoint**: Quickstart §8 (log, backup) đạt.

---

## Phase 10: Polish & Cross-Cutting Concerns

- [X] T122 [P] Kho bằng chứng dùng chung: test ràng buộc (VERIFIED ⇒ có nguồn; UNKNOWN ⇒ value NULL; unique nguồn; mặc định loại MOCK) trong `backend/tests/integration/test_evidence_constraints.py`; migration `0007_evidence` theo data-model.md research_sources.project_id, research_sources.source_type, research_sources.canonical_url, research_sources.content_hash, research_evidence.project_id, research_evidence.source_id, research_evidence.value, research_evidence.excerpt, research_evidence.verification_status, research_evidence.collected_by_job_id trong `backend/alembic/versions/0007_evidence.py`; `EvidenceService` trong `backend/src/nichepilot/modules/evidence/service.py` (FR-007, FR-018(g))
- [X] T123 [P] Tài liệu vận hành tiếng Việt: `docs/operations/README.md`, `docs/operations/windows-setup.md` (Docker Desktop + WSL2, mã nguồn trong WSL, `.wslconfig`), `docs/operations/troubleshooting.md` (CRLF, cổng, RAM WSL, đồng hồ lệch, ổ đĩa log đầy), `docs/operations/backup-restore.md`, `docs/operations/enable-real-api.md` (chuyển mock → API thật, xác minh model/giá/chính sách phí, cần chủ sở hữu cho phép) (FR-071, AC-20)
- [X] T124 [P] Test tài liệu/cấu hình: mọi biến trong `deploy/env/.env.example` có trong contracts/configuration.md và ngược lại; các file tài liệu vận hành bắt buộc tồn tại và không rỗng trong `backend/tests/contract/test_config_docs.py` (FR-071)
- [X] T125 [P] Smoke test Compose trong CI: `make up` → healthy ≤ 5 phút, đo RAM nghỉ ≤ 3 GB (`docker stats`) ghi artifact; smoke dev override: sửa một file backend/frontend → api/worker/Vite tự nạp lại trong `.github/workflows/ci.yml` và `deploy/tests/smoke.sh` (FR-070, FR-074, SC-001, SC-002)
- [X] T126 [P] Bộ test live tách riêng (chỉ chạy thủ công, từ chối nếu thiếu key + `AI_PAID_CALLS_ENABLED=true` + `NICHEPILOT_LIVE_MAX_USD`; ghi vào mục "Tích hợp provider thật") trong `backend/tests/live/test_live_providers.py` và target `make test-live` (SC-003, FR-018(h)) – **không chạy khi chưa được cho phép**
- [X] T127 Script báo cáo truy vết (quét `TC-<REQ-ID>-nn`, báo FR/SC chưa có test, tách kết quả mock và live, CI thất bại nếu FR Must thiếu test) trong `backend/scripts/traceability_report.py`, kèm test của script trong `backend/tests/unit/test_traceability_report.py`, chạy trong CI (SC-011)
- [X] T128 Nghiên cứu (không gọi API có phí) và ghi vào `docs/operations/enable-real-api.md`: chính sách tính phí khi phản hồi lỗi của Anthropic/OpenAI theo tài liệu chính thức → đề xuất `billing.error_responses_not_billed_verified`; model ID và giá chính thức hiện hành của các model R-04 – để chủ sở hữu xác nhận trước khi bật gọi có phí (FR-019c, FR-047)
- [X] T129 Chạy quickstart §1–§8 và §10, ghi kết quả thực tế vào `specs/001-foundation-ai-infrastructure/checklists/verification.md`; §9 (API thật) ghi "chưa kiểm chứng" nếu chưa được cho phép (SC-003, Constitution I)
- [X] T130 Checklist kiểm thử thủ công Windows 10/11 (Docker Desktop + WSL2, 4 core, 15 GB): khởi động (SC-001), đo RAM nghỉ bằng `docker stats` và Task Manager/`vmmem` ≤ 3 GB (SC-002), hot-reload (FR-074), khởi động lại máy/WSL, hướng dẫn tài liệu dùng được (FR-071) trong `specs/001-foundation-ai-infrastructure/checklists/windows-manual.md` (AC-01, FR-070)
- [X] T131 Cập nhật `README.md` và `CLAUDE.md` (trạng thái E0, lệnh chạy, cảnh báo API có phí)

---

## Dependencies & Execution Order

### Phase Dependencies (đồ thị có hướng, không vòng)

```text
Phase 1 → Phase 2 → US1 (Phase 3)
                  → US2 (Phase 4) → US3 (Phase 5) → US4 (Phase 6) → US5 (Phase 7)
                  → US6 (Phase 8)
                  → US7 (Phase 9)   [T116 cần job chạy được: sau US2]
US1…US7 → Phase 10                  [T128 làm được bất cứ lúc nào – chỉ đọc tài liệu]
```

- **Phase 2** chứa toàn bộ migration lõi `0001`–`0006`, interface provider và `BudgetService` lõi, nên US2 không phụ thuộc
  US3 (đã loại bỏ phụ thuộc vòng ở phiên bản trước).
- **US3** cần gateway (T076) và runtime (T078) của US2.
- **US4** cần US3 (resume `PAUSED_BUDGET`, reservation khi worker chết).
- **US5** cần US4 (tạo job + idempotency); bảng `job_schedules` đã có từ T032 vì `agent_jobs.schedule_id` tham chiếu nó.
- **US6** chỉ cần Phase 2; **US7** cần Phase 2 (backup, retention) và US2 cho T116.
- Thứ tự migration theo khóa ngoại: `0001_core` → `0002_procrastinate` → `0003_seed_core` → `0004_ai_jobs` → `0005_seed_ai`
  → `0006_budget` → `0007_evidence`.

### Within Each Phase

- Test viết trước và FAIL → migration/model → service → endpoint → frontend → checkpoint.
- Task cùng file phải tuần tự: `runtime.py` (T078 → T090 → T099), `maintenance.py` (T089 → T100 → T119), `costs.py`
  (T082 → T091), `jobs.py` (T081 → T102), `system.py` (T051 → T119), `budget.py` (T038 → T088), `docker-compose.yml`
  (T008 → T120 → T121).

### Parallel Opportunities

- Phase 1: T003–T006, T009–T011 song song sau T001–T002.
- Phase 2: test T012–T020, T022 song song; T024–T028, T031, T033, T035–T037, T040, T041 song song theo file.
- US1: test T042–T047 song song; frontend T052–T053 song song với backend T048–T051.
- US2: test T057–T066, T068, T069 song song; T070–T075, T077 song song.
- US6 làm song song với US2–US5 sau Phase 2.

---

## Parallel Example: User Story 2

```bash
# Viết test trước, song song:
Task: "T057 Unit test MockAIProvider trong backend/tests/unit/ai/test_mock_provider.py"
Task: "T059 Contract test adapter Anthropic bằng httpx2.MockTransport trong backend/tests/contract/test_anthropic_adapter.py"
Task: "T062 Unit test catalog trong backend/tests/unit/ai/test_catalog.py"
Task: "T069 Integration test DB mất kết nối trong backend/tests/integration/test_db_outage.py"

# Rồi triển khai song song các thành phần độc lập:
Task: "T070 MockAIProvider trong backend/src/nichepilot/ai/providers/mock.py"
Task: "T071 AnthropicAPIProvider trong backend/src/nichepilot/ai/providers/anthropic_api.py"
Task: "T073 Pricing service trong backend/src/nichepilot/ai/pricing.py"
Task: "T077 Tool Registry trong backend/src/nichepilot/tools/registry.py"
```

---

## Implementation Strategy

### MVP trong E0

1. Phase 1 + Phase 2 → nền tảng + sổ ngân sách nguyên tử (SC-004 đã kiểm chứng ở đây).
2. US1 → khởi động + đăng nhập + VI/EN (không cần API key).
3. US2 → job chẩn đoán với MockAIProvider.
4. US3 → `PAUSED_BUDGET`, giới hạn UNCERTAIN, đối soát.
5. **Dừng và kiểm chứng**: quickstart §1–§5.

### Incremental Delivery

US4 → US5 → US6 → US7 → Polish. Mỗi bước chạy lại toàn bộ test và quickstart tương ứng; không chuyển sang E1 khi E0 chưa
qua T129.

### Ranh giới chi phí

Không task nào gọi API có phí. T126 (live) chỉ chạy khi chủ sở hữu cho phép; trước đó SC-003 báo cáo "chưa kiểm chứng".
Trước khi bật `AI_PAID_CALLS_ENABLED`, T128 phải hoàn tất và được chủ sở hữu xác nhận.

---

## Notes

- [P] = khác file, không phụ thuộc; [USx] = truy vết user story.
- Commit sau mỗi task hoặc nhóm task logic; mỗi commit giữ test xanh.
- Không thêm chức năng ngoài spec; phát hiện thiếu sót → cập nhật spec/plan trước khi code.
- Tổng số task: 131.
