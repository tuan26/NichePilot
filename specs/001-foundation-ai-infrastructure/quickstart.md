# Quickstart & Kịch bản Kiểm chứng: E0

**Ngày**: 2026-11-18 | Liên quan: [spec.md](./spec.md), [contracts/openapi.yaml](./contracts/openapi.yaml),
[contracts/configuration.md](./contracts/configuration.md)

Tài liệu này mô tả **cách chứng minh E0 hoạt động** sau khi triển khai. Các lệnh `make` / tên service sẽ được tạo trong
giai đoạn implement đúng như mô tả dưới đây; tài liệu vận hành đầy đủ nằm ở `docs/operations/` (tạo trong E0).

> **Không tốn phí:** Kịch bản 1–8 chạy hoàn toàn với `MockAIProvider`, không cần API key, không gọi mạng tới provider.
> Kịch bản 9 gọi API thật và **chỉ được chạy khi chủ sở hữu cho phép**.

## 0. Điều kiện tiên quyết

| Môi trường | Yêu cầu |
|---|---|
| Windows 10/11 | Docker Desktop (backend WSL2), một distro WSL2 (Ubuntu), Git trong WSL; `.wslconfig` giới hạn RAM WSL (đề xuất `memory=8GB`) |
| Linux | Docker Engine + Docker Compose v2 |
| Chung | `make`; cổng trống: 8080 (web), 5432 chỉ bind localhost khi dev |

Trên Windows: **clone mã nguồn vào filesystem WSL** (ví dụ `~/code/nichepilot`), không đặt trong `C:\` (`/mnt/c`) để tránh
chậm I/O và lỗi hot-reload.

## 1. Khởi động lần đầu (US1, SC-001, SC-002)

```bash
cp deploy/env/.env.example deploy/env/.env
```

```bash
make up
```

Kỳ vọng:

- `make up` chạy `migrate` (one-shot) rồi `postgres`, `api`, `worker`, `web`; mọi service `healthy` trong ≤ 5 phút.
- `curl -s localhost:8080/health` → `{"status":"ok"}`.
- `docker stats --no-stream` → tổng RAM các service bắt buộc ≤ 3 GB ở trạng thái nghỉ.
- Mở `http://localhost:8080` → trang **Khởi tạo tài khoản** bằng tiếng Việt.

## 2. Tài khoản, đăng nhập, khóa, ngôn ngữ (US1)

1. Tạo tài khoản (mật khẩu ≥ 12 ký tự) → tự đăng nhập, thấy trang **Trạng thái hệ thống**.
2. Trang trạng thái hiển thị: database `OK`, worker `OK`, provider `anthropic`/`openai` = "chưa cấu hình", chế độ AI =
   **Giả lập (MOCK)**, "Gọi API có phí: TẮT".
3. Đăng xuất, nhập sai mật khẩu 5 lần → lần 6 nhận thông báo khóa 15 phút; `GET /api/v1/audit-logs?action=auth.account_locked`
   có bản ghi.
4. Bấm nút **EN** → toàn bộ chuỗi chuyển tiếng Anh ngay; tải lại trang vẫn là tiếng Anh.

## 3. Job chẩn đoán với MockAIProvider (US2, SC-003b)

Gọi API bằng phiên đã đăng nhập (cookie + header CSRF), ví dụ qua Swagger UI tại `http://localhost:8080/api/docs`:

`POST /api/v1/jobs` với body `{"job_type": "system.diagnostic"}`

Kỳ vọng sau vài giây (`GET /api/v1/jobs/{id}`):

- `status = SUCCEEDED`, `data_origin = MOCK`, `result.note` bắt đầu bằng `[MOCK]`.
- `GET /api/v1/jobs/{id}/steps` → 3 bước (AI_CALL → TOOL_CALL `system.runtime_info` → AI_CALL), mỗi bước `data_origin = MOCK`.
- `GET /api/v1/costs/usage?job_id={id}` → 2 bản ghi `provider = mock`, có token và `cost_usd` giả lập.
- `GET /api/v1/budget` → chi tiêu nằm ở `mock`, phần `real` vẫn bằng 0.

## 4. Kịch bản lỗi giả lập (US2, QA-01/02/15, FR-014, FR-017)

Tạo job với `params.mock_scenario`:

| mock_scenario | Kỳ vọng |
|---|---|
| `timeout` | Retry theo backoff (thấy nhiều lần thử trong steps/usage), cuối cùng `FAILED`, `PROVIDER_TIMEOUT` |
| `rate_limit` | Chờ theo `retry_after`, retry, cuối cùng `FAILED`, `PROVIDER_RATE_LIMITED` |
| `fail_n_then_success:timeout:2` | 2 lần lỗi rồi `SUCCEEDED`; không có bước trùng |
| `schema_invalid` | Thử lại `schema_retry_max` lần, `FAILED`, `AI_SCHEMA_INVALID`; không lưu `result` |
| `provider_error` | Retry rồi `FAILED`, `PROVIDER_UNAVAILABLE` (không fallback vì chưa cấu hình) |
| `auth_error` | `FAILED` ngay, không retry, `PROVIDER_AUTH_ERROR` |
| `refusal` | Bước `REFUSED`, job `FAILED` với `AI_REFUSED`, usage có `refusal_category`; không đổi model/provider |
| `truncated` | Bước `TRUNCATED`, `FAILED`, không lưu kết quả thiếu |

