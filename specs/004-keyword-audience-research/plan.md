# Implementation Plan: E3 – Keyword & Audience Research

**Branch**: `feature/e3-keyword-audience` (feature dir `specs/004-keyword-audience-research`) | **Date**: 2026-11-27 | **Spec**: [spec.md](./spec.md)

**Input**: `specs/004-keyword-audience-research/spec.md` (Q1 = A của chủ sở hữu 2026-11-27; clarify (b) mặc định kỹ thuật)

**Trạng thái**: Draft – tự tiếp tục theo A4 khi analyze không còn CRITICAL/HIGH. Không gọi API có phí, không bật nguồn `UNVERIFIED`.

## Summary

E3 thêm module `keywords` trên nền E0/E1/E2: từ một ngách đủ điều kiện, agent `keywords.run` dùng AI (qua Gateway, schema `extra=forbid`)
**đề xuất** keyword gắn nguồn gốc (pain point / thuộc tính persona / sản phẩm E2), cộng keyword commercial theo mẫu xác định; mã chuẩn hóa,
gộp trùng, phân loại độ dài. SERP và trang đối thủ chỉ lấy qua **chuỗi tuân thủ E1** (nguồn `ALLOWED`, robots, giới hạn tốc độ, che PII);
không có nguồn → keyword nội bộ vẫn được chấm, tiêu chí phụ thuộc SERP `UNKNOWN`. Mã tính content gap, kênh, cạnh tranh quan sát, cluster,
Opportunity (5 tiêu chí 30/20/20/15/15, Coverage ≥ 60%) và Confidence tách biệt. Search Volume/CPC/KD **luôn `UNKNOWN`** (không có đường ghi
không nguồn). API + 2 màn hình song ngữ; theo dõi SERP (Should) qua `keywords.serp_check`.

## Technical Context

**Language/Version**: Python 3.13, TypeScript + React 19.
**Primary Dependencies**: giữ nguyên E0–E2. **Không thêm dependency, service, image hay tool mới.**
**Storage**: PostgreSQL 17 – migration `0013_keywords`, `0014_keywords_seed` ([data-model.md](./data-model.md)).
**Testing**: pytest marker mới `keywords` (unit, integration testcontainers, contract, perf); Vitest; Playwright (bộ `discovery`). Nguồn ngoài =
`MockWeb` fixture, AI = kịch bản giả lập; rào chắn socket E0 giữ nguyên.
**Target Platform**: Docker Compose Linux / Windows WSL2.
**Project Type**: Web application.
**Performance Goals**: lượt MOCK (≤ 60 keyword, ≤ 10 SERP) ≤ 10 phút (SC-005); API danh sách cluster p95 < 500 ms với ≤ 200 keyword/ngách.
**Constraints**: ngân sách AI E0; ≤ 40 lời gọi AI/lượt; mặc định 60 trang, 30 phút; trích đoạn ≤ 1000 ký tự; không PII chưa che.
**Scale/Scope**: 1 chủ sở hữu; 5 user story; FR-001…FR-032 (FR-031 Should, FR-032 Later); SC-001…SC-008.

## Constitution Check (v1.2.0)

| Nguyên tắc | Trước Phase 0 | Sau Phase 1 |
|---|---|---|
| I. Evidence-First | FR-009, FR-012…FR-014 | PASS – chỉ số keyword NULL + CHECK nguồn (R-02); SERP/đối thủ là bằng chứng E0; gap/kênh có URL; `UNKNOWN` khi thiếu |
| II. Opportunity ⟂ Confidence | FR-017…FR-019 | PASS – hai hàm riêng; trọng số có version; Coverage ≥ 60% |
| III. Niche-First & AI-First | FR-005 | PASS – keyword bắt buộc origin trong ngách; chấm điểm/gộp/cluster là mã |
| IV. Human-in-the-Loop | FR-025 | PASS – quyết định cluster do chủ sở hữu; không xuất bản nội dung |
| V. AI Safety | FR-029 | PASS – AgentDefinition (internal §2), schema forbid, `<untrusted_content>`, allowlist tool |
| VI. Cost-Aware | Gateway | PASS – keyword mẫu/chấm điểm không AI; ≤ 40 lời gọi/lượt; serp_check/recompute không AI; gọi có phí vẫn tắt |
| VII. OSS-First | – | PASS – không công nghệ mới; không API keyword trả phí (FR-032 Later) |
| VIII. Module & API-First | Module riêng | PASS – `modules/keywords`; discovery/products/E0 không import keywords |
| IX. TDD & truy vết | TC cho FR Must | PASS – `TC_E3_FRxxx_nn`; profile `E3` trong `traceability_report.py` |
| X. Security | PII | PASS – PII che trong tool E1; ledger gate; audit |
| XI. Self-hosted | – | PASS |
| XII. Song ngữ | 2 màn hình | PASS – namespace i18n `keywords` |

12/12 PASS.

