---

description: "Danh sách công việc triển khai E1 — Autonomous Niche Discovery"
---

# Tasks: E1 — Autonomous Niche Discovery

**Input**: Tài liệu thiết kế trong `/specs/002-niche-discovery/`

**Prerequisites**: plan.md (APPROVED WITH CONDITIONS 2026-11-20; quyết định A1/I1/I2 2026-11-20 (b)), spec.md, research.md (R-01…R-13),
data-model.md, contracts/ (openapi.yaml, internal-interfaces.md, scoring-rubric.md), quickstart.md, source-verification.md,
technology-evaluation.md

**Trạng thái**: CHƯA TRIỂN KHAI – chờ chủ sở hữu duyệt báo cáo `/speckit-analyze` cuối trước `/speckit-implement`.

**Tests**: BẮT BUỘC (Constitution IX). Trong mỗi phase, task test viết trước và phải FAIL trước khi triển khai. Test tự động KHÔNG gọi
API có phí, KHÔNG gọi mạng (rào chắn socket E0); nguồn ngoài dùng `MockSourceAdapter`/`MockPageFetcher`, AI dùng `MockAIProvider`.
Test giả lập KHÔNG được báo cáo là đã kiểm thử nguồn thật hay Claude/OpenAI API thật. Test cần nguồn `ALLOWED` thật mà chưa có → kết
quả `BLOCKED` (không bao giờ PASS).

**Truy vết**: mỗi task ghi mã yêu cầu trong ngoặc ở cuối; test đặt mã `TC_E1_<REQ>_<nn>` trong tên/docstring; T006 mở rộng
`traceability_report.py` cho spec 002. Field có ràng buộc được trích dẫn dạng `data-model.md <bảng>.<cột>`.

**Ràng buộc chung cho mọi task**: không thêm finding vào `.secrets.baseline`; không credential thật; không đặt `compliance_status = ALLOWED`
hay bật nguồn trong seed/test dữ liệu thật; không có tham số/cờ/nút nào cho phép dùng nguồn `UNVERIFIED`/`PROHIBITED` (A1); không thêm
Crawl4AI hay thành phần stealth/chống phát hiện bot (I1); không cài/tải spaCy model trong production (I2); không hard-code model ID trong
`modules/discovery` và `jobs/agents`; không sửa Job Runtime, Scheduler, `/api/v1/system/status`, state machine job, Gateway, giữ chỗ ngân
sách của E0 (H1) – chỉ các điểm mở rộng X1–X8 đã duyệt.

## Format: `[ID] [P?] [Story] Description (REQ-IDs)`

- **[P]**: Chạy song song được (khác file, không phụ thuộc task chưa xong)
- **[Story]**: User story (US1…US7)

## Path Conventions

Backend `backend/src/nichepilot/…`, test `backend/tests/{unit,integration,contract,live_sources,perf}/discovery/…`, migration
`backend/alembic/versions/…`, frontend `frontend/src/…`, test frontend `frontend/tests/{unit,e2e}/…`, triển khai `deploy/…`.

---

## Phase 1: Setup (hạ tầng dùng chung)

- [X] T001 Thêm dependency production đã xác minh vào `backend/pyproject.toml` + `backend/uv.lock`, ghim phiên bản theo research R-12
  (trafilatura 2.3.1, protego 0.7.0, phonenumbers 9.0.43, rapidfuzz 3.14.6, tldextract 5.4.0); thêm nhóm tùy chọn `pii-ner` (spacy 3.8.18)
  **không** thuộc cài đặt mặc định; kiểm tra lại giấy phép bắc cầu và ghi vào `docs/operations/discovery.md` §Dependency; không thêm crawl4ai,
  playwright-stealth, patchright (FR-005, FR-012a, FR-015, FR-022, FR-030a)
- [X] T002 Sửa `backend/Dockerfile`: build arg `INSTALL_PII_NER=false` mặc định; chỉ khi `true` (image dev) cài nhóm `pii-ner` + wheel
  `en_core_web_sm-3.8.0` từ URL ghim phiên bản kèm kiểm tra SHA-256; stage production không bao giờ cài; ghi kích thước image hai biến thể vào
  `docs/operations/discovery.md` (FR-012a, FR-012b)
- [X] T003 [P] Thêm vào `deploy/docker-compose.yml`: service `searxng` (image `searxng/searxng:2026.11.18-b867c56a5`, `mem_limit 256m`, mạng
  nội bộ, không publish cổng, `GRANIAN_HOST=0.0.0.0`, `SEARXNG_SECRET` từ env, volume `searxng-config`), volume `erasure-ledger`, profile tùy
  chọn `browser-fetcher`; thêm biến vào `deploy/env/.env.example` không có giá trị thật (FR-006, FR-006b, FR-013f)
  *[Ghi chú triển khai: service `browser-fetcher` thêm cùng image ở T128; SearXNG không nạp plugin (`plugins: {}`) vì plugin
  tracker_url_remover tự tải dữ liệu từ Internet – phát hiện khi chạy thử]*
- [X] T004 [P] Tạo `deploy/searxng/settings.base.yml`: `use_default_settings.engines.keep_only: []`, `search.formats: [html, json]`,
  `server.limiter: false`, `public_instance: false`, `image_proxy: false` (FR-006c, FR-006d)
- [X] T005 [P] Thêm mã lỗi E1 vào `frontend/src/api/error-codes.json` + bản dịch VI/EN: `NO_COMPLIANT_SEARCH_SOURCE`, `SOURCE_NOT_ALLOWED`,
  `SOURCE_VERIFICATION_INCOMPLETE`, `SOURCE_CONFIG_INVALID`, `SOURCE_EXISTS`, `RUN_BUDGET_EXCEEDS_DAILY_LIMIT`, `WEIGHTS_INVALID`,
  `DISCOVERY_RUN_NOT_FOUND`, `NICHE_NOT_FOUND`, `EVIDENCE_NOT_FOUND`, `EVIDENCE_ALREADY_ERASED`, `ERASURE_LEDGER_NOT_APPLIED`,
  `PII_ENGINE_NOT_APPROVED` (FR-004, FR-006c, FR-006d, FR-006e, FR-006g, FR-013e, FR-013f, FR-018, FR-012a)
- [X] T006 [P] Mở rộng `backend/scripts/traceability_report.py`: nhiều spec (001 dùng `TC_FR…/TC_SC…`, 002 dùng `TC_E1_FR…/TC_E1_SC…`);
  `--strict` lỗi khi FR/SC Must của bất kỳ spec nào thiếu test; báo cáo riêng test có trạng thái `BLOCKED`; test hồi quy spec 001 vẫn 58/58 trong
  `backend/tests/unit/test_traceability_report.py` (SC-011)
- [X] T007 [P] Tạo khung gói `backend/src/nichepilot/modules/discovery/__init__.py`, `backend/src/nichepilot/tools/sources/__init__.py`,
  `backend/src/nichepilot/tools/privacy/__init__.py`, `backend/src/nichepilot/tools/fetchers/__init__.py`, thư mục test và marker pytest
  `discovery`, `live_sources`, `perf`, `pii_ner`, `browser` (bốn marker sau deselected mặc định) trong `backend/pyproject.toml`; hook
  `backend/tests/conftest.py` ghi kết quả skip có lý do bắt đầu `BLOCKED:` thành trạng thái BLOCKED trong báo cáo (SC-011, SC-013)
- [X] T008 [P] Thêm `nichepilot.modules.discovery` vào hợp đồng `modules-independent` trong `backend/.importlinter` (FR-006, FR-028)
  *[Ghi chú triển khai: dùng hợp đồng `forbidden` một chiều (module E0 không import discovery) thay cho `independence`, vì discovery
  cần dùng service công khai của evidence/audit/settings (Constitution VIII)]*
- [X] T009 [P] Tạo trang HTML cố định tự soạn (diễn đàn, đánh giá, bản sao khác tên miền, trang chứa PII mẫu, tên người không theo mẫu, trang
  CAPTCHA giả, robots.txt mẫu, trang lỗi) trong `backend/tests/fixtures/discovery/` (FR-005, FR-012a, FR-015, FR-031)
- [X] T010 [P] Tạo `frontend/src/i18n/locales/vi/discovery.json`, `frontend/src/i18n/locales/en/discovery.json` (gồm
  `discovery.opportunity.disclaimer`) và đăng ký namespace trong `frontend/src/i18n/index.ts` (FR-026, FR-019c)
  *[Ghi chú triển khai: khóa `discovery.*` đặt trong `frontend/src/i18n/locales/{vi,en}.json` hiện có để test i18n E0 bao phủ]*
- [X] T011 [P] Thêm mục "E1 – Technology Evaluation" vào `docs/architecture/system-architecture.md` trỏ tới
  `specs/002-niche-discovery/technology-evaluation.md` (7 tiêu chí, nghĩa vụ AGPL của SearXNG, Crawl4AI loại, spaCy chưa phê duyệt) (FR-005, FR-006, FR-012a)

**Checkpoint**: `uv sync` OK trên Python 3.13 (không cài `pii-ner`); `docker compose config` hợp lệ; `searxng` chạy trong mạng nội bộ,
`/healthz` OK, không engine nào bật.

---

## Phase 2: Foundational (bắt buộc trước mọi user story)

### Tests cho Foundational (viết trước, phải FAIL)

- [X] T012 [P] Test migration `0009_discovery` up/down/up và ORM khớp migration trong
  `backend/tests/integration/discovery/test_migration_0009.py` (TC_E1_FR029_01) (FR-029, FR-013e)
