# Implementation Plan: E2 – Product & Affiliate Discovery

**Branch**: `claude/inspiring-wright-06dzhw` (feature dir `specs/003-product-affiliate-discovery`) | **Date**: 2026-11-27 | **Spec**: [spec.md](./spec.md)

**Input**: `specs/003-product-affiliate-discovery/spec.md` (clarify 2026-11-27: Q1, Q2 của chủ sở hữu; Coverage 60%; đánh giá theo cặp)

**Trạng thái**: Draft – tự tiếp tục theo A4 (CLAUDE.md) khi analyze không còn CRITICAL/HIGH. Không gọi API có phí.

## Summary

E2 thêm module `products` trên nền E0/E1: từ một ngách đủ điều kiện (ngưỡng bằng chứng E1, chưa bị loại), agent `products.run` sinh truy
vấn xác định từ pain point/persona, tìm và tải trang qua **chuỗi tuân thủ của E1** (chỉ nguồn `ALLOWED`, robots.txt, 1 request/2 s/tên miền,
che PII trong tool), AI chỉ **trích xuất có dẫn bằng chứng** sản phẩm, giá, tính năng, khách hàng mục tiêu, chương trình affiliate và 7 thuộc
tính chương trình; **mã** quyết định trạng thái xác minh (theo tên miền nguồn), loại giá trị số không có trong trích đoạn, gộp trùng, trạng
thái sẵn sàng (`READY_TO_PROMOTE`…), chấm Opportunity (5 tiêu chí, Coverage ≥ 60%) và Confidence tách biệt theo cặp (sản phẩm, ngách).
Không có chức năng đăng ký affiliate. API + 2 màn hình song ngữ; theo dõi điều khoản (Should) qua job `products.terms_check`.

## Technical Context

**Language/Version**: Python 3.13, TypeScript + React 19 (như E0/E1).
**Primary Dependencies**: giữ nguyên E0/E1 (FastAPI, SQLAlchemy 2.1 async, Alembic, Procrastinate, structlog, httpx, trafilatura,
protego, tldextract, rapidfuzz, phonenumbers; React, i18next, TanStack Query). **Không thêm dependency, service hay image mới.**
**Storage**: PostgreSQL 17 – migration `0011_products`, `0012_products_seed` ([data-model.md](./data-model.md)).
**Testing**: pytest (unit, integration testcontainers, contract) marker mới `products`; Vitest; Playwright (bộ `discovery`). Nguồn ngoài =
`MockWeb` fixture, AI = kịch bản giả lập; rào chắn socket của E0 giữ nguyên.
**Target Platform**: Docker Compose Linux / Windows WSL2.
**Project Type**: Web application (backend + frontend).
**Performance Goals**: lượt MOCK ≤ 10 sản phẩm ≤ 5 phút (SC-005); API danh sách sản phẩm p95 < 500 ms với ≤ 500 sản phẩm/ngách; tính lại
một cặp (không AI) < 200 ms.
**Constraints**: ngân sách AI E0 ($2/job, $3/ngày, $30/tháng); mặc định 60 trang, 30 phút/lượt; không PII chưa che; không vượt CAPTCHA/
đăng nhập/paywall; RAM không tăng đáng kể (không service mới).
**Scale/Scope**: 1 chủ sở hữu; ≤ 20 sản phẩm/lượt; 5 user story; FR-001…FR-041 (+ 026, 028a, 029a); SC-001…SC-008.

## Constitution Check (v1.2.0)

