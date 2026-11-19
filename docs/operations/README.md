# Vận hành NichePilot (E0)

Tài liệu dành cho chủ sở hữu khi cài đặt, chạy và bảo trì NichePilot trên một máy (Linux hoặc Windows 10/11 + Docker
Desktop/WSL2). Phạm vi: E0 – nền tảng & hạ tầng AI. Chưa có chức năng nghiệp vụ E1–E8.

| Tài liệu | Nội dung |
|---|---|
| [windows-setup.md](windows-setup.md) | Cài đặt trên Windows 10/11 bằng Docker Desktop + WSL2 |
| [windows-testing.md](windows-testing.md) | Kịch bản kiểm thử E0 trên Windows (SC-001, SC-002, FR-074) |
| [troubleshooting.md](troubleshooting.md) | Xử lý sự cố thường gặp (CRLF, cổng, RAM WSL, đồng hồ lệch, ổ đĩa log đầy…) |
| [backup-restore.md](backup-restore.md) | Backup theo lịch, backup thủ công, khôi phục và kiểm thử khôi phục |
| [security.md](security.md) | Quét secret (detect-secrets), baseline có kiểm soát |
| [enable-real-api.md](enable-real-api.md) | Chuyển từ MockAIProvider sang API thật – chỉ khi chủ sở hữu cho phép |

## Khởi động nhanh (Linux)

```bash
cp deploy/env/.env.example deploy/env/.env
```

Sửa `deploy/env/.env`: đổi `POSTGRES_PASSWORD` và mật khẩu trong `DATABASE_URL` (hai giá trị phải giống nhau). Giữ
`AI_PROVIDER_OVERRIDE=mock` và `AI_PAID_CALLS_ENABLED=false` khi chưa có API key.

```bash
make up
```

Mở `http://localhost:8080` → tạo tài khoản chủ sở hữu lần đầu → trang trạng thái hiển thị database, worker, provider.

## Thành phần

| Service | Vai trò | RAM giới hạn |
|---|---|---|
| `postgres` | PostgreSQL 17 – dữ liệu, hàng đợi job (Procrastinate), audit log | 1 GB |
| `migrate` | Chạy `alembic upgrade head` rồi thoát | 256 MB |
| `api` | FastAPI – REST API `/api/v1` | 512 MB |
| `worker` | Procrastinate worker: chạy job, scheduler mỗi phút, bảo trì (reservation treo, job mất heartbeat, retention log) | 1 GB |
| `web` | Caddy phục vụ dashboard React và proxy `/api` | 128 MB |
| `backup` (profile `ops`) | Backup theo `BACKUP_CRON` | 256 MB |

## Lệnh thường dùng

| Lệnh | Tác dụng |
|---|---|
| `make up` / `make down` | Khởi động / dừng toàn bộ |
| `make dev` | Chế độ phát triển (hot reload api/worker/Vite) |
| `make logs` | Xem stdout của api và worker (bản sao xem nhanh) |
| `make migrate` | Chạy migration |
| `make backup` / `make restore FILE=…` | Backup / khôi phục (xem backup-restore.md) |
| `make test` | Lint + test backend + frontend (không gọi API thật) |

## Phục hồi worker khi mất kết nối database

- Hành vi đã kiểm chứng (2026-11-18, stack Docker thật): khi PostgreSQL dừng, tiến trình `worker` **thoát** (lỗi
  `procrastinate.exceptions.ConnectorException`) thay vì tự kết nối lại; `api` trả `503 SERVICE_UNAVAILABLE` rồi tự phục hồi.
- Khi chạy bằng Docker Compose, cơ chế phục hồi worker là chính sách `restart: unless-stopped` trong
  `deploy/docker-compose.yml`: Docker khởi động lại worker cho tới khi database sẵn sàng. **Không** gỡ chính sách này.
- Khi chạy worker **ngoài Docker** (ví dụ `python -m nichepilot.worker` trực tiếp), bắt buộc dùng một process supervisor
  tự khởi động lại khi tiến trình thoát (systemd `Restart=always`, supervisord `autorestart=true`…). Không có supervisor,
  worker sẽ dừng hẳn sau sự cố database.
- Sau khi khởi động lại không có job chạy trùng: lượt thực thi dùng `lock` theo `job_id`; job `RUNNING` mất heartbeat được
  tác vụ bảo trì đưa về `RETRY_SCHEDULED` (hoặc `PAUSED_BUDGET` nếu còn reservation `UNCERTAIN`) và tiếp tục từ checkpoint.
- E0 cố ý **không** thêm vòng lặp tự kết nối lại trong worker: chưa chứng minh được an toàn với Procrastinate (lock, lượt
  thực thi đang dở), connection pool và cơ chế phục hồi job stalled.


- Bản lưu chính: file theo ngày `app-YYYY-MM-DD.jsonl` trong volume `logs` (`LOG_DIR`), JSON có `request_id`, `job_id`,
  `step_id`; secret được che tự động.
- Giữ tối thiểu 90 ngày (`logging.retention_days`, không cho đặt < 90). Tác vụ hằng ngày chỉ xóa file quá hạn lưu.
- Vượt `logging.disk_warn_gb` → cảnh báo trong log và `GET /api/v1/system/status` (`log_storage.warning`), **không** xóa
  log chưa đủ hạn. Cần mở rộng ổ đĩa hoặc tăng ngưỡng.
- Audit log nằm trong database, chỉ đọc, không bị chính sách xóa log tác động.
- Stdout Docker xoay vòng (20 MB × 5 cho api/worker) – chỉ để xem nhanh.

## Ngân sách AI (mặc định)

$3/ngày, $30/tháng, $2/job – sửa qua `PUT /api/v1/budget` (có audit). Sổ MOCK tách riêng sổ REAL. Reservation
`UNCERTAIN` (không xác định được chi phí) không bao giờ tự giải phóng: chủ sở hữu đối chiếu trang usage của provider rồi
gọi `POST /api/v1/budget/reservations/{id}/resolve`.

## Bảo mật

- API key chỉ nằm trong `deploy/env/.env` hoặc Docker secrets – không lưu trong database, không hiển thị trên dashboard
  (chỉ `key_hint` 4 ký tự cuối), không ghi vào log.
- Không commit `deploy/env/.env`. Thư mục `backups/` bị loại khỏi git; file backup có quyền 0600.
- `APP_ENV=production` từ chối khởi động nếu cấu hình mock (`MOCK_NOT_ALLOWED`). Khi dùng HTTPS đặt `COOKIE_SECURE=true`.