- [X] T013 [P] Test ràng buộc DB `source_policies`: bật nguồn khi `UNVERIFIED` hoặc `PROHIBITED` bị CHECK từ chối; `ALLOWED` thiếu căn cứ bị
  từ chối; `PROHIBITED` thiếu `verified_at`/`verification_note` bị từ chối; đổi khỏi `ALLOWED` đặt `enabled = false` trong
  `backend/tests/integration/discovery/test_source_policy_constraints.py` (TC_E1_FR006c_01, TC_E1_FR006c_02, TC_E1_FR006c_03,
  TC_E1_FR006d_01) (FR-006c, FR-006d)
- [X] T014 [P] Test `EvidenceService.query` mặc định chỉ trả `ACTIVE`; CHECK `ERASED ⇒ excerpt/value NULL` trong
  `backend/tests/integration/discovery/test_evidence_lifecycle.py` (TC_E1_FR013e_01) (FR-013e)
- [X] T015 [P] Test sổ xóa: genesis/`ledger_id`, hash chain, fsync, ghi sổ trước DB, áp dụng lại idempotent trong
  `backend/tests/unit/discovery/test_erasure_ledger.py` (TC_E1_FR013f_01) (FR-013f)
- [X] T016 [P] Test `apply_erasure_ledger --strict` thất bại an toàn: sổ thiếu khi DB có `ledger_id`; `ledger_id` lệch; hash chain bị sửa;
  `applied_seq` > seq cuối; lỗi giữa chừng → rollback + `BLOCKED` + exit ≠ 0 trong
  `backend/tests/integration/discovery/test_ledger_apply_failsafe.py` (TC_E1_FR013f_02…TC_E1_FR013f_06) (FR-013f)
- [X] T017 [P] Test gate: `BLOCKED`/lệch → endpoint dữ liệu nghiên cứu E1 trả 503 `ERASURE_LEDGER_NOT_APPLIED`; `GET /api/v1/discovery/status`
  báo `BLOCKED`; endpoint cấu hình E1 vẫn chạy; phản hồi `/health` và `/api/v1/system/status` của E0 không đổi (hồi quy schema); job
  `discovery.*` thất bại ở bước `preflight`, 0 lời gọi AI trong `backend/tests/integration/discovery/test_ledger_gate.py`
  (TC_E1_FR013f_07, TC_E1_FR013f_08) (FR-013f)
- [X] T018 [P] Test `SourcePolicyService.usable_for_run()` chỉ trả `enabled ∧ ALLOWED` cho mọi loại lượt; không có tham số đưa nguồn khác
  vào; test kiến trúc quét mã: chỉ `update_policy` ghi `compliance_status`/`enabled` trong
  `backend/tests/unit/discovery/test_source_policy_service.py` (TC_E1_FR006d_02, TC_E1_SC017_01) (FR-006d, SC-017)
- [X] T019 [P] Test `SearxngConfigWriter` sinh `keep_only` đúng engine của nguồn `ALLOWED` đang bật (rỗng khi không có) trong
  `backend/tests/unit/discovery/test_searxng_config.py` (TC_E1_FR006g_01) (FR-006g)
- [X] T020 [P] Test tool `source.query`: từ chối mọi trạng thái khác `ALLOWED`; snippet được che PII; tôn trọng `rate_limit_per_minute`,
  `max_retries`, `timeout_s` của từng nguồn; 401/403 → `AUTH_FAILED` không thử lại; lỗi mạng → `NETWORK_ERROR`; CAPTCHA/429 không thử
  vượt trong `backend/tests/unit/discovery/test_source_query_tool.py` (TC_E1_FR006_01, TC_E1_FR006_02, TC_E1_FR006f_01,
  TC_E1_FR012b_01) (FR-006, FR-006f, FR-012b)
- [X] T021 [P] Test validate `source_policies.config`: từ chối mọi khóa bị cấm ở internal-interfaces §1.1 (kể cả lồng nhau/mảng, biến thể
  chữ hoa, `-`/`_`/`.`), từ chối giá trị có dạng credential; chấp nhận `auth_env_var` hợp lệ trong
  `backend/tests/unit/discovery/test_source_config_validation.py` (TC_E1_FR006g_02) (FR-006g)
- [X] T022 [P] Test `RegexPhonePiiEngine` trên bộ mẫu SC-016 (email, điện thoại nhiều định dạng/quốc gia, @username, `u/…`, "Posted by");
  tên người không theo mẫu → `NEEDS_REVIEW`; ngôn ngữ khác tiếng Anh có cụm viết hoa nghi ngờ → `NEEDS_REVIEW`; còn mẫu sau khi che →
  `UNSAFE`; đoạn có nguy cơ không bao giờ `REDACTED` chỉ nhờ regex trong `backend/tests/unit/discovery/test_pii_engine.py`
  (TC_E1_FR012a_01…TC_E1_FR012a_04, TC_E1_SC016_01) (FR-012a, SC-016)
- [X] T131 [P] Bộ đo chất lượng `PiiEngine` (bổ sung 2026-11-20, thực hiện cùng T022): tập đoạn văn tự soạn có nhãn (có/không chứa tên người
  hoặc PII) trong `backend/tests/fixtures/discovery/pii_labeled.jsonl`; script `backend/scripts/pii_engine_eval.py` tính tỷ lệ
  `NEEDS_REVIEW`, cảnh báo đúng/sai, false positive/false negative theo loại PII; test `backend/tests/unit/discovery/test_pii_engine_eval.py`
  khẳng định false negative = 0 trên tập có nhãn (không nới bảo vệ để tăng số ngách đủ bằng chứng); kết quả đo báo cáo cho chủ sở hữu,
  không tự đổi engine (TC_E1_FR012a_08, TC_E1_FR032_02) (FR-012a, FR-012b, FR-032, SC-016)
- [X] T023 [P] Test `select_pii_engine` fail-closed: production + `PII_ENGINE` ∉ `PII_APPROVED_ENGINES` → từ chối khởi động
  (`PII_ENGINE_NOT_APPROVED`); engine cần model mà model vắng → từ chối; không có lời gọi mạng tải model (rào chắn socket) trong
  `backend/tests/unit/discovery/test_pii_engine_selection.py` (TC_E1_FR012a_05) (FR-012a)
- [X] T024 [P] Test `SpacyEnPiiEngine` (marker `pii_ner`, chỉ dev/test; skip có lý do khi nhóm `pii-ner` không cài) trong
  `backend/tests/unit/discovery/test_pii_engine_spacy.py` (TC_E1_FR012a_06) (FR-012a)
- [X] T025 [P] Test tool `page.fetch`: output và bản ghi `tool_calls` chỉ chứa văn bản đã che; bỏ `author`; chỉ `text/html`, ≤ 3 MB, timeout
  20 s; CAPTCHA/đăng nhập → `SKIPPED ACCESS_RESTRICTED` trong `backend/tests/integration/discovery/test_page_fetch_tool.py`
  (TC_E1_FR012b_02, TC_E1_FR005_01, TC_E1_FR031_01) (FR-005, FR-012b, FR-031)
- [X] T026 [P] Test `DomainAccessService`: robots (protego, wildcard RFC 9309) → `ROBOTS_DISALLOWED`; khoảng cách = max(trần, Crawl-delay,
  Retry-After); trạng thái bền qua khởi động lại; robots 4xx → cho phép, 5xx/mạng → không thu thập tên miền trong
  `backend/tests/integration/discovery/test_domain_access.py` (TC_E1_FR030a_01…TC_E1_FR030a_03) (FR-030a)
- [X] T027 [P] Test tldextract không gọi mạng (`suffix_list_urls=()`) dưới rào chắn socket trong
  `backend/tests/unit/discovery/test_registered_domain.py` (TC_E1_FR015_01) (FR-015)
- [X] T028 [P] Test production từ chối `MockSourceAdapter`/`MockPageFetcher` trong `backend/tests/unit/discovery/test_mock_sources_guard.py`
  (TC_E1_FR016_01) (FR-016)
- [X] T029 [P] Test interface thay thế được: mỗi `adapter_type` có bản mock đạt Protocol; thay adapter không đổi kết quả nghiệp vụ trên
  cùng fixture trong `backend/tests/unit/discovery/test_source_adapter_contract.py` (TC_E1_FR006_03) (FR-006)

### Implementation cho Foundational

- [X] T030 Viết phần 1 của `backend/alembic/versions/0009_discovery.py` – mở rộng E0 (X2): `data-model.md research_sources.registered_domain`,
  `data-model.md research_sources.simhash`, `data-model.md research_sources.lifecycle_status`, `data-model.md research_sources.erased_at`,
  `data-model.md research_sources.source_policy_id`, `data-model.md research_sources.policy_verified_at`,
  `data-model.md research_evidence.redaction_status`, `data-model.md research_evidence.redaction_counts`,
  `data-model.md research_evidence.pii_engine`, `data-model.md research_evidence.lifecycle_status`, `data-model.md research_evidence.erased_at`,
  `data-model.md research_evidence.content_hash` (FR-012a, FR-013e, FR-015)
- [X] T031 Viết phần 2 của `backend/alembic/versions/0009_discovery.py` – bảng cấu hình: `data-model.md scoring_weights_versions.version`,
  `data-model.md scoring_weights_versions.weights`, `data-model.md scoring_weights_versions.coverage_threshold`,
  `data-model.md scoring_weights_versions.evidence_rules`, `data-model.md scoring_weights_versions.confidence_params`,
  `data-model.md scoring_weights_versions.dedup_params`, `data-model.md scoring_weights_versions.is_active`,
  `data-model.md scoring_weights_versions.created_by`, `data-model.md source_policies.source_key`, `data-model.md source_policies.display_name`,
  `data-model.md source_policies.adapter_type`, `data-model.md source_policies.config`, `data-model.md source_policies.tos_url`,
  `data-model.md source_policies.verified_at`, `data-model.md source_policies.verified_by`, `data-model.md source_policies.verification_note`,
  `data-model.md source_policies.allowed_access_methods`, `data-model.md source_policies.permitted_use_scope`,
  `data-model.md source_policies.known_limits`, `data-model.md source_policies.compliance_status`, `data-model.md source_policies.enabled`,
  `data-model.md source_policies.updated_by` và các CHECK bảng (FR-006c, FR-006d, FR-018)
