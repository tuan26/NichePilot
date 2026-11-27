---

description: "Danh sách công việc triển khai E2 — Product & Affiliate Discovery"
---

# Tasks: E2 — Product & Affiliate Discovery

**Input**: `/specs/003-product-affiliate-discovery/` – plan.md, spec.md (Clarifications 2026-11-27, 2026-11-27 (b)), research.md (R-01…R-11),
data-model.md, contracts/ (openapi.yaml, internal-interfaces.md, scoring-rubric.md), quickstart.md.

**Tests**: BẮT BUỘC (Constitution IX). Trong mỗi phase, test viết trước và phải FAIL trước khi triển khai. Test không gọi API có phí, không
gọi mạng (rào chắn socket E0); nguồn ngoài = `MockWeb` fixture, AI = kịch bản giả lập (`tests/fakes/products_ai.py`). Kết quả MOCK không
được báo cáo là đã kiểm thử nguồn/AI thật; SC-008 giữ `BLOCKED`.

**Truy vết**: test đặt mã `TC_E2_<REQ>_<nn>`; T004 thêm spec 003 (prefix `E2`) vào `traceability_report.py`. Field ràng buộc trích dẫn
`data-model.md <bảng>.<cột>`.

**Ràng buộc chung**: không sửa hành vi E0/E1 (chỉ điểm chạm Y1–Y6 của plan); không tool/endpoint đăng ký affiliate; không bật nguồn; không
hard-code model ID; không thêm dependency; không thêm finding vào `.secrets.baseline`.

## Format: `[ID] [P?] [Story] Description (REQ-IDs)`

## Path Conventions

Backend `backend/src/nichepilot/…`, test `backend/tests/{unit,integration,contract}/products/…`, fixture `backend/tests/fixtures/products/…`,
migration `backend/alembic/versions/…`, frontend `frontend/src/…`, test frontend `frontend/tests/{unit,e2e}/…`.

---

## Phase 1: Setup

- [ ] T001 Tạo gói `backend/src/nichepilot/modules/products/__init__.py` (+ `scoring/__init__.py`) và thư mục test `backend/tests/{unit,integration,contract}/products/__init__.py` (plan Structure)
- [ ] T002 [P] Đăng ký marker pytest `products` trong `backend/pyproject.toml` (Constitution IX)
- [ ] T003 [P] Thêm 2 hợp đồng import-linter vào `backend/.importlinter`: `modules.discovery` và module E0 không import `modules.products` (FR-030, Y5)
- [ ] T004 [P] Mở rộng `backend/scripts/traceability_report.py` đọc `specs/003-product-affiliate-discovery/spec.md` với prefix `TC_E2_`; sửa regex dòng yêu cầu chấp nhận chú thích `**FR-xxx** *(Should)*:` (nợ FR-034 E1 – chủ sở hữu yêu cầu 2026-11-26) (Y4)
- [ ] T005 [P] Fixture `backend/tests/fixtures/products/web.json` + HTML tự soạn trên tên miền `.example` (trang review liệt kê sản phẩm, trang pricing chính thức, trang affiliate chính thức đủ/thiếu thuộc tính, trang bên thứ ba ghi hoa hồng khác, trang điều khoản v2) – mọi nội dung có tiền tố `[MOCK]` (R-10)
- [ ] T006 [P] AI giả lập theo kịch bản `backend/tests/fakes/products_ai.py` (trả đầu ra theo task type `products.extract`, `products.program_extract`, `products.assess`) (R-10)

---

## Phase 2: Foundational

### Tests (viết trước, phải FAIL)