| Nguyên tắc | Trước Phase 0 | Sau Phase 1 |
|---|---|---|
| I. Evidence-First | FR-007…FR-010, `UNKNOWN`, không bịa | PASS – thuộc tính = bằng chứng E0 có nguồn; kiểm số trong trích đoạn (R-03); trạng thái do mã (R-04); MOCK ẩn mặc định |
| II. Opportunity ⟂ Confidence | FR-027…FR-029 | PASS – hai hàm riêng, Confidence không nhận Opportunity; trọng số có version; `MONETIZATION_RISK` khi chưa sẵn sàng |
| III. Niche-First & AI-First | Bắt đầu từ ngách + pain point | PASS – sản phẩm phải liên kết pain point; chấm điểm/gộp/readiness là mã |
| IV. Human-in-the-Loop | Không đăng ký affiliate | PASS – không tool/endpoint đăng ký; tool chỉ đọc; quyết định do chủ sở hữu |
| V. AI Safety | Agent khai báo đủ | PASS – AgentDefinition (internal-interfaces §2), schema `extra=forbid`, `<untrusted_content>`, tool allowlist |
| VI. Cost-Aware | Gateway + ngân sách E0 | PASS – truy vấn không AI (R-02); ≤ 60 lời gọi AI/lượt; tính lại không AI; gọi có phí vẫn tắt |
| VII. OSS-First | – | PASS – không công nghệ mới |
| VIII. Module & API-First | Module riêng | PASS – `modules/products`, import-linter: discovery/E0 không import products; API cho mọi chức năng |
| IX. TDD & truy vết | TC cho FR Must | PASS – mã `TC_E2_FRxxx_nn`; `traceability_report.py` thêm spec 003 (prefix `E2`) |
| X. Security | PII, nguồn | PASS – PII che trong tool E1; ledger gate; audit; không secret mới |
| XI. Self-hosted | – | PASS – không service mới |
| XII. Song ngữ | 2 màn hình VI/EN | PASS – namespace i18n `products`, test khóa i18n |

12/12 PASS. Không vi phạm cần biện minh.

## Project Structure

### Documentation

```text
specs/003-product-affiliate-discovery/
├── spec.md, plan.md, research.md (R-01…R-11), data-model.md, quickstart.md
├── contracts/openapi.yaml, internal-interfaces.md, scoring-rubric.md
├── checklists/requirements.md
└── tasks.md   (/speckit-tasks)
```

### Source Code

```text
backend/src/nichepilot/
├── modules/products/                # MỚI (internal-interfaces §1)
│   ├── models.py schemas.py eligibility.py queries.py extraction.py attributes.py programs.py readiness.py
│   ├── scoring/{criteria,opportunity,confidence}.py weights.py dedup.py evaluation.py service.py report.py
├── jobs/agents/_collector.py        # MỚI – PageCollector (R-01)
├── jobs/agents/product_discovery.py # MỚI – products.run
├── jobs/agents/program_terms_check.py # MỚI – products.terms_check, products.recompute
├── jobs/products_demo_seed.py       # MỚI – dev/test
├── api/v1/products.py               # MỚI – router (contracts/openapi.yaml)
├── core/errors.py                   # + 6 mã lỗi
├── services.py / worker.py          # + đăng ký 3 agent, router (bổ sung)
backend/alembic/versions/0011_products.py, 0012_products_seed.py
backend/tests/{unit,integration,contract}/products/   # TC_E2_*
backend/tests/fixtures/products/                      # MockWeb JSON + HTML tự soạn (.example)
backend/scripts/traceability_report.py                # + spec 003
backend/.importlinter                                 # + 2 hợp đồng

frontend/src/pages/products/{NicheProductsPage,ProductDetailPage}.tsx (+ View tách logic như E1)
frontend/src/pages/discovery/NicheDetailView.tsx      # + liên kết/tóm tắt "Sản phẩm" (bổ sung, không đổi hành vi cũ)
frontend/src/i18n/locales/{vi,en}.json                # + namespace products
frontend/tests/unit/products-*.test.ts, frontend/tests/e2e/discovery.spec.ts (+1 test)
.github/workflows/ci.yml                              # + chạy products_demo_seed trước E2E
docs/operations/products.md                           # vận hành E2
```

**Structure Decision**: giữ phân tầng `api > jobs > (ai : tools : modules) > core`. `modules/products` dùng API công khai của
`modules/discovery` (đọc ngách/pain point/persona, `DomainAccessService`, `SourcePolicyService`, `fingerprint`, `risk`) – chiều ngược
lại bị cấm bằng import-linter. Agent E2 dùng tool E1 sẵn có, không thêm tool.

