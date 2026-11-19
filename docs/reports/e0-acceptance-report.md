# Báo cáo nghiệm thu E0 – Foundation & AI Infrastructure

**Ngày**: 2026-11-19 | **Nhánh**: `claude/inspiring-wright-06dzhw` | **Commit mốc**: `161f77c`
**Trạng thái E0**: `IMPLEMENTATION_COMPLETE / PENDING_EXTERNAL_VERIFICATION` (chủ sở hữu xác nhận 2026-11-19)
**Không** phải `PRODUCTION_VERIFIED`. Hai hạng mục ở trạng thái `NOT_TESTED`: kiểm thử trên Windows 10/11 và tích hợp
Claude/OpenAI API thật.

Quy ước trạng thái: **PASS** – đã chạy, có bằng chứng · **FAIL** – đã chạy, không đạt · **NOT_TESTED** – chưa chạy ·
**BLOCKED** – không chạy được trong môi trường hiện tại. Mọi kiểm thử tự động dùng `MockAIProvider` hoặc transport HTTP giả
lập; không có lời gọi API có phí nào.

## 1. Acceptance Criteria (Master Requirements §AC) thuộc phạm vi E0

| AC | Nội dung | Trạng thái | Bằng chứng |
|---|---|---|---|
| AC-01 | Khởi động hệ thống trên Windows | **NOT_TESTED** | Chưa có máy Windows. Phần Linux PASS: smoke prod (healthy 22 s, RAM nghỉ 324–361 MB), CI job `smoke`. Hướng dẫn: §3 |
| AC-02 | Claude API hoạt động | **NOT_TESTED** | Chưa có API key và chưa được phép gọi có phí. Adapter chỉ kiểm thử bằng `httpx2.MockTransport` (TC_FR010…, `test_anthropic_adapter.py`). Bộ live `tests/live` BLOCKED theo thiết kế. Hướng dẫn: §4 |
| AC-03 | Có giới hạn chi phí AI | **PASS** | US3 + C3: TC_SC004_01, TC_FR043_*, TC_FR045_01, TC_FR049_03/04, TC_FR040_*/TC_FR041_*; tranh chấp 2 worker × 10 lời gọi (`test_budget_concurrency.py`); quickstart §5 trên stack thật |
| AC-07 | Có nguồn bằng chứng (phần E0: hạ tầng) | **PASS** (hạ tầng) | Bảng `research_sources/research_evidence` + `EvidenceService`: TC_FR007_01–03. Dữ liệu nghiên cứu thật thuộc E1+ |
| AC-12 | Dashboard VI/EN (phần khung E0) | **PASS** (khung) | `i18n-keys.test.ts` (100% chuỗi có bản dịch, không chuỗi cứng trong JSX); Playwright E2E US1 chuyển VI/EN; TC_FR061_* |
| AC-13 | Chạy thủ công và theo lịch | **PASS** | TC_FR033_01–08, TC_SC007_01/02; quickstart §3, §7 trên stack thật (đúng 1 job/mốc 5 phút) |
| AC-14 | Có logging và retry | **PASS** | TC_FR050_01/02 (log theo job, không secret), TC_FR014_01–04, TC_QA01_01, US4 auto-retry; quickstart §4 (10/10 kịch bản lỗi) |
| AC-15 | Dữ liệu lưu PostgreSQL | **PASS** | TC_FR003_01/02 (chỉ nhận `postgresql+psycopg`), TC_FR004_01/02 (migration up/down/up, ORM khớp migration), migration tới `0008` |
| AC-17 | Có automated tests | **PASS** | Backend 322 passed (2 live deselected); frontend 4; E2E 1; CI 6 job xanh |
| AC-19 | Không tự đăng ký affiliate hoặc xuất bản | **PASS** (E0) | Tool có tác động bên ngoài bị từ chối: TC_FR023_01, TC_FR022_01, TC_FR024_*; E0 không có tích hợp bên ngoài |
| AC-20 | Có hướng dẫn vận hành và cấu hình | **PASS** | `docs/operations/` (README, windows-setup, windows-testing, troubleshooting, backup-restore, enable-real-api, security); TC_FR071_01/02 |

