# Xử lý sự cố

| Triệu chứng | Nguyên nhân thường gặp | Cách xử lý |
|---|---|---|
| Script `.sh` báo `/bin/sh^M: bad interpreter` | File bị chuyển sang CRLF khi clone trên Windows | `git config core.autocrlf input`, rồi `git rm --cached -r . && git reset --hard` (mất thay đổi chưa commit); hoặc clone lại trong WSL |
| `port is already allocated` (8080 hoặc 5432) | Ứng dụng khác dùng cổng | Dừng ứng dụng đó, hoặc đổi cổng bên trái trong `deploy/docker-compose.yml` (`"8081:8080"`) |
| Container bị kill (`OOMKilled`), máy chậm | WSL hết RAM | Tăng `memory` trong `.wslconfig` (≥ 6 GB), `wsl --shutdown`, kiểm tra `docker stats` |
| Đăng nhập hết hạn ngay, lịch chạy sai giờ, job "mất heartbeat" vô cớ | Đồng hồ WSL lệch sau khi máy ngủ | `wsl --shutdown` rồi mở lại; hoặc trong WSL `sudo hwclock -s` |
| Trang trạng thái: `log_storage.warning = true` | Log vượt `logging.disk_warn_gb` | Hệ thống **không** tự xóa log chưa đủ 90 ngày. Mở rộng ổ đĩa / volume, hoặc tăng ngưỡng qua `PATCH /api/v1/settings` |
| Ổ đĩa đầy, postgres không ghi được | Log/backup/image Docker chiếm chỗ | `docker system df`, `docker image prune`; chuyển backup cũ ra ngoài; giảm `BACKUP_RETENTION` |
| API trả `503 SERVICE_UNAVAILABLE` | Postgres dừng/khởi động lại | Kiểm tra `docker compose ps`; api tự phục hồi khi postgres chạy lại |
| `worker` thoát / `RestartCount` tăng sau sự cố database | Hành vi thiết kế: worker thoát khi mất kết nối DB | Compose tự khởi động lại (`restart: unless-stopped`). Chạy ngoài Docker phải dùng process supervisor (xem README.md mục Phục hồi worker) |
| `api`/`worker` thoát với `MOCK_NOT_ALLOWED` | `APP_ENV=production` nhưng `AI_PROVIDER_OVERRIDE=mock` | Production không được dùng mock: để trống override và cấu hình provider thật (xem enable-real-api.md) |
| Job `PAUSED_BUDGET` với `UNCERTAIN_RESERVATION_LIMIT` | 3 lời gọi không xác định được chi phí | Đối chiếu trang usage của provider, resolve từng reservation, rồi `POST /api/v1/jobs/{id}/resume` |
| Job `PAUSED_BUDGET` với `BUDGET_*_EXCEEDED` | Hết hạn mức ngày/tháng/job | Chờ sang kỳ mới hoặc chủ sở hữu tăng hạn mức (có audit), rồi resume |
| Hot reload không chạy trên Windows | Mã nguồn nằm trong `/mnt/c` | Chuyển mã nguồn vào filesystem của WSL (`~/…`) |
| `test-connection` trả `NETWORK_ERROR` | Không có Internet/proxy chặn | Kiểm tra mạng; kết quả này không tính phí |