## Project Structure

```text
specs/004-keyword-audience-research/
├── spec.md, plan.md, research.md (R-01…R-10), data-model.md, quickstart.md
├── contracts/openapi.yaml, internal-interfaces.md, scoring-rubric.md
├── checklists/requirements.md
└── tasks.md

backend/src/nichepilot/
├── modules/keywords/                 # MỚI (internal §1)
├── jobs/agents/keyword_research.py   # MỚI – keywords.run
├── jobs/agents/serp_check.py         # MỚI – keywords.serp_check, keywords.recompute
├── jobs/keywords_demo_seed.py        # MỚI – dev/test
├── api/v1/keywords.py                # MỚI
├── core/errors.py                    # + 4 mã lỗi
backend/alembic/versions/0013_keywords.py, 0014_keywords_seed.py
backend/tests/{unit,integration,contract,perf}/keywords/, tests/fixtures/keywords/, tests/fakes/keywords_ai.py
frontend/src/pages/keywords/{NicheKeywordsView,NicheKeywordsPage,KeywordClusterView,KeywordClusterPage}.tsx
frontend/src/pages/discovery/NicheDetailView.tsx   # + khối tóm tắt Keyword (bổ sung)
frontend/src/i18n/locales/{vi,en}.json             # + keywords.*
.github/workflows/ci.yml                           # + keywords_demo_seed trước E2E
docs/operations/keywords.md
```

**Structure Decision**: phân tầng `api > jobs > (ai : tools : modules) > core`. `modules/keywords` đọc API công khai của `discovery` và
`products`; chiều ngược lại cấm bằng import-linter. Tái dùng `PageCollector` (E2) và tool E1, không thêm tool.

## Ánh xạ yêu cầu → thiết kế

| Yêu cầu | Thiết kế | Artifact |
|---|---|---|
| FR-001…FR-004 | `check_niche_eligible` (E2), `POST /keyword-runs`, job E0 checkpoint, upsert idempotent | openapi, data-model |
| FR-005…FR-008 | `generation.py`, `normalize.py`, mẫu commercial | R-01, R-03, R-04 |
| FR-009, FR-010 | cột NULL + CHECK; schema AI không trường chỉ số; không lọc theo volume | R-02 |
| FR-011…FR-015 | `serp.py`, `analysis.py`, `PageCollector` | R-05, R-06 |
| FR-016…FR-021 | `clustering.py`, `scoring/*`, `evaluation.py`, `weights.py` | scoring-rubric |
| FR-022…FR-024 | `strategy.py`, `analysis.channels` | R-06, R-08 |
| FR-025, FR-026 | `service.decide`, `report.py` | openapi |
| FR-027, FR-028 | MOCK filter, 2 màn hình | quickstart |
| FR-029, FR-030 | AgentDefinition, `keyword_runs.metrics` | internal §2 |
| FR-031 (Should) | `keywords.serp_check`, phiên bản SERP | R-09 |
| FR-032 (Later) | cột chỉ số + `metrics_source` sẵn cho adapter tương lai – không triển khai | – |

## Complexity Tracking – điểm chạm E0/E1/E2 (đều là bổ sung)

| # | Điểm chạm | Giới hạn |
|---|---|---|
| Z1 | `jobs/agents/__init__.py`, `api/v1/__init__.py`: đăng ký | chỉ thêm dòng |
| Z2 | `core/errors.py`: 4 mã | không đổi mã cũ |
| Z3 | `NicheDetailView` E1: khối Keyword | không đổi hành vi E1/E2; test cũ giữ |
| Z4 | `traceability_report.py`: profile E3 | như E2 |
| Z5 | `.importlinter`: hợp đồng mới | – |
| Z6 | `scoring.confidence.source_kind` (E1) chỉ được gọi, không sửa; `page_type` E3 mở rộng ở `serp.py` | – |
| Z7 | Test danh sách E0/E1 (migrations, openapi contract, traceability) thêm E3 | như E2 |

## Kiểm tra nhất quán với Master Requirements

| Yêu cầu | Bao phủ |
|---|---|
| E3-01 (AC-10) | FR-005 |
| E3-02, E3-03 | FR-006, FR-007 |
| E3-04 (AC-11) | FR-011 |
| E3-05 | FR-012 |
| E3-06 (AC-11, BR-09) | FR-013 |
| E3-07 | FR-016 |
| E3-08 | FR-014 |
| E3-09 | FR-022 |
| E3-10 | FR-023 |
| E3-11 | FR-015 |
| E3-12 (BR-04) | FR-017…FR-019 |
| E3-13 (AC-16) | FR-024, FR-026 |
| E3-14 (Should) | FR-032 – Later (cần quyền truy cập Google, ngoài A4) |
| E3-15 (Should) | FR-031 |
| BR-05, BR-15 | FR-009, FR-010 |

**Không còn `NEEDS CLARIFICATION`.**
