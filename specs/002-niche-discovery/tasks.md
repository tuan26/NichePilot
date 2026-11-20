---

description: "Danh sách công việc triển khai E1 — Autonomous Niche Discovery"
---

# Tasks: E1 — Autonomous Niche Discovery

**Input**: Tài liệu thiết kế trong `/specs/002-niche-discovery/`

**Prerequisites**: plan.md (APPROVED WITH CONDITIONS 2026-11-20), spec.md, research.md (R-01…R-13), data-model.md, contracts/
(openapi.yaml, internal-interfaces.md, scoring-rubric.md), quickstart.md, source-verification.md

**Trạng thái**: CHƯA ĐƯỢC TRIỂN KHAI – chờ chủ sở hữu duyệt kết quả `/speckit-analyze` trước `/speckit-implement`.

**Tests**: BẮT BUỘC (Constitution IX). Trong mỗi phase, task test viết trước và phải FAIL trước khi triển khai. Test tự động KHÔNG gọi
API có phí, KHÔNG gọi mạng (rào chắn socket E0); nguồn ngoài dùng `MockSourceAdapter`/`MockPageFetcher`, AI dùng `MockAIProvider`.
Test giả lập KHÔNG được báo cáo là đã kiểm thử nguồn thật hay Claude/OpenAI API thật.

**Truy vết**: mã test `TC_E1_<REQ>_<nn>` (ví dụ `TC_E1_FR013f_02`, `TC_E1_SC017_01`) trong tên test/docstring; T006 mở rộng
`traceability_report.py` để tính riêng spec 002. Field có ràng buộc được trích dẫn dạng `data-model.md Entity.field`.

**Ràng buộc chung cho mọi task**: không thêm finding vào `.secrets.baseline`; không credential thật; không đặt `compliance_status =
ALLOWED` hay bật nguồn trong seed/test dữ liệu thật; không hard-code model ID trong `modules/discovery` và `jobs/agents`; không đổi state
machine job, Gateway, giữ chỗ ngân sách của E0.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Chạy song song được (khác file, không phụ thuộc task chưa xong)
- **[Story]**: User story (US1…US7)

## Path Conventions

Backend `backend/src/nichepilot/…`, test `backend/tests/{unit,integration,contract}/discovery/…`, migration
`backend/alembic/versions/…`, frontend `frontend/src/…`, E2E `frontend/tests/e2e/…`, triển khai `deploy/…`.

---

## Phase 1: Setup (hạ tầng dùng chung)

**Purpose**: dependency đã xác minh (X8), service SearXNG (X1), mã lỗi (X5), truy vết (X7), khung thư mục.

- [ ] T001 Thêm dependency đã xác minh vào `backend/pyproject.toml` và `backend/uv.lock`, ghim đúng phiên bản trong research R-12
  (trafilatura 2.3.1, protego 0.7.0, phonenumbers 9.0.43, rapidfuzz 3.14.6, tldextract 5.4.0, spacy 3.8.18); chạy lại kiểm tra
  giấy phép bắc cầu và ghi kết quả vào `docs/operations/discovery.md` §Dependency; không thêm crawl4ai, không thêm playwright vào image
  worker (X8)
- [ ] T002 Cài model `en_core_web_sm-3.8.0` trong `backend/Dockerfile` từ URL GitHub release ghim phiên bản + kiểm tra SHA-256 (không tải
  lúc chạy); đo kích thước image trước/sau và ghi vào `docs/operations/discovery.md` (X8, research R-05)
- [ ] T003 [P] Thêm service `searxng` (image `searxng/searxng:2026.11.18-b867c56a5`, `mem_limit 256m`, mạng nội bộ, không publish cổng,
  `GRANIAN_HOST=0.0.0.0`, `SEARXNG_SECRET` từ `.env`, volume `searxng-config`), volume `erasure-ledger`, profile tùy chọn
  `browser-fetcher` vào `deploy/docker-compose.yml`; thêm biến vào `deploy/env/.env.example` không có giá trị thật (X1, research R-02)
- [ ] T004 [P] Tạo `deploy/searxng/settings.base.yml`: `use_default_settings.engines.keep_only: []`, `search.formats: [html, json]`,
  `server.limiter: false`, `public_instance: false`, `image_proxy: false` (research R-02)
- [ ] T005 [P] Thêm mã lỗi E1 vào `frontend/src/api/error-codes.json` và bản dịch VI/EN: `NO_COMPLIANT_SEARCH_SOURCE`,
  `UNVERIFIED_SOURCE_NOT_ENABLED`, `SOURCE_PROHIBITED`, `SOURCE_WARNING_NOT_ACKNOWLEDGED`, `SOURCE_VERIFICATION_INCOMPLETE`,
  `SOURCE_CONFIG_INVALID`, `SOURCE_EXISTS`, `RUN_BUDGET_EXCEEDS_DAILY_LIMIT`, `WEIGHTS_INVALID`, `DISCOVERY_RUN_NOT_FOUND`,
  `NICHE_NOT_FOUND`, `EVIDENCE_NOT_FOUND`, `EVIDENCE_ALREADY_ERASED`, `ERASURE_LEDGER_NOT_APPLIED` (X5)
- [ ] T006 [P] Mở rộng `backend/scripts/traceability_report.py` nhận nhiều spec: spec 001 dùng `TC_FR…/TC_SC…`, spec 002 dùng
  `TC_E1_FR…/TC_E1_SC…`; `--strict` lỗi khi FR Must của bất kỳ spec nào thiếu test; test hồi quy cho spec 001 vẫn 58/58 trong
  `backend/tests/unit/test_traceability_report.py` (X7)
- [ ] T007 [P] Tạo khung gói `backend/src/nichepilot/modules/discovery/__init__.py`, `backend/src/nichepilot/tools/sources/__init__.py`,
  `backend/src/nichepilot/tools/privacy/__init__.py`, `backend/src/nichepilot/tools/fetchers/__init__.py`, thư mục test
  `backend/tests/{unit,integration,contract}/discovery/` và marker pytest `discovery`, `live_sources` (deselected mặc định) trong
  `backend/pyproject.toml`
- [ ] T008 [P] Thêm `nichepilot.modules.discovery` vào hợp đồng `modules-independent` trong `backend/.importlinter`
- [ ] T009 [P] Tạo bộ trang HTML cố định (diễn đàn, bài đánh giá, bản sao khác tên miền, trang chứa PII mẫu, trang CAPTCHA giả, robots.txt
  mẫu) trong `backend/tests/fixtures/discovery/` – dữ liệu tự soạn, không sao chép trang thật
- [ ] T010 [P] Tạo file i18n `frontend/src/i18n/locales/vi/discovery.json`, `frontend/src/i18n/locales/en/discovery.json` (khung khóa,
  gồm `discovery.opportunity.disclaimer`) và đăng ký namespace trong `frontend/src/i18n/index.ts`