- [ ] T007 [P] Test migration: bảng/ràng buộc E2 khớp ORM, upgrade→downgrade→upgrade sạch trong `backend/tests/integration/products/test_migration.py` (TC_E2_FR005_01: UNIQUE chống trùng `data-model.md products.dedup_key`, `affiliate_programs.dedup_key`, `product_niches(product_id,niche_id)`, `product_runs.job_id`) (FR-005, DATA-01)
- [ ] T008 [P] Test `attributes.verification_for`/`resolve` trong `backend/tests/unit/products/test_attributes.py` (TC_E2_FR008_01…04: VERIFIED theo tên miền chính thức, INFERRED bên thứ ba, CONFLICTING lưu mọi giá trị, UNKNOWN khi không có bằng chứng ACTIVE) (FR-008, FR-012)
- [ ] T009 [P] Test `extraction.validate_extract` trong `backend/tests/unit/products/test_extraction.py` (TC_E2_FR009_01…03: evidence_id lạ → loại sản phẩm; số không có trong trích đoạn → UNKNOWN + `rejected_values`; mã quốc gia/giới hạn quảng cáo ngoài danh mục → loại) (FR-009, FR-024)
- [ ] T010 [P] Test `eligibility.check_niche_eligible` trong `backend/tests/integration/products/test_eligibility.py` (TC_E2_FR001_01…02: EVIDENCE_SUFFICIENT ∧ CANDIDATE/WATCH/PURSUE được; INSUFFICIENT_EVIDENCE, REJECTED, HIDDEN, đã gộp → `NICHE_NOT_ELIGIBLE`) (FR-001)
- [ ] T011 [P] Test hợp đồng import + không có tool có `external_effect` trong allowlist agent E2 trong `backend/tests/unit/products/test_architecture.py` (TC_E2_FR025_01, TC_E2_FR030_01, TC_E2_FR041_01: agent dùng nguồn qua `source.query`/registry adapter, không tham chiếu `adapter_type` cụ thể; TC_E2_FR039_01: AgentDefinition của `products.run`, `products.terms_check`, `products.recompute` khai báo input/output model, allowed_tools, timeout_s, token_budget, max_steps, max_ai_calls, acceptance theo internal-interfaces §2; TC_E2_FR039_02: đầu ra AI sai schema → thử lại có giới hạn rồi lỗi, không lưu) (FR-025, FR-030, FR-039, FR-041)

### Implementation

- [ ] T012 ORM `backend/src/nichepilot/modules/products/models.py` + thêm vào `backend/src/nichepilot/db_models.py`, ràng buộc theo
  `data-model.md`: `product_runs.job_id` (UNIQUE), `product_runs.outcome` (enum), `product_runs.stop_reason`, `product_runs.params`,
  `product_runs.data_origin`; `products.name` (1–200), `products.official_domain` (chữ thường), `products.dedup_key` (UNIQUE với project,
  data_origin), `products.category` (enum), `products.risk_flags` (⊆ danh mục), `products.merged_into_id` (≠ id); `product_niches.product_id`
  + `product_niches.niche_id` (UNIQUE), `product_niches.readiness_status`, `product_niches.risk_flags`, `product_niches.persona_match`,
  `product_niches.ai_recommendation`, `product_niches.decision_status` (enum), `product_niches.decision_reason` (bắt buộc khi ≠ CANDIDATE),
  `product_niches.decided_by`; `product_pain_point_links.verification_status` (VERIFIED/INFERRED, UNIQUE bộ ba);
  `affiliate_programs.operator_type` (enum), `affiliate_programs.operator_domain` (chữ thường), `affiliate_programs.dedup_key` (UNIQUE),
  `affiliate_programs.verification_status` (enum), `affiliate_programs.watch_enabled` (mặc định false); `product_programs.product_id` +
  `product_programs.program_id` (UNIQUE); `program_terms_versions.version` (UNIQUE với program_id); `product_scoring_weights.version`
  (UNIQUE), `product_scoring_weights.is_active` (một dòng); `product_evaluations.opportunity_score` (NULL/0–100),
  `product_evaluations.confidence_score` (0–100), `product_evaluations.coverage` (0–100), `product_evaluations.scoring_status` (enum)
  (FR-002, FR-011, FR-017, FR-027)
