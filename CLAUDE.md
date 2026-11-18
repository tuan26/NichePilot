# NichePilot – Hướng dẫn cho AI coding agent

- Luật gốc: `.specify/memory/constitution.md` (v1.1.0). Đọc trước mọi thay đổi.
- Yêu cầu tổng thể: `docs/requirements/master-requirements.md`. Kiến trúc: `docs/architecture/system-architecture.md`.
- Quy trình Spec Kit v1.4.2 (skills trong `.claude/skills/`): constitution → specify → clarify → plan → tasks → analyze → implement.
- Feature hiện tại: `specs/001-foundation-ai-infrastructure` (E0) – plan đã duyệt có điều kiện, đã có tasks.md (123 task) và báo cáo analyze; CHỜ chủ sở hữu cho phép triển khai. CHƯA được viết implementation code.
- Stack E0 (plan.md): Python 3.13, FastAPI, SQLAlchemy 2.1 async + psycopg 3, Alembic, Procrastinate (PostgreSQL queue), anthropic/openai SDK, structlog; React + Vite + Tailwind + shadcn + i18next; PostgreSQL 17; Docker Compose (Windows WSL2 + Linux).
- AI provider: `AnthropicAPIProvider` (chính), `OpenAIAPIProvider` (dự phòng), `MockAIProvider` (dev/test, dữ liệu gắn `MOCK`, cấm production). Không dùng OAuth/cookie/Claude Code CLI làm backend. `AI_PAID_CALLS_ENABLED=false` mặc định – KHÔNG gọi API có phí khi chưa được chủ sở hữu cho phép.
- Tài liệu, spec, báo cáo: tiếng Việt. Mã nguồn, tên biến/hàm/class/endpoint/bảng: tiếng Anh.
- Không bịa dữ liệu; thiếu dữ liệu ghi `UNKNOWN`. Không báo cáo tích hợp API thật là "đã kiểm thử" khi chưa gọi API thật.
- Không triển khai E5–E8 khi chưa được yêu cầu. Không mở rộng phạm vi ngoài spec.