## 5. Ngân sách (US3, QA-11, SC-004, FR-045)

1. `PUT /api/v1/budget` đặt `per_job_default_usd = 0.01` (giữ ngày/tháng mặc định).
2. Tạo job với `mock_scenario = budget_heavy` → job `PAUSED_BUDGET`, `status_reason_code = BUDGET_JOB_EXCEEDED`,
   `status_reason_detail` có hạn mức, đã chi, ước tính; **không** có usage log cho lời gọi bị chặn.
3. `POST /api/v1/jobs/{id}/resume` khi chưa tăng ngân sách → `402 BUDGET_STILL_INSUFFICIENT`.
4. Tăng ngân sách job (hoặc `PUT /api/v1/budget`) rồi resume → job tiếp tục từ checkpoint, không lặp bước đã xong.
5. Đặt lại `per_job_default_usd = 2.00`.

## 6. Vòng đời job: hủy, tạm dừng, retry, worker chết (US4, SC-006, QA-09/10)

- Tạo job `mock_scenario = fail_n_then_success:timeout:1` rồi `POST …/cancel` ngay → `CANCELLED`, không có thêm lời gọi AI.
- Tạo job, `POST …/pause` → `PAUSED` sau bước hiện tại; `POST …/resume` → tiếp tục từ bước kế.
- Gửi `POST /api/v1/jobs` hai lần cùng `idempotency_key` → lần 2 trả `200` cùng job.
- Tạo job dài, chạy `docker compose kill worker` giữa chừng, `docker compose up -d worker` → trong ≤ 5 phút job chuyển
  `RETRY_SCHEDULED` → `RUNNING` → `SUCCEEDED`, `job_steps` không có `seq` trùng.

## 7. Lịch (US5, SC-007)

- `POST /api/v1/schedules` với `cron_expr = "*/5 * * * *"`, `job_type = system.diagnostic`, `enabled = true` → sau mỗi mốc
  5 phút có đúng 1 job `trigger = SCHEDULE`.
- Đặt ngân sách ngày = 0 rồi bật lịch → `422 BUDGET_NOT_CONFIGURED`.
- Tắt lịch → không tạo job mới.

## 8. Bảo mật, audit, log, backup (US6, US7, SC-008, SC-012)

- `GET /api/v1/providers` không chứa giá trị key (chỉ `configured`, `key_hint`).
- `docker compose logs api worker | grep -E "sk-ant-|sk-proj-|Bearer "` → không có kết quả.
- `PATCH /api/v1/settings` đổi `agent.default_max_steps` → audit log có before/after.
- Thử khởi động với `APP_ENV=production` và `AI_PROVIDER_OVERRIDE=mock` → `api`/`worker` thoát với `MOCK_NOT_ALLOWED`.
- `make backup` → file `backups/nichepilot-<timestamp>.dump`; `make restore FILE=…` vào database trống → số bản ghi khớp.

## 9. (Chỉ khi chủ sở hữu cho phép) Kiểm thử tích hợp API thật

Chỉ thực hiện khi đã có API key **và** chủ sở hữu đồng ý chi phí (ước tính < $0.01 cho job chẩn đoán với Haiku 5.5):

1. Điền `ANTHROPIC_API_KEY`, để rỗng `AI_PROVIDER_OVERRIDE`, khởi động lại.
2. `POST /api/v1/providers/anthropic/test-connection` → `OK` (không tính phí).
3. Đặt `AI_PAID_CALLS_ENABLED=true`, khởi động lại `worker`.
4. Tạo job `system.diagnostic` → `SUCCEEDED`, `data_origin = REAL`; đối chiếu `cost_usd` với usage × bảng giá (lệch ≤ 1%, SC-003).
5. Đặt lại `AI_PAID_CALLS_ENABLED=false` nếu chưa cần dùng tiếp.

Trước bước 4, tiêu chí SC-003 phải được báo cáo là **"chưa kiểm chứng"**.

## 10. Bộ test tự động

```bash
make test
```

```bash
make test-e2e
```

Kỳ vọng: lint + type check sạch; unit + integration (PostgreSQL thật qua testcontainers) + E2E (Playwright) pass; báo cáo
truy vết yêu cầu → test được sinh ra; không có lời gọi mạng tới provider thật (test chặn mạng ra ngoài cho adapter).
Bộ test live (`make test-live`) **không** nằm trong `make test` và từ chối chạy nếu thiếu `AI_PAID_CALLS_ENABLED=true`.