**Checkpoint**: `uv sync` thành công trên Python 3.13; `docker compose config` hợp lệ; `searxng` khởi động trong mạng nội bộ với
`/healthz` OK và không engine nào được bật.

---

## Phase 2: Foundational (bắt buộc trước mọi user story)

**Purpose**: schema, mở rộng E0 (X2, X3), sổ xóa fail-safe (X4), policy nguồn, SourceAdapter, PII engine, fetcher, job/agent khung.

### Tests cho Foundational (viết trước, phải FAIL)

- [ ] T011 [P] Test migration `0009_discovery` up/down/up và ORM khớp migration trong
  `backend/tests/integration/discovery/test_migration_0009.py` (TC_E1_FR029_01)
- [ ] T012 [P] Test ràng buộc DB `data-model.md source_policies.enabled`, `source_policies.compliance_status`,
  `source_policies.warning_acknowledged_at` (CHECK PROHIBITED không bật được; ALLOWED thiếu căn cứ bị từ chối; UNVERIFIED bật thiếu xác
  nhận bị từ chối) trong `backend/tests/integration/discovery/test_source_policy_constraints.py` (TC_E1_FR006c_01…03)
- [ ] T013 [P] Test `EvidenceService.query` mặc định chỉ trả `data-model.md research_evidence.lifecycle_status = ACTIVE`, và CHECK
  `ERASED ⇒ excerpt IS NULL` trong `backend/tests/integration/discovery/test_evidence_lifecycle.py` (TC_E1_FR013e_01)
- [ ] T014 [P] Test sổ xóa: genesis/`ledger_id`, hash chain, fsync, ghi sổ trước DB, idempotent khi áp dụng lại trong
  `backend/tests/unit/discovery/test_erasure_ledger.py` (TC_E1_FR013f_01)
- [ ] T015 [P] Test `apply_erasure_ledger --strict` thất bại an toàn: sổ thiếu khi DB có `ledger_id`; `ledger_id` lệch; hash chain bị sửa;
  `applied_seq` > seq cuối; lỗi giữa chừng → rollback + `data-model.md erasure_ledger_state.status = BLOCKED` + exit ≠ 0 trong
  `backend/tests/integration/discovery/test_ledger_apply_failsafe.py` (TC_E1_FR013f_02…06)
- [ ] T016 [P] Test gate: `BLOCKED` hoặc lệch đuôi sổ → endpoint dữ liệu E1 trả 503 `ERASURE_LEDGER_NOT_APPLIED`,
  `/api/v1/system/status` báo `erasure_ledger` lỗi, `/health` vẫn ok, worker không nhận job E1 trong
  `backend/tests/integration/discovery/test_ledger_gate.py` (TC_E1_FR013f_07, TC_E1_FR013f_08)
- [ ] T017 [P] Test `SourcePolicyService.usable_for_run`: SCHEDULED chỉ ALLOWED+enabled; MANUAL+opt-in thêm UNVERIFIED đã bật có xác nhận;
  PROHIBITED không bao giờ; không có API nội bộ nào tự đổi `compliance_status`/`enabled` (test kiến trúc quét mã) trong
  `backend/tests/unit/discovery/test_source_policy_service.py` (TC_E1_FR006d_01…03, TC_E1_SC017_01)
- [ ] T018 [P] Test `SearxngConfigWriter` sinh `keep_only` đúng engine của nguồn đang bật (rỗng khi không có) trong
  `backend/tests/unit/discovery/test_searxng_config.py` (TC_E1_FR006g_01)
- [ ] T019 [P] Test tool `source.query`: từ chối PROHIBITED và UNVERIFIED khi `run_allows_unverified = false`; snippet được che PII trước
  khi trả; `ACCESS_RESTRICTED`/`RATE_LIMITED` không thử vượt; cấu hình chứa khóa gợi ý thông tin xác thực bị từ chối; `auth_env_var` chỉ là
  tên biến trong `backend/tests/unit/discovery/test_source_query_tool.py` (TC_E1_FR006f_01, TC_E1_FR006g_02, TC_E1_FR012b_01)
- [ ] T020 [P] Test `PiiEngine` trên bộ mẫu SC-016 (email, điện thoại nhiều định dạng/quốc gia, @username, u/…, "Posted by", tên người
  tiếng Anh); ngôn ngữ không hỗ trợ → `NEEDS_REVIEW`; model không nạp được → `NEEDS_REVIEW`; còn mẫu sau khi che → `UNSAFE` trong
  `backend/tests/unit/discovery/test_pii_engine.py` (TC_E1_FR012a_01…04, TC_E1_SC016_01)
- [ ] T021 [P] Test tool `page.fetch`: output và bản ghi `tool_calls` chỉ chứa văn bản đã che (không có mẫu PII thô); bỏ `author`; chỉ
  `text/html`, ≤ 3 MB, timeout 20 s; trang CAPTCHA/đăng nhập → `SKIPPED ACCESS_RESTRICTED` trong
  `backend/tests/integration/discovery/test_page_fetch_tool.py` (TC_E1_FR012b_02, TC_E1_FR005_01, TC_E1_FR031_01)
- [ ] T022 [P] Test `DomainAccessService`: robots (protego, wildcard RFC 9309) chặn → `ROBOTS_DISALLOWED`; khoảng cách
  = max(trần, Crawl-delay, Retry-After); trạng thái bền qua khởi động lại; 4xx robots → cho phép, 5xx/mạng → không thu thập tên miền trong
  `backend/tests/integration/discovery/test_domain_access.py` (TC_E1_FR030a_01…03)
- [ ] T023 [P] Test tldextract không gọi mạng (`suffix_list_urls=()`) dưới rào chắn socket trong
  `backend/tests/unit/discovery/test_registered_domain.py` (TC_E1_FR015_01)
- [ ] T024 [P] Test production từ chối `MockSourceAdapter`/`MockPageFetcher` (như guard mock E0) trong
  `backend/tests/unit/discovery/test_mock_sources_guard.py` (TC_E1_FR016_01)

### Implementation cho Foundational

- [ ] T025 Viết migration `backend/alembic/versions/0009_discovery.py`: thêm cột E0 theo `data-model.md research_sources.registered_domain`,
  `research_sources.simhash`, `research_sources.lifecycle_status`, `research_sources.erased_at`, `research_sources.source_policy_id`,
  `research_sources.source_compliance`, `research_evidence.redaction_status`, `research_evidence.redaction_counts`,
  `research_evidence.lifecycle_status`, `research_evidence.erased_at`, `research_evidence.content_hash` (X2) và tạo mọi bảng ở
  data-model §2 với ràng buộc nêu ở đó (CHECK, UNIQUE, FK)
