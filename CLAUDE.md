# NichePilot – Hướng dẫn cho AI coding agent

- Luật gốc: `.specify/memory/constitution.md` (v1.0.0). Đọc trước mọi thay đổi.
- Yêu cầu tổng thể: `docs/requirements/master-requirements.md`. Kiến trúc đề xuất: `docs/architecture/system-architecture.md`.
- Quy trình Spec Kit v1.4.2 (skills trong `.claude/skills/`): constitution → specify → clarify → plan → tasks → analyze → implement.
- Feature hiện tại: `specs/001-foundation-ai-infrastructure` (E0). Chưa có plan/tasks; CHƯA được viết implementation code cho tới khi chủ sở hữu xác nhận plan E0.
- Tài liệu, spec, báo cáo: tiếng Việt. Mã nguồn, tên biến/hàm/class/endpoint/bảng: tiếng Anh.
- Không bịa dữ liệu; thiếu dữ liệu ghi `UNKNOWN`. Mock chỉ trong test. Không gọi API trả phí trong test tự động.
- Không triển khai E5–E8 khi chưa được yêu cầu. Không mở rộng phạm vi ngoài spec.
