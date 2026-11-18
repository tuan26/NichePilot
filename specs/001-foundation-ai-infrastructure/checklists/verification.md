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
| Smoke dev (hot reload) | `SMOKE_NO_BUILD=1 SMOKE_EXTRA_COMPOSE=<override cục bộ> deploy/tests/smoke.sh dev` (14:29Z) | PASS (có điều kiện) | reload api=1 worker=1 web=1. Cần override cục bộ (không commit) cho web dùng mạng host + CA/proxy; chạy KHÔNG build nên không phát hiện lỗi kế thừa `build:` – lỗi đó chỉ lộ trên CI (run 17) và đã sửa ở `7c4afc7` |
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
| 16 | `4d13bed` | smoke – bước "Smoke dev" | FAIL – web dev lặp `sh: npm: not found` (xác định ở run 17) |
| 17 (44326619845) | `de9d104` | smoke – bước "Smoke dev" (có chẩn đoán) | FAIL – nguyên nhân: override dev kế thừa `build:` Caddy, `up --build` gắn nhãn đè node:22-alpine |
| 18 (44328603640) | `7c4afc7` | backend, frontend, traceability, e2e | PASS |
| 18 | `7c4afc7` | smoke – "Smoke prod" (14:51:08–14:53:10Z) | PASS |
| 18 | `7c4afc7` | smoke – "Smoke dev" (14:53:11–14:54:08Z) | **PASS** – `reload api=1 worker=1 web=1`, `PASS dev` |
| 18 | `7c4afc7` | secrets | FAIL – dương tính giả detect-secrets (N1, ngoài phạm vi) |

### Windows 10/11

BLOCKED – NOT RUN: không có máy Windows trong môi trường này; `checklists/windows-manual.md` giữ nguyên trạng thái chưa thực hiện.

---

## Quyết định chủ sở hữu N1 & C3 (2026-11-18)

### C3 – Chính sách giá cuối cùng (APPROVED WITH CONDITIONS)

| Trường hợp | Giá áp dụng |
|---|---|
| Cache write có giá đã xác minh | Giá chính thức trong bảng giá |
| Cache write NULL, prompt ≤ ngưỡng | 2 × giá input bậc thường |
| Prompt > ngưỡng (Haiku 5.5: 100.000 token) | Bậc cao cho input/output; độ dài prompt = input + cache read + cache write |
| Cache write ở bậc cao (schema chưa có giá cache bậc cao) | 2 × giá input bậc cao |
| Cache read có giá đã xác minh (bậc thường) | Giá chính thức – **không** nhân 2× |
| Cache read NULL, hoặc cache read ở bậc cao | Giá input của bậc áp dụng (cao hơn mọi giá cache read chính thức → bảo thủ) |
| Không đếm được token đầu vào, hoặc giá input/output = 0 (provider có phí) | Chặn trước khi giữ chỗ và gửi: `COST_ESTIMATE_UNAVAILABLE` |
| Model hoặc giá chưa xác minh | Chặn: `MODEL_NOT_VERIFIED` / `PRICING_NOT_VERIFIED` |
| Giá `verified = true` của provider có phí | Bắt buộc `source_note` có URL nguồn chính thức + ngày xác minh YYYY-MM-DD (API 422; DB `ck_model_pricing_verified_source_date`, migration 0008) |

Usage của provider tách riêng `cache_read_tokens` và `cache_write_tokens` → chi phí thực tính đúng từng loại. **Giả định khi không
phân biệt được** (lúc giữ chỗ, trước khi gửi, chưa biết phần nào của prompt sẽ là cache read/write): mỗi token prompt tính theo
mức cao nhất trong input / cache read / cache write của bậc áp dụng.

**Công thức giữ chỗ** (`ai/pricing.py:max_cost`):
`reserve = ceil_6dp( (N_prompt × max(r_input, r_cache_read, r_cache_write) + N_max_output × r_output) / 1.000.000 )`,
tối thiểu 0.000001; `N_prompt` = số token đếm bởi provider (count_tokens – không tính phí), bậc giá chọn theo `N_prompt`.
Ví dụ mock (giá giả lập trong DB: input 0.10, cache read 0.01, cache write 0.125, output 0.50; prompt 2.000; max output 1.024):
`(2.000 × 0.125 + 1.024 × 0.50) / 1e6 = 0.000762` – test TC_FR043_20 tính lại từ DB, không hardcode.

**Nguồn giá và ngày xác minh**: trang chính thức `https://platform.claude.com/docs/en/about-claude/pricing`, agent đọc ngày
2026-11-18 (bảng tham khảo trong `docs/operations/enable-real-api.md` §3). Trong database **không** có bản giá provider thật nào
`verified = true`: agent không tự điền giá đã xác minh – chủ sở hữu thêm qua `POST /api/v1/model-pricing` với URL + ngày.

Test C3 (đều chạy, PASS): (1) TC_FR040_10; (2) TC_FR040_11; (3) TC_FR040_12; (4) TC_FR040_13; (5) TC_FR041_10;
(6) TC_FR041_11; (7) TC_FR043_12; (8) TC_FR043_13 (giá 0), TC_FR043_14 + TC_FR019c_01 (chưa xác minh), TC_FR041_20/21
(thiếu nguồn/ngày); (9) TC_FR043_20; (10) TC_FR043_12/13 (gateway fail closed). Thêm: TC_FR043_10 (giữ chỗ ≥ chi phí thực
với mọi cách chia prompt).

### N1 – Kết quả quét secret (APPROVED)

detect-secrets 1.5.0, 42 finding / 16 file: 42 Confirmed false positive, 0 Potential secret, 0 Confirmed secret
(chi tiết và cách xác minh: `docs/operations/security.md`). `.secrets.baseline` chỉ chứa các mục đã rà soát (`is_secret: false`,
chỉ hash). Kiểm tra: `backend/scripts/check_secrets.py` (cục bộ PASS); canary sinh lúc chạy bị phát hiện (TC_SC008_12 PASS).