- [X] T032 Viết phần 3 của `backend/alembic/versions/0009_discovery.py` – lượt và ngách: `data-model.md discovery_runs.job_id`,
  `data-model.md discovery_runs.market`, `data-model.md discovery_runs.research_language`, `data-model.md discovery_runs.seed_topic`,
  `data-model.md discovery_runs.max_candidates`, `data-model.md discovery_runs.budget_usd`, `data-model.md discovery_runs.time_limit_s`,
  `data-model.md discovery_runs.page_limit`, `data-model.md discovery_runs.per_domain_interval_s`, `data-model.md discovery_runs.trigger`,
  `data-model.md discovery_runs.source_policy_ids`, `data-model.md discovery_runs.weights_version_id`, `data-model.md discovery_runs.source_mode`,
  `data-model.md discovery_runs.outcome`, `data-model.md discovery_runs.stop_reason`, `data-model.md discovery_runs.metrics`,
  `data-model.md discovery_runs.idempotency_key`, `data-model.md niches.name`, `data-model.md niches.micro_niche`,
  `data-model.md niches.country`, `data-model.md niches.customer_group`, `data-model.md niches.core_problem`, `data-model.md niches.dedup_key`,
  `data-model.md niches.evidence_status`, `data-model.md niches.decision_status`, `data-model.md niches.ai_recommendation`,
  `data-model.md niches.ai_recommendation_reason`, `data-model.md niches.owner_decision_reason`, `data-model.md niches.decided_by`,
  `data-model.md niches.monetization_status`, `data-model.md niches.risk_flags`, `data-model.md niches.merged_into_id`,
  `data-model.md niches.latest_evaluation_id`, `data-model.md niche_run_links.niche_id`, `data-model.md niche_run_links.run_id`,
  `data-model.md niche_run_links.role`, `data-model.md niche_similarity.niche_a_id`, `data-model.md niche_similarity.niche_b_id`,
  `data-model.md niche_similarity.score`, `data-model.md niche_similarity.status`, `data-model.md niche_similarity.resolved_by`
  (FR-003, FR-022, FR-025, FR-029)
- [X] T033 Viết phần 4 của `backend/alembic/versions/0009_discovery.py` – phân tích: `data-model.md niche_evaluations.niche_id`,
  `data-model.md niche_evaluations.run_id`, `data-model.md niche_evaluations.weights_version_id`, `data-model.md niche_evaluations.criteria`,
  `data-model.md niche_evaluations.coverage`, `data-model.md niche_evaluations.scoring_status`, `data-model.md niche_evaluations.opportunity_score`,
  `data-model.md niche_evaluations.confidence_score`, `data-model.md niche_evaluations.confidence_components`,
  `data-model.md niche_evaluations.evidence_status`, `data-model.md niche_evaluations.independent_groups`,
  `data-model.md niche_evaluations.computed_without_ai` (trigger bất biến), `data-model.md niche_findings.niche_id`,
  `data-model.md niche_findings.field`, `data-model.md niche_findings.value`, `data-model.md niche_findings.verification_status`,
  `data-model.md niche_findings.evidence_ids`, `data-model.md pain_points.niche_id`, `data-model.md pain_points.title`,
  `data-model.md pain_points.normalized_title`, `data-model.md pain_points.severity`, `data-model.md pain_points.evidence_count`,
  `data-model.md pain_points.verification_status`, `data-model.md buyer_personas.niche_id`, `data-model.md buyer_personas.attributes`,
  `data-model.md competitors.niche_id`, `data-model.md competitors.name`, `data-model.md competitors.kind`, `data-model.md competitors.url`,
  `data-model.md competitors.strengths`, `data-model.md competitors.weaknesses`, `data-model.md niche_evidence_links.niche_id`,
  `data-model.md niche_evidence_links.evidence_id`, `data-model.md niche_evidence_links.purpose`, `data-model.md niche_evidence_links.pain_point_id`,
  `data-model.md niche_evidence_links.relevance`, `data-model.md niche_evidence_links.quality`, `data-model.md niche_evidence_links.copy_suspected`,
  `data-model.md niche_evidence_links.independence_group`, `data-model.md niche_evidence_links.counted_for_threshold`
  (FR-007, FR-008, FR-009, FR-010, FR-011, FR-013b, FR-014, FR-017, FR-020, FR-023)
- [X] T034 Viết phần 5 của `backend/alembic/versions/0009_discovery.py` – vận hành: `data-model.md domain_access_state.domain`,
  `data-model.md domain_access_state.last_request_at`, `data-model.md domain_access_state.min_interval_s`,
  `data-model.md domain_access_state.robots_status`, `data-model.md domain_access_state.robots_fetched_at`,
  `data-model.md domain_access_state.crawl_delay_s`, `data-model.md domain_access_state.blocked_until`,
  `data-model.md domain_access_state.block_reason`, `data-model.md page_fetch_log.run_id`, `data-model.md page_fetch_log.url_hash`,
  `data-model.md page_fetch_log.domain`, `data-model.md page_fetch_log.outcome`, `data-model.md page_fetch_log.reason`,
  `data-model.md page_fetch_log.http_status`, `data-model.md page_fetch_log.source_id`, `data-model.md evidence_erasure_requests.target_type`,
  `data-model.md evidence_erasure_requests.target_id`, `data-model.md evidence_erasure_requests.content_hash`,
  `data-model.md evidence_erasure_requests.reason`, `data-model.md evidence_erasure_requests.requested_by`,
  `data-model.md evidence_erasure_requests.applied_at`, `data-model.md evidence_erasure_requests.ledger_seq`,
  `data-model.md erasure_ledger_state.id`, `data-model.md erasure_ledger_state.ledger_id`, `data-model.md erasure_ledger_state.applied_seq`,
  `data-model.md erasure_ledger_state.applied_hash`, `data-model.md erasure_ledger_state.status`, `data-model.md erasure_ledger_state.last_error`
  (FR-013e, FR-013f, FR-030a, FR-032)
- [X] T035 Tạo ORM trong `backend/src/nichepilot/modules/discovery/models.py` khớp 0009; cập nhật ORM E0 trong
  `backend/src/nichepilot/modules/evidence/models.py` cho cột mới (FR-029, FR-013e)
- [X] T036 Sửa `backend/src/nichepilot/modules/evidence/service.py`: `query` mặc định lọc `data-model.md research_evidence.lifecycle_status` =
  ACTIVE (X3); tham số tường minh xem bản ghi đã xóa chỉ cho audit (FR-013e)
- [X] T037 Viết seed `backend/alembic/versions/0010_discovery_seed.py`: `data-model.md scoring_weights_versions.weights` v1 = BR-03,
  `data-model.md scoring_weights_versions.coverage_threshold` 60, `data-model.md scoring_weights_versions.evidence_rules`,
  `data-model.md scoring_weights_versions.confidence_params`, `data-model.md scoring_weights_versions.dedup_params` mặc định,
  `data-model.md scoring_weights_versions.is_active` = true; nguồn S1–S11 với `data-model.md source_policies.compliance_status` = UNVERIFIED và
  `data-model.md source_policies.enabled` = false; Model Task Profile `discovery.candidates|extract|assess|normalize` (model seed theo R-10,
  `verified = false`); dòng `data-model.md erasure_ledger_state.id` = 1, `data-model.md erasure_ledger_state.status` = OK
  (FR-006c, FR-017, FR-018, FR-028)
  *[Ghi chú triển khai: cột `domain_access_state.robots_rules` (≤ 64 KB, chỉ luật robots) bổ sung để áp dụng luật; ghi vào data-model]*
- [X] T038 Triển khai sổ xóa trong `backend/src/nichepilot/modules/discovery/erasure.py`: `LedgerWriter` (genesis, hash chain, fsync file +
  thư mục), `apply_erasure_ledger(strict)` một transaction, `ledger_health()`; cập nhật `data-model.md erasure_ledger_state.ledger_id`,
  `data-model.md erasure_ledger_state.applied_seq`, `data-model.md erasure_ledger_state.applied_hash`,
  `data-model.md erasure_ledger_state.status`, `data-model.md erasure_ledger_state.last_error` (FR-013f)
- [X] T039 Tạo CLI `backend/src/nichepilot/jobs/erasure_ledger.py` (`python -m nichepilot.jobs.erasure_ledger --strict`, exit ≠ 0 khi lỗi,
  log không chứa nội dung) và đổi lệnh service `migrate` trong `deploy/docker-compose.yml` thành `alembic upgrade head && python -m
  nichepilot.jobs.erasure_ledger --strict` (X4) (FR-013f)
- [X] T040 Sửa `deploy/scripts/restore.sh` gọi `apply_erasure_ledger --strict` ngay sau `pg_restore` (exit ≠ 0 + hướng dẫn khi lỗi); sửa
  `deploy/scripts/backup.sh` sao bản ledger kèm dump; mở rộng `backend/tests/integration/test_backup_restore.py` cho bước mới (X4)
  (FR-013f, SC-016)
- [X] T041 Khung router `backend/src/nichepilot/api/v1/discovery.py` với dependency gate ledger (chỉ endpoint dữ liệu nghiên cứu E1) và
  `GET /api/v1/discovery/status`; đăng ký router trong `backend/src/nichepilot/api/v1/__init__.py`; không sửa
  `backend/src/nichepilot/api/v1/system.py` (H1) (FR-013f, FR-026)