- [ ] T026 Tạo ORM trong `backend/src/nichepilot/modules/discovery/models.py` khớp migration 0009; cập nhật ORM E0 trong
  `backend/src/nichepilot/modules/evidence/models.py` cho cột mới
- [ ] T027 Sửa `backend/src/nichepilot/modules/evidence/service.py`: `query` mặc định lọc `data-model.md research_evidence.lifecycle_status`
  = ACTIVE (X3), tham số tường minh để xem bản ghi đã xóa chỉ cho mục đích audit
- [ ] T028 Viết migration seed `backend/alembic/versions/0010_discovery_seed.py`: `data-model.md scoring_weights_versions.weights` v1 =
  25/20/20/15/10/10, `scoring_weights_versions.coverage_threshold` 60, `evidence_rules`/`confidence_params`/`dedup_params` mặc định
  (scoring-rubric §1–§5); nguồn S1–S11 (source-verification.md) với `data-model.md source_policies.compliance_status` = UNVERIFIED,
  `source_policies.enabled` = false; Model Task Profile `discovery.candidates|extract|assess|normalize` (model seed theo research R-10,
  `verified = false`); dòng `erasure_ledger_state`
- [ ] T029 Triển khai sổ xóa trong `backend/src/nichepilot/modules/discovery/erasure.py`: `LedgerWriter` (genesis, hash chain, fsync file
  + thư mục), `apply_erasure_ledger(strict)` một transaction, `ledger_health()` cập nhật `data-model.md erasure_ledger_state.applied_seq`,
  `erasure_ledger_state.applied_hash`, `erasure_ledger_state.status` (X4, research R-09)
- [ ] T030 Tạo CLI `backend/src/nichepilot/jobs/erasure_ledger.py` (`python -m nichepilot.jobs.erasure_ledger --strict`, mã thoát ≠ 0 khi
  lỗi, log không chứa nội dung) và sửa service `migrate` trong `deploy/docker-compose.yml` chạy `alembic upgrade head && python -m
  nichepilot.jobs.erasure_ledger --strict` (X4)
- [ ] T031 Sửa `deploy/scripts/restore.sh` gọi `apply_erasure_ledger --strict` ngay sau `pg_restore`, thoát ≠ 0 và in hướng dẫn khi lỗi;
  sửa `deploy/scripts/backup.sh` sao bản ledger kèm dump; mở rộng `backend/tests/integration/test_backup_restore.py` cho bước mới (X4)
- [ ] T032 Gate ledger: dependency FastAPI cho router E1 trong `backend/src/nichepilot/api/v1/discovery.py` (khung router) trả 503
  `ERASURE_LEDGER_NOT_APPLIED`; thành phần `erasure_ledger` trong `backend/src/nichepilot/api/v1/system.py`; worker kiểm tra trước khi nhận
  job `discovery.*` trong `backend/src/nichepilot/jobs/runtime.py` qua hook đăng ký (không đổi state machine)
- [ ] T033 [P] Triển khai `SourcePolicyService` (`usable_for_run`, `create_policy`, `update_policy(actor_id, …)` với audit
  `source.created`/`source.updated`) trong `backend/src/nichepilot/modules/discovery/sources/policy.py` theo `data-model.md
  source_policies.allowed_access_methods`, `source_policies.permitted_use_scope`, `source_policies.verification_note`
- [ ] T034 [P] Triển khai `SearxngConfigWriter` trong `backend/src/nichepilot/modules/discovery/sources/searxng_config.py` (ghi
  `settings.yml` vào volume `searxng-config`, trả `requires_service_restart`)
- [ ] T035 [P] Triển khai `PiiEngine` + `RegexSpacyPiiEngine` (regex, phonenumbers theo thị trường, spaCy chỉ `ner`, `RedactedText`
  NewType) trong `backend/src/nichepilot/tools/privacy/pii.py` (research R-05)
- [ ] T036 [P] Triển khai `SourceAdapter`, `SourceResult`, registry theo `adapter_type` và validate `data-model.md source_policies.config`
  (danh sách chặn khóa gợi ý thông tin xác thực) trong `backend/src/nichepilot/tools/sources/base.py`
- [ ] T037 [P] Triển khai `SearxngEngineAdapter` trong `backend/src/nichepilot/tools/sources/searxng_engine.py` (chỉ `engines=` của policy
  hợp lệ; ánh xạ lỗi → `UNAVAILABLE`/`NO_RESULTS`/`RATE_LIMITED`/`ACCESS_RESTRICTED`)
- [ ] T038 [P] Triển khai `HttpJsonApiAdapter` (khung; xác thực từ `os.environ[auth_env_var]` lúc gọi, không log) trong
  `backend/src/nichepilot/tools/sources/http_json_api.py` và interface `OpenDatasetAdapter`/`LicensedDataAdapter` + mock trong
  `backend/src/nichepilot/tools/sources/dataset.py` (research R-13)
- [ ] T039 [P] Triển khai `MockSourceAdapter`, `MockPageFetcher` (fixture T009, `data_origin = MOCK`, guard production) trong
  `backend/src/nichepilot/tools/mock_sources.py`
- [ ] T040 Triển khai `HttpPageFetcher` (httpx + trafilatura, bỏ `author`, giới hạn kích thước/loại/timeout) trong
  `backend/src/nichepilot/tools/fetchers/http_fetcher.py`
- [ ] T041 Đăng ký tool chỉ đọc `source.query`, `page.fetch` (che PII trong handler – output chỉ `RedactedText`), `robots.fetch` (protego)
  với `external_effect = false` trong `backend/src/nichepilot/tools/builtin/source_query.py`,
  `backend/src/nichepilot/tools/builtin/page_fetch.py`, `backend/src/nichepilot/tools/builtin/robots_fetch.py`
- [ ] T042 Triển khai `DomainAccessService` (`permit(url)`, robots cache 24 h, khoảng cách theo tên miền) trong
  `backend/src/nichepilot/modules/discovery/access.py` theo `data-model.md domain_access_state.min_interval_s`,
  `domain_access_state.crawl_delay_s`, `domain_access_state.blocked_until`, `domain_access_state.robots_status`
- [ ] T043 Triển khai SimHash 64-bit và `registered_domain` (tldextract, `suffix_list_urls=()`) trong
  `backend/src/nichepilot/modules/discovery/fingerprint.py`
- [ ] T044 Khung `NicheDiscoveryAgent` (`AgentDefinition` job type `discovery.run`, `max_steps` 240, `max_ai_calls` 120, `timeout_s` 6000,
  `allowed_tools` = {source.query, page.fetch, robots.fetch}, checkpoint chỉ ID/hash/bộ đếm) trong
  `backend/src/nichepilot/jobs/agents/niche_discovery.py` và đăng ký job type trong `backend/src/nichepilot/jobs/agents/__init__.py`
