---

description: "Danh sách công việc triển khai E3 — Keyword & Audience Research"
---

# Tasks: E3 — Keyword & Audience Research

**Input**: `/specs/004-keyword-audience-research/` – plan.md, spec.md (Clarifications Q1 = A, (b)), research.md (R-01…R-10), data-model.md,
contracts/ (openapi.yaml, internal-interfaces.md, scoring-rubric.md), quickstart.md.

**Tests**: BẮT BUỘC (Constitution IX), viết trước và FAIL trước khi triển khai. Không gọi API có phí, không mạng (rào chắn socket E0);
nguồn ngoài = `MockWeb` fixture, AI = kịch bản giả lập (`tests/fakes/keywords_ai.py`). SC-008 giữ `BLOCKED`.

**Truy vết**: mã test `TC_E3_<REQ>_<nn>`; T004 thêm profile `E3` vào `traceability_report.py`.

**Ràng buộc chung**: không sửa hành vi E0/E1/E2 (chỉ điểm chạm Z1–Z7); không ghi chỉ số keyword không nguồn; không bật nguồn; không thêm
dependency; không thêm finding vào `.secrets.baseline`.

## Format: `[ID] [P?] [Story] Description (REQ-IDs)`

---

## Phase 1: Setup

- [x] T001 Tạo gói `backend/src/nichepilot/modules/keywords/` (+ `scoring/`) và thư mục test `backend/tests/{unit,integration,contract,perf}/keywords/`
- [x] T002 [P] Marker pytest `keywords` trong `backend/pyproject.toml`
- [x] T003 [P] Hợp đồng import-linter: `modules.discovery`, `modules.products` và module E0 không import `modules.keywords` (Z5)
- [x] T004 [P] Profile `E3` (spec 004) trong `scripts/traceability_report.py` + test profile (Z4, Z7)
- [x] T005 [P] Fixture `backend/tests/fixtures/keywords/web.json` + HTML tự soạn `.example` (SERP: forum, Q&A, review, bài viết; trang đối thủ phủ/không phủ pain point) – nội dung tiền tố `[MOCK]`
- [x] T006 [P] AI giả lập `backend/tests/fakes/keywords_ai.py` cho `keywords.generate`, `keywords.analyze`, `keywords.strategy`

## Phase 2: Foundational

### Tests

- [x] T007 [P] Test migration 0013/0014 trong `tests/integration/keywords/test_migration.py` (TC_E3_FR004_01 UNIQUE `keywords.dedup_key`, `keyword_clusters.cluster_key`, `serp_observations(keyword_id,version)`, `competitor_pages(keyword_id,url)`; TC_E3_FR009_01 CHECK chỉ số có nguồn; trigger bất biến `keyword_evaluations`) + mở rộng danh sách bảng/bất biến E0 (FR-004, FR-009)
- [x] T008 [P] Test `normalize` trong `tests/unit/keywords/test_normalize.py` (TC_E3_FR006_01 độ dài HEAD/MID/LONG_TAIL; TC_E3_FR008_01…02 gộp hoa/thường, dấu, số nhiều, thứ tự từ) (FR-006, FR-008)
- [x] T009 [P] Test kiến trúc trong `tests/unit/keywords/test_architecture.py` (TC_E3_FR029_01 AgentDefinition 3 agent; TC_E3_FR029_02 schema AI forbid; TC_E3_FR003_01 job E0 + tool allowlist chỉ đọc) (FR-003, FR-029)

### Implementation

- [x] T010 ORM `modules/keywords/models.py` + `db_models.py` theo data-model §2
- [x] T011 Migration `0013_keywords.py` (bảng, CHECK, trigger bất biến) và `0014_keywords_seed.py` (trọng số v1 30/20/20/15/15, rubric, coverage_min 60, templates; Model Task Profile 3 task type)
- [x] T012 `schemas.py` (đầu ra AI forbid, DTO, `KeywordRunParams`), `normalize.py`, `weights.py`
- [x] T013 4 mã lỗi `core/errors.py` + xuất `frontend/src/api/error-codes.json` (Z2)

## Phase 3: US1 – Sinh keyword (P1) 🎯 MVP

### Tests

