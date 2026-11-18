# Kết quả kiểm chứng Quickstart E0 (T129)

**Ngày chạy**: 2026-11-18 | **Môi trường**: Linux (container phát triển), Docker Engine, image `nichepilot-backend:local`,
`nichepilot-web:local`, `postgres:17-alpine`; `APP_ENV=development`, `AI_PROVIDER_OVERRIDE=mock`,
`AI_PAID_CALLS_ENABLED=false`. Kịch bản §2–§8 chạy bằng script HTTP trên stack Docker Compose thật (cổng 8080).

> Mọi kết quả dưới đây dùng **MockAIProvider** (dữ liệu gắn `MOCK`). Không có lời gọi API có phí nào. Đây **không** phải
> bằng chứng tích hợp Claude/OpenAI API thật.

| Mục | Kiểm tra | Kết quả | Số đo / ghi chú |
|---|---|---|---|
| §1 | `make up` (image dựng sẵn) → healthy | PASS | 26 giây (≤ 300) – `deploy/tests/smoke.sh prod` |
| §1 | RAM nghỉ (`docker stats`) | PASS (Linux) | 317 MB (web 10, api 133, worker 125, postgres 49) – Windows: chưa đo |
| §1 | Trang khởi tạo tiếng Việt | PASS | Playwright E2E US1 trên stack thật |
| §2 | Tạo tài khoản, trang trạng thái (DB/worker OK, provider chưa cấu hình, MOCK, gọi có phí TẮT) | PASS | |
| §2 | Sai mật khẩu 5 lần → lần 6 khóa | PASS | 401×5 rồi 423 `auth_locked` |
| §2 | Chuyển VI/EN, giữ sau tải lại | PASS | Playwright E2E |
| §3 | Job chẩn đoán SUCCEEDED, MOCK, `[MOCK]`, 3 bước AI→TOOL→AI | PASS | |
| §3 | 2 bản ghi usage `provider=mock` | PASS | cần `data_origin=MOCK` (mặc định chỉ REAL – đã sửa quickstart) |
| §3 | Chi tiêu ở sổ mock, sổ real = 0 | PASS | mock $0.000900 |
| §4 | 10 kịch bản lỗi (timeout, rate_limit, fail_n_then_success, schema_invalid, provider_error, auth_error, refusal, truncated, timeout_after_send, network_error) | PASS 10/10 | mã lỗi và số lần thử đúng bảng; auth_error không retry |
| §4 | Hệ thống vẫn phục vụ khi job lỗi mạng (QA-14) | PASS | |
| §5 | budget_heavy → PAUSED_BUDGET `BUDGET_JOB_EXCEEDED`, có chi tiết; resume → 402 | PASS | |
| §5.4 | Tăng ngân sách job rồi resume tiếp tục từ checkpoint | NOT_TESTED trên stack | Không có API sửa hạn mức của job đã tạo; kiểm tự động bằng TC_FR045_01 (sửa DB) – xem phát hiện F-2 trong báo cáo |
| §5.6–7b | UNCERTAIN: cảnh báo, resume → 423, resolve → RESOLVED + audit, resume → 202 | PASS | |
| §6 | Hủy, tạm dừng/tiếp tục, idempotency_key | PASS | không lặp `seq` |
| §6 | Kill worker giữa chừng → tự phục hồi | PASS | job RUNNING lúc kill → SUCCEEDED sau 138 giây, attempt 2, seq [1,2,3] |
| §7 | Lịch */5 → đúng 1 job `SCHEDULE` tại mốc | PASS | |
| §7 | Ngân sách = 0 → bật lịch 422 `BUDGET_NOT_CONFIGURED`; tắt lịch | PASS | |
| §8 | `/providers` không trả key | PASS | |
| §8 | Quét `sk-ant-|sk-proj-|Bearer ` trong stdout và file log | PASS | 0 kết quả |
| §8 | PATCH settings → audit before/after | PASS | |
| §8 | Production + mock → api/worker thoát `MOCK_NOT_ALLOWED` | PASS | worker exit 1, api exit 3 |
| §8 | `log_storage.retention_days = 90` | PASS | |
| §8 | Ngưỡng dung lượng nhỏ → cảnh báo, không xóa | PASS (tự động) | TC_FR057_10/12; không chạy lại trên stack |
| §8 | Tắt postgres 30 giây → 503 rồi tự phục hồi | PASS | 10 lần 503 `SERVICE_UNAVAILABLE`, sau đó 200; không job nào thành công sai. Worker thoát khi mất DB và được Docker khởi động lại (F-3) |
| §8 | `make backup` → `.dump` 0600; khôi phục vào DB trống, số bản ghi khớp | PASS | 17 job / 43 audit / 72 usage / 1 user / `0007_evidence`; `make restore` vào DB có dữ liệu bị từ chối (đúng thiết kế) |
| §9 | Tích hợp API thật | **CHƯA KIỂM CHỨNG** | chưa có API key và chưa được chủ sở hữu cho phép; `tests/live` BLOCKED |
| §10 | Bộ test tự động | PASS | backend 289 passed (2 live deselected), frontend 4, E2E 1; lint/format/mypy/import-linter sạch |
| – | Smoke dev (hot reload trong Docker) | BLOCKED | môi trường này không build được image dev qua proxy; sẽ chạy ở job CI `smoke` |
| – | Windows 10/11 | NOT_TESTED | `checklists/windows-manual.md` chờ chủ sở hữu thực hiện |