- [X] T042 [P] Triển khai `SourcePolicyService` (`usable_for_run()` chỉ `ALLOWED ∧ enabled`; `create_policy`; `update_policy(actor_id, …)` kiểm
  tra căn cứ, tự tắt khi rời `ALLOWED`, audit `source.created`/`source.updated`) trong
  `backend/src/nichepilot/modules/discovery/sources/policy.py` theo `data-model.md source_policies.compliance_status`,
  `data-model.md source_policies.enabled`, `data-model.md source_policies.verified_at`, `data-model.md source_policies.verified_by`,
  `data-model.md source_policies.verification_note`, `data-model.md source_policies.allowed_access_methods`,
  `data-model.md source_policies.permitted_use_scope`, `data-model.md source_policies.updated_by` (FR-006c, FR-006d, FR-036)
- [X] T043 [P] Triển khai `SearxngConfigWriter` trong `backend/src/nichepilot/modules/discovery/sources/searxng_config.py` (ghi
  `settings.yml` vào volume `searxng-config` từ nguồn `ALLOWED` đang bật, trả `requires_service_restart`) (FR-006g, FR-006d)
- [X] T044 [P] Triển khai `PiiEngine`, `RegexPhonePiiEngine` (regex + phonenumbers theo thị trường + `PersonNameRiskDetector`),
  `RedactedText`, `select_pii_engine` fail-closed với cài đặt E1 riêng `PII_ENGINE`/`PII_APPROVED_ENGINES` (không sửa `core/config.py` của
  E0) trong `backend/src/nichepilot/tools/privacy/pii.py` (FR-012a, FR-012b)
  *[Ghi chú triển khai: cài đặt E1 ở `backend/src/nichepilot/core/discovery_config.py`; kiểm tra cấu hình nguồn chuyển xuống `core/source_config.py` vì `modules` và `tools` không được import lẫn nhau]*
- [X] T045 [P] Triển khai `SpacyEnPiiEngine` (import lười, chỉ nạp khi được phê duyệt và model có sẵn; không tải mạng) trong
  `backend/src/nichepilot/tools/privacy/pii_spacy.py` (FR-012a)
- [X] T046 [P] Triển khai `SourceAdapter`, `SourceResult`, registry theo `adapter_type`, validate `data-model.md source_policies.config`
  (khóa bị cấm §1.1, giá trị dạng credential, chính sách truy cập riêng) và `data-model.md source_policies.adapter_type` trong
  `backend/src/nichepilot/tools/sources/base.py` (FR-006, FR-006g)
- [X] T047 [P] Triển khai `SearxngEngineAdapter` trong `backend/src/nichepilot/tools/sources/searxng_engine.py` (chỉ `engines=` của nguồn
  `ALLOWED`; ánh xạ lỗi `UNAVAILABLE`/`NO_RESULTS`/`RATE_LIMITED`/`ACCESS_RESTRICTED`/`NETWORK_ERROR`) (FR-006, FR-006a, FR-006f)
- [X] T048 [P] Triển khai `HttpJsonApiAdapter` (xác thực từ `os.environ[auth_env_var]` lúc gọi, không log; `AUTH_FAILED` không thử lại) trong
  `backend/src/nichepilot/tools/sources/http_json_api.py` và interface + mock `OpenDatasetAdapter`/`LicensedDataAdapter` trong
  `backend/src/nichepilot/tools/sources/dataset.py` (FR-006, FR-006g)
- [X] T049 [P] Triển khai `MockSourceAdapter`, `MockPageFetcher` (fixture T009, `data_origin = MOCK`, guard production) trong
  `backend/src/nichepilot/tools/mock_sources.py` (FR-016, FR-006)
- [X] T050 Triển khai `HttpPageFetcher` (httpx + trafilatura, bỏ `author`, giới hạn kích thước/loại/timeout, lỗi mạng → `NETWORK_ERROR`) trong
  `backend/src/nichepilot/tools/fetchers/http_fetcher.py` (FR-005, FR-031)
- [X] T051 Đăng ký tool chỉ đọc `source.query` (từ chối khác `ALLOWED`, che PII snippet), `page.fetch` (che PII trong handler – output chỉ
  `RedactedText`), `robots.fetch` (protego), `external_effect = false`, trong `backend/src/nichepilot/tools/builtin/source_query.py`,
  `backend/src/nichepilot/tools/builtin/page_fetch.py`, `backend/src/nichepilot/tools/builtin/robots_fetch.py` (FR-005, FR-006d, FR-006f, FR-012b)
- [X] T052 Triển khai `DomainAccessService` (`permit(url)`, robots cache 24 h, khoảng cách theo tên miền) trong
  `backend/src/nichepilot/modules/discovery/access.py` theo `data-model.md domain_access_state.min_interval_s`,
  `data-model.md domain_access_state.robots_status`, `data-model.md domain_access_state.robots_fetched_at`,
  `data-model.md domain_access_state.crawl_delay_s`, `data-model.md domain_access_state.last_request_at` (FR-030, FR-030a)
- [X] T053 Triển khai SimHash 64-bit, `registered_domain` (tldextract, `suffix_list_urls=()`), `content_hash` trong
  `backend/src/nichepilot/modules/discovery/fingerprint.py` cho `data-model.md research_sources.registered_domain`,
  `data-model.md research_sources.simhash`, `data-model.md research_evidence.content_hash` (FR-015)
- [X] T054 Khung `NicheDiscoveryAgent` (`AgentDefinition` job type `discovery.run`, `max_steps` 240, `max_ai_calls` 120, `timeout_s` 6000,
  `allowed_tools` = {source.query, page.fetch, robots.fetch}) với bước `preflight` (ledger) + `ensure_run` (`INSERT … ON CONFLICT
  (job_id) DO NOTHING`, `data-model.md discovery_runs.job_id`, `data-model.md discovery_runs.trigger` sao chép từ `agent_jobs.trigger`
  của E0) trong `backend/src/nichepilot/jobs/agents/niche_discovery.py`; đăng ký trong `backend/src/nichepilot/jobs/agents/__init__.py`;
  checkpoint chỉ ID/hash/bộ đếm; không sửa `jobs/runtime.py`/`jobs/scheduler.py` (H1) (FR-027, FR-029, FR-033, FR-013f)
  *[Ghi chú triển khai: Phase 2 chỉ có `preflight` + `ensure_run` + bước kết thúc tạm (`NO_COMPLIANT_SEARCH_SOURCE`); các bước nghiên cứu ở US1. Lắp ráp E1 ở `backend/src/nichepilot/discovery_wiring.py`, `services.py` chỉ thêm một lời gọi]*
- [X] T055 Pydantic schema đầu ra AI `discovery.candidates|extract|assess|normalize` (`evidence_ids` thuộc tập đã cung cấp; mức tiêu chí
  ∈ {0,25,50,75,100,null}) và DTO API trong `backend/src/nichepilot/modules/discovery/schemas.py` (FR-013, FR-014, FR-019)
  *[Ghi chú triển khai: schema `discovery.assess`/`normalize` bổ sung ở US2/US5]*

**Checkpoint**: lint-imports xanh; T012–T029 PASS; stack khởi động với ledger rỗng; restore thiếu sổ thất bại an toàn.

---

## Phase 3: User Story 1 – Khám phá ngách tự động khi chưa chọn lĩnh vực (P1) 🎯 MVP

**Goal**: tạo lượt khám phá (thị trường, không lĩnh vực), job `discovery.run` đề xuất ứng viên, tìm và thu thập nguồn, trả danh sách ngách; màn hình 1.

**Independent Test**: lượt US không lĩnh vực với AI + nguồn giả lập → ứng viên đủ trường, ≥ 3 lĩnh vực, gắn MOCK; không có nguồn `ALLOWED`
(kể cả khi có nguồn `UNVERIFIED`) → 409 `NO_COMPLIANT_SEARCH_SOURCE`.

### Tests cho User Story 1 (viết trước, phải FAIL)

- [X] T056 [P] [US1] Contract test `POST/GET /api/v1/discovery/runs`, `GET /api/v1/discovery/runs/{run_id}` (mặc định 20/$2/90 phút/300 trang;
  `Idempotency-Key`; giới hạn trường theo openapi; không có trường nào chọn nguồn chưa xác minh – trường lạ → 422) trong
  `backend/tests/contract/discovery/test_runs_api.py` (TC_E1_FR001_01, TC_E1_FR002_01, TC_E1_FR003_01) (FR-001, FR-002, FR-003)
- [X] T057 [P] [US1] Test từ chối sớm: ngân sách chưa cấu hình → `BUDGET_NOT_CONFIGURED`; vượt hạn mức ngày → `RUN_BUDGET_EXCEEDS_DAILY_LIMIT`;
  chỉ có nguồn `UNVERIFIED`/`PROHIBITED` → `NO_COMPLIANT_SEARCH_SOURCE`; không job nào được tạo, 0 lời gọi AI trong
  `backend/tests/integration/discovery/test_run_preconditions.py` (TC_E1_FR004_01, TC_E1_FR006e_01, TC_E1_SC017_02) (FR-004, FR-006e, SC-017)
- [X] T058 [P] [US1] Test luồng `discovery.run` với mock: preflight → plan_queries → check_sources → search → fetch → extract; ≥ 3 lĩnh vực khi
  không seed topic; nguồn lỗi ghi trạng thái, không tạo dữ liệu thay thế; nguồn có `policy_verified_at` trong
  `backend/tests/integration/discovery/test_discovery_run_flow.py` (TC_E1_FR002_02, TC_E1_FR006a_01, TC_E1_FR006b_01, TC_E1_SC002_01)
  (FR-002, FR-006a, FR-006b, SC-002)
- [X] T059 [P] [US1] Test nội dung ngoài chứa chỉ dẫn (prompt injection) không đổi hành vi/tool; nội dung bọc `<untrusted_content>` trong
  `backend/tests/integration/discovery/test_untrusted_content.py` (TC_E1_FR012_01) (FR-012)
