# Implementation Plan: E1 – Autonomous Niche Discovery

**Branch**: `claude/inspiring-wright-06dzhw` (feature dir `specs/002-niche-discovery`) | **Date**: 2026-11-19 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification `specs/002-niche-discovery/spec.md` (đã clarify Q1–Q8, 2026-11-19)

**Trạng thái**: `DRAFT – CHỜ CHỦ SỞ HỮU PHÊ DUYỆT`. Chưa chạy `/speckit-tasks`, chưa `/speckit-implement`. Không có lời gọi API có phí.

## Summary

E1 bổ sung một module nghiệp vụ `discovery` chạy trên nền E0 (Job Runtime, AI Gateway + giữ chỗ ngân sách, Tool Registry,
EvidenceService, audit, i18n) để tự động: (1) tìm vấn đề khách hàng thật qua **SearXNG** tự host (chỉ truy vấn máy tìm kiếm có hồ sơ
tuân thủ `ALLOWED`, hoặc `UNVERIFIED` do chủ sở hữu tự bật có cảnh báo + audit), (2) tải trang công khai tôn trọng robots.txt và
mức trần 1 request/2 giây/tên miền, trích nội dung chính, **che PII trước khi lưu hoặc gửi AI**, (3) dùng AI (qua Gateway) gom pain
point, persona, giải pháp, đối thủ, tín hiệu monetization, đánh giá độc lập/chất lượng bằng chứng, (4) **mã xác định** áp ngưỡng
bằng chứng (≥ 2 bằng chứng pain point hợp lệ từ ≥ 2 nhóm nguồn độc lập), tính Opportunity (chuẩn hóa trọng số trên tiêu chí hợp lệ,
Coverage ≥ 60%), Confidence (công thức riêng), phát hiện trùng, (5) lưu và trình bày qua API + 3 màn hình song ngữ.

Giới hạn mỗi lượt: 20 ngách ứng viên, $2 ngân sách AI, 90 phút thời gian hoạt động, 300 trang; kết quả `COMPLETED` hoặc
`PARTIAL_COMPLETED` + lý do. Không thay đổi kiến trúc E0; các điểm mở rộng cần duyệt được liệt kê ở **Complexity Tracking**.

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript 7 + React 19 (frontend) – như E0.

**Primary Dependencies** (E0 giữ nguyên): FastAPI, SQLAlchemy 2.1 async + psycopg 3, Alembic, Procrastinate, anthropic/openai SDK,
structlog, httpx; React + Vite + Tailwind + shadcn + i18next + TanStack Query.
**Mới cho E1** (cần duyệt – research R-02…R-08):

| Thành phần | Giấy phép | Vai trò | Ghi chú |
|---|---|---|---|
| SearXNG (container chính thức, không sửa mã) | AGPL-3.0 | Metasearch tự host | Dịch vụ riêng trong Compose; gọi qua HTTP JSON API nội bộ; không phân phối lại mã đã sửa |
| `trafilatura` | Apache-2.0 | Trích nội dung chính từ HTML | Mặc định – nhẹ, không cần trình duyệt |
| Crawl4AI (tùy chọn, profile `crawl4ai`) | Apache-2.0 | Trang cần JavaScript | Tắt mặc định (cần Chromium, shm 1 GB); câu chữ ghi công trong README chưa rõ → chờ chủ sở hữu quyết định |
| `protego` | BSD-3 (cần xác minh khi thêm) | Phân tích robots.txt (Crawl-delay) | Bổ sung so với research R-04 (stdlib `urllib.robotparser` là phương án thay) |
| `phonenumbers` | Apache-2.0 | Nhận diện số điện thoại theo quốc gia | |
| spaCy + `en_core_web_sm` | MIT (giấy phép model cần xác minh khi thêm) | Nhận diện tên người (tiếng Anh) | Ngôn ngữ khác: heuristic + `NEEDS_REVIEW` (R-05); dự phòng Presidio |
| `rapidfuzz` | MIT | So khớp mờ tên ngách | |
| `tldextract` | BSD-3 (cần xác minh khi thêm) | eTLD+1 cho tính độc lập nguồn | Dùng snapshot Public Suffix List đóng gói, không tải lúc chạy |
| SimHash (tự viết ~40 dòng) | – | Phát hiện nội dung sao chép | Không thêm phụ thuộc |