- [ ] T045 Pydantic schema đầu ra AI cho `discovery.candidates|extract|assess|normalize` (evidence_ids phải thuộc tập đã cung cấp; mức tiêu chí
  ∈ {0,25,50,75,100,null}) và DTO API trong `backend/src/nichepilot/modules/discovery/schemas.py`

**Checkpoint**: lint-imports xanh (gồm modules-independent mới); test T011–T024 PASS; stack khởi động với ledger rỗng; restore thiếu sổ
thất bại an toàn.

---

## Phase 3: User Story 1 – Khám phá ngách tự động khi chưa chọn lĩnh vực (P1) 🎯 MVP

**Goal**: chủ sở hữu tạo lượt khám phá (thị trường, không lĩnh vực), job `discovery.run` đề xuất ứng viên, tìm và thu thập nguồn, trả danh
sách ngách; màn hình 1.

**Independent Test**: lượt thị trường US, không chọn lĩnh vực, AI + nguồn giả lập → ngách ứng viên đủ trường, thuộc ≥ 3 lĩnh vực, dữ liệu
gắn MOCK; không có nguồn ALLOWED và không opt-in → 409 `NO_COMPLIANT_SEARCH_SOURCE`.

### Tests cho User Story 1 (viết trước, phải FAIL)

- [ ] T046 [P] [US1] Contract test `POST/GET /api/v1/discovery/runs`, `GET /api/v1/discovery/runs/{run_id}` theo contracts/openapi.yaml
  (mặc định 20/$2/90 phút/300 trang; `Idempotency-Key`; `include_unverified_sources` bị từ chối cho lượt SCHEDULED) trong
  `backend/tests/contract/discovery/test_runs_api.py` (TC_E1_FR001_01, TC_E1_FR002_01, TC_E1_FR003_01)
- [ ] T047 [P] [US1] Test từ chối sớm: ngân sách chưa cấu hình → `BUDGET_NOT_CONFIGURED`; `budget_usd` > hạn mức ngày →
  `RUN_BUDGET_EXCEEDS_DAILY_LIMIT`; không nguồn hợp lệ → `NO_COMPLIANT_SEARCH_SOURCE`; opt-in nhưng không có UNVERIFIED bật →
  `UNVERIFIED_SOURCE_NOT_ENABLED`; không job nào được tạo, 0 lời gọi AI trong
  `backend/tests/integration/discovery/test_run_preconditions.py` (TC_E1_FR004_01, TC_E1_FR006e_01)
- [ ] T048 [P] [US1] Test luồng `discovery.run` với mock: plan_queries → check_sources → search → fetch → extract; ứng viên ≥ 3 lĩnh vực
  khi không seed topic; nguồn lỗi ghi trạng thái, không tạo dữ liệu thay thế; bằng chứng mang `source_compliance` trong
  `backend/tests/integration/discovery/test_discovery_run_flow.py` (TC_E1_FR002_02, TC_E1_FR006a_01, TC_E1_FR006b_01, TC_E1_SC002_01)
- [ ] T049 [P] [US1] Test nội dung ngoài chứa chỉ dẫn (prompt injection) không làm thay đổi hành vi/tool được gọi; nội dung bọc trong
  `<untrusted_content>` trong `backend/tests/integration/discovery/test_untrusted_content.py` (TC_E1_FR012_01)
- [ ] T050 [P] [US1] Vitest màn hình 1 (đang tải/rỗng/lỗi, nhãn MOCK, chi phí REAL/MOCK, thông báo `NO_COMPLIANT_SEARCH_SOURCE`) trong
  `frontend/tests/unit/discovery-runs-page.test.tsx` (TC_E1_FR026_01)

### Implementation cho User Story 1

- [ ] T051 [US1] `DiscoveryService.create_run` (kiểm tra ngân sách E0, hạn mức ngày, nguồn hợp lệ, opt-in; chốt
  `data-model.md discovery_runs.weights_version_id`, `discovery_runs.source_policy_ids`, `discovery_runs.trigger`,
  `discovery_runs.include_unverified_sources`; tạo job E0 idempotent; audit `discovery.run_created`) trong
  `backend/src/nichepilot/modules/discovery/service.py`
- [ ] T052 [US1] Bước `plan_queries` và `check_sources` của agent (task type `discovery.candidates` qua AI Gateway; dừng
  `NO_COMPLIANT_SEARCH_SOURCE` khi rỗng) trong `backend/src/nichepilot/jobs/agents/niche_discovery.py`
- [ ] T053 [US1] Bước `search` và `fetch` của agent (`usable_for_run` → `source.query`; `DomainAccessService.permit` → `page.fetch`; lưu
  `research_sources`/`research_evidence` đã che với `data-model.md research_evidence.redaction_status`,
  `research_sources.source_compliance`; ghi `data-model.md page_fetch_log.outcome`, `page_fetch_log.reason`) trong
  `backend/src/nichepilot/jobs/agents/niche_discovery.py`
- [ ] T054 [US1] Bước `extract` cơ bản (task type `discovery.extract`, chỉ nhận `RedactedText` REDACTED, bọc `<untrusted_content>`) tạo
  bản ghi `niches` theo `data-model.md niches.name`, `niches.micro_niche`, `niches.country`, `niches.customer_group`, `niches.core_problem`,
  `niches.data_origin` trong `backend/src/nichepilot/jobs/agents/niche_discovery.py`
- [ ] T055 [US1] Router `POST/GET /api/v1/discovery/runs`, `GET /api/v1/discovery/runs/{run_id}` trong
  `backend/src/nichepilot/api/v1/discovery.py` và đăng ký trong `backend/src/nichepilot/api/v1/__init__.py`
- [ ] T056 [P] [US1] Kiểu API và hook TanStack Query cho runs trong `frontend/src/api/types.ts`, `frontend/src/api/discovery.ts`
- [ ] T057 [US1] Màn hình 1 `frontend/src/pages/discovery/DiscoveryRunsPage.tsx` (lịch sử, trạng thái, outcome + lý do, chi phí REAL/MOCK,
  tạo lượt có tùy chọn dùng nguồn chưa xác minh kèm cảnh báo, chạy/tạm dừng/tiếp tục/hủy qua `/api/v1/jobs/*`) và route trong
  `frontend/src/app/router.tsx`

**Checkpoint**: US1 chạy độc lập với mock; quickstart §1–§2 PASS.

---

## Phase 4: User Story 2 – Pain point, buyer persona và bằng chứng có nguồn (P1)