- [x] T014 [P] [US1] `tests/unit/keywords/test_generation.py` (TC_E3_FR005_01 keyword thiếu origin/origin ngách khác bị loại; TC_E3_FR005_02 origin hợp lệ giữ; TC_E3_FR007_01 mẫu commercial cho mọi sản phẩm không `REJECTED`; TC_E3_FR002_01 đầu vào gồm pain point/persona/sản phẩm) (FR-002, FR-005, FR-007)
- [x] T015 [P] [US1] `tests/integration/keywords/test_keyword_run.py` (TC_E3_FR001_01 tạo lượt 202 + 409 `NICHE_NOT_ELIGIBLE` + 409 `KEYWORD_RUN_ACTIVE`; TC_E3_FR005_03 SC-001; TC_E3_SC003_01 ≥ 50% LONG_TAIL; TC_E3_FR009_02 AI trả thêm `search_volume` → loại đầu ra, chỉ số NULL; TC_E3_FR010_01 không lọc theo volume; TC_E3_FR002_02 không ghi bảng E1/E2; TC_E3_FR030_01 số liệu lượt: lời gọi AI, chi phí REAL/MOCK, trang, keyword theo loại/độ dài, outcome/stop_reason) (FR-001, FR-002, FR-005, FR-009, FR-010, FR-030)
- [x] T016 [P] [US1] `tests/integration/keywords/test_keyword_run_resume.py` (TC_E3_FR004_02 chạy lại/tiếp tục sau sự cố 0 bản ghi trùng; TC_E3_FR003_02 pause/resume/cancel qua E0) (FR-003, FR-004)

### Implementation

- [x] T017 [US1] `generation.py` (inputs, validate, mẫu commercial, cờ BRAND_TERM/COMPLIANCE_SENSITIVE) + `store.py` upsert keyword/origin
- [x] T018 [US1] Agent `jobs/agents/keyword_research.py` bước preflight → generate → finalize (+ đăng ký Z1)
- [x] T019 [US1] `service.create_run`, `list_runs`, `get_run` + router `api/v1/keywords.py` (`/keyword-runs`)

## Phase 4: US2 – Intent, SERP, đối thủ (P1)

### Tests

- [x] T020 [P] [US2] `tests/unit/keywords/test_serp_analysis.py` (TC_E3_FR012_01 `page_type`; TC_E3_FR014_01 content gap đúng/UNKNOWN; TC_E3_FR015_01 tỷ lệ yếu; TC_E3_FR013_01 tóm tắt đối thủ evidence/pain point lạ bị loại; TC_E3_FR011_01 intent ngoài danh mục bị loại; TC_E3_FR023_01 kênh từ forum/qa/video) (FR-011…FR-015, FR-023)
- [x] T021 [P] [US2] `tests/integration/keywords/test_serp_run.py` (TC_E3_FR012_02 SERP qua nguồn ALLOWED, lưu kết quả; TC_E3_FR013_02 trích đoạn ≤ 1000 ký tự – SC-007; TC_E3_FR012_03 không nguồn → PARTIAL_COMPLETED/NO_COMPLIANT_SEARCH_SOURCE, SERP UNKNOWN; TC_E3_FR011_02 intent VERIFIED chỉ khi có SERP + bằng chứng) (FR-011…FR-013)

### Implementation

- [x] T022 [US2] `serp.py`, `analysis.py`
- [x] T023 [US2] Bước pre_score → serp → fetch (`PageCollector`) → analyze trong agent

## Phase 5: US3 – Cluster, chấm điểm, xếp hạng (P1)

### Tests