**Storage**: PostgreSQL 17 (bảng mới ở [data-model.md](./data-model.md), migration `0009_discovery`, `0010_discovery_seed`);
sổ xóa bằng chứng `erasure-ledger` là file append-only trên volume riêng (R-09).

**Testing**: pytest (unit, integration testcontainers `postgres:17-alpine`, contract), Vitest, Playwright E2E. Nguồn bên ngoài trong
test dùng **adapter giả lập** (`MockSearchAdapter`, `MockPageFetcher` với HTML cố định) – dữ liệu gắn `MOCK`; AI dùng
`MockAIProvider`. Rào chắn socket của E0 giữ nguyên: test không truy cập mạng. Bộ kiểm thử thu thập thật (`tests/live_sources`)
deselected mặc định, chỉ chạy khi chủ sở hữu bật và có ít nhất một nguồn `ALLOWED`.

**Target Platform**: Docker Compose trên Linux và Windows 10/11 (WSL2), như E0.

**Project Type**: Web application (backend + frontend) – cấu trúc E0.

**Performance Goals**: một lượt ≤ 90 phút hoạt động; API danh sách/xếp hạng p95 < 500 ms với ≤ 5.000 ngách; tính lại điểm
(`discovery.recompute`, không AI) ≤ 60 s cho 1.000 ngách.

**Constraints**: ≤ $2 AI/lượt, $3/ngày, $30/tháng (E0); 1 request/2 s/tên miền (trần); 300 trang/lượt; RAM nghỉ toàn hệ thống
≤ 3 GB (SearXNG ≈ 150–250 MB; Crawl4AI không bật mặc định); không lưu PII chưa che; không vượt CAPTCHA.

**Scale/Scope**: 1 chủ sở hữu, 1 project; ~20 ngách/lượt, vài lượt/tuần; 7 user story, FR-001…FR-036, SC-001…SC-016.

## Constitution Check

*GATE: kiểm tra trước Phase 0 và lại sau Phase 1.*

| Nguyên tắc | Đánh giá trước Phase 0 | Sau Phase 1 (thiết kế) |
|---|---|---|
| I. Evidence-First (KTL) | Spec bắt buộc nguồn + trạng thái xác minh, `UNKNOWN`, không bịa (FR-013…FR-016) | PASS – ngưỡng bằng chứng do mã tính (R-06); AI chỉ gán `INFERRED`; `research_evidence` giữ ràng buộc E0; không có đường ghi bằng chứng không nguồn |
| II. Opportunity ⟂ Confidence | FR-017…FR-020 | PASS – hai hàm riêng (`scoring/opportunity.py`, `scoring/confidence.py`), Confidence không nhận Opportunity làm đầu vào; test kiểm tra tính độc lập (contracts/scoring-rubric.md) |
| III. Niche-First & AI-First | Phân tích cấp ngách; sản phẩm/affiliate chỉ ở dạng tín hiệu | PASS – không tạo bảng sản phẩm/chương trình affiliate (E2) |
| IV. Human-in-the-Loop (KTL) | AI chỉ đề xuất; chủ sở hữu quyết định; không đăng ký/xuất bản | PASS – endpoint quyết định chỉ do người dùng gọi; tool thu thập là chỉ đọc, `external_effect = false` |
| V. AI Safety | Nội dung ngoài là dữ liệu không tin cậy (FR-012) | PASS – nội dung bọc trong khối dữ liệu có nhãn, schema đầu ra bắt buộc, giới hạn bước/lời gọi (R-11), tool allowlist |
| VI. Cost-Aware (KTL) | $2/lượt, Gateway + giữ chỗ E0 | PASS – mọi lời gọi qua Gateway; ước tính ≈ $0,7/lượt (chưa đo); gọi có phí vẫn tắt; không tự tăng ngân sách |
| VII. OSS-First | Đánh giá SearXNG, Crawl4AI, trafilatura | PASS có điều kiện – phụ thuộc mới liệt kê ở trên cần duyệt; Crawl4AI chỉ tùy chọn |
| VIII. Module & API-First | Module riêng, API cho mọi chức năng | PASS – `modules/discovery`, tool `searxng_search`/`page_fetch`, import-linter giữ lớp E0 |
| IX. TDD & truy vết (KTL) | Mỗi FR Must có TC | PASS – mã test `TC_E1_FRxxx_nn`, mở rộng `traceability_report.py` cho spec 002 (xem Complexity) |
| X. Security-by-Design | PII, secret | PASS – che PII trước DB/AI/log; không secret mới (SearXNG `server.secret_key` sinh lúc cài, nằm ngoài repo); CI secret scanning giữ nguyên |
| XI. Self-hosted, tiết kiệm | ≤ 3 GB RAM | PASS – SearXNG nhẹ; Crawl4AI tắt mặc định |
| XII. Song ngữ | 3 màn hình VI/EN | PASS – khóa i18n mới, test `i18n-keys` áp dụng |