**Goal**: mỗi ngách có pain point, persona, giải pháp, đối thủ, tín hiệu monetization có bằng chứng; ngưỡng bằng chứng; PII; xóa bằng chứng;
màn hình 3 phần bằng chứng.

**Independent Test**: lượt giả lập dữ liệu cố định → mỗi pain point có ≥ 1 bằng chứng (URL, trích đoạn đã che, thời điểm); ngách thiếu nguồn
độc lập → `INSUFFICIENT_EVIDENCE`; xóa bằng chứng → tính lại; restore backup cũ → vẫn ERASED.

### Tests cho User Story 2 (viết trước, phải FAIL)

- [ ] T058 [P] [US2] Test ngưỡng bằng chứng + nhóm độc lập (eTLD+1, SimHash ≤ 3, `copy_suspected`, relevance/quality, NEEDS_REVIEW không
  tính, MOCK tách) theo scoring-rubric §1 trong `backend/tests/unit/discovery/test_evidence_rules.py` (TC_E1_FR013b_01…04,
  TC_E1_FR015_02, TC_E1_SC003a_01)
- [ ] T059 [P] [US2] Test `INSUFFICIENT_EVIDENCE` được lưu cùng bằng chứng, không vào xếp hạng, không đếm là ngách hợp lệ trong
  `backend/tests/integration/discovery/test_insufficient_evidence.py` (TC_E1_FR013c_01)
- [ ] T060 [P] [US2] Test trích xuất: pain point nhóm + severity, persona 5 thuộc tính có trạng thái, giải pháp/khoảng trống, đối thủ,
  monetization, kênh; `evidence_ids` lạ → đầu ra bị loại; `UNKNOWN` không có giá trị; `CONFLICTING` lưu mọi giá trị (QA-05) trong
  `backend/tests/integration/discovery/test_extraction.py` (TC_E1_FR007_01, TC_E1_FR008_01, TC_E1_FR009_01, TC_E1_FR010_01,
  TC_E1_FR011_01, TC_E1_FR013_01, TC_E1_FR014_01, TC_E1_SC004_01, TC_E1_SC008_01)
- [ ] T061 [P] [US2] Test đầu-cuối PII: sau một lượt mock với trang chứa PII, 0 mẫu PII trong DB (mọi bảng E1 + `tool_calls` + audit),
  log file, checkpoint, prompt gửi MockAIProvider trong `backend/tests/integration/discovery/test_pii_end_to_end.py` (TC_E1_FR012a_05,
  TC_E1_FR012b_03, TC_E1_FR012c_01, TC_E1_SC016_02)
- [ ] T062 [P] [US2] Contract + integration test `POST /api/v1/evidence/{evidence_id}/erase` (EVIDENCE/SOURCE; 409 khi đã xóa; audit không
  nội dung; ngách đủ đúng 2 nhóm → `INSUFFICIENT_EVIDENCE` sau recompute; không thu thập lại cùng `content_hash`) trong
  `backend/tests/contract/discovery/test_erasure_api.py` (TC_E1_FR013e_02…04)
- [ ] T063 [P] [US2] Test restore: backup trước khi xóa → restore vào DB trống → `apply --strict` → bằng chứng vẫn ERASED, API không trả
  trích đoạn; ghi sổ OK + DB lỗi → lần áp dụng sau hoàn tất trong `backend/tests/integration/discovery/test_erasure_restore.py`
  (TC_E1_FR013f_09, TC_E1_FR013f_10, TC_E1_SC016_03)
- [ ] T064 [P] [US2] Contract test `GET /api/v1/niches/{niche_id}` (16 trường BR-07, `source_compliance`, `redaction_status`) trong
  `backend/tests/contract/discovery/test_niche_detail_api.py` (TC_E1_FR023_01, TC_E1_SC003_01)
- [ ] T065 [P] [US2] Vitest màn hình 3 phần pain point/persona/bằng chứng (đang tải/rỗng/lỗi, nhãn MOCK, nhãn nguồn chưa xác minh) trong
  `frontend/tests/unit/niche-detail-page.test.tsx` (TC_E1_FR026_02)

### Implementation cho User Story 2

- [ ] T066 [US2] Quy tắc ngưỡng + nhóm độc lập (thuần, không I/O) trong `backend/src/nichepilot/modules/discovery/evidence_rules.py` theo
  `data-model.md niche_evidence_links.independence_group`, `niche_evidence_links.counted_for_threshold`, `niche_evidence_links.relevance`,
  `niche_evidence_links.quality`, `niche_evidence_links.copy_suspected`
- [ ] T067 [US2] Hoàn thiện bước `extract` + bước `assess` (relevance/quality/copy_suspected từng bằng chứng) lưu `pain_points`,
  `buyer_personas`, `competitors`, `niche_findings`, `niche_evidence_links` theo `data-model.md pain_points.severity`,
  `buyer_personas.attributes`, `competitors.kind`, `niche_findings.field`, `niche_findings.value` trong
  `backend/src/nichepilot/jobs/agents/niche_discovery.py` và `backend/src/nichepilot/modules/discovery/service.py`
- [ ] T068 [US2] Gán `data-model.md niches.evidence_status` sau bước evaluate trong `backend/src/nichepilot/modules/discovery/service.py`
- [ ] T069 [US2] `EvidenceErasureService.erase` (ghi sổ → transaction → job `discovery.recompute`; `data-model.md
  evidence_erasure_requests.ledger_seq`, `research_sources.erased_at`) trong `backend/src/nichepilot/modules/discovery/erasure.py` và job
  type `discovery.recompute` (0 lời gọi AI) trong `backend/src/nichepilot/jobs/agents/niche_reevaluate.py`
- [ ] T070 [US2] Router `POST /api/v1/evidence/{evidence_id}/erase`, `GET /api/v1/niches/{niche_id}` trong
  `backend/src/nichepilot/api/v1/discovery.py`
- [ ] T071 [US2] Màn hình 3 (phần pain point, persona, giải pháp, đối thủ, bằng chứng + nguồn, nút xóa bằng chứng có xác nhận) trong
  `frontend/src/pages/discovery/NicheDetailPage.tsx`

**Checkpoint**: US2 độc lập với dữ liệu fixture; quickstart §6 PASS (gồm bảng thất bại an toàn).

---

## Phase 5: User Story 3 – Chấm điểm cơ hội và độ tin cậy, xếp hạng ngách (P1)

**Goal**: Opportunity/Coverage/Confidence tách biệt, phiên bản trọng số, ba danh sách xếp hạng; màn hình 2 và phần lý do chấm điểm của
màn hình 3.

**Independent Test**: bộ đánh giá cố định → điểm khớp ví dụ tính tay scoring-rubric §3 (60,71 / 66,00); Coverage < 60 →
`INSUFFICIENT_SCORING_DATA`; đổi trọng số → tính lại 0 lời gọi AI.