- [X] T060 [P] [US1] Vitest màn hình 1 (đang tải/rỗng/lỗi, nhãn MOCK, chi phí REAL/MOCK, thông báo `NO_COMPLIANT_SEARCH_SOURCE`, không có
  tùy chọn dùng nguồn chưa xác minh) trong `frontend/tests/unit/discovery-runs-page.test.tsx` (TC_E1_FR026_01) (FR-026)
  *[Ghi chú triển khai: test view thuần bằng `react-dom/server` (`frontend/tests/unit/discovery-runs-page.test.ts`) – không thêm jsdom/testing-library]*
- [X] T061 [P] [US1] Test thu thập thật (marker `live_sources`, deselected) trong `backend/tests/live_sources/test_real_collection.py`: khi
  không có nguồn `ALLOWED` đang bật → `pytest.skip("BLOCKED: no ALLOWED source …")` được báo cáo là BLOCKED, không bao giờ PASS; khi có →
  kiểm tra ≥ 80% ứng viên có nguồn thật, 0 vượt CAPTCHA/robots (TC_E1_SC013_01) (SC-013, FR-006b)
  *[Kết quả: BLOCKED – chưa có nguồn ALLOWED; test không bao giờ báo PASS khi thiếu nguồn]*

### Implementation cho User Story 1

- [X] T062 [US1] `DiscoveryService.create_run` (kiểm tra ngân sách E0 + hạn mức ngày, nguồn `ALLOWED`; tạo job E0 idempotent; audit
  `discovery.run_created`) trong `backend/src/nichepilot/modules/discovery/service.py` theo `data-model.md discovery_runs.market`,
  `data-model.md discovery_runs.research_language`, `data-model.md discovery_runs.seed_topic`, `data-model.md discovery_runs.max_candidates`,
  `data-model.md discovery_runs.budget_usd`, `data-model.md discovery_runs.time_limit_s`, `data-model.md discovery_runs.page_limit`,
  `data-model.md discovery_runs.per_domain_interval_s`, `data-model.md discovery_runs.idempotency_key`,
  `data-model.md discovery_runs.source_policy_ids`, `data-model.md discovery_runs.weights_version_id`,
  `data-model.md discovery_runs.source_mode` (FR-001, FR-002, FR-003, FR-004, FR-006e)
  *[Ghi chú triển khai: `create_run_record` dùng chung cho API và `ensure_run` của agent; API tái dùng `create_job` của E0 (idempotency, audit, hàng đợi)]*
- [X] T063 [US1] Bước `plan_queries` (task type `discovery.candidates` qua AI Gateway) và `check_sources` (`usable_for_run()`; rỗng →
  `NO_COMPLIANT_SEARCH_SOURCE`) trong `backend/src/nichepilot/jobs/agents/niche_discovery.py` (FR-002, FR-006d, FR-006e)
  *[Ghi chú triển khai: `JobContext.call_ai` của E0 thêm tham số tùy chọn `task_type` (mặc định = task type của agent – hành vi E0 không đổi) để mỗi bước dùng Model Task Profile riêng (X6)]*
- [X] T064 [US1] Bước `search` và `fetch` (`source.query`; `DomainAccessService.permit` → `page.fetch`; lưu nguồn/bằng chứng đã che với
  `data-model.md research_sources.source_policy_id`, `data-model.md research_sources.policy_verified_at`,
  `data-model.md research_evidence.redaction_status`, `data-model.md research_evidence.redaction_counts`, `data-model.md research_evidence.pii_engine`;
  ghi `data-model.md page_fetch_log.run_id`, `data-model.md page_fetch_log.url_hash`, `data-model.md page_fetch_log.domain`,
  `data-model.md page_fetch_log.outcome`, `data-model.md page_fetch_log.reason`, `data-model.md page_fetch_log.http_status`,
  `data-model.md page_fetch_log.source_id`) trong `backend/src/nichepilot/jobs/agents/niche_discovery.py` (FR-005, FR-006a, FR-012a, FR-031)
- [X] T065 [US1] Bước `extract` cơ bản (task type `discovery.extract`, chỉ nhận `RedactedText` REDACTED, bọc `<untrusted_content>`) tạo ngách
  theo `data-model.md niches.name`, `data-model.md niches.micro_niche`, `data-model.md niches.country`, `data-model.md niches.customer_group`,
  `data-model.md niches.core_problem`, liên kết `data-model.md niche_run_links.role` trong `backend/src/nichepilot/jobs/agents/niche_discovery.py`
  (FR-002, FR-012, FR-016)
- [X] T066 [US1] Endpoint `POST/GET /api/v1/discovery/runs`, `GET /api/v1/discovery/runs/{run_id}` trong
  `backend/src/nichepilot/api/v1/discovery.py` (FR-001, FR-003, FR-026)
- [X] T067 [P] [US1] Kiểu API và hook TanStack Query trong `frontend/src/api/types.ts`, `frontend/src/api/discovery.ts` (FR-026)
- [X] T068 [US1] Màn hình 1 `frontend/src/pages/discovery/DiscoveryRunsPage.tsx` (lịch sử, trạng thái, outcome + lý do, chi phí REAL/MOCK,
  tạo lượt, chạy/tạm dừng/tiếp tục/hủy qua `/api/v1/jobs/*`) + route trong `frontend/src/app/router.tsx` (FR-026, FR-027, FR-032)

**Checkpoint**: US1 chạy độc lập với mock; quickstart §1–§2 PASS.

---

## Phase 4: User Story 2 – Pain point, buyer persona và bằng chứng có nguồn (P1)

**Goal**: pain point, persona, giải pháp, đối thủ, monetization có bằng chứng; ngưỡng; PII; xóa bằng chứng; màn hình 3 phần bằng chứng.

**Independent Test**: lượt giả lập dữ liệu cố định → mỗi pain point có ≥ 1 bằng chứng đủ trường; thiếu nguồn độc lập → `INSUFFICIENT_EVIDENCE`;
xóa bằng chứng → tính lại; restore backup cũ → vẫn ERASED.

### Tests cho User Story 2 (viết trước, phải FAIL)

- [x] T069 [P] [US2] Test ngưỡng + nhóm độc lập (eTLD+1, SimHash ≤ 3, `copy_suspected`, relevance/quality, `NEEDS_REVIEW` không tính, MOCK tách;
  bằng chứng thiếu URL/trích đoạn/thời điểm/trạng thái không tính) theo scoring-rubric §1 trong
  `backend/tests/unit/discovery/test_evidence_rules.py` (TC_E1_FR013a_01, TC_E1_FR013b_01…TC_E1_FR013b_04, TC_E1_FR015_02, TC_E1_SC003a_01)
  (FR-013a, FR-013b, FR-015, SC-003a)
- [x] T070 [P] [US2] Test `INSUFFICIENT_EVIDENCE` được lưu cùng bằng chứng, không vào xếp hạng, không đếm là ngách hợp lệ trong
  `backend/tests/integration/discovery/test_insufficient_evidence.py` (TC_E1_FR013c_01) (FR-013c)
- [x] T071 [P] [US2] Test đạt ngưỡng ≠ sinh lợi: ngách `EVIDENCE_SUFFICIENT` + `MONETIZATION_UNVERIFIED` có trong bảng cơ hội nhưng không có trong
  danh sách affiliate; `evidence_status` không phụ thuộc Opportunity; báo cáo/API kèm `disclaimer_key` trong
  `backend/tests/integration/discovery/test_evidence_not_profitability.py` (TC_E1_FR013d_01) (FR-013d)
- [x] T072 [P] [US2] Test trích xuất: pain point + severity, persona 5 thuộc tính có trạng thái, giải pháp/khoảng trống, đối thủ, monetization,
  kênh; `evidence_ids` lạ → đầu ra bị loại; `UNKNOWN` không có giá trị; `CONFLICTING` lưu mọi giá trị (QA-05) trong
  `backend/tests/integration/discovery/test_extraction.py` (TC_E1_FR007_01, TC_E1_FR008_01, TC_E1_FR009_01, TC_E1_FR010_01, TC_E1_FR011_01,
  TC_E1_FR013_01, TC_E1_FR014_01, TC_E1_SC004_01, TC_E1_SC008_01) (FR-007, FR-008, FR-009, FR-010, FR-011, FR-013, FR-014, SC-004, SC-008)
- [x] T073 [P] [US2] Test đầu-cuối PII: sau lượt mock với trang PII, 0 mẫu PII trong DB (bảng E1, `tool_calls`, audit), log, checkpoint, prompt
  MockAIProvider; đoạn `NEEDS_REVIEW` không có trong prompt trong `backend/tests/integration/discovery/test_pii_end_to_end.py`
  (TC_E1_FR012a_07, TC_E1_FR012b_03, TC_E1_FR012c_01, TC_E1_SC016_02) (FR-012a, FR-012b, FR-012c, SC-016)
- [x] T074 [P] [US2] Contract + integration test `POST /api/v1/evidence/{evidence_id}/erase` (EVIDENCE/SOURCE; 409 khi đã xóa; audit không nội
  dung; ngách đủ đúng 2 nhóm → `INSUFFICIENT_EVIDENCE`; không thu thập lại cùng `content_hash`) trong
  `backend/tests/contract/discovery/test_erasure_api.py` (TC_E1_FR013e_02…TC_E1_FR013e_04) (FR-013e)
- [x] T075 [P] [US2] Test restore: backup trước khi xóa → restore → `apply --strict` → vẫn ERASED, API không trả trích đoạn; sổ OK + DB lỗi →
  lần áp dụng sau hoàn tất trong `backend/tests/integration/discovery/test_erasure_restore.py` (TC_E1_FR013f_09, TC_E1_FR013f_10,
  TC_E1_SC016_03) (FR-013f, SC-016)
