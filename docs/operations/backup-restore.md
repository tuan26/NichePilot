# Backup và khôi phục

## Backup theo lịch

```bash
docker compose -f deploy/docker-compose.yml --env-file deploy/env/.env --profile ops up -d backup
```

Service `backup` (image `postgres:17-alpine`) chạy `deploy/scripts/backup.sh` theo `BACKUP_CRON` (mặc định `0 3 * * *`)
ở múi giờ `BACKUP_TZ` (mặc định `Asia/Ho_Chi_Minh`), giữ `BACKUP_RETENTION` bản mới nhất (mặc định 7).

## Backup thủ công

```bash
make backup
```

Kết quả: `backups/nichepilot-<YYYYMMDDTHHMMSSZ>.dump` (định dạng `pg_dump -Fc`). Script ghi vào file tạm, kiểm tra file
đọc được bằng `pg_restore --list` rồi mới đổi tên – không để lại bản backup hỏng.

## Bảo vệ dữ liệu nhạy cảm

- File backup có quyền `0600`; thư mục `backups/` bị loại khỏi git.
- Database **không** chứa API key. Backup chứa hash mật khẩu (Argon2), hash phiên đăng nhập và audit log → chỉ lưu ở nơi
  chủ sở hữu kiểm soát; nếu chép ra ngoài máy, hãy mã hóa (ví dụ `gpg -c`).

## Khôi phục

`restore.sh` **từ chối** khôi phục vào database đã có bảng để tránh ghi đè ngoài ý muốn. Quy trình:

1. Dừng ứng dụng (giữ postgres chạy):

   ```bash
   docker compose -f deploy/docker-compose.yml --env-file deploy/env/.env stop api worker web
   ```

2. Tạo database trống (đổi tên database cũ để giữ lại):

   ```bash
   docker compose -f deploy/docker-compose.yml --env-file deploy/env/.env exec postgres sh -c 'psql -U "$POSTGRES_USER" -d postgres -c "ALTER DATABASE \"$POSTGRES_DB\" RENAME TO \"${POSTGRES_DB}_old\"" -c "CREATE DATABASE \"$POSTGRES_DB\""'
   ```

3. Khôi phục:

   ```bash
   make restore FILE=backups/nichepilot-20261118T030000Z.dump
   ```

4. Khởi động lại và kiểm tra trang trạng thái:

   ```bash
   make up
   ```

5. Khi đã chắc chắn, xóa database cũ `<POSTGRES_DB>_old`.

## Kiểm thử khôi phục

Test tự động `backend/tests/integration/test_backup_restore.py` chạy script thật trong `postgres:17-alpine`: backup →
khôi phục vào database trống → so khớp số bản ghi mọi bảng; kiểm tra xoay vòng và quyền file. Nên tự kiểm thử khôi phục
thủ công ít nhất mỗi quý vào một database tạm.
