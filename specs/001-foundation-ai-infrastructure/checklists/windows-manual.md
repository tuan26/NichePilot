# Checklist kiểm thử thủ công: Windows 10/11 (Docker Desktop + WSL2)

**Liên quan**: AC-01, FR-070, FR-071, FR-074, SC-001, SC-002 | **Cấu hình mục tiêu**: 4 core, 15 GB RAM

> Trạng thái: **CHƯA THỰC HIỆN** – môi trường phát triển của agent là Linux, không có máy Windows. Chủ sở hữu (hoặc người
> được giao) điền kết quả thực tế. Không đánh dấu PASS khi chưa chạy.

Người thực hiện: ____________ Ngày: ____________ Windows: ☐ 10 22H2 ☐ 11 (bản: ______) Docker Desktop: ______
CPU/RAM máy: ______ `.wslconfig` (memory/processors): ______

| # | Bước | Kỳ vọng | Kết quả (PASS/FAIL/BLOCKED) | Ghi chú / số đo |
|---|---|---|---|---|
| W1 | Làm theo `docs/operations/windows-setup.md` mục 1–3 (WSL2, Docker Desktop, clone trong WSL, `core.autocrlf input`) | Không cần bước ngoài tài liệu | | |
| W2 | `cp deploy/env/.env.example deploy/env/.env`, sửa mật khẩu, `make up` | Mọi service healthy; đo thời gian | | thời gian: ____ giây (≤ 300, SC-001) |
| W3 | Mở `http://localhost:8080` trên trình duyệt Windows | Trang khởi tạo tài khoản tiếng Việt | | |
| W4 | Tạo tài khoản, đăng nhập | Trang trạng thái: database OK, worker OK, MOCK, gọi có phí TẮT | | |
| W5 | Chờ 2 phút ở trạng thái nghỉ, `docker stats --no-stream` | Tổng MEM USAGE ≤ 3 GB (SC-002) | | tổng: ____ MB |
| W6 | Task Manager → `VmmemWSL`/`vmmem` | Ghi lại số đo (gồm cache WSL) | | ____ MB |
| W7 | Tạo job `system.diagnostic` (Swagger `/api/docs`) | `SUCCEEDED`, `data_origin = MOCK` | | |
| W8 | Chuyển ngôn ngữ EN rồi tải lại trang | Giữ tiếng Anh | | |
| W9 | `make down`, `make dev`; sửa một file trong `backend/src` | api/worker tự nạp lại (log `Reloading`) | | |
| W10 | Sửa một chuỗi trong `frontend/src` | Trình duyệt cập nhật (Vite HMR) | | |
| W11 | Khởi động lại Windows (hoặc `wsl --shutdown` + mở Docker Desktop) | Container tự chạy lại; dữ liệu còn nguyên | | |
| W12 | `make backup`, rồi khôi phục theo `docs/operations/backup-restore.md` vào DB trống | File `backups/*.dump`; khôi phục thành công | | |
| W13 | Thử lỗi CRLF/cổng bận theo `troubleshooting.md` (nếu gặp) | Hướng dẫn xử lý được | | |
| W14 | Đánh giá tài liệu: có bước nào thiếu/sai? | Tài liệu đủ dùng (FR-071) | | |

Kết luận: ☐ Đạt AC-01 ☐ Chưa đạt – lý do: ____________________________________________