- [x] T076 [P] [US2] Test xóa khi lượt đang chạy: xóa bằng chứng giữa `fetch` và `extract` → không xuất hiện trong prompt `extract`/`assess`, không
  tính ở `evaluate`; URL trùng `content_hash` đã xóa → `ERASED_CONTENT` trong `backend/tests/integration/discovery/test_erasure_during_run.py`
  (TC_E1_FR013e_05) (FR-013e)
- [x] T077 [P] [US2] Contract test `GET /api/v1/niches/{niche_id}` (16 trường BR-07, `redaction_status`, `policy_verified_at`) trong
  `backend/tests/contract/discovery/test_niche_detail_api.py` (TC_E1_FR023_01, TC_E1_SC003_01) (FR-023, SC-003)
- [x] T078 [P] [US2] Vitest màn hình 3 phần pain point/persona/bằng chứng (đang tải/rỗng/lỗi, nhãn MOCK) trong
  `frontend/tests/unit/niche-detail-page.test.ts` (TC_E1_FR026_02) (FR-026)

### Implementation cho User Story 2

- [x] T079 [US2] Quy tắc ngưỡng + nhóm độc lập (thuần) trong `backend/src/nichepilot/modules/discovery/evidence_rules.py` theo
  `data-model.md niche_evidence_links.purpose`, `data-model.md niche_evidence_links.pain_point_id`, `data-model.md niche_evidence_links.relevance`,
  `data-model.md niche_evidence_links.quality`, `data-model.md niche_evidence_links.copy_suspected`,
  `data-model.md niche_evidence_links.independence_group`, `data-model.md niche_evidence_links.counted_for_threshold` (FR-013a, FR-013b, FR-015)
- [x] T080 [US2] Hoàn thiện `extract` + bước `assess` lưu kết quả theo `data-model.md pain_points.title`, `data-model.md pain_points.normalized_title`,
  `data-model.md pain_points.severity`, `data-model.md pain_points.evidence_count`, `data-model.md pain_points.verification_status`,
  `data-model.md buyer_personas.attributes`, `data-model.md competitors.name`, `data-model.md competitors.kind`, `data-model.md competitors.url`,
  `data-model.md competitors.strengths`, `data-model.md competitors.weaknesses`, `data-model.md niche_findings.field`,
  `data-model.md niche_findings.value`, `data-model.md niche_findings.verification_status`, `data-model.md niche_findings.evidence_ids`,
  `data-model.md niche_evidence_links.niche_id`, `data-model.md niche_evidence_links.evidence_id` trong
  `backend/src/nichepilot/jobs/agents/niche_discovery.py` và `backend/src/nichepilot/modules/discovery/service.py`
  (FR-007, FR-008, FR-009, FR-010, FR-011, FR-013, FR-014)
- [x] T081 [US2] Đọc lại bằng chứng `ACTIVE` trước mỗi bước `extract`/`assess`/`evaluate`; gán `data-model.md niches.evidence_status` trong
  `backend/src/nichepilot/modules/discovery/service.py` (FR-013c, FR-013d, FR-013e)
- [x] T082 [US2] `EvidenceErasureService.erase` (ghi sổ → transaction → job `discovery.recompute`) theo
  `data-model.md evidence_erasure_requests.target_type`, `data-model.md evidence_erasure_requests.target_id`,
  `data-model.md evidence_erasure_requests.content_hash`, `data-model.md evidence_erasure_requests.reason`,
  `data-model.md evidence_erasure_requests.requested_by`, `data-model.md evidence_erasure_requests.applied_at`,
  `data-model.md evidence_erasure_requests.ledger_seq`, `data-model.md research_sources.lifecycle_status`,
  `data-model.md research_sources.erased_at`, `data-model.md research_evidence.lifecycle_status`, `data-model.md research_evidence.erased_at`
  trong `backend/src/nichepilot/modules/discovery/erasure.py`; job type `discovery.recompute` (0 lời gọi AI) trong
  `backend/src/nichepilot/jobs/agents/niche_reevaluate.py` (FR-013e, FR-013f)
- [x] T083 [US2] Endpoint `POST /api/v1/evidence/{evidence_id}/erase`, `GET /api/v1/niches/{niche_id}` trong
  `backend/src/nichepilot/api/v1/discovery.py` (FR-013e, FR-023)
- [x] T084 [US2] Màn hình 3 (pain point, persona, giải pháp, đối thủ, bằng chứng + nguồn, nút xóa bằng chứng có xác nhận) trong
  `frontend/src/pages/discovery/NicheDetailPage.tsx` (FR-026, FR-013e)

**Checkpoint**: US2 độc lập với fixture; quickstart §6 PASS (gồm bảng thất bại an toàn).

---

## Phase 5: User Story 3 – Chấm điểm cơ hội và độ tin cậy, xếp hạng ngách (P1)

**Goal**: Opportunity/Coverage/Confidence tách biệt, phiên bản trọng số, ba danh sách; màn hình 2 và lý do chấm điểm.

**Independent Test**: bộ đánh giá cố định → khớp ví dụ tính tay scoring-rubric §3 (60,71 / 66,00); Coverage < 60 →
`INSUFFICIENT_SCORING_DATA`; đổi trọng số → tính lại 0 lời gọi AI.

### Tests cho User Story 3 (viết trước, phải FAIL)

- [ ] T085 [P] [US3] Test `compute_opportunity` (đủ 6; thiếu 1; nhiều tiêu chí thiếu; Coverage đúng 60 và dưới 60; CONFLICTING; không gán 0/100
  cho UNKNOWN; ví dụ 60,71) trong `backend/tests/unit/discovery/test_opportunity.py` (TC_E1_FR017_01, TC_E1_FR019_01…TC_E1_FR019_03,
  TC_E1_FR019a_01, TC_E1_SC005_01, TC_E1_SC005a_01) (FR-017, FR-019, FR-019a, SC-005, SC-005a)
- [ ] T086 [P] [US3] Test `compute_confidence` (ví dụ 66,00; trần 30 khi INSUFFICIENT_EVIDENCE; chữ ký không có Opportunity) trong
  `backend/tests/unit/discovery/test_confidence.py` (TC_E1_FR020_01, TC_E1_FR020_02) (FR-020)
- [ ] T087 [P] [US3] Test search volume thấp không làm giảm điểm/không loại ngách trong `backend/tests/unit/discovery/test_search_volume.py`
  (TC_E1_FR021_01) (FR-021)
- [ ] T088 [P] [US3] Contract test `GET/POST /api/v1/scoring/weights` (`WEIGHTS_INVALID`; bản cũ không đổi; `recompute_existing` → 0 lời gọi AI)
  trong `backend/tests/contract/discovery/test_weights_api.py` (TC_E1_FR018_01, TC_E1_FR018_02) (FR-018)
- [ ] T089 [P] [US3] Contract test `GET /api/v1/niches?list=research|affiliate|needs_research` (scoring-rubric §4; MOCK ẩn mặc định;
  `disclaimer_key`) trong `backend/tests/contract/discovery/test_ranking_api.py` (TC_E1_FR019b_01, TC_E1_FR019c_01, TC_E1_FR016_02,
  TC_E1_SC009_01) (FR-019b, FR-019c, FR-016, SC-009)
- [ ] T090 [P] [US3] Test cờ rủi ro tuân thủ cho lĩnh vực nhạy cảm trong `backend/tests/unit/discovery/test_risk_flags.py` (TC_E1_FR035_01) (FR-035)
- [ ] T091 [P] [US3] Vitest màn hình 2 (3 tab, Opportunity/Confidence/Coverage, trạng thái xác minh, Monetization, chú thích, đang tải/rỗng/lỗi)
  trong `frontend/tests/unit/niche-ranking-page.test.tsx` (TC_E1_FR026_03) (FR-026)
- [ ] T092 [P] [US3] Performance test (marker `perf`): `GET /api/v1/niches` p95 < 500 ms với 5.000 ngách giả lập; `discovery.recompute` ≤ 60 s cho
  1.000 ngách, 0 lời gọi AI trong `backend/tests/perf/discovery/test_discovery_perf.py` (TC_E1_FR024_02, TC_E1_FR018_03) (FR-024, FR-018)

### Implementation cho User Story 3

- [ ] T093 [P] [US3] `compute_opportunity` trong `backend/src/nichepilot/modules/discovery/scoring/opportunity.py` theo
  `data-model.md niche_evaluations.criteria`, `data-model.md niche_evaluations.coverage`, `data-model.md niche_evaluations.scoring_status`,
  `data-model.md niche_evaluations.opportunity_score` (FR-017, FR-019, FR-019a, FR-021)
- [ ] T094 [P] [US3] `compute_confidence` trong `backend/src/nichepilot/modules/discovery/scoring/confidence.py` theo
  `data-model.md niche_evaluations.confidence_score`, `data-model.md niche_evaluations.confidence_components`,
  `data-model.md niche_evaluations.evidence_status`, `data-model.md niche_evaluations.independent_groups` (FR-020)
- [ ] T095 [US3] `EvaluationService` (bước `evaluate` + `recompute`) trong `backend/src/nichepilot/modules/discovery/evaluation.py` theo
  `data-model.md niche_evaluations.niche_id`, `data-model.md niche_evaluations.run_id`, `data-model.md niche_evaluations.weights_version_id`,
  `data-model.md niche_evaluations.computed_without_ai`, `data-model.md niches.latest_evaluation_id`, `data-model.md niches.monetization_status`,
  `data-model.md niches.risk_flags`, `data-model.md niches.ai_recommendation`, `data-model.md niches.ai_recommendation_reason`
  (FR-017, FR-019b, FR-020, FR-035)