### Tests cho User Story 3 (viết trước, phải FAIL)

- [ ] T072 [P] [US3] Test `compute_opportunity` (đủ 6; thiếu 1; nhiều tiêu chí thiếu; Coverage đúng 60 và dưới 60; CONFLICTING; không gán
  0/100 cho UNKNOWN) gồm ví dụ 60,71 trong `backend/tests/unit/discovery/test_opportunity.py` (TC_E1_FR017_01, TC_E1_FR019_01…03,
  TC_E1_FR019a_01, TC_E1_SC005_01, TC_E1_SC005a_01)
- [ ] T073 [P] [US3] Test `compute_confidence` (ví dụ 66,00; trần 30 khi INSUFFICIENT_EVIDENCE; chữ ký không có tham số Opportunity) trong
  `backend/tests/unit/discovery/test_confidence.py` (TC_E1_FR020_01, TC_E1_FR020_02)
- [ ] T074 [P] [US3] Test search volume thấp không làm giảm điểm và không loại ngách trong `backend/tests/unit/discovery/test_opportunity.py`
  (TC_E1_FR021_01)
- [ ] T075 [P] [US3] Contract test `GET/POST /api/v1/scoring/weights` (`WEIGHTS_INVALID`; phiên bản cũ không đổi; `recompute_existing`
  tạo `discovery.recompute` 0 lời gọi AI) trong `backend/tests/contract/discovery/test_weights_api.py` (TC_E1_FR018_01, TC_E1_FR018_02)
- [ ] T076 [P] [US3] Contract test `GET /api/v1/niches?list=research|affiliate|needs_research` (điều kiện scoring-rubric §4,
  `MONETIZATION_UNVERIFIED` không vào affiliate, MOCK ẩn mặc định, `disclaimer_key`) trong
  `backend/tests/contract/discovery/test_ranking_api.py` (TC_E1_FR019b_01, TC_E1_FR019c_01, TC_E1_FR016_02, TC_E1_SC009_01)
- [ ] T077 [P] [US3] Test cờ rủi ro tuân thủ cho lĩnh vực nhạy cảm trong `backend/tests/unit/discovery/test_risk_flags.py` (TC_E1_FR035_01)
- [ ] T078 [P] [US3] Vitest màn hình 2 (3 tab, Opportunity/Confidence/Coverage, trạng thái xác minh, Monetization, chú thích không phải dự
  báo doanh thu, đang tải/rỗng/lỗi) trong `frontend/tests/unit/niche-ranking-page.test.tsx` (TC_E1_FR026_03)

### Implementation cho User Story 3

- [ ] T079 [P] [US3] `compute_opportunity` trong `backend/src/nichepilot/modules/discovery/scoring/opportunity.py` theo
  `data-model.md niche_evaluations.criteria`, `niche_evaluations.coverage`, `niche_evaluations.scoring_status`,
  `niche_evaluations.opportunity_score`
- [ ] T080 [P] [US3] `compute_confidence` trong `backend/src/nichepilot/modules/discovery/scoring/confidence.py` theo
  `data-model.md niche_evaluations.confidence_score`, `niche_evaluations.confidence_components`
- [ ] T081 [US3] Bước `evaluate` của agent + `recompute` dùng chung `EvaluationService` (ghi `niche_evaluations` bất biến, cập nhật
  `data-model.md niches.latest_evaluation_id`, `niches.monetization_status`, `niches.risk_flags`) trong
  `backend/src/nichepilot/modules/discovery/evaluation.py`
- [ ] T082 [US3] `WeightsService` (validate tổng 100, phiên bản mới active, audit `scoring.weights_version_created`) theo `data-model.md
  scoring_weights_versions.weights`, `scoring_weights_versions.is_active` trong `backend/src/nichepilot/modules/discovery/weights.py`
- [ ] T083 [US3] `ranking.py` ba danh sách theo scoring-rubric §4 trong `backend/src/nichepilot/modules/discovery/ranking.py`
- [ ] T084 [US3] Router `GET/POST /api/v1/scoring/weights`, `GET /api/v1/niches`, `GET /api/v1/niches/{niche_id}/evaluations` trong
  `backend/src/nichepilot/api/v1/discovery.py`
- [ ] T085 [US3] Màn hình 2 `frontend/src/pages/discovery/NicheRankingPage.tsx` và phần lý do chấm điểm (điểm thành phần, phiên bản trọng
  số, Coverage, tiêu chí UNKNOWN, dữ liệu còn thiếu) trong `frontend/src/pages/discovery/NicheDetailPage.tsx`

**Checkpoint**: US3 độc lập trên dữ liệu đánh giá cố định; quickstart §5 bước 1, 2, 4 PASS.

---

## Phase 6: User Story 4 – Kiểm soát chi phí và độ bền của lượt khám phá (P1)

**Goal**: giới hạn ngân sách AI, thời gian, số trang, tốc độ theo tên miền; dừng sớm; checkpoint/tiếp tục không trùng; metrics; quản lý
nguồn qua API/UI.

**Independent Test**: hạn mức nhỏ → `PAUSED_BUDGET` không lời gọi vượt; page/time limit → `PARTIAL_COMPLETED` đúng lý do; kill worker →
tiếp tục không trùng; 2 URL cùng tên miền cách ≥ 2 s.

### Tests cho User Story 4 (viết trước, phải FAIL)

- [ ] T086 [P] [US4] Test ngân sách: mọi lời gọi qua Gateway + giữ chỗ; vượt lượt/ngày/tháng → `PAUSED_BUDGET`, không lời gọi vượt; không
  tự tăng ngân sách trong `backend/tests/integration/discovery/test_run_budget.py` (TC_E1_FR028_01, TC_E1_FR030e_01, TC_E1_SC006_01,
  TC_E1_SC012_01)
- [ ] T087 [P] [US4] Test giới hạn: `page_limit`, `time_limit` (thời gian tạm dừng không tính), dừng sớm khi đủ bằng chứng, phân bổ trang ưu
  tiên ứng viên thiếu bằng chứng, `COMPLETED`/`PARTIAL_COMPLETED` + `data-model.md discovery_runs.stop_reason` trong
  `backend/tests/integration/discovery/test_run_limits.py` (TC_E1_FR030b_01, TC_E1_FR030c_01, TC_E1_FR030d_01, TC_E1_SC015_01)
- [ ] T088 [P] [US4] Test tốc độ và lỗi: khoảng cách cùng tên miền ≥ trần/Crawl-delay; 429/503 thử lại ≤ 2 lần theo Retry-After rồi
  `RATE_LIMITED`; trang lỗi bỏ qua có lý do không dừng lượt (QA-06, QA-07) trong `backend/tests/integration/discovery/test_rate_and_errors.py`
  (TC_E1_FR030_01, TC_E1_FR030a_04, TC_E1_FR031_02, TC_E1_SC015_02)
