# Implementation Plan: E1 – Autonomous Niche Discovery

**Branch**: `claude/inspiring-wright-06dzhw` (feature dir `specs/002-niche-discovery`) | **Date**: 2026-11-19, cập nhật 2026-11-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification `specs/002-niche-discovery/spec.md` (đã clarify Q1–Q8, 2026-11-19; quyết định phê duyệt 2026-11-20)

**Trạng thái**: `APPROVED WITH CONDITIONS` (chủ sở hữu, 2026-11-20) – plan đã cập nhật theo điều kiện; được phép `/speckit-tasks`,
`/speckit-analyze`. Chưa `/speckit-implement`. Không có lời gọi API có phí.

## Summary

E1 bổ sung một module nghiệp vụ `discovery` chạy trên nền E0 (Job Runtime, AI Gateway + giữ chỗ ngân sách, Tool Registry,
EvidenceService, audit, i18n) để tự động: (1) tìm vấn đề khách hàng thật qua `SourceAdapter` chung – SearXNG tự host và (sau này) API chính
thức/dữ liệu mở/dữ liệu cấp phép; lượt tự động chỉ dùng nguồn `ALLOWED`, nguồn `UNVERIFIED` chỉ dùng khi chủ sở hữu tự bật và chọn
cho lượt thủ công, (2) tải trang công khai tôn trọng robots.txt và
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
**Mới cho E1** (X8 – đã xác minh giấy phép/phiên bản/tương thích Python 3.13 ngày 2026-11-20, chi tiết research R-12):

| Thành phần | Phiên bản xác minh | Giấy phép | Vai trò | Điều kiện |
|---|---|---|---|---|
| SearXNG (image chính thức, không sửa mã) | `2026.11.18-b867c56a5` | AGPL-3.0-or-later (nhãn OCI) | Metasearch tự host | Service riêng, mạng nội bộ; RAM nghỉ đo được ≈ 103 MiB; `keep_only` engine theo policy |
| `trafilatura` | 2.3.1 | Apache-2.0 (deps: Apache/BSD/MIT/MPL-2.0) | Trích nội dung chính – **mặc định** | – |
| Playwright + Chromium (tùy chọn) | 1.65.2 | Apache-2.0 | Trang cần JavaScript | Profile `browser-fetcher`, **tắt mặc định**, không cài vào image worker; tài nguyên đo khi bật |
| `protego` | 0.7.0 | BSD-3-Clause | robots.txt theo RFC 9309 | `urllib.robotparser` của Python 3.13 thiếu wildcard RFC 9309 |
| `phonenumbers` | 9.0.43 | Apache-2.0 | `[PHONE]` | – |
| spaCy + `en_core_web_sm` | 3.8.18 + 3.8.0 | MIT; model MIT + ghi chú dữ liệu OntoNotes "licensed by Explosion" | `[PERSON]` tiếng Anh | Đo: +291 MB image, RSS ≈ 151 MB; cài từ wheel ghim + SHA-256, không tải lúc chạy; **production chờ chủ sở hữu chấp nhận ghi chú dữ liệu model** |
| `rapidfuzz` | 3.14.6 | MIT | So khớp mờ | – |
| `tldextract` | 5.4.0 | BSD-3-Clause | eTLD+1 | Bắt buộc `suffix_list_urls=()` (không tải PSL lúc chạy) |
| SimHash (tự viết) | – | – | Phát hiện bản sao | – |
| ~~Crawl4AI~~ | 0.9.5 | Apache-2.0 | – | **Không dùng**: phụ thuộc bắt buộc `playwright-stealth`, `patchright` (lẩn tránh phát hiện bot – trái FR-006f), README mâu thuẫn về ghi công (R-03) |

**Storage**: PostgreSQL 17 (bảng mới ở [data-model.md](./data-model.md), migration `0009_discovery`, `0010_discovery_seed`);
sổ xóa bằng chứng `erasure-ledger` là file append-only trên volume riêng (R-09).

**Testing**: pytest (unit, integration testcontainers `postgres:17-alpine`, contract), Vitest, Playwright E2E. Nguồn bên ngoài trong
test dùng **adapter giả lập** (`MockSourceAdapter`, `MockPageFetcher` với HTML cố định) – dữ liệu gắn `MOCK`; AI dùng
`MockAIProvider`. Rào chắn socket của E0 giữ nguyên: test không truy cập mạng. Bộ kiểm thử thu thập thật (`tests/live_sources`)
deselected mặc định, chỉ chạy khi chủ sở hữu bật và có ít nhất một nguồn `ALLOWED`.