- [ ] T096 [US3] `WeightsService` (tổng 100, phiên bản mới active, audit `scoring.weights_version_created`) trong
  `backend/src/nichepilot/modules/discovery/weights.py` theo `data-model.md scoring_weights_versions.version`,
  `data-model.md scoring_weights_versions.weights`, `data-model.md scoring_weights_versions.coverage_threshold`,
  `data-model.md scoring_weights_versions.evidence_rules`, `data-model.md scoring_weights_versions.confidence_params`,
  `data-model.md scoring_weights_versions.dedup_params`, `data-model.md scoring_weights_versions.is_active`,
  `data-model.md scoring_weights_versions.created_by` (FR-018, FR-036)
- [ ] T097 [US3] Ba danh sách xếp hạng theo scoring-rubric §4 trong `backend/src/nichepilot/modules/discovery/ranking.py` (FR-013d, FR-019b, FR-024)
- [ ] T098 [US3] Endpoint `GET/POST /api/v1/scoring/weights`, `GET /api/v1/niches`, `GET /api/v1/niches/{niche_id}/evaluations` trong
  `backend/src/nichepilot/api/v1/discovery.py` (FR-018, FR-024, FR-034)
- [ ] T099 [US3] Màn hình 2 `frontend/src/pages/discovery/NicheRankingPage.tsx` và phần lý do chấm điểm trong
  `frontend/src/pages/discovery/NicheDetailPage.tsx` (FR-026, FR-019c)

**Checkpoint**: US3 độc lập; quickstart §5 bước 1, 2, 4 và §6c PASS.

---

## Phase 6: User Story 4 – Kiểm soát chi phí và độ bền của lượt khám phá (P1)

**Goal**: giới hạn ngân sách AI, thời gian, số trang, tốc độ; dừng sớm; checkpoint/tiếp tục; lỗi mạng/DB; metrics; quản lý nguồn.

**Independent Test**: hạn mức nhỏ → `PAUSED_BUDGET`; page/time limit → `PARTIAL_COMPLETED` đúng lý do; kill worker/mất DB → tiếp tục không trùng;
mất mạng → `SOURCES_UNAVAILABLE`; bật nguồn chưa `ALLOWED` → `SOURCE_NOT_ALLOWED`.

### Tests cho User Story 4 (viết trước, phải FAIL)

- [ ] T100 [P] [US4] Test ngân sách: mọi lời gọi qua Gateway + giữ chỗ; vượt lượt/ngày/tháng → `PAUSED_BUDGET`, không lời gọi vượt; không tự tăng
  ngân sách trong `backend/tests/integration/discovery/test_run_budget.py` (TC_E1_FR028_01, TC_E1_FR030e_01, TC_E1_SC006_01, TC_E1_SC012_01)
  (FR-028, FR-030e, SC-006, SC-012)
- [ ] T101 [P] [US4] Test giới hạn: `page_limit`, `time_limit` (tạm dừng không tính), dừng sớm, phân bổ trang, outcome + stop_reason; chạm 90 phút
  khi đang chờ lời gọi AI → không gửi lời gọi mới, `PARTIAL_COMPLETED/TIME_LIMIT_REACHED` trong
  `backend/tests/integration/discovery/test_run_limits.py` (TC_E1_FR030b_01, TC_E1_FR030c_01, TC_E1_FR030d_01, TC_E1_FR030d_02,
  TC_E1_SC015_01) (FR-030b, FR-030c, FR-030d, SC-015)
- [ ] T102 [P] [US4] Test tốc độ và lỗi: khoảng cách cùng tên miền ≥ trần/Crawl-delay; 429/503 thử lại ≤ 2 lần theo Retry-After rồi
  `RATE_LIMITED`; Retry-After dài hơn thời gian còn lại → bỏ tên miền ngay; trang lỗi bỏ qua không dừng lượt (QA-06, QA-07) trong
  `backend/tests/integration/discovery/test_rate_and_errors.py` (TC_E1_FR030_01, TC_E1_FR030_02, TC_E1_FR030a_04, TC_E1_FR031_02,
  TC_E1_SC015_02) (FR-030, FR-030a, FR-031, SC-015)
- [ ] T103 [P] [US4] Test bền: pause/resume/cancel qua API job E0; kill worker giữa `fetch` → tiếp tục từ checkpoint, 0 trùng ngách/pain point/nguồn/
  `page_fetch_log` trong `backend/tests/integration/discovery/test_run_resume.py` (TC_E1_FR027_01, TC_E1_FR029_02, TC_E1_SC007_01)
  (FR-027, FR-029, SC-007)
- [ ] T104 [P] [US4] Test lỗi hạ tầng khi đang chạy (C5): mất kết nối PostgreSQL giữa bước → worker E0 khởi động lại, tiếp tục từ checkpoint, 0
  trùng; mất Internet (adapter/fetcher ném lỗi mạng) → trang `NETWORK_ERROR`, mọi nguồn lỗi → `PARTIAL_COMPLETED/SOURCES_UNAVAILABLE`, không
  dữ liệu thay thế; AI provider không kết nối được → xử lý theo E0 (thử lại/UNCERTAIN) trong
  `backend/tests/integration/discovery/test_infra_failures.py` (TC_E1_FR027_02, TC_E1_FR006a_02, TC_E1_SC008_02) (FR-027, FR-006a, SC-008)
- [ ] T105 [P] [US4] Test metrics FR-032 (trang theo kết quả/lý do, `needs_review_segments` của `data-model.md discovery_runs.metrics`, nguồn độc lập, lời gọi AI, chi phí REAL/MOCK) trong
  `backend/tests/integration/discovery/test_run_metrics.py` (TC_E1_FR032_01) (FR-032)
- [ ] T106 [P] [US4] Contract test `GET/POST /api/v1/sources`, `PUT /api/v1/sources/{source_id}`: bật nguồn `UNVERIFIED`/`PROHIBITED` → 409
  `SOURCE_NOT_ALLOWED`; trường lạ (ví dụ cờ xác nhận cảnh báo) → 422; `ALLOWED` thiếu căn cứ → 422 `SOURCE_VERIFICATION_INCOMPLETE`; rời
  `ALLOWED` → tự tắt; `SOURCE_CONFIG_INVALID`; `requires_service_restart`; audit trước/sau; không trả giá trị biến môi trường trong
  `backend/tests/contract/discovery/test_sources_api.py` (TC_E1_FR006c_04, TC_E1_FR006d_03, TC_E1_FR006g_03, TC_E1_FR036_01, TC_E1_SC017_03)
  (FR-006c, FR-006d, FR-006g, FR-036, SC-017)

### Implementation cho User Story 4

- [ ] T107 [US4] Bộ đếm thời gian/trang trong checkpoint, kiểm tra giới hạn trước mỗi `fetch`, phân bổ trang, dừng sớm, `finalize` ghi
  `data-model.md discovery_runs.outcome`, `data-model.md discovery_runs.stop_reason`, `data-model.md discovery_runs.metrics` trong
  `backend/src/nichepilot/jobs/agents/niche_discovery.py` (FR-030b, FR-030c, FR-030d, FR-032)
- [ ] T108 [US4] Thử lại có giới hạn theo `Retry-After`, bỏ tên miền khi vượt thời gian còn lại, ghi `data-model.md domain_access_state.blocked_until`,
  `data-model.md domain_access_state.block_reason` trong `backend/src/nichepilot/modules/discovery/access.py` (FR-030, FR-031)
- [ ] T109 [US4] Endpoint `GET/POST /api/v1/sources`, `PUT /api/v1/sources/{source_id}` (gọi `SourcePolicyService` + `SearxngConfigWriter`;
  `data-model.md source_policies.verified_by` = người gọi) trong `backend/src/nichepilot/api/v1/discovery.py` (FR-006c, FR-006d, FR-006g, FR-036)
- [ ] T110 [US4] Màn hình quản lý nguồn (danh sách, trạng thái, form xác minh đủ mục source-verification.md §2; nút bật chỉ hiển thị cho nguồn
  `ALLOWED`; lưu ý khởi động lại SearXNG) trong `frontend/src/pages/discovery/SourcesPage.tsx` + route trong `frontend/src/app/router.tsx`
  (FR-006c, FR-006d, FR-026)

**Checkpoint**: quickstart §4, §6d PASS với mock.

---

## Phase 7: User Story 5 – Phát hiện ngách trùng/tương đồng (P2)

**Goal**: trùng chắc chắn gộp, có thể tương đồng chờ chủ sở hữu. **Independent Test**: bộ cặp có nhãn ≥ 90% đúng, 0 gộp nhầm.

- [ ] T111 [P] [US5] Bộ ≥ 40 cặp ngách có nhãn tự soạn trong `backend/tests/fixtures/discovery/dedup_pairs.json` và test độ chính xác ≥ 90%, 0 gộp
  nhầm trong `backend/tests/unit/discovery/test_dedup.py` (TC_E1_FR022_01, TC_E1_SC010_01) (FR-022, SC-010)
- [ ] T112 [P] [US5] Contract test `GET /api/v1/niche-similarities`, `PUT /api/v1/niche-similarities/{similarity_id}` (gộp giữ `keep_niche_id`,
  audit `niche.similarity_resolved`) trong `backend/tests/contract/discovery/test_similarity_api.py` (TC_E1_FR022_02) (FR-022)
- [ ] T113 [US5] `similarity()` + bước `dedup` (task type `discovery.normalize`; ngưỡng từ `data-model.md scoring_weights_versions.dedup_params`)
  ghi `data-model.md niche_similarity.niche_a_id`, `data-model.md niche_similarity.niche_b_id`, `data-model.md niche_similarity.score`,
  `data-model.md niche_similarity.status`, `data-model.md niches.merged_into_id`, `data-model.md niches.dedup_key` trong
  `backend/src/nichepilot/modules/discovery/dedup.py` và `backend/src/nichepilot/jobs/agents/niche_discovery.py` (FR-022, FR-029)
