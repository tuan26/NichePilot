# Hợp đồng Cấu hình Môi trường: E0

**Ngày**: 2026-11-18 | Liên quan: FR-054, FR-019, FR-019b, R-08, R-14

Cấu hình đọc theo thứ tự ưu tiên: Docker secret file (`/run/secrets/<name>`) > biến môi trường > file `.env` > giá trị mặc
định. Chỉ `deploy/env/.env.example` được commit; `.env` thật bị `.gitignore` loại. Cấu hình **không bí mật** có thể thay đổi
lúc chạy nằm trong bảng `settings` (xem data-model §4); bảng dưới là cấu hình khởi động.

## Biến môi trường

| Biến | Bí mật | Mặc định | Mô tả |
|---|---|---|---|
| `APP_ENV` | Không | `development` | `development` \| `test` \| `production`. `production` cấm mock |
| `APP_VERSION` | Không | (build) | Hiển thị ở trang trạng thái |
| `DATABASE_URL` | **Có** (chứa mật khẩu) | — | `postgresql+psycopg://user:pass@postgres:5432/nichepilot` |
| `POSTGRES_PASSWORD` | **Có** | — | Dùng cho container postgres (nên dùng Docker secret) |
| `SESSION_IDLE_TIMEOUT_HOURS` | Không | `12` | Hết hạn phiên khi không hoạt động (giá trị khởi tạo cho setting `auth.session_idle_timeout_hours`) |
| `AUTH_LOCKOUT_THRESHOLD` | Không | `5` | Số lần sai trước khi khóa (khởi tạo `auth.lockout_threshold`) |
| `AUTH_LOCKOUT_MINUTES` | Không | `15` | Thời gian khóa (khởi tạo `auth.lockout_minutes`) |
| `COOKIE_SECURE` | Không | `false` (dev) / `true` (prod) | Cookie chỉ qua HTTPS |
| `ANTHROPIC_API_KEY` | **Có** | rỗng | API key chính thức Anthropic. Rỗng = provider `anthropic` "chưa cấu hình" |
| `OPENAI_API_KEY` | **Có** | rỗng | API key chính thức OpenAI (dự phòng) |
| `AI_PROVIDER_OVERRIDE` | Không | `mock` trong `.env.example` dev; rỗng trong production | Ép mọi tác vụ dùng một provider (`mock`\|`anthropic`\|`openai`). Rỗng = theo Model Task Profile |
| `AI_PAID_CALLS_ENABLED` | Không | `false` | Công tắc cho phép gọi API có phí (FR-019). Chỉ đặt `true` khi chủ sở hữu cho phép |
| `MOCK_AI_DEFAULT_SCENARIO` | Không | `success` | Kịch bản mặc định của MockAIProvider |
| `WORKER_CONCURRENCY` | Không | `1` | Trần cứng số job đồng thời (setting `worker.max_concurrent_jobs` không vượt được) |
| `LOG_LEVEL` | Không | `INFO` | |
| `LOG_FORMAT` | Không | `json` | `json` \| `console` (dev) |
| `LOG_DIR` | Không | `/var/log/nichepilot` (volume `logs`) | Nơi lưu file log ứng dụng theo ngày (`app-YYYY-MM-DD.jsonl`) – nguồn lưu chính |
| `LOG_RETENTION_DAYS` | Không | `90` | Khởi tạo setting `logging.retention_days`; giá trị < 90 bị từ chối |
| `LOG_DISK_WARN_GB` | Không | `2` | Khởi tạo `logging.disk_warn_gb`; vượt ngưỡng chỉ cảnh báo |
| `BACKUP_RETENTION` | Không | `7` | Số bản backup giữ lại |
| `BACKUP_CRON` | Không | `0 3 * * *` | Lịch backup (service `backup`, profile `ops`) |
| `NICHEPILOT_LIVE_MAX_USD` | Không | `0.05` | Trần chi phí cho bộ test live thủ công |

## Quy tắc khởi động (fail-fast)

1. `APP_ENV=production` và (`AI_PROVIDER_OVERRIDE=mock` hoặc có profile `provider=mock`) → thoát với `MOCK_NOT_ALLOWED`.
   Đây là tầng cấu hình; tầng runtime kiểm tra lại ở AI Gateway, API cập nhật profile và tham số `mock_scenario`
   (contracts/internal-interfaces.md §1). Trong production `AI_PROVIDER_OVERRIDE` chỉ nhận `anthropic`/`openai`/rỗng.
2. `APP_ENV=production` và `COOKIE_SECURE=false` → cảnh báo nghiêm trọng trong log và trang trạng thái.
3. Phát hiện `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_PROFILE` hoặc thư mục hồ sơ đăng nhập Anthropic trong container → bỏ qua,
   ghi cảnh báo; client provider luôn được tạo với `api_key` tường minh (FR-019b).
4. Secret không bao giờ được in ra log, kể cả khi khởi động lỗi (chỉ in tên biến thiếu).

## Chuyển từ phát triển (mock) sang vận hành (API thật) — không sửa mã

1. Điền `ANTHROPIC_API_KEY` (và tùy chọn `OPENAI_API_KEY`) vào `.env` hoặc Docker secret.
2. Xóa hoặc để rỗng `AI_PROVIDER_OVERRIDE` (hoặc đặt `anthropic`).
3. Gọi `POST /api/v1/providers/anthropic/test-connection` (không tính phí) → `OK`.
3b. Gọi `POST /api/v1/providers/anthropic/verify-models` (không tính phí) để xác minh model ID/khả năng; nhập bảng giá
    từ trang giá chính thức qua `POST /api/v1/model-pricing` với `verified = true` và `source_note` ghi nguồn + ngày.
    Xác minh chính sách tính phí khi lỗi (setting `billing.error_responses_not_billed_verified`) từ tài liệu chính thức.
4. Khi chủ sở hữu cho phép: đặt `AI_PAID_CALLS_ENABLED=true`, khởi động lại `worker`.
5. Kiểm tra ngân sách (`GET /api/v1/budget`) – mặc định $3/ngày, $30/tháng, $2/job.