Các AC khác (AC-04…06, 08…11, 16, 18) thuộc E1–E4, ngoài phạm vi E0.

## 2. Success Criteria của spec E0

| SC | Trạng thái | Bằng chứng |
|---|---|---|
| SC-001 – khởi động Windows ≤ 30 phút | **NOT_TESTED** | Cần máy Windows (§3). Linux: healthy trong 22 s |
| SC-002 – RAM nghỉ ≤ 3 GB | **PASS (Linux)** / **NOT_TESTED (Windows)** | Linux 324–361 MB (`docker stats`), CI smoke; Windows chưa đo |
| SC-003 – job với provider thật, chi phí lệch ≤ 1% | **NOT_TESTED** | Chưa được phép; TC_SC003_01 chỉ kiểm tra công thức. §4 |
| SC-003b – toàn bộ luồng chạy với mock, 0 lời gọi mạng | **PASS** | TC_SC003b_01, rào chắn socket (TC_FR072_02), quickstart 39/39 |
| SC-004 – không vượt ngân sách, kể cả tranh chấp | **PASS** | TC_SC004_01, `test_budget_concurrency.py`, TC_FR043_10 (giữ chỗ ≥ chi phí thực) |
| SC-004b – UNCERTAIN không tự giải phóng | **PASS** | TC_FR049_03/04, TC_FR048_01, TC_FR032_21 |
| SC-005 – kết quả sai schema không được lưu | **PASS** | TC_SC005_01, TC_FR013_01/02 |
| SC-006 – tiếp tục từ checkpoint, không trùng | **PASS** | TC_SC006_01–03; stack thật: kill worker và mất DB 20 s → không `seq` trùng |
| SC-007 – lịch đúng 1 job/mốc | **PASS** | TC_SC007_01/02, quickstart §7 |
| SC-008 – 0 secret trong log/API/UI/git | **PASS** | TC_SC008_01, TC_SC008_10–12, CI `secrets` (baseline đã rà soát, `docs/operations/security.md`) |
| SC-009 – QA-01, 02, 08, 09, 10, 11, 14, 15 có test và pass | **PASS** | TC_QA01_01, TC_SC005_01, TC_QA08_01, TC_QA09_01, TC_SC006_*, US3, TC_QA14_01, TC_FR014_04 + test-connection INVALID_KEY |
| SC-010 – 100% chuỗi UI có VI/EN | **PASS** | `i18n-keys.test.ts`, E2E US1 |
| SC-011 – 100% FR Must truy vết được | **PASS** | `traceability_report.py --strict`: 58/58 |
| SC-012 – backup → restore khớp 100% | **PASS** | TC_SC012_01 (script thật trong postgres:17-alpine); `make backup/restore` trên stack thật |

## 3. Bằng chứng CI (GitHub Actions)

| Run | Commit | backend | frontend | traceability | secrets | e2e | smoke prod | smoke dev |
|---|---|---|---|---|---|---|---|---|
| 44328603640 | `7c4afc7` | PASS | PASS | PASS | FAIL (trước N1) | PASS | PASS | PASS |
| 44348170145 | `f171f56` | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 44349886271 | `955083a` | PASS | PASS | PASS | PASS | PASS | PASS | PASS |
| 44350874298 | `161f77c` | PASS | PASS | PASS | PASS | PASS | PASS | PASS |

Chi tiết từng lần kiểm chứng (cục bộ, stack Docker thật, CI): `specs/001-foundation-ai-infrastructure/checklists/verification.md`.

## 4. Hướng dẫn kiểm thử Windows 10/11

Xem `docs/operations/windows-testing.md` (quy trình từng bước, số đo cần ghi) và điền kết quả vào
`specs/001-foundation-ai-infrastructure/checklists/windows-manual.md`. Chỉ đánh dấu PASS khi chạy trên Windows thật.

## 5. Hướng dẫn cấu hình và kiểm thử Claude API thật (khi được phép)