- [ ] T114 [US5] Endpoint similarity (ghi `data-model.md niche_similarity.resolved_by`) trong `backend/src/nichepilot/api/v1/discovery.py` và
  cờ `has_possible_duplicate` + hộp xác nhận trong `frontend/src/pages/discovery/NicheDetailPage.tsx` (FR-022, FR-026)

---

## Phase 8: User Story 6 – Báo cáo xếp hạng và quyết định của chủ sở hữu (P2)

**Goal**: báo cáo theo lượt (JSON/Markdown, ba danh sách), AI đề xuất + lý do, chủ sở hữu ghi quyết định.

- [ ] T115 [P] [US6] Contract test `GET /api/v1/discovery/runs/{run_id}/report` (json, markdown; ba danh sách; `disclaimer_key`; MOCK loại khỏi
  báo cáo mặc định) trong `backend/tests/contract/discovery/test_report_api.py` (TC_E1_FR024_01, TC_E1_SC009_02) (FR-024, SC-009)
- [ ] T116 [P] [US6] Contract test `PUT /api/v1/niches/{niche_id}/decision` (5 trạng thái, lý do, audit `niche.decision_recorded`, AI không tự đổi)
  trong `backend/tests/contract/discovery/test_decision_api.py` (TC_E1_FR025_01) (FR-025)
- [ ] T117 [US6] Sinh báo cáo JSON/Markdown trong `backend/src/nichepilot/modules/discovery/report.py` + endpoint trong
  `backend/src/nichepilot/api/v1/discovery.py` (FR-024, FR-019c)
- [ ] T118 [US6] `record_decision` theo `data-model.md niches.decision_status`, `data-model.md niches.owner_decision_reason`,
  `data-model.md niches.decided_by` trong `backend/src/nichepilot/modules/discovery/service.py` + endpoint `PUT /api/v1/niches/{niche_id}/decision`
  (FR-025, FR-036)
- [ ] T119 [US6] Nút ghi quyết định + đề xuất AI trong `frontend/src/pages/discovery/NicheDetailPage.tsx`; tải báo cáo Markdown trong
  `frontend/src/pages/discovery/DiscoveryRunsPage.tsx` (FR-025, FR-026)

---

## Phase 9: User Story 7 – Nghiên cứu theo lịch và đánh giá lại (P3)

**Goal**: lịch khám phá định kỳ (nguồn `ALLOWED`), đánh giá lại ngách đang theo dõi; không sửa Scheduler E0.

- [ ] T120 [P] [US7] Test lịch E0 với `job_type = discovery.run`: đúng 1 lượt/mốc; `ensure_run` tạo đúng một `discovery_runs` kể cả khi job được
  giao lại (idempotent); `trigger = SCHEDULE` lấy từ `agent_jobs`; chỉ nguồn `ALLOWED`; không nguồn → `NO_COMPLIANT_SEARCH_SOURCE`; ngân sách
  chưa cấu hình → lịch bị từ chối theo E0 trong `backend/tests/integration/discovery/test_discovery_schedule.py` (TC_E1_FR033_01,
  TC_E1_FR033_02, TC_E1_SC017_04) (FR-033, SC-017)
- [ ] T121 [P] [US7] Test `POST /api/v1/niches/{niche_id}/reevaluate` + lịch `discovery.reevaluate`: đánh giá mới, giữ đánh giá cũ, so sánh thay đổi,
  giữ chỗ ngân sách trong `backend/tests/integration/discovery/test_reevaluate.py` (TC_E1_FR034_01) (FR-034)
- [ ] T122 [US7] Xử lý lượt theo lịch trong `preflight`/`ensure_run` (đọc `agent_jobs.trigger`, `agent_jobs.schedule_id`; tham số lượt mặc định
  khi input lịch thiếu; ghi `data-model.md discovery_runs.job_id`, `data-model.md discovery_runs.trigger`) trong
  `backend/src/nichepilot/jobs/agents/niche_discovery.py` – không sửa `backend/src/nichepilot/jobs/scheduler.py` (FR-033, FR-029)
- [ ] T123 [US7] `NicheReevaluationAgent` (job type `discovery.reevaluate`, max_steps 60, max_ai_calls 20, có `preflight`; ghi
  `data-model.md niche_run_links.role` = REEVALUATED) trong `backend/src/nichepilot/jobs/agents/niche_reevaluate.py` + endpoint
  `POST /api/v1/niches/{niche_id}/reevaluate` (FR-034)

---

## Phase 10: Polish & Cross-Cutting

- [ ] T124 [P] Playwright E2E "tạo lượt (mock) ≤ 3 thao tác → bảng xếp hạng → chi tiết → ghi quyết định" VI/EN trong
  `frontend/tests/e2e/discovery.spec.ts` (TC_E1_SC014_01, TC_E1_SC001_01) (SC-014, SC-001)
- [ ] T125 [P] Test kiến trúc trong `backend/tests/unit/discovery/test_architecture_rules.py`: không model ID hard-code trong
  `modules/discovery`/`jobs/agents/niche_*`; hàm tạo prompt chỉ nhận `RedactedText` REDACTED; không import `crawl4ai`, `playwright_stealth`,
  `patchright` ở bất kỳ đâu; chỉ `update_policy` ghi `compliance_status`/`enabled`; không có định danh `include_unverified`/`acknowledge_warning`
  trong mã E1 (TC_E1_FR028_02, TC_E1_FR012b_04, TC_E1_FR006d_04, TC_E1_FR006f_02) (FR-028, FR-012b, FR-006d, FR-006f)
- [ ] T126 [P] Test i18n: 100% khóa `discovery.*` có VI/EN, không chuỗi cứng trong JSX (mở rộng `frontend/tests/unit/i18n-keys.test.ts`)
  (TC_E1_FR026_04) (FR-026)
- [ ] T127 [P] Tài liệu vận hành `docs/operations/discovery.md` (xác minh/bật nguồn chỉ khi `ALLOWED`, khởi động lại SearXNG, PII engine và danh
  sách phê duyệt, xóa bằng chứng, ledger và restore thất bại an toàn, profile `browser-fetcher`); cập nhật `docs/operations/backup-restore.md`,
  `docs/operations/troubleshooting.md` (FR-006c, FR-012a, FR-013f)
- [ ] T128 [P] Profile tùy chọn `browser-fetcher`: `PlaywrightPageFetcher` (không stealth) trong
  `backend/src/nichepilot/tools/fetchers/playwright_fetcher.py`, image `deploy/browser-fetcher/Dockerfile`; test marker `browser` với trang
  fixture cần JS trong `backend/tests/integration/discovery/test_playwright_fetcher.py`; đo RAM khi bật (TC_E1_FR031_03) (FR-005, FR-006f, FR-031)
- [ ] T129 Chạy toàn bộ quality gate (ruff, mypy, lint-imports, pytest, frontend lint/typecheck/test, E2E, `check_secrets.py`,
  `traceability_report.py --strict`), đo tài nguyên stack nghỉ (`docker stats`) và ghi PASS/FAIL/NOT_TESTED/BLOCKED vào
  `specs/002-niche-discovery/checklists/verification.md` (TC_E1_SC011_01) (SC-011)
- [ ] T130 Chạy quickstart §1–§8 với mock trên stack Docker thật; ghi bằng chứng vào `specs/002-niche-discovery/checklists/verification.md`;
  §3 và SC-013 ghi `BLOCKED – chờ xác minh nguồn` (không phải lỗi implementation) (SC-011, SC-013)

---

## Dependencies & Execution Order (đồ thị có hướng, không vòng)

```text
Phase 1 (T001–T011)
  └─> Phase 2 tests (T012–T029) ─> Phase 2 impl (T030→T031→T032→T033→T034 cùng file migration, tuần tự) ─> T035 ─> T036, T037
        T038 ─> T039 ─> T040 ; T038 ─> T041
        T042, T043, T044, T045, T046, T047, T048, T049 (song song, sau T035)
        T050 ─> T051 (cần T044, T046) ; T052, T053 (sau T035) ; T054 (cần T038, T042, T051, T052) ; T055
  └─> US1 (T056–T068) ─> US2 (T069–T084) ─> US3 (T085–T099) ─> US4 (T100–T110)
        US5 (T111–T114) cần US1–US3 ; US6 (T115–T119) cần US3 ; US7 (T120–T123) cần US1 (+ US3 cho đánh giá lại)
  └─> Polish (T124–T130) ; T128 tùy chọn, không chặn phát hành
```

Phụ thuộc chỉ đi theo chiều Setup → Foundational → US theo thứ tự ưu tiên → Polish; không task nào phụ thuộc task phía sau → không có
phụ thuộc vòng. Phân lớp mã giữ hợp đồng import-linter của E0 (`api > jobs > (ai : tools : modules) > core`).

## Parallel Example

```text
# Phase 2 – test song song:   T013 T014 T015 T018 T019 T020 T021 T022 T131 T023 T026 T027 T028 T029
# Phase 2 – triển khai song song (khác file): T042 T043 T044 T045 T046 T047 T048 T049
# US3: T085 T086 T087 T088 T089 T090 T091 T092 → T093 ∥ T094 → T095 → T096 → T097 → T098 → T099
```

## Implementation Strategy

1. **MVP** = Phase 1 + 2 + US1 (lượt với mock, từ chối đúng khi không có nguồn `ALLOWED`, ledger fail-safe, PII fail-closed).
2. US2 + US3 → AC-05/06/07 ở mức mock; US4 → độ bền/chi phí; US5–US7 sau.
3. Dữ liệu thật chỉ sau khi chủ sở hữu xác minh nguồn (source-verification.md); SC-013 giữ `BLOCKED` tới khi đó.
4. Mỗi phase kết thúc bằng checkpoint và commit riêng; không đánh dấu PASS cho test chưa chạy.
