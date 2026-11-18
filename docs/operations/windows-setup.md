# Cài đặt trên Windows 10/11 (Docker Desktop + WSL2)

Cấu hình tham chiếu: 4 core, 15 GB RAM. Mục tiêu: hệ thống nghỉ dùng ≤ 3 GB RAM (SC-002), khởi động ≤ 5 phút (SC-001).

## 1. Chuẩn bị

1. Windows 10 22H2 hoặc Windows 11, bật ảo hóa trong BIOS.
2. PowerShell (Administrator):

   ```powershell
   wsl --install -d Ubuntu-24.04
   ```

   Khởi động lại máy, mở Ubuntu, tạo user.
3. Cài [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/), chọn backend **WSL 2**.
   Settings → Resources → WSL integration → bật cho `Ubuntu-24.04`.

## 2. Giới hạn RAM của WSL

Tạo `%UserProfile%\.wslconfig`:

```ini
[wsl2]
memory=6GB
processors=4
swap=2GB
```

Áp dụng: `wsl --shutdown` rồi mở lại Docker Desktop.

## 3. Đặt mã nguồn TRONG WSL (bắt buộc)

Không đặt mã nguồn trong `C:\…` (`/mnt/c`) – I/O chậm và hot reload không nhận thay đổi file. Trong terminal Ubuntu:

```bash
cd ~ && git clone <url-repo> NichePilot && cd NichePilot
```

```bash
git config core.autocrlf input
```

## 4. Cấu hình và chạy

```bash
cp deploy/env/.env.example deploy/env/.env
```

Sửa mật khẩu database trong `deploy/env/.env` (ví dụ bằng `nano`), sau đó:

```bash
make up
```

Mở `http://localhost:8080` trên trình duyệt Windows.

Chế độ phát triển có hot reload (sửa file trong WSL bằng VS Code + extension WSL):

```bash
make dev
```

## 5. Kiểm tra tài nguyên

```bash
docker stats --no-stream
```

Tổng cột MEM USAGE khi nghỉ phải ≤ 3 GB. Trong Task Manager, tiến trình `vmmem`/`VmmemWSL` phản ánh toàn bộ RAM của WSL
(bao gồm cache hệ điều hành) nên thường cao hơn tổng `docker stats`.

## 6. Sau khi khởi động lại máy

Docker Desktop tự khởi động (nếu bật "Start Docker Desktop when you sign in"); các container có `restart: unless-stopped`
tự chạy lại. Kiểm tra `docker compose -f deploy/docker-compose.yml ps`.

Checklist kiểm thử thủ công: `specs/001-foundation-ai-infrastructure/checklists/windows-manual.md`.