- [ ] T013 Migration `backend/alembic/versions/0011_products.py` (bảng + CHECK + index) và `0012_products_seed.py` (trọng số v1 25/25/20/15/15, `coverage_min` 60, `rubric`, `confidence_params`, `query_templates`, `non_official_domains`; Model Task Profile cho `products.extract`, `products.program_extract`, `products.assess` dùng model seed `verified = false`) (FR-027, FR-028, Clarification Q2)
- [ ] T014 [P] Mã lỗi `NICHE_NOT_ELIGIBLE`, `PRODUCT_RUN_ACTIVE`, `PRODUCT_RUN_NOT_FOUND`, `PRODUCT_NOT_FOUND`, `PROGRAM_NOT_FOUND`, `PRODUCT_WEIGHTS_INVALID` trong `backend/src/nichepilot/core/errors.py` (Y2)
- [ ] T015 [P] Schema Pydantic (`extra="forbid"`) đầu ra AI + DTO + `ProductRunParams` (`data-model.md product_runs.params`: max_products 1–20, page_limit 5–200, time_limit_s 60–5400) trong `backend/src/nichepilot/modules/products/schemas.py` (FR-002, FR-039)
- [ ] T016 [P] `backend/src/nichepilot/modules/products/attributes.py` – `verification_for`, `resolve` (R-04, `data-model.md` §3 claim_key) (FR-008)
- [ ] T017 [P] `backend/src/nichepilot/modules/products/extraction.py` – `validate_extract` (R-03) (FR-009)
- [ ] T018 [P] `backend/src/nichepilot/modules/products/eligibility.py` (FR-001)
- [ ] T019 [P] `backend/src/nichepilot/modules/products/dedup.py` – `product_dedup_key`, `program_dedup_key`, upsert/gộp (R-08) (FR-015)
- [ ] T020 `PageCollector` trong `backend/src/nichepilot/jobs/agents/_collector.py` theo internal-interfaces §3 (FR-006, FR-010)

**Checkpoint**: nền dữ liệu + quy tắc xác minh sẵn sàng.

---

## Phase 3: User Story 1 – Tìm sản phẩm tiềm năng cho một ngách (P1) 🎯 MVP

**Goal**: lượt `products.run` tìm sản phẩm gắn pain point, website chính thức, giá, tính năng, khách hàng mục tiêu có bằng chứng.
**Independent Test**: kịch bản quickstart §2 #1, #4, #5, #6 với MockWeb + AI giả lập.

### Tests (viết trước, phải FAIL)

- [ ] T021 [P] [US1] Contract test `POST/GET /api/v1/product-runs`, `GET /product-runs/{id}` theo `contracts/openapi.yaml` trong `backend/tests/contract/products/test_runs_api.py` (TC_E2_FR001_03, TC_E2_FR002_01, TC_E2_FR004_01: thiếu ngân sách → `BUDGET_NOT_CONFIGURED`; TC_E2_FR006_01: không nguồn ALLOWED → 422; TC_E2_FR003_02: lượt đang chạy → `PRODUCT_RUN_ACTIVE`; TC_E2_FR001_04: lịch/job `products.run` thiếu `niche_id` bị từ chối – không chạy hàng loạt) (FR-001…FR-004, FR-006)
- [ ] T022 [P] [US1] Unit `queries.build_queries` xác định trong `backend/tests/unit/products/test_queries.py` (TC_E2_FR011_01) (FR-011, R-02)
- [ ] T023 [US1] Integration lượt đầy đủ trong `backend/tests/integration/products/test_product_run.py` (TC_E2_FR011_02: sản phẩm liên kết ≥ 1 pain point có bằng chứng; TC_E2_FR012_01: `official_domain` đúng, trang review không thành website chính thức; TC_E2_FR013_01: giá theo gói + tiền tệ + chu kỳ có bằng chứng; TC_E2_FR014_01: khách hàng mục tiêu INFERRED + persona_match; TC_E2_FR007_01: mọi thuộc tính có URL/trích đoạn/collected_at/verified_at; TC_E2_FR010_01: trích đoạn REDACTED, NEEDS_REVIEW không vào prompt; TC_E2_FR038_01: metrics đủ khóa; TC_E2_FR035_01: lượt mock gắn MOCK) (FR-007, FR-010…FR-014, FR-035, FR-038)
- [ ] T024 [P] [US1] Integration rỗng/lỗi trong `backend/tests/integration/products/test_product_run_edges.py` (TC_E2_FR011_03: 0 sản phẩm → COMPLETED/NO_PRODUCTS_FOUND, không sản phẩm giả, cờ ngách; TC_E2_FR006_02: robots chặn/CAPTCHA/đăng nhập → bỏ qua có lý do; TC_E2_FR006_03: job theo lịch không nguồn → 0 lời gọi AI; TC_E2_FR016_01: sản phẩm lĩnh vực nhạy cảm gắn cờ COMPLIANCE_SENSITIVE) (FR-006, FR-011, FR-016)
- [ ] T025 [P] [US1] Integration idempotent/tiếp tục sau sự cố trong `backend/tests/integration/products/test_product_run_resume.py` (TC_E2_FR005_02 = SC-003; TC_E2_FR003_01: checkpoint, tạm dừng/tiếp tục/hủy; TC_E2_FR004_02: hết ngân sách → PAUSED_BUDGET; TC_E2_FR015_01: hai lượt cùng sản phẩm → một bản ghi) (FR-003…FR-005, FR-015)