Không có vi phạm cần biện minh; các mở rộng E0 dưới đây là **bổ sung** (không sửa hành vi đã nghiệm thu) nhưng vẫn cần chủ sở hữu duyệt
theo yêu cầu "không thay đổi kiến trúc E0 khi chưa được phê duyệt".

## Project Structure

### Documentation (this feature)

```text
specs/002-niche-discovery/
├── spec.md
├── plan.md              # File này
├── research.md          # Phase 0 (R-01…R-11)
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1 – kịch bản kiểm chứng
├── contracts/
│   ├── openapi.yaml             # REST API E1
│   ├── internal-interfaces.md   # SearchAdapter, PageFetcher, PiiRedactor, agent, tool, job types
│   └── scoring-rubric.md        # Công thức Opportunity/Coverage/Confidence/dedup + ví dụ tính tay
├── checklists/requirements.md
└── tasks.md             # Chưa tạo (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/src/nichepilot/
├── modules/discovery/               # MỚI – nghiệp vụ E1 (lớp modules, chỉ phụ thuộc core)
│   ├── models.py                    # ORM bảng E1 (data-model §2)
│   ├── schemas.py                   # Pydantic: đầu ra AI (schema bắt buộc), DTO API
│   ├── service.py                   # DiscoveryService: tạo lượt, truy vấn xếp hạng, quyết định
│   ├── sources/policy.py            # SearchSourcePolicyService (ALLOWED/UNVERIFIED/PROHIBITED, cảnh báo, audit)
│   ├── privacy/redactor.py          # PiiRedactor (EMAIL/PHONE/USER/PERSON), NEEDS_REVIEW
│   ├── privacy/erasure.py           # EvidenceErasureService + ledger (append-only, reapply)
│   ├── evidence_rules.py            # ngưỡng, nhóm độc lập (eTLD+1 + SimHash)
│   ├── scoring/opportunity.py       # Opportunity + Coverage
│   ├── scoring/confidence.py        # Confidence (N,Q,D,F,K,V)
│   ├── dedup.py                     # rapidfuzz token_set_ratio
│   └── ranking.py                   # 3 danh sách: cơ hội / ưu tiên affiliate / cần nghiên cứu thêm
├── tools/                           # MỞ RỘNG – thêm tool chỉ đọc (Tool Registry E0)
│   ├── searxng_search.py            # SearchAdapter (SearXNG JSON API, lọc engine theo policy)
│   ├── page_fetch.py                # PageFetcher (robots, rate per domain, trafilatura; Crawl4AI tùy chọn)
│   └── mock_sources.py              # MockSearchAdapter/MockPageFetcher (dev/test, MOCK)
├── ai/agents/niche_discovery.py     # MỚI – NicheDiscoveryAgent (định nghĩa agent: bước, checkpoint)
├── jobs/discovery_jobs.py           # MỚI – đăng ký job type discovery.run / reevaluate / recompute
└── api/v1/discovery.py              # MỚI – router (contracts/openapi.yaml)

backend/alembic/versions/0009_discovery.py, 0010_discovery_seed.py
backend/tests/{unit,integration,contract}/discovery/…  # TC_E1_*
backend/tests/fixtures/discovery/*.html                 # trang mẫu cố định cho MockPageFetcher

frontend/src/pages/discovery/
├── DiscoveryRunsPage.tsx            # Màn hình 1
├── NicheRankingPage.tsx             # Màn hình 2 (3 tab danh sách)
└── NicheDetailPage.tsx              # Màn hình 3
frontend/src/i18n/locales/{vi,en}/discovery.json
frontend/tests/e2e/discovery.spec.ts

deploy/docker-compose.yml            # + service `searxng` (profile mặc định), `crawl4ai` (profile tùy chọn), volume `erasure-ledger`
deploy/searxng/settings.yml          # engines tắt mặc định; bật theo policy; limiter tắt (mạng nội bộ)
deploy/scripts/restore.sh            # + bước áp lại erasure ledger sau restore
docs/operations/discovery.md         # vận hành E1 (nguồn, xác minh ToS, xóa bằng chứng)
```

