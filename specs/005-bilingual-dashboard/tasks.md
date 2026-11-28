---

description: "Danh sách công việc triển khai E4 — Bilingual Dashboard"
---

# Tasks: E4 — Bilingual Dashboard

**Input**: plan.md, spec.md (Clarifications 2026-11-28), research.md (R-01…R-07), data-model.md, contracts/openapi.yaml, quickstart.md.
**Tests**: bắt buộc (Constitution IX); MOCK; không mạng/không API có phí. Mã `TC_E4_<REQ>_<nn>`.

## Phase 1: Setup

- [ ] T001 Gói `modules/dashboard`, thư mục test `tests/{unit,integration,contract,perf}/dashboard`, marker `dashboard`
- [ ] T002 [P] Hợp đồng import-linter: không module nào import `modules.dashboard`; profile `E4` trong traceability + test danh sách openapi

## Phase 2: Backend chỉ đọc (US1, US2)

- [ ] T003 [P] Test `tests/integration/dashboard/test_overview.py` (TC_E4_FR006_01 số liệu khớp DB; TC_E4_FR007_01 MOCK ẩn/hiện; TC_E4_FR012_01 top niches kèm Confidence; TC_E4_FR008_01 DB rỗng → số 0 + danh sách rỗng)
- [ ] T004 [P] Test `tests/integration/dashboard/test_research_niches.py` (TC_E4_FR010_01 tóm tắt E2 + has_run; TC_E4_FR011_01 tóm tắt E3 + best cluster; TC_E4_FR009_01 eligible theo quy tắc E2)
- [ ] T005 [P] Test `tests/contract/dashboard/test_dashboard_api.py` (TC_E4_FR006_02 hợp đồng; ledger 503; limit 422; TC_E4_FR019_01 không secret; TC_E4_FR023_01 module không ghi DB/không import nghiệp vụ)
- [ ] T006 `modules/dashboard/queries.py` + `api/v1/dashboard.py` + đăng ký router
- [ ] T007 [P] Perf `tests/perf/dashboard/test_dashboard_perf.py` (TC_E4_SC003_01 500 ngách/500 job p95 < 500 ms)

## Phase 3: Frontend

- [ ] T008 [P] Test `frontend/tests/unit/csv.test.ts` (TC_E4_FR020_01 BOM, quote, chống công thức, UNKNOWN; TC_E4_SC006_01)
- [ ] T009 [P] Test `frontend/tests/unit/dashboard-pages.test.ts` (TC_E4_FR005_01 nav + aria-current; TC_E4_FR006_03 Tổng quan; TC_E4_FR008_02 rỗng/lỗi; TC_E4_FR010_02/FR011_02 trang toàn cục; TC_E4_FR013_01/FR014_01/FR015_01 Jobs; TC_E4_FR016_01 chi phí REAL/MOCK; TC_E4_FR017_01/FR018_01 Settings chỉ đọc phần có phí; TC_E4_FR004_01 ngôn ngữ giao diện ⟂ nội dung; TC_E4_FR003_01 định dạng locale; TC_E4_FR001_01/FR002_01/SC001_01 khóa VI/EN; TC_E4_FR021_01 không có route Content Calendar/Revenue (Later))
- [ ] T010 `lib/csv.ts`, `formatMoney`/`formatPercent`, hook API, Layout nav, router
- [ ] T011 Trang Tổng quan, Sản phẩm/Keyword toàn cục, Agent Jobs (+ chi tiết), Chi phí, Cài đặt; nút Xuất CSV ở 3 bảng; i18n `dashboard.*`

## Phase 4: Polish

- [ ] T012 E2E Playwright (TC_E4_FR022_01 / SC-005) trong `tests/e2e/discovery.spec.ts`
- [ ] T013 `docs/operations/dashboard.md`, README, CLAUDE.md; full gates; CI; báo cáo `docs/reports/e4-final-report.md`