### Implementation

- [ ] T026 [P] [US1] `backend/src/nichepilot/modules/products/queries.py` (R-02) (FR-011)
- [ ] T027 [US1] `backend/src/nichepilot/modules/products/service.py`: `create_run` (eligibility, ngân sách, nguồn usable, 1 lượt hoạt động/ngách, audit `product.run_created`), `ensure_run_record`, `list_runs`, `get_run` (FR-001…FR-004, FR-037)
- [ ] T028 [US1] Agent `backend/src/nichepilot/jobs/agents/product_discovery.py` bước preflight→search_products→fetch→extract_products→finalize theo internal-interfaces §2 (AgentDefinition FR-039; lưu thuộc tính sản phẩm vào `research_evidence` với claim_key §3; `data-model.md product_runs.metrics`) (FR-003, FR-005…FR-014, FR-038, FR-039)
- [ ] T029 [US1] Router `backend/src/nichepilot/api/v1/products.py` (`/product-runs*`, ledger gate) + đăng ký agent/router trong `backend/src/nichepilot/services.py`, `backend/src/nichepilot/worker.py`, `backend/src/nichepilot/main.py` (Y1) (FR-036)

**Checkpoint**: US1 chạy độc lập bằng MOCK.

---

## Phase 4: User Story 2 – Tìm và xác minh chương trình affiliate (P1)

**Goal**: chương trình + 7 thuộc tính có cấu trúc, trạng thái do mã, không đăng ký.
**Independent Test**: quickstart §2 #1–#3, #7, #10.

### Tests (viết trước, phải FAIL)

- [ ] T030 [P] [US2] Unit `programs.program_status`, `best_program` trong `backend/tests/unit/products/test_programs.py` (TC_E2_FR018_01…02: VERIFIED/PARTIAL/UNVERIFIED/CLOSED theo data-model §4) (FR-018)
- [ ] T031 [P] [US2] Unit thuộc tính có cấu trúc trong `backend/tests/unit/products/test_program_attributes.py` (TC_E2_FR019_01: hoa hồng percent/fixed/tiered/recurring/khoảng/"lên tới"; TC_E2_FR020_01: cookie ngày/session; TC_E2_FR021_01: thanh toán; TC_E2_FR022_01: im lặng → UNKNOWN, không suy ra ALLOWED; TC_E2_FR023_01: so thị trường ngách; TC_E2_FR024_01: mã giới hạn, không thấy → UNKNOWN) (FR-019…FR-024)
- [ ] T032 [US2] Integration xác minh chương trình trong `backend/tests/integration/products/test_program_verification.py` (TC_E2_FR017_01: tìm chương trình VENDOR/NETWORK + terms_url; TC_E2_FR008_05: trang bên thứ ba khác hoa hồng → CONFLICTING đủ 2 nguồn (QA-05); TC_E2_FR018_03: không truy cập trang điều khoản → UNVERIFIED (QA-04); TC_E2_FR009_04: hoa hồng không có trong trích đoạn → UNKNOWN; TC_E2_FR022_02 điều khoản cần đăng nhập → UNKNOWN "cần tài khoản") (FR-008, FR-009, FR-017, FR-018, FR-022)
- [ ] T033 [P] [US2] Integration không hành động bên ngoài trong `backend/tests/integration/products/test_no_external_actions.py` (TC_E2_FR025_02 = SC-002: mọi request ra ngoài trong lượt đầy đủ chỉ là GET qua `source.query`/`page.fetch`/`robots.fetch`; không form POST) (FR-025)