**Structure Decision**: giữ cấu trúc web app của E0; E1 là một module trong `modules/` + tool trong `tools/` + agent trong `ai/agents/`
+ job type trong `jobs/`, đúng hợp đồng lớp import-linter `api > jobs > (ai, tools, modules) > core`. `modules/discovery` không import
`ai`/`tools`; agent (lớp `ai`) điều phối qua interface trong `core` – xem contracts/internal-interfaces.md §6.

## Luồng xử lý một lượt khám phá (job `discovery.run`)

Mỗi bước là một bước checkpoint của Job Runtime E0 (idempotent theo `seq`):

1. **plan_queries** – AI `discovery.candidates` đề xuất ≤ 20 ngách ứng viên + truy vấn tìm kiếm (theo thị trường/ngôn ngữ/lĩnh vực
   gợi ý). Không AI (mock) → kết quả `MOCK`.
2. **check_sources** – lấy engine được bật từ policy; không có → kết thúc `PARTIAL_COMPLETED` / `NO_COMPLIANT_SEARCH_SOURCE`
   (không gọi AI thêm).
3. **search** (lặp theo ứng viên) – `searxng_search`; lưu URL ứng viên; lỗi nguồn → ghi trạng thái (FR-006a).
4. **fetch** (lặp theo trang, ưu tiên ứng viên còn thiếu bằng chứng – FR-030b) – kiểm tra giới hạn thời gian/trang → robots →
   rate per domain → tải → trích nội dung → **che PII** → SimHash → lưu `research_sources` + trích đoạn ứng viên; ghi `page_fetch_log`.
5. **extract** – AI `discovery.extract` trên trích đoạn đã che PII → pain point, persona, giải pháp, đối thủ, tín hiệu monetization
   (schema bắt buộc; sai schema → không lưu, E0 FR-013).
6. **assess** – AI `discovery.assess`: relevance/quality/copy_suspected từng bằng chứng, điểm tiêu chí + trạng thái + lý do.
7. **evaluate** (không AI) – nhóm độc lập, ngưỡng bằng chứng, Opportunity/Coverage, Confidence, monetization status, cờ rủi ro.
8. **dedup** – `discovery.normalize` (AI, rẻ) + rapidfuzz → gộp/ghi cặp tương đồng.
9. **finalize** – outcome + stop_reason + metrics; ngách không đạt ngưỡng ghi `INSUFFICIENT_EVIDENCE`.

Bước 3–6 lặp có dừng sớm khi mọi ứng viên đã đủ bằng chứng (FR-030c). Chạm giới hạn thời gian/trang → nhảy tới bước 7–9 với dữ liệu
đã có (FR-030d). Hết ngân sách AI → `PAUSED_BUDGET` của E0 (FR-028).

## Ánh xạ yêu cầu → thiết kế (tóm tắt)

