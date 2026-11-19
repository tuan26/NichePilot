# Hướng dẫn kiểm thử E0 trên Windows 10/11

Mục tiêu: chứng minh AC-01 / SC-001 (khởi động và đăng nhập ≤ 30 phút với một lệnh), SC-002 (RAM nghỉ ≤ 3 GB) và FR-074
(hot reload) trên máy Windows thật. Kết quả ghi vào `specs/001-foundation-ai-infrastructure/checklists/windows-manual.md`.
Chỉ đánh dấu PASS khi đã chạy thật trên Windows; không chạy được thì ghi BLOCKED kèm lý do.

Toàn bộ kiểm thử dùng **MockAIProvider** – không cần API key, không phát sinh chi phí. Giữ `AI_PAID_CALLS_ENABLED=false`.

## 0. Chuẩn bị (không tính vào 30 phút)

- Cấu hình tham chiếu: 4 core, 15 GB RAM, không GPU. Ghi lại CPU/RAM/phiên bản Windows/Docker Desktop.
- Cài WSL2 + Ubuntu và Docker Desktop theo `windows-setup.md` mục 1–2 (`.wslconfig`: `memory=6GB`, `processors=4`).
- Có quyền truy cập repository từ WSL (git).

## 1. Khởi động lần đầu – SC-001 (bấm giờ từ bước này)

Trong terminal Ubuntu (WSL):

```bash
cd ~ && git clone <url-repo> NichePilot && cd NichePilot
```

```bash
git config core.autocrlf input
```

```bash
cp deploy/env/.env.example deploy/env/.env
```

Sửa `POSTGRES_PASSWORD` và mật khẩu trong `DATABASE_URL` cho giống nhau (`nano deploy/env/.env`), rồi:

```bash
make up
```

Kỳ vọng: mọi container `healthy`/`running`; kiểm tra bằng `docker compose -f deploy/docker-compose.yml --env-file deploy/env/.env ps`.
Mở `http://localhost:8080` trên trình duyệt Windows → trang **Khởi tạo tài khoản** tiếng Việt → tạo tài khoản → trang trạng
thái: database OK, worker OK, chế độ AI = Giả lập (MOCK), gọi API có phí = TẮT. **Dừng bấm giờ** – ghi số phút (≤ 30).

## 2. RAM nghỉ – SC-002

Chờ 2 phút không thao tác, rồi:

```bash
docker stats --no-stream
```

Cộng cột MEM USAGE của postgres, api, worker, web (≤ 3 GB). Ghi thêm số đo `VmmemWSL` trong Task Manager (gồm cache của WSL,
thường cao hơn – chỉ để tham khảo).

## 3. Chức năng cơ bản

1. Swagger `http://localhost:8080/api/docs` → `POST /api/v1/jobs` với `{"job_type": "system.diagnostic"}` → sau vài giây
   `GET /api/v1/jobs/{id}`: `SUCCEEDED`, `data_origin = MOCK`.
2. Bấm **EN** → giao diện chuyển tiếng Anh ngay; tải lại trang vẫn là tiếng Anh.
3. (Tùy chọn) Chạy thêm các kịch bản ở `specs/001-foundation-ai-infrastructure/quickstart.md` §4–§8.

## 4. Hot reload – FR-074

```bash
make down
```

```bash
make dev
```

- Sửa một dòng comment trong `backend/src/nichepilot/__init__.py` → log `api` có `Reloading`, log `worker` có `restarting`.
- Mở `http://localhost:8080` rồi sửa một chuỗi trong `frontend/src` → trình duyệt cập nhật (Vite HMR / page reload).
- Hoàn tác các thay đổi thử (`git checkout -- backend/src frontend/src`).

Có thể chạy tự động: `deploy/tests/smoke.sh dev` (cần Docker build được image dev).

## 5. Khởi động lại, backup

1. Khởi động lại Windows (hoặc `wsl --shutdown` rồi mở lại Docker Desktop) → container tự chạy lại, đăng nhập được, dữ liệu
   còn nguyên.
2. `make backup` → có file `backups/nichepilot-*.dump`. Khôi phục thử theo `backup-restore.md` vào database trống.

## 6. Ghi kết quả

Điền bảng W1–W14 trong `windows-manual.md` (PASS/FAIL/BLOCKED + số đo + ghi chú), ký tên/ngày. Gặp lỗi: `troubleshooting.md`
(CRLF, cổng bận, RAM WSL, đồng hồ lệch, ổ đĩa log đầy).