Xem `docs/operations/enable-real-api.md` §2 (cấu hình) và §5 (kịch bản kiểm thử, tiêu chí đạt, quay lui). Điều kiện bắt buộc:
API key chính thức (không dùng Claude Pro, OAuth, cookie hay Claude Code CLI), model và bảng giá đã xác minh (có URL nguồn và
ngày), `AI_PAID_CALLS_ENABLED=true` chỉ trong thời gian kiểm thử, `NICHEPILOT_LIVE_MAX_USD` giới hạn chi phí.

## 6. Rủi ro còn lại

| # | Rủi ro | Mức | Giảm thiểu hiện có / việc cần làm |
|---|---|---|---|
| R1 | Adapter Anthropic/OpenAI chưa từng gọi API thật – định dạng phản hồi thật có thể khác payload giả lập | Cao | Kiểm thử live theo §5 trước khi dùng cho E1 |
| R2 | Chính sách tính phí khi phản hồi lỗi của provider = UNKNOWN | Trung bình | Giữ `billing.error_responses_not_billed_verified = false` → lời gọi lỗi sau khi gửi thành UNCERTAIN, chờ đối soát |
| R3 | Chưa có bảng giá provider thật nào đã xác minh | Trung bình | Gateway chặn gọi có phí (`PRICING_NOT_VERIFIED`); chủ sở hữu thêm giá có URL + ngày |
| R4 | Chưa kiểm thử Windows/WSL2 (RAM, hot reload qua bind mount, khởi động lại) | Trung bình | Checklist `windows-manual.md` |
| R5 | Worker thoát khi mất kết nối DB, phụ thuộc restart policy | Thấp | Compose `restart: unless-stopped`; chạy ngoài Docker cần process supervisor (`docs/operations/README.md`) |
| R6 | Giá cache bậc > 100K chưa có cột riêng → tính bảo thủ (cao hơn thực tế) | Thấp | Chấp nhận (C3); bổ sung khi E1+ dùng prompt dài |
| R7 | Refusal được ghi `BILLED` theo usage (có thể cao hơn thực tế với category không tính phí) | Thấp | Bảo thủ có chủ đích; xem lại khi có dữ liệu thật |
| R8 | Docker Hub giới hạn tần suất khi build image | Thấp | Cache image; thử lại có backoff |
| R9 | Không có API tăng hạn mức của job đã tạo | Thấp | Theo quyết định U1: hủy hoặc tạo job mới |

## 7. Điều kiện chuyển sang `PRODUCTION_VERIFIED`

1. Checklist Windows 10/11 (`windows-manual.md`) được chủ sở hữu hoặc người được giao chạy trên máy thật: W1–W14 PASS, gồm
   SC-001 (≤ 30 phút) và SC-002 (≤ 3 GB RAM nghỉ).
2. Kiểm thử Claude API thật theo `enable-real-api.md` §5 được phép và PASS: test-connection OK, verify-models, job chẩn đoán
   `SUCCEEDED` với `data_origin = REAL`, chi phí ghi nhận lệch ≤ 1% so với trang usage của Anthropic (SC-003); kết quả ghi vào
   mục "Tích hợp provider thật" của `verification.md`.
3. Model và bảng giá dùng cho production được xác minh (URL nguồn chính thức + ngày), có audit.
4. Chủ sở hữu quyết định chính sách tính phí khi phản hồi lỗi (R2) dựa trên văn bản chính thức hoặc xác nhận của provider.
5. CI xanh toàn bộ (6 job) tại commit phát hành; `AI_PAID_CALLS_ENABLED` được đặt theo quyết định vận hành của chủ sở hữu.
6. Nếu dùng OpenAI làm dự phòng: thêm model/giá đã xác minh và kiểm thử live tương tự.

## 8. Các yêu cầu tiếp tục duy trì (chủ sở hữu, 2026-11-19)

Giữ CI secret scanning và quy trình rà soát finding mới; không tự động thêm finding vào baseline; không dùng credential thật
trong repository; không gọi API có phí khi model/giá chưa xác minh; không tự động bật API thật; giữ MockAIProvider, budget
reservation và kiểm soát chi phí; không dùng Claude Pro hoặc Claude Code CLI thay cho API backend.