| Nhóm yêu cầu | Thiết kế | Artifact |
|---|---|---|
| FR-001…FR-004 cấu hình/ngân sách lượt | `POST /discovery/runs`, kiểm tra hạn mức trước khi tạo job | openapi, data-model `discovery_runs` |
| FR-005, FR-006…FR-006f nguồn | SearchSourcePolicy + SearXNG + adapter độc lập | research R-01/R-02, internal-interfaces §1 |
| FR-007…FR-011 phân tích | AI extract/assess với schema; `pain_points`, `buyer_personas`, `competitors`, `niche_findings` | data-model §2 |
| FR-012…FR-012c PII | PiiRedactor trước DB/AI/log; `NEEDS_REVIEW` | research R-05, internal-interfaces §3 |
| FR-013…FR-016 bằng chứng | `niche_evidence_links`, ngưỡng do mã tính, MOCK | research R-06, scoring-rubric §1 |
| FR-013e/f xóa | EvidenceErasureService + ledger + restore hook | research R-09, internal-interfaces §4 |
| FR-017…FR-021 chấm điểm | `niche_evaluations` bất biến, phiên bản trọng số | scoring-rubric §2–3 |
| FR-022 dedup | `niche_similarity`, `dedup_key` | scoring-rubric §4 |
| FR-023…FR-026 báo cáo, quyết định, UI | API + 3 màn hình | openapi, quickstart |
| FR-027…FR-032 job, chi phí, độ bền | Job Runtime E0, `page_fetch_log`, `domain_access_state`, metrics | research R-04/R-11 |
| FR-033, FR-034 lịch, đánh giá lại | Scheduler E0 với job type `discovery.run`/`discovery.reevaluate` | openapi (dùng `/schedules` E0) |
| FR-035, FR-036 rủi ro, audit | `risk_flags`, audit action `discovery.*`, `niche.*`, `search_source.*`, `scoring.*`, `evidence.erased` | data-model |

## Complexity Tracking – điểm mở rộng E0 cần chủ sở hữu duyệt

| # | Mở rộng | Lý do | Phương án đơn giản hơn đã cân nhắc |
|---|---|---|---|
| X1 | Thêm service `searxng` (Compose profile mặc định) và `crawl4ai` (profile tùy chọn) | FR-006b – dữ liệu thật; Q1 chọn SearXNG | Gọi trực tiếp máy tìm kiếm: nhiều điều khoản cấm hơn, không có lớp lọc engine |
| X2 | Thêm cột vào `research_sources`/`research_evidence` (E0) | Tính độc lập, xóa bằng chứng, trạng thái che PII | Bảng phụ 1-1: thêm join cho mọi truy vấn bằng chứng, dễ quên lọc `ERASED` |
| X3 | `EvidenceService.query` lọc mặc định `lifecycle_status = ACTIVE` | FR-013e | Lọc ở từng nơi gọi: rủi ro rò rỉ bằng chứng đã xóa |
| X4 | Volume `erasure-ledger` + bước áp lại trong `restore.sh` | FR-013f – dữ liệu đã xóa không quay lại sau restore | Xóa khỏi mọi bản backup: không khả thi với backup đã nén/ngoài máy |
| X5 | Mã lỗi mới (`NO_COMPLIANT_SEARCH_SOURCE`, `SOURCE_PROHIBITED`, `SOURCE_WARNING_NOT_ACKNOWLEDGED`, `RUN_BUDGET_EXCEEDS_DAILY_LIMIT`, `WEIGHTS_INVALID`, `NICHE_NOT_FOUND`, `EVIDENCE_ALREADY_ERASED`, `DISCOVERY_RUN_NOT_FOUND`) trong `error-codes.json` | Hợp đồng lỗi E0 (code ổn định + i18n) | – |
| X6 | Task type mới trong Model Task Profile (seed) + định nghĩa agent mới | FR-028 | – (là dữ liệu cấu hình E0 đã hỗ trợ) |
| X7 | Mở rộng `traceability_report.py` đọc nhiều spec (`TC_E1_` prefix) | Constitution IX | Script riêng cho E1: trùng logic |
| X8 | Phụ thuộc mới (bảng Technical Context) | R-02…R-08 | Tự viết trích nội dung/robots/PII: kém tin cậy, trái OSS-First |

## Rủi ro và việc cần chủ sở hữu quyết định trước `/speckit-tasks`