### Implementation

- [ ] T034 [P] [US2] `backend/src/nichepilot/modules/products/programs.py` (data-model §4) (FR-018)
- [ ] T035 [US2] Bước search_details→fetch→extract_programs trong `backend/src/nichepilot/jobs/agents/product_discovery.py` (claim_key chương trình §3, `data-model.md affiliate_programs.verification_status`, `product_programs`) (FR-017…FR-024)
- [ ] T036 [US2] `GET /api/v1/affiliate-programs/{id}` trong `backend/src/nichepilot/api/v1/products.py` + `service.get_program` (FR-036)

---

## Phase 5: User Story 3 – Chấm điểm và xếp hạng sản phẩm (P1)

**Goal**: Opportunity/Confidence theo cặp, readiness, khuyến nghị theo rubric, danh sách xếp hạng.
**Independent Test**: ví dụ tính tay scoring-rubric §3; quickstart §2 #7, #8.

### Tests (viết trước, phải FAIL)

- [ ] T037 [P] [US3] Unit tiêu chí trong `backend/tests/unit/products/test_criteria.py` (TC_E2_FR027_01…05: 5 tiêu chí theo rubric §2, ngưỡng đọc từ `rubric`; TC_E2_FR028a_01: hoa hồng cao không tạo SELECT) (FR-027, FR-028a)
- [ ] T038 [P] [US3] Unit Opportunity/Coverage/Confidence trong `backend/tests/unit/products/test_scoring.py` (TC_E2_FR027_06: 88,24; TC_E2_FR028_01: 83,33 tại ngưỡng; TC_E2_FR028_02: Coverage 45 → INSUFFICIENT_SCORING_DATA; TC_E2_FR028_03: fit null → INSUFFICIENT dù Coverage ≥ 60; TC_E2_FR029_01: Confidence 80,00; TC_E2_FR029_02: Confidence không đổi khi Opportunity đổi; TC_E2_FR030_02: không lời gọi AI trong tính điểm) (FR-027…FR-030)
- [ ] T039 [P] [US3] Unit readiness trong `backend/tests/unit/products/test_readiness.py` (TC_E2_FR026_01…06: đủ 6 trạng thái + cờ theo rubric §4; ELIGIBILITY_UNVERIFIED không bao giờ READY) (FR-026)
- [ ] T040 [US3] Integration đánh giá trong `backend/tests/integration/products/test_evaluation.py` (TC_E2_FR029a_01: cùng sản phẩm hai ngách → hai đánh giá khác nhau; TC_E2_FR027_07: lưu phiên bản trọng số + thành phần, tái lập 100% (SC-004); TC_E2_FR028_04: missing + Coverage hiển thị; R-06: xóa bằng chứng hoa hồng → đọc lại tính lại, affiliate null (TC_E2_FR007_02)) (FR-007, FR-027…FR-029a)
- [ ] T041 [P] [US3] Contract `GET /niches/{id}/products`, `GET /products/{id}`, `GET/POST /product-scoring/weights` trong `backend/tests/contract/products/test_products_api.py` (TC_E2_FR032_01: hai danh sách; TC_E2_FR035_02: MOCK ẩn mặc định; TC_E2_FR031_01: `disclaimer_key`; TC_E2_FR027_08: trọng số sai tổng → `PRODUCT_WEIGHTS_INVALID`, đúng → phiên bản mới + job recompute; TC_E2_FR037_01: audit `product.weights_created`) (FR-027, FR-031, FR-032, FR-035, FR-037)