---

## Kiểm chứng sau khắc phục findings (2026-11-18, chiều)

Commit kiểm chứng: `4d13bed` (nhánh `claude/inspiring-wright-06dzhw`). Mọi kiểm thử dùng MockAIProvider;
`AI_PAID_CALLS_ENABLED=false`, API key trống; 0 bản ghi usage `REAL`/provider khác `mock`.

### Cục bộ (container phát triển Linux, Docker Engine)

| Kiểm tra | Lệnh | Kết quả | Bằng chứng |
|---|---|---|---|
| Backend toàn bộ | `cd backend && uv run pytest` | PASS | 309 passed, 2 live deselected |
| Lint/format/type/import | `ruff check`, `ruff format --check`, `mypy`, `lint-imports` | PASS | 0 lỗi; 3/3 contract import KEPT |
| Truy vết strict | `uv run --no-project python scripts/traceability_report.py --strict` | PASS | exit 0; 58/58 FR Must; 0 mã "không có trong spec" |
| Frontend | `npx vitest run`, `npm run typecheck`, `npm run lint` | PASS | 4 tests |
| Smoke prod | `SMOKE_NO_BUILD=1 deploy/tests/smoke.sh prod` (image build từ `4d13bed`, 14:31Z) | PASS | healthy 22 s; RAM nghỉ 324 MB |
| E2E Playwright | `npx playwright test` trên stack prod | PASS | 1 passed |
| Smoke dev (hot reload) | `SMOKE_NO_BUILD=1 SMOKE_EXTRA_COMPOSE=<override cục bộ> deploy/tests/smoke.sh dev` (14:29Z) | PASS (có điều kiện) | reload api=1 worker=1 web=1. Cần override cục bộ (không commit) cho container web dùng mạng host + CA/proxy của môi trường này |
| C1 – mất DB 20 s khi đang có job RUNNING | script HTTP trên stack prod | PASS | worker RestartCount=1; 4/4 job SUCCEEDED; không `seq` trùng; job đang chạy có 2 lượt `job.started` (lượt đầu + phục hồi attempt 2), job khác 1 lượt → không thực thi trùng |
| Secret trong log | grep `sk-ant-`/`sk-proj-`/`Bearer `/mật khẩu owner/mật khẩu DB trong stdout và `/var/log/nichepilot` | PASS | 0 kết quả |

Lần chạy smoke prod 14:29Z trước đó dùng image CŨ (build mới bị Docker Hub 429) – **không** tính làm bằng chứng.

### GitHub Actions (CI thật)

| Run | Commit | Job | Kết quả |
|---|---|---|---|
| 12 (44275024260) | `ffeac4c` | backend, frontend, traceability, e2e | PASS |
| 12 | `ffeac4c` | smoke – bước "Smoke prod" | PASS |
| 12 | `ffeac4c` | smoke – bước "Smoke dev" | FAIL → nguyên nhân: web dev OOM (128m) + Vite chưa có module trong graph; đã sửa ở `4d13bed` |
| 12, 16 | `ffeac4c`, `4d13bed` | secrets (detect-secrets) | FAIL – dương tính giả (xem N1 trong báo cáo); ngoài phạm vi đợt sửa này |
| 16 (44324814680) | `4d13bed` | backend, frontend, traceability, e2e | PASS |
| 16 | `4d13bed` | smoke – bước "Smoke prod" | PASS |
| 16 | `4d13bed` | smoke – bước "Smoke dev" | NOT RUN (đang chạy lúc ghi 14:40Z – cập nhật khi có kết quả) |

### Windows 10/11

BLOCKED – NOT RUN: không có máy Windows trong môi trường này; `checklists/windows-manual.md` giữ nguyên trạng thái chưa thực hiện.