- [ ] T089 [P] [US4] Test bền: pause/resume/cancel qua API job E0; kill worker giữa `fetch` → tiếp tục từ checkpoint, 0 trùng `niches`,
  `pain_points`, `research_sources`, `page_fetch_log` (UNIQUE `data-model.md page_fetch_log.url_hash`) trong
  `backend/tests/integration/discovery/test_run_resume.py` (TC_E1_FR027_01, TC_E1_FR029_02, TC_E1_SC007_01)
- [ ] T090 [P] [US4] Test metrics FR-032 (trang theo kết quả/lý do, nguồn độc lập, lời gọi AI, chi phí REAL/MOCK tách) trong
  `backend/tests/integration/discovery/test_run_metrics.py` (TC_E1_FR032_01)
- [ ] T091 [P] [US4] Contract test `GET/POST /api/v1/sources`, `PUT /api/v1/sources/{source_id}` (`SOURCE_PROHIBITED`,
  `SOURCE_WARNING_NOT_ACKNOWLEDGED`, `SOURCE_VERIFICATION_INCOMPLETE`, `SOURCE_CONFIG_INVALID`, `requires_service_restart`, audit trước/sau,
  không trả giá trị biến môi trường) trong `backend/tests/contract/discovery/test_sources_api.py` (TC_E1_FR006c_04, TC_E1_FR006d_04,
  TC_E1_FR006g_03, TC_E1_FR036_01)

### Implementation cho User Story 4

- [ ] T092 [US4] Bộ đếm thời gian hoạt động/trang trong checkpoint, kiểm tra giới hạn trước mỗi `fetch`, phân bổ trang theo ứng viên, dừng
  sớm, `finalize` ghi `data-model.md discovery_runs.outcome`, `discovery_runs.stop_reason`, `discovery_runs.metrics` trong
  `backend/src/nichepilot/jobs/agents/niche_discovery.py`
- [ ] T093 [US4] Thử lại có giới hạn theo `Retry-After`, đánh dấu tên miền `blocked_until` trong
  `backend/src/nichepilot/modules/discovery/access.py`
- [ ] T094 [US4] Router `GET/POST /api/v1/sources`, `PUT /api/v1/sources/{source_id}` (gọi `SourcePolicyService` + `SearxngConfigWriter`)
  trong `backend/src/nichepilot/api/v1/discovery.py`
- [ ] T095 [US4] Màn hình quản lý nguồn (danh sách, trạng thái, form xác minh đủ mục source-verification.md §2, cảnh báo khi bật UNVERIFIED,
  lưu ý khởi động lại SearXNG) trong `frontend/src/pages/discovery/SourcesPage.tsx` và route trong `frontend/src/app/router.tsx`

**Checkpoint**: quickstart §4 PASS với mock.

---

## Phase 7: User Story 5 – Phát hiện ngách trùng/tương đồng (P2)

**Goal**: trùng chắc chắn gộp, có thể tương đồng chờ chủ sở hữu.

**Independent Test**: ứng viên khác tên cùng khách hàng/vấn đề → trùng/tương đồng đúng ngưỡng; bộ cặp có nhãn ≥ 90% đúng, 0 gộp nhầm.

- [ ] T096 [P] [US5] Bộ ≥ 40 cặp ngách có nhãn tự soạn trong `backend/tests/fixtures/discovery/dedup_pairs.json` và test độ chính xác
  ≥ 90%, 0 gộp nhầm trong `backend/tests/unit/discovery/test_dedup.py` (TC_E1_FR022_01, TC_E1_SC010_01)
- [ ] T097 [P] [US5] Contract test `GET /api/v1/niche-similarities`, `PUT /api/v1/niche-similarities/{similarity_id}` (gộp giữ
  `keep_niche_id`, audit `niche.similarity_resolved`) trong `backend/tests/contract/discovery/test_similarity_api.py` (TC_E1_FR022_02)
- [ ] T098 [US5] `similarity()` + bước `dedup` (task type `discovery.normalize`; ngưỡng từ `data-model.md scoring_weights_versions.dedup_params`;
  ghi `data-model.md niche_similarity.status`, `niches.merged_into_id`, `niches.dedup_key`) trong
  `backend/src/nichepilot/modules/discovery/dedup.py` và `backend/src/nichepilot/jobs/agents/niche_discovery.py`
- [ ] T099 [US5] Router similarity trong `backend/src/nichepilot/api/v1/discovery.py` và cờ `has_possible_duplicate` + hộp xác nhận trong
  `frontend/src/pages/discovery/NicheDetailPage.tsx`

**Checkpoint**: US5 độc lập với dữ liệu cặp cố định.

---

## Phase 8: User Story 6 – Báo cáo xếp hạng và quyết định của chủ sở hữu (P2)

**Goal**: báo cáo theo lượt (JSON/Markdown, ba danh sách), AI đề xuất + lý do, chủ sở hữu ghi quyết định.

**Independent Test**: sau lượt giả lập → báo cáo sắp xếp đúng, hai điểm tách biệt, ghi quyết định có audit.

- [ ] T100 [P] [US6] Contract test `GET /api/v1/discovery/runs/{run_id}/report` (json, markdown; ba danh sách; `disclaimer_key`; MOCK loại
  khỏi báo cáo mặc định) trong `backend/tests/contract/discovery/test_report_api.py` (TC_E1_FR024_01, TC_E1_SC009_02)
- [ ] T101 [P] [US6] Contract test `PUT /api/v1/niches/{niche_id}/decision` (5 trạng thái, lý do, audit `niche.decision_recorded`, AI không
  tự đổi quyết định) trong `backend/tests/contract/discovery/test_decision_api.py` (TC_E1_FR025_01)
- [ ] T102 [US6] Sinh báo cáo JSON/Markdown (tiêu đề theo ngôn ngữ giao diện, trích dẫn giữ ngôn ngữ gốc) trong
  `backend/src/nichepilot/modules/discovery/report.py` và router trong `backend/src/nichepilot/api/v1/discovery.py`
- [ ] T103 [US6] `record_decision` theo `data-model.md niches.decision_status`, `niches.owner_decision_reason`, `niches.ai_recommendation`
  trong `backend/src/nichepilot/modules/discovery/service.py` và router `PUT /api/v1/niches/{niche_id}/decision`
- [ ] T104 [US6] Nút ghi quyết định + hiển thị đề xuất AI trong `frontend/src/pages/discovery/NicheDetailPage.tsx`; tải báo cáo Markdown
  trong `frontend/src/pages/discovery/DiscoveryRunsPage.tsx`