**Target Platform**: Docker Compose trên Linux và Windows 10/11 (WSL2), như E0.

**Project Type**: Web application (backend + frontend) – cấu trúc E0.

**Performance Goals**: một lượt ≤ 90 phút hoạt động; API danh sách/xếp hạng p95 < 500 ms với ≤ 5.000 ngách; tính lại điểm
(`discovery.recompute`, không AI) ≤ 60 s cho 1.000 ngách.

**Constraints**: ≤ $2 AI/lượt, $3/ngày, $30/tháng (E0); 1 request/2 s/tên miền (trần); 300 trang/lượt; RAM nghỉ toàn hệ thống
≤ 3 GB (đo 2026-11-20: SearXNG ≈ 103 MiB nghỉ, spaCy NER ≈ 151 MB RSS; ước tính E0 + E1 ≈ 0,6–0,7 GB nghỉ); CPU 4 core / RAM
15 GB của chủ sở hữu; trình duyệt không bật mặc định; không lưu PII chưa che; không vượt CAPTCHA.

**Scale/Scope**: 1 chủ sở hữu, 1 project; ~20 ngách/lượt, vài lượt/tuần; 7 user story, FR-001…FR-036 (gồm FR-006g), SC-001…SC-017.

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
| VII. OSS-First | Đánh giá SearXNG, Crawl4AI, trafilatura | PASS – X8 duyệt có điều kiện; giấy phép/phiên bản/tương thích đã xác minh (R-12); Crawl4AI bị loại có lý do; điều kiện còn lại: ghi chú dữ liệu model spaCy trước production |
| VIII. Module & API-First | Module riêng, API cho mọi chức năng | PASS – `modules/discovery`, `SourceAdapter` tổng quát (nguồn = cấu hình, không sửa code), import-linter giữ lớp E0 |
| IX. TDD & truy vết (KTL) | Mỗi FR Must có TC | PASS – mã test `TC_E1_FRxxx_nn`, mở rộng `traceability_report.py` cho spec 002 (xem Complexity) |
| X. Security-by-Design | PII, secret, tuân thủ nguồn | PASS – `PiiEngine` trước DB/AI/log/checkpoint; nguồn tự động chỉ `ALLOWED`, không đường mã tự bật nguồn; secret nguồn chỉ qua tên biến môi trường; `SEARXNG_SECRET` sinh lúc cài, ngoài repo; erasure ledger fail-safe; CI secret scanning giữ nguyên |
| XI. Self-hosted, tiết kiệm | ≤ 3 GB RAM | PASS – số đo thật (SearXNG 103 MiB, NER 151 MB); trình duyệt tắt mặc định |
| XII. Song ngữ | 3 màn hình VI/EN | PASS – khóa i18n mới, test `i18n-keys` áp dụng |

Constitution Check lại 2026-11-20 sau khi cập nhật theo phê duyệt: 12/12 PASS, không vi phạm cần biện minh. Các mở rộng E0 (X1–X8)
là bổ sung, đã được chủ sở hữu duyệt có điều kiện; điều kiện được ghi ở Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/002-niche-discovery/
├── spec.md
├── plan.md              # File này
├── research.md          # Phase 0 (R-01…R-13)
├── source-verification.md # Nguồn cần xác minh (BLOCKED do mạng)
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1 – kịch bản kiểm chứng
├── contracts/
│   ├── openapi.yaml             # REST API E1
│   ├── internal-interfaces.md   # SourceAdapter, PageFetcher, PiiEngine, erasure ledger, agent, job types
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
│   ├── sources/policy.py            # SourcePolicyService (usable_for_run, cảnh báo, audit; không tự bật/nâng trạng thái)
│   ├── sources/searxng_config.py    # sinh settings.yml SearXNG (keep_only) từ policy
│   ├── privacy/engine.py            # PiiEngine (interface) + RegexSpacyPiiEngine; NEEDS_REVIEW/UNSAFE
│   ├── privacy/erasure.py           # EvidenceErasureService, ledger (hash chain, fsync), apply --strict, ledger_health
│   ├── evidence_rules.py            # ngưỡng, nhóm độc lập (eTLD+1 + SimHash)
│   ├── scoring/opportunity.py       # Opportunity + Coverage
│   ├── scoring/confidence.py        # Confidence (N,Q,D,F,K,V)
│   ├── dedup.py                     # rapidfuzz token_set_ratio
│   └── ranking.py                   # 3 danh sách: cơ hội / ưu tiên affiliate / cần nghiên cứu thêm
├── tools/                           # MỞ RỘNG – thêm tool chỉ đọc (Tool Registry E0)
│   ├── sources/base.py              # SourceAdapter, SourceResult, registry theo adapter_type
│   ├── sources/searxng_engine.py    # adapter_type searxng_engine
│   ├── sources/http_json_api.py     # adapter_type http_json_api (khung, auth qua tên biến môi trường)
│   ├── sources/dataset.py           # open_dataset / licensed_data (interface + mock)
│   ├── page_fetch.py                # PageFetcher (robots/protego, rate per domain, httpx + trafilatura)
│   ├── page_fetch_playwright.py     # tùy chọn, chỉ trong image browser-fetcher
│   └── mock_sources.py              # MockSourceAdapter/MockPageFetcher (dev/test, MOCK)
├── ops/apply_erasure_ledger.py      # MỚI – CLI dùng bởi migrate và restore.sh
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