## Ánh xạ yêu cầu → thiết kế

| Yêu cầu | Thiết kế | Artifact |
|---|---|---|
| FR-001…FR-005 | `eligibility.py`, `POST /product-runs` (kiểm ngân sách/nguồn như E1, 1 lượt hoạt động/ngách), job E0 checkpoint, `ensure_run` idempotent | openapi, data-model `product_runs` |
| FR-006, FR-010 | `PageCollector` + tool E1 | research R-01, internal §3 |
| FR-007…FR-009 | bằng chứng E0, `extraction.validate_extract`, `attributes.resolve` | research R-03…R-05 |
| FR-011…FR-016 | `products`, `product_niches`, `product_pain_point_links`, `dedup.py`, `risk` | data-model, R-08 |
| FR-017…FR-024 | `affiliate_programs`, claim_key §3, `programs.program_status` | data-model §3–4 |
| FR-025, SC-002 | không tool/endpoint đăng ký; test kiểm request ra ngoài | R-11 |
| FR-026, FR-028a | `readiness.py`, rubric §4–5 | scoring-rubric |
| FR-027…FR-031, FR-029a | `scoring/*`, `evaluation.evaluate_pair`, `weights.py` | scoring-rubric §1–3, R-06/R-07 |
| FR-032…FR-036 | `report.py`, API, 2 màn hình, MOCK filter | openapi, quickstart |
| FR-037, FR-038 | audit actions, `product_runs.metrics` | data-model §5 |
| FR-039 | AgentDefinition | internal §2 |
| FR-040 (Should) | `products.terms_check`, `program_terms_versions` | R-09 |
| FR-041 (Later) | adapter nguồn E1 mở rộng được (`http_json_api`) – không triển khai | – |

## Complexity Tracking – điểm chạm E0/E1 (đều là bổ sung)

| # | Điểm chạm | Lý do | Giới hạn |
|---|---|---|---|
| Y1 | `services.py`/`worker.py`: đăng ký agent + router E2 | bắt buộc để chạy job/API | chỉ thêm dòng đăng ký |
| Y2 | `core/errors.py`: 6 mã lỗi | hợp đồng lỗi | không đổi mã cũ |
| Y3 | `NicheDetailView` E1: thêm khối tóm tắt/liên kết Sản phẩm | FR-034 | không đổi dữ liệu/hành vi E1; test E1 giữ nguyên |
| Y4 | `traceability_report.py`: spec 003 | IX | như X7 của E1 |
| Y5 | `.importlinter`: hợp đồng mới | VIII | – |
| Y6 | `PageCollector` lặp lại logic `_fetch` của E1 thay vì tách chung | tránh sửa agent E1 đã nghiệm thu | ghi nợ kỹ thuật: hợp nhất ở feature sau khi có test hồi quy |

## Kiểm tra nhất quán với Master Requirements

| Yêu cầu | Bao phủ |
|---|---|
| E2-01 (AC-08) | FR-011, `products.extract` + liên kết pain point |
| E2-02 | FR-012 `official_domain` (R-04) |
| E2-03, E2-04 | FR-017, FR-018 |
| E2-05…E2-10 | FR-019…FR-024, claim_key §3 |
| E2-11, E2-12 | FR-013, FR-014 |
| E2-13 | FR-015 (R-08) |
| E2-14 (BR-04) | FR-027…FR-029 |
| E2-15 (DATA-03, AC-07) | FR-007 – bằng chứng E0 có `collected_at`, `verified_at`, URL |
| E2-16 (Should) | FR-040 |
| E2-17 (Later) | FR-041 |
| BR-02, AC-09 | FR-008, FR-009 |
| BR-06 | FR-026 |
| BR-08, AC-19 | FR-025 |
| QA-03, QA-04, QA-05, QA-10 | US1-AC3, US2-AC4, US2-AC3, FR-005 |

Ngoài phạm vi: `affiliate_applications`, `affiliate_links` (không có chức năng cần), API mạng affiliate (E2-17 Later), keyword (E3).

**Không còn `NEEDS CLARIFICATION`.**