**Checkpoint**: quickstart §5 bước 3 PASS.

---

## Phase 9: User Story 7 – Nghiên cứu theo lịch và đánh giá lại (P3)

**Goal**: lịch khám phá định kỳ (chỉ nguồn ALLOWED), đánh giá lại ngách đang theo dõi.

**Independent Test**: lịch đến hạn tạo đúng một lượt `trigger = SCHEDULED` chỉ dùng nguồn ALLOWED; lịch khi ngân sách chưa cấu hình bị từ chối.

- [ ] T105 [P] [US7] Test lịch E0 với `job_type = discovery.run`: đúng 1 lượt/mốc, `trigger = SCHEDULED`,
  `include_unverified_sources = false` bắt buộc, chỉ nguồn ALLOWED, không nguồn → `NO_COMPLIANT_SEARCH_SOURCE` trong
  `backend/tests/integration/discovery/test_discovery_schedule.py` (TC_E1_FR033_01, TC_E1_FR006d_05, TC_E1_SC017_02)
- [ ] T106 [P] [US7] Test `POST /api/v1/niches/{niche_id}/reevaluate` + lịch `discovery.reevaluate`: tạo đánh giá mới, giữ đánh giá cũ, so sánh
  thay đổi, giữ chỗ ngân sách trong `backend/tests/integration/discovery/test_reevaluate.py` (TC_E1_FR034_01)
- [ ] T107 [US7] Tham số job `discovery.run` từ lịch E0 (ép `trigger = SCHEDULED`) trong `backend/src/nichepilot/modules/discovery/service.py`
  và kiểm tra trong `backend/src/nichepilot/jobs/scheduler.py` qua hook đăng ký job type (không đổi logic lịch E0)
- [ ] T108 [US7] `NicheReevaluationAgent` (job type `discovery.reevaluate`, max_steps 60, max_ai_calls 20) trong
  `backend/src/nichepilot/jobs/agents/niche_reevaluate.py` và router `POST /api/v1/niches/{niche_id}/reevaluate`

**Checkpoint**: quickstart §3 bước 3 PASS với mock.

---

## Phase 10: Polish & Cross-Cutting

- [ ] T109 [P] Playwright E2E luồng chính "tạo lượt (mock) → bảng xếp hạng → chi tiết → ghi quyết định" VI/EN trong
  `frontend/tests/e2e/discovery.spec.ts` (TC_E1_SC014_01, TC_E1_SC001_01)
- [ ] T110 [P] Test kiến trúc: không model ID hard-code trong `backend/src/nichepilot/modules/discovery/` và
  `backend/src/nichepilot/jobs/agents/niche_*.py`; hàm tạo prompt chỉ nhận `RedactedText` trong
  `backend/tests/unit/discovery/test_architecture_rules.py` (TC_E1_FR028_02, TC_E1_FR012b_04)
- [ ] T111 [P] Test i18n: 100% khóa `discovery.*` có VI/EN, không chuỗi cứng trong JSX (mở rộng `frontend/tests/unit/i18n-keys.test.ts`)
  (TC_E1_FR026_04)
- [ ] T112 [P] Tài liệu vận hành `docs/operations/discovery.md`: xác minh/bật nguồn (source-verification.md), khởi động lại SearXNG, xóa bằng
  chứng, ledger và restore thất bại an toàn, profile `browser-fetcher`; cập nhật `docs/operations/backup-restore.md`,
  `docs/operations/troubleshooting.md`
- [ ] T113 [P] Đo tài nguyên stack E0 + E1 nghỉ (`docker stats`) và kích thước image worker; ghi vào
  `specs/002-niche-discovery/checklists/verification.md` (Constitution XI, SC-002 E0)
- [ ] T114 Chạy toàn bộ quality gate (ruff, mypy, lint-imports, pytest, frontend lint/typecheck/test, E2E, `check_secrets.py`,
  `traceability_report.py --strict`) và ghi kết quả PASS/FAIL/NOT_TESTED/BLOCKED vào
  `specs/002-niche-discovery/checklists/verification.md` (TC_E1_SC011_01)
- [ ] T115 Chạy quickstart §1–§8 với mock trên stack Docker thật; ghi bằng chứng vào `specs/002-niche-discovery/checklists/verification.md`;
  §3 (nguồn thật) và SC-013 ghi `BLOCKED – chờ xác minh nguồn` (không phải lỗi implementation)
- [ ] T116 [P] Profile tùy chọn `browser-fetcher`: `PlaywrightPageFetcher` trong `backend/src/nichepilot/tools/fetchers/playwright_fetcher.py`
  + image riêng `deploy/browser-fetcher/Dockerfile` (không stealth); test với trang fixture cần JS trong
  `backend/tests/integration/discovery/test_playwright_fetcher.py` (marker riêng, không chạy mặc định); đo RAM khi bật

---

## Dependencies & Execution Order

- **Phase 1 → Phase 2 → US**: Phase 2 chặn mọi user story (schema, ledger gate, policy, adapter, PII, fetcher, agent khung).
- **US1 (P1)** là MVP; **US2** dùng bước fetch/extract của US1 nhưng test độc lập bằng fixture; **US3** cần `niche_evidence_links` (US2) cho
  Confidence, nhưng test đơn vị chấm điểm độc lập; **US4** mở rộng agent US1; **US5**, **US6** cần ngách + đánh giá (US1–US3);
  **US7** cần US1 (+ đánh giá lại dùng US3).
- Trong mỗi phase: test → model/service → agent → API → UI.
- T116 tùy chọn, không chặn phát hành E1.

### Thứ tự đề xuất

Phase 1 → Phase 2 → US1 → US2 → US3 → US4 → US5 → US6 → US7 → Polish.

## Parallel Example

```text
# Phase 2 – viết test song song:
T012, T013, T014, T017, T018, T019, T020, T022, T023, T024
# Phase 2 – triển khai song song (khác file):
T033, T034, T035, T036, T037, T038, T039
# US3:
T072, T073, T075, T076, T077, T078 → T079 ∥ T080 → T081 → T082 → T083 → T084 → T085
```

## Implementation Strategy

1. **MVP** = Phase 1 + 2 + US1 (lượt khám phá chạy với mock, từ chối đúng khi không có nguồn hợp lệ, ledger fail-safe sẵn sàng).
2. Thêm US2 + US3 → đạt AC-05, AC-06, AC-07 ở mức mock; US4 → độ bền/chi phí; US5–US7 sau.
3. Dữ liệu thật chỉ sau khi chủ sở hữu xác minh nguồn (source-verification.md) – không thuộc phạm vi tự động của tasks này.
4. Mỗi phase kết thúc bằng checkpoint và commit riêng; không đánh dấu PASS cho test chưa chạy.