1. **Hồ sơ tuân thủ nguồn**: trong môi trường này chỉ đọc được điều khoản của Microsoft/Bing (có điều khoản cấm "impermissible
   scraping") – mọi engine khác `UNVERIFIED` do mạng bị chặn (research R-01). Hệ quả: mặc định mọi lượt kết thúc
   `NO_COMPLIANT_SEARCH_SOURCE` cho tới khi chủ sở hữu xác minh ít nhất một nguồn `ALLOWED` hoặc tự bật nguồn `UNVERIFIED` có cảnh báo.
2. **Crawl4AI**: chấp nhận làm profile tùy chọn (khuyến nghị) hay mặc định; xác nhận cách hiểu yêu cầu ghi công.
3. **Nhận diện tên người**: spaCy `en_core_web_sm` cho tiếng Anh + heuristic/`NEEDS_REVIEW` cho ngôn ngữ khác (R-05), hay Presidio.
4. **Model cho task type mới** (Haiku 5.5 / Sonnet 5.5) – chỉ dùng khi giá đã xác minh; gọi có phí vẫn tắt.
5. Duyệt các mở rộng X1–X8.

## Kiểm tra tính nhất quán (Phase 1 – 2026-11-19)

**Với Master Requirements**

| Yêu cầu | Bao phủ |
|---|---|
| E1-01…E1-03 (AC-04) | FR-001…FR-003; `discovery.candidates`; lượt không chọn lĩnh vực |
| E1-04 (BR-01) | FR-005, FR-006…f; SearXNG + policy nguồn; không giả định API miễn phí |
| E1-05, E1-06 (AC-05), E1-10 | `pain_points`, `buyer_personas.attributes.ability_to_pay` |
| E1-07…E1-09, E1-11…E1-13 | `discovery.extract/assess`, `niche_findings`, `competitors`, thang chấm scoring-rubric §2 |
| E1-14, E1-15 (BR-03, BR-04, AC-06) | `niche_evaluations`, scoring-rubric §3; hai hàm tách biệt |
| E1-16 | `niche_similarity`, scoring-rubric §5 |
| E1-17 (DATA-03, AC-07) | `research_sources/research_evidence` E0 + `collected_at`, `verified_at` |
| E1-18 (AC-16) | `/discovery/runs/{id}/report`, `/niches?list=…` |
| E1-19 (AC-13), E1-20 (Should) | Scheduler E0 + `discovery.run`/`discovery.reevaluate` |
| BR-07 (16 trường) | tên, micro-niche, quốc gia, nhóm KH (`niches`); pain points; giải pháp hiện tại, khoảng trống, sản phẩm tiềm năng, khả năng kiếm tiền, kênh, rủi ro (`niche_findings`); đối thủ (`competitors`); Opportunity, Confidence (`niche_evaluations`); nguồn (`niche_evidence_links`); đề xuất (`ai_recommendation`) – đủ 16 |
| BR-08, AC-19 | Tool E1 chỉ đọc; không đăng ký/xuất bản |
| BR-09 | Trích đoạn ≤ 1000 ký tự (ràng buộc E0), không lưu nguyên văn trang |
| BR-10 | `research_language` độc lập ngôn ngữ UI |

Ngoài phạm vi (không thiết kế): bảng sản phẩm/chương trình affiliate (E2), keyword/search volume (E3), biểu đồ/phân tích nâng cao (E4),
E5–E8.

**Với E0 (đã nghiệm thu)**: không đổi state machine job, Gateway, công thức giữ chỗ ngân sách, cơ chế mock/production guard, hợp
đồng lỗi, phân lớp import. Mọi thay đổi chạm E0 là bổ sung và nằm trong X1–X8 (Complexity Tracking). Hạn mức $3/ngày, $30/tháng giữ
nguyên; $2/lượt là giới hạn job E0 sẵn có. `AI_PAID_CALLS_ENABLED=false` giữ nguyên; chưa có model/giá đã xác minh nên E1 chạy với
`MockAIProvider` cho tới khi chủ sở hữu bật API thật theo `docs/operations/enable-real-api.md`.

**Không còn `NEEDS CLARIFICATION`** trong Technical Context. Các mục chờ quyết định là phê duyệt (X1–X8, mục "Rủi ro và việc cần
chủ sở hữu quyết định"), không phải mơ hồ yêu cầu.