### Implementation

- [ ] T042 [P] [US3] `backend/src/nichepilot/modules/products/scoring/criteria.py` (rubric §2) (FR-027)
- [ ] T043 [P] [US3] `backend/src/nichepilot/modules/products/scoring/opportunity.py`, `scoring/confidence.py` (rubric §3) (FR-027…FR-029)
- [ ] T044 [P] [US3] `backend/src/nichepilot/modules/products/readiness.py` (rubric §4) (FR-026)
- [ ] T045 [P] [US3] `backend/src/nichepilot/modules/products/weights.py` (`data-model.md product_scoring_weights.weights` tổng 100, 5 khóa; `coverage_min`) (FR-027, FR-028)
- [ ] T046 [US3] `backend/src/nichepilot/modules/products/evaluation.py` – `evaluate_pair` (nơi duy nhất ghi `data-model.md product_evaluations.*`, fingerprint R-06, khuyến nghị rubric §5) (FR-026…FR-029a, FR-028a)
- [ ] T047 [US3] Bước assess→evaluate trong `backend/src/nichepilot/jobs/agents/product_discovery.py` (`products.assess`, `third_party_mention`) (FR-014, FR-027)
- [ ] T048 [US3] Danh sách/chi tiết/trọng số trong `backend/src/nichepilot/modules/products/service.py` + router; agent `products.recompute` trong `backend/src/nichepilot/jobs/agents/program_terms_check.py` (FR-027, FR-032, FR-036)

---

## Phase 6: User Story 4 – Báo cáo sản phẩm & quyết định (P2)

**Goal**: báo cáo VI/EN, quyết định có lý do + audit, tóm tắt ngách, 2 màn hình.
**Independent Test**: quickstart §3, §4.

### Tests (viết trước, phải FAIL)

- [ ] T049 [P] [US4] Contract `POST /products/{id}/decision`, `GET /niches/{id}/product-summary`, `GET /niches/{id}/product-report` trong `backend/tests/contract/products/test_report_decision_api.py` (TC_E2_FR033_01: lý do bắt buộc, điểm không đổi, audit `product.decision`; TC_E2_FR034_01: tóm tắt không đổi bảng `niches`/`niche_evaluations`; TC_E2_FR032_02: báo cáo markdown VI/EN loại MOCK) (FR-032…FR-034, FR-037)
- [ ] T050 [P] [US4] Vitest `frontend/tests/unit/products-pages.test.ts` (TC_E2_FR036_01: danh sách xếp hạng/cần nghiên cứu thêm, lọc MOCK, nhãn readiness, Coverage + thiếu; TC_E2_FR036_02: chi tiết thuộc tính + trạng thái + nguồn, chương trình, quyết định; TC_E2_FR036_03: khóa i18n `products` đủ VI/EN) (FR-036, SC-006)

### Implementation

- [ ] T051 [P] [US4] `backend/src/nichepilot/modules/products/report.py` (FR-032)
- [ ] T052 [US4] Quyết định, tóm tắt ngách, báo cáo trong `service.py` + router (FR-033, FR-034, FR-037)
- [ ] T053 [P] [US4] API client + kiểu `frontend/src/api/products.ts` (FR-036)
- [ ] T054 [US4] Màn hình `frontend/src/pages/products/NicheProductsView.tsx`/`NicheProductsPage.tsx` và `ProductDetailView.tsx`/`ProductDetailPage.tsx`, route trong `frontend/src/app/` (FR-036)
- [ ] T055 [US4] Khối "Sản phẩm" (tóm tắt + liên kết) trong `frontend/src/pages/discovery/NicheDetailView.tsx` – bổ sung, không đổi hành vi E1 (Y3) (FR-034)
- [ ] T056 [P] [US4] Khóa i18n `products.*` + mã lỗi mới trong `frontend/src/i18n/locales/vi.json`, `en.json` (FR-036, Constitution XII)

---