deploy/docker-compose.yml            # + service `searxng`, `browser-fetcher` (profile tùy chọn), volume `erasure-ledger`, `searxng-config`;
                                     #   migrate: alembic upgrade && apply_erasure_ledger --strict
deploy/searxng/settings.base.yml     # keep_only rỗng, formats html+json, limiter/public_instance/image_proxy tắt
deploy/scripts/restore.sh            # + apply_erasure_ledger --strict sau pg_restore; lỗi → exit ≠ 0
deploy/scripts/backup.sh             # + sao bản ledger kèm dump
docs/operations/discovery.md         # vận hành E1 (nguồn, xác minh ToS, xóa bằng chứng)
```

**Structure Decision**: giữ cấu trúc web app của E0; E1 là một module trong `modules/` + tool trong `tools/` + agent trong `ai/agents/`
+ job type trong `jobs/`, đúng hợp đồng lớp import-linter `api > jobs > (ai, tools, modules) > core`. `modules/discovery` không import
`ai`/`tools`; agent (lớp `ai`) điều phối qua interface trong `core` – xem contracts/internal-interfaces.md §6.

## Luồng xử lý một lượt khám phá (job `discovery.run`)

Mỗi bước là một bước checkpoint của Job Runtime E0 (idempotent theo `seq`):

1. **plan_queries** – AI `discovery.candidates` đề xuất ≤ 20 ngách ứng viên + truy vấn tìm kiếm (theo thị trường/ngôn ngữ/lĩnh vực
   gợi ý). Không AI (mock) → kết quả `MOCK`.
2. **check_sources** – `SourcePolicyService.usable_for_run(trigger, include_unverified)`; rỗng → kết thúc `PARTIAL_COMPLETED` /
   `NO_COMPLIANT_SEARCH_SOURCE` (không gọi AI thêm). (API tạo lượt đã từ chối sớm trường hợp này; bước này bắt trường hợp nguồn bị
   tắt giữa chừng hoặc lượt theo lịch.)
3. **search** (lặp theo ứng viên) – `SourceAdapter.query` cho từng nguồn hợp lệ; lưu URL ứng viên; lỗi nguồn → ghi trạng thái (FR-006a).
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
| FR-005, FR-006…FR-006g nguồn | `source_policies` + `SourceAdapter` + SearXNG; lượt tự động chỉ `ALLOWED` | research R-01/R-02/R-13, internal-interfaces §1, source-verification.md |
| FR-007…FR-011 phân tích | AI extract/assess với schema; `pain_points`, `buyer_personas`, `competitors`, `niche_findings` | data-model §2 |
| FR-012…FR-012c PII | `PiiEngine` (regex + phonenumbers + spaCy) trước DB/AI/log; `NEEDS_REVIEW` | research R-05, internal-interfaces §3 |
| FR-013…FR-016 bằng chứng | `niche_evidence_links`, ngưỡng do mã tính, MOCK | research R-06, scoring-rubric §1 |
| FR-013e/f xóa | ledger hash chain + apply `--strict` trong migrate/restore + gate 503 | research R-09, internal-interfaces §4 |
| FR-017…FR-021 chấm điểm | `niche_evaluations` bất biến, phiên bản trọng số | scoring-rubric §2–3 |
| FR-022 dedup | `niche_similarity`, `dedup_key` | scoring-rubric §4 |
| FR-023…FR-026 báo cáo, quyết định, UI | API + 3 màn hình | openapi, quickstart |
| FR-027…FR-032 job, chi phí, độ bền | Job Runtime E0, `page_fetch_log`, `domain_access_state`, metrics | research R-04/R-11 |
| FR-033, FR-034 lịch, đánh giá lại | Scheduler E0 với job type `discovery.run`/`discovery.reevaluate` | openapi (dùng `/schedules` E0) |
| FR-035, FR-036 rủi ro, audit | `risk_flags`, audit action `discovery.*`, `niche.*`, `source.*`, `scoring.*`, `evidence.erased` | data-model |

## Complexity Tracking – điểm mở rộng E0 (duyệt có điều kiện 2026-11-20)

| # | Mở rộng | Quyết định | Điều kiện / cách đáp ứng |
|---|---|---|---|
| X1 | Service `searxng` (mặc định) và `browser-fetcher` (profile tùy chọn, Playwright) | Đồng ý | `searxng` chỉ mạng nội bộ, `keep_only` rỗng tới khi có nguồn bật; trình duyệt tắt mặc định (thay Crawl4AI – R-03) |
| X2 | Thêm cột `research_sources`/`research_evidence` | Đồng ý | data-model §1 (gồm `source_policy_id`, `source_compliance`) |
| X3 | `EvidenceService.query` lọc `ACTIVE` | Đồng ý | – |
| X4 | Erasure ledger + áp dụng lại khi restore | Đồng ý có điều kiện | (a) bền vững: volume riêng, append-only, fsync, hash chain, bản sao kèm backup; (b) áp dụng **trước khi** dùng/phục vụ: chạy trong `migrate` (api/worker phụ thuộc) và trong `restore.sh`; (c) thất bại an toàn: thiếu/hỏng/lệch → exit ≠ 0, `BLOCKED`, API 503 `ERASURE_LEDGER_NOT_APPLIED`, worker không nhận job; (d) test TC_E1_FR013f_* (research R-09) |
| X5 | Mã lỗi mới | Đồng ý | Bổ sung: `UNVERIFIED_SOURCE_NOT_ENABLED`, `SOURCE_VERIFICATION_INCOMPLETE`, `SOURCE_CONFIG_INVALID`, `SOURCE_EXISTS`, `ERASURE_LEDGER_NOT_APPLIED`, `EVIDENCE_NOT_FOUND` |
| X6 | Task type AI + agent mới | Đồng ý | Model chỉ qua Model Task Profile; không hard-code |
| X7 | `traceability_report.py` đọc nhiều spec | Đồng ý | – |
| X8 | Dependency mới | Đồng ý có điều kiện | Đã xác minh (R-12). Thêm vào `pyproject.toml` từng gói kèm ghim phiên bản trong task riêng; spaCy model chỉ cài từ wheel ghim + SHA-256; Playwright chỉ trong image tùy chọn; production chờ chủ sở hữu chấp nhận ghi chú dữ liệu model spaCy – nếu không chấp nhận, PII engine chạy regex + phonenumbers và mọi đoạn tiếng Anh có khả năng chứa tên → `NEEDS_REVIEW` |

## Mục BLOCKED do giới hạn mạng (không phải lỗi implementation)

Chi tiết: [source-verification.md](./source-verification.md) §4.

| Mục | Trạng thái | Ảnh hưởng |
|---|---|---|
| Xác minh điều khoản 11 nguồn (S1–S11) | BLOCKED | Mọi nguồn `UNVERIFIED`; lượt nguồn thật → `NO_COMPLIANT_SEARCH_SOURCE`; SC-013 chưa kiểm chứng được |
| Đọc RFC 9309 (S12) | BLOCKED | Dùng phương án thận trọng (R-04) |
| Truy vấn JSON thật qua SearXNG | NOT_TESTED (không được phép khi chưa có nguồn hợp lệ) | Định dạng phản hồi thật từng engine chưa kiểm chứng |
| Claude/OpenAI API thật | NOT_TESTED (kế thừa E0) | Phân tích AI chạy `MockAIProvider`, kết quả `MOCK` |

## Câu hỏi cần chủ sở hữu xác nhận (không chặn `/speckit-tasks`)

1. Cách hiểu FR-006d: nguồn `UNVERIFIED` do chủ sở hữu bật **chỉ** dùng trong lượt thủ công có chọn rõ `include_unverified_sources`,
   không bao giờ trong lượt theo lịch. Nếu muốn chặt hơn (cấm hẳn dùng nguồn `UNVERIFIED`), chỉ cần bỏ tùy chọn này.
2. Chấp nhận ghi chú dữ liệu huấn luyện của model `en_core_web_sm` cho production (X8).

## Kiểm tra tính nhất quán (Phase 1 – 2026-11-19, kiểm tra lại 2026-11-20)

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

**Không còn `NEEDS CLARIFICATION`** trong Technical Context. Hai câu hỏi xác nhận ở trên không chặn lập task (mặc định đã chọn phương án
chặt hơn trong phạm vi quyết định của chủ sở hữu).