- [x] T024 [P] [US3] `tests/unit/keywords/test_scoring.py` (TC_E3_FR017_01…02 ví dụ rubric 71,25 / 63,46; TC_E3_FR018_01 Coverage < 60 hoặc thiếu fit → INSUFFICIENT; TC_E3_FR019_01 Confidence 92,00 và không phụ thuộc Opportunity; TC_E3_FR017_03 intent_value: PROBLEM informational = transactional; TC_E3_FR020_01 tái lập) (FR-017…FR-020)
- [x] T025 [P] [US3] `tests/unit/keywords/test_clustering.py` (TC_E3_FR016_01 mỗi keyword đúng 1 cluster, keyword chính, điểm cluster = trung bình SCORED) (FR-016)
- [x] T026 [P] [US3] `tests/integration/keywords/test_evaluation.py` (TC_E3_FR017_04 đổi trọng số → phiên bản mới, recompute không AI, đánh giá cũ giữ; TC_E3_SC004_01 điểm tái lập; TC_E3_FR020_02 bằng chứng bị xóa → tính lại khi đọc) (FR-017, FR-020)
- [x] T027 [P] [US3] `tests/contract/keywords/test_keywords_api.py` (TC_E3_FR028_01 các endpoint khớp openapi; TC_E3_FR027_01 MOCK ẩn mặc định; TC_E3_FR021_01 disclaimer; TC_E3_FR009_03 chỉ số `value=null` + nguồn null; TC_E3_FR028_02 ledger 503) (FR-009, FR-021, FR-027, FR-028)

### Implementation

- [x] T028 [US3] `scoring/criteria.py`, `scoring/opportunity.py`, `scoring/confidence.py`, `clustering.py`, `evaluation.py`
- [x] T029 [US3] Bước cluster_evaluate trong agent; agent `keywords.recompute`; `service` danh sách/chi tiết cluster/tóm tắt; endpoint weights

## Phase 6: US4 – Persona, kênh, strategy, quyết định, báo cáo (P2)

### Tests

- [x] T030 [P] [US4] `tests/unit/keywords/test_strategy.py` (TC_E3_FR022_01 thuộc tính persona không evidence → UNKNOWN; TC_E3_FR024_01 strategy có loại nội dung/pain point/keyword hợp lệ; TC_E3_BR11_01 câu "we tested" bị loại) (FR-022, FR-024)
- [x] T031 [P] [US4] `tests/contract/keywords/test_report_decision_api.py` (TC_E3_FR025_01 quyết định bắt buộc lý do, audit, điểm không đổi; TC_E3_FR026_01 báo cáo JSON/Markdown VI/EN, không MOCK mặc định – SC-007) (FR-025, FR-026)

### Implementation

- [x] T032 [US4] `strategy.py`; bước strategy trong agent; `service.decide`; `report.py`; endpoint decision/report

## Phase 7: US5 – Theo dõi SERP (P3, Should)

- [x] T033 [P] [US5] `tests/integration/keywords/test_serp_check.py` (TC_E3_FR031_01 kết quả đổi → phiên bản + changes; không đổi → không phiên bản; lỗi → giữ cũ; watch/acknowledge audit) (FR-031)
- [x] T034 [US5] `jobs/agents/serp_check.py` (`keywords.serp_check`) + endpoint watch/acknowledge + lịch E0 chấp nhận `keywords.serp_check`/`keywords.run`

## Phase 8: Frontend (FR-028, SC-006)

- [x] T035 [P] `frontend/tests/unit/keywords-pages.test.ts` (TC_E3_FR028_03 render cluster/keyword, chỉ số UNKNOWN, disclaimer, quyết định; TC_E3_SC006_01 khóa i18n VI/EN đầy đủ)
- [x] T036 `src/api/keywords.ts`, types; trang `NicheKeywordsView/Page`, `KeywordClusterView/Page`; route; khối Keyword trong `NicheDetailView` (Z3); i18n `keywords.*`

## Phase 9: Polish

- [x] T037 `jobs/keywords_demo_seed.py` + `tests/integration/keywords/test_demo_seed.py` (TC_E3_FR027_02 từ chối production, idempotent)
- [x] T038 [P] `tests/perf/keywords/test_keywords_perf.py` (TC_E3_SC005_01 lượt MOCK; p95 danh sách cluster) – `NICHEPILOT_RUN_PERF=1`
- [x] T039 [P] `tests/live_sources/test_keywords_live.py` (TC_E3_SC008_01 – skip "BLOCKED:")
- [x] T040 E2E Playwright (+1 test) + bước seed trong `.github/workflows/ci.yml`
- [x] T041 `docs/operations/keywords.md`, README, CLAUDE.md trạng thái; full gates; báo cáo `docs/reports/e3-final-report.md`

## Dependencies

Phase 1 → 2 → US1 → US2 → US3 → US4 → US5 → Frontend → Polish. Trong phase: test [P] song song, rồi implementation.