## Phase 7: User Story 5 – Theo dõi thay đổi điều khoản (P3, Should)

### Tests (viết trước, phải FAIL)

- [ ] T057 [US5] Integration `backend/tests/integration/products/test_terms_check.py` (TC_E2_FR040_01: điều khoản đổi → phiên bản 2 + changes + cảnh báo; TC_E2_FR040_02: không đổi → không phiên bản mới; TC_E2_FR040_03: lỗi truy cập giữ giá trị cũ, ghi `last_check_error`; TC_E2_FR040_04: watch/acknowledge có audit) (FR-040, FR-037)

### Implementation

- [ ] T058 [US5] `terms_snapshot`/`diff_snapshots` trong `programs.py` + agent `products.terms_check` trong `backend/src/nichepilot/jobs/agents/program_terms_check.py` (`data-model.md program_terms_versions.*`) (FR-040)
- [ ] T059 [US5] `PUT /affiliate-programs/{id}/watch`, `POST …/terms-versions/{v}/acknowledge` + hiển thị lịch sử/cảnh báo trong `ProductDetailView.tsx` (FR-040)

---

## Phase 8: Polish & Cross-Cutting

- [ ] T060 [P] Lệnh `backend/src/nichepilot/jobs/products_demo_seed.py` + test `backend/tests/integration/products/test_demo_seed.py` (TC_E2_FR035_03: MOCK, idempotent, từ chối production, 1 READY + 1 ELIGIBILITY_UNVERIFIED; TC_E2_SC007_01: production + nguồn/AI giả lập → api/worker từ chối khởi động, đường E2 dùng chung guard) (FR-035, SC-007, R-10)
- [ ] T061 Playwright: thêm test sản phẩm MOCK → chi tiết → quyết định WATCH → EN trong `frontend/tests/e2e/discovery.spec.ts`; CI chạy `products_demo_seed` sau `discovery_demo_seed` trong `.github/workflows/ci.yml` (SC-006)
- [ ] T062 [P] Test hiệu năng `backend/tests/integration/products/test_perf.py` (TC_E2_SC005_01: lượt MOCK 10 sản phẩm ≤ 5 phút; danh sách 500 sản phẩm p95 < 500 ms) (SC-005)
- [ ] T063 [P] Test SC-001 `backend/tests/integration/products/test_no_fabrication.py` (TC_E2_SC001_01: mọi giá trị hoa hồng/cookie/giá trong báo cáo truy về bằng chứng chứa giá trị đó) (SC-001)
- [ ] T064 [P] Test live đánh dấu `BLOCKED` cho SC-008 trong `backend/tests/live_sources/test_products_live.py` (deselected mặc định; chỉ chạy khi có nguồn ALLOWED + AI thật) (SC-008)
- [ ] T065 [P] Tài liệu `docs/operations/products.md`, cập nhật `README.md`, `CLAUDE.md` (trạng thái E2)
- [ ] T066 Chạy toàn bộ quality gate (ruff, format, mypy, lint-imports, pytest, oxlint, tsc, vitest, Playwright, truy vết `--strict`, check_secrets) và báo cáo `docs/reports/e2-final-report.md`

---

## Dependencies & Execution Order

Setup (T001–T006) → Foundational (T007–T020) → US1 (T021–T029) → US2 (T030–T036) → US3 (T037–T048) → US4 (T049–T056) → US5 (T057–T059) →
Polish (T060–T066). US2 phụ thuộc agent US1; US3 phụ thuộc thuộc tính US1/US2; US4 phụ thuộc đánh giá US3; US5 phụ thuộc chương trình US2.

## Parallel Example

Foundational tests T007–T011 song song; T014–T019 song song sau T012–T013. US3: T037–T039, T041 song song; T042–T045 song song.

## Implementation Strategy

MVP = US1 (sản phẩm có bằng chứng) → thêm US2 (chương trình) → US3 (điểm) là phạm vi P1 đầy đủ; US4 hoàn thiện ra quyết định; US5 (Should)
sau cùng. Commit sau mỗi phase khi gate đạt.
