# Implementation Plan: E4 – Bilingual Dashboard

**Branch**: `feature/e4-bilingual-dashboard` | **Date**: 2026-11-28 | **Spec**: [spec.md](./spec.md)

**Trạng thái**: Draft – tự tiếp tục theo A4. Không gọi API có phí, không bật nguồn, không đổi cấu hình mạng.

## Summary

E4 hoàn thiện dashboard song ngữ trên khung E0: menu điều hướng chung; trang Tổng quan (API tổng hợp chỉ đọc + ngân sách E0); trang Sản phẩm
và Keyword toàn cục (API danh sách ngách kèm tóm tắt E2/E3, liên kết tới trang theo ngách đã có); trang Agent Jobs (danh sách, chi tiết, điều
khiển, lịch chạy qua API E0); trang Chi phí (REAL/MOCK tách) và Settings (cấu hình không bí mật; provider/model chỉ đọc); xuất CSV an toàn.

## Technical Context

**Language/Version**: Python 3.13; TypeScript + React 19. **Dependencies**: giữ nguyên (không thêm). **Storage**: không bảng mới.
**Testing**: pytest marker `dashboard`; Vitest; Playwright (bộ `discovery`). **Performance**: API p95 < 500 ms với 500 ngách/job (SC-003).
**Constraints**: chỉ đọc ở module dashboard; MOCK ẩn mặc định; không thao tác có phí trên UI.

## Constitution Check (v1.2.0)

| Nguyên tắc | Kết quả |
|---|---|
| I. Evidence-First | PASS – điểm luôn kèm Confidence + đường tới bằng chứng; MOCK ẩn mặc định, có nhãn |
| II. Opportunity ⟂ Confidence | PASS – hiển thị cả hai, không gộp |
| III. Niche-First | PASS – trang Sản phẩm/Keyword đi từ ngách |
| IV. Human-in-the-Loop | PASS – thao tác ghi = quyết định/điều khiển của chủ sở hữu qua API có audit |
| V. AI Safety | PASS – E4 không gọi AI |
| VI. Cost-Aware | PASS – chi phí REAL/MOCK tách; không có nút gọi provider/xác minh model |
| VII. OSS-First | PASS – không công nghệ mới |
| VIII. Module & API-First | PASS – `modules/dashboard` chỉ đọc, không ai import; UI chỉ gọi API |
| IX. TDD & truy vết | PASS – `TC_E4_*`, profile `E4` |
| X. Security | PASS – không secret trên UI/response; ledger gate |
| XI. Self-hosted | PASS |
| XII. Song ngữ | PASS – namespace `dashboard`, test khóa VI/EN + không hard-code |

## Project Structure

```text
backend/src/nichepilot/modules/dashboard/{__init__,queries}.py   # MỚI – SQL chỉ đọc
backend/src/nichepilot/api/v1/dashboard.py                       # MỚI – 2 endpoint
backend/tests/{unit,integration,contract,perf}/dashboard/         # TC_E4_*
frontend/src/app/Layout.tsx (+ nav), router.tsx (+ 7 route)
frontend/src/api/dashboard.ts, jobs.ts, admin.ts                  # hook API
frontend/src/lib/csv.ts                                           # CSV an toàn
frontend/src/pages/dashboard/{Overview,ResearchNiches,Jobs,JobDetail,Costs,Settings}{View,Page}.tsx
frontend/src/pages/discovery/NicheRankingView.tsx, products/NicheProductsView.tsx, keywords/KeywordClusterView.tsx (+ nút Xuất CSV)
frontend/src/i18n/{index.ts (+formatMoney/formatPercent), locales/*.json (+ dashboard.*)}
frontend/tests/unit/dashboard-*.test.ts, csv.test.ts; tests/e2e/discovery.spec.ts (+1)
```

## Ánh xạ yêu cầu → thiết kế

| Yêu cầu | Thiết kế |
|---|---|
| FR-001…FR-005 | hạ tầng i18n E0 + nav trong Layout + test i18n hiện có mở rộng |
| FR-006…FR-008, FR-012 | `queries.overview`, `OverviewView` (+ `/budget`) |
| FR-009…FR-011 | `queries.research_niches`, `ResearchNichesView` (mode products/keywords) |
| FR-013…FR-015 | `JobsView`, `JobDetailView` (API E0 jobs/schedules) |
| FR-016 | `CostsView` (`/budget`, `/costs/summary` REAL/MOCK) |
| FR-017…FR-019 | `SettingsView` (`/settings`, `/projects/default`, `/budget`; `/providers`, `/models`, `/model-profiles` chỉ đọc) |
| FR-020 | `lib/csv.ts` + nút xuất ở 3 bảng |
| FR-022 | E2E mới |
| FR-023 | test kiến trúc: dashboard không ghi DB; UI không gọi endpoint có phí |

## Complexity Tracking – điểm chạm (bổ sung)

| # | Điểm chạm | Giới hạn |
|---|---|---|
| W1 | `api/v1/__init__.py` đăng ký router | chỉ thêm dòng |
| W2 | `Layout` thêm nav (tắt ở trang đăng nhập/khởi tạo) | trang E0 giữ nội dung; E2E E0 không đổi |
| W3 | Nút Xuất CSV trên 3 view E1–E3 | không đổi dữ liệu/hành vi cũ |
| W4 | `traceability_report.py` profile E4; test danh sách openapi thêm E4 | như E2/E3 |
| W5 | `.importlinter` hợp đồng mới | – |

**Không còn `NEEDS CLARIFICATION`.**
