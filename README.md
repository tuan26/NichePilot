# NichePilot (Affiliate Automation OS)

Hệ thống AI Agent tự host, tự động hóa quy trình Affiliate Marketing quốc tế: khám phá ngách → sản phẩm & affiliate →
keyword → nội dung → xuất bản → doanh thu → tối ưu. *(Tên làm việc, chưa xác nhận nhãn hiệu/tên miền.)*

**Trạng thái E0:** `IMPLEMENTATION_COMPLETE / PENDING_EXTERNAL_VERIFICATION` (chủ sở hữu xác nhận 2026-11-19) – chưa phải
`PRODUCTION_VERIFIED`. Windows 10/11 và Claude/OpenAI API thật: `NOT_TESTED`. Báo cáo: `docs/reports/e0-acceptance-report.md`.
E1 (Autonomous Niche Discovery) đang ở giai đoạn đặc tả; chưa triển khai E1–E8.

> ⚠️ **API có phí**: mặc định `AI_PAID_CALLS_ENABLED=false` và `AI_PROVIDER_OVERRIDE=mock`. Chỉ bật gọi API thật khi chủ
> sở hữu cho phép, sau khi xác minh model và bảng giá – xem `docs/operations/enable-real-api.md`. Không dùng Claude Pro,
> OAuth token, cookie hay Claude Code CLI làm backend.

## Chạy nhanh

```bash
cp deploy/env/.env.example deploy/env/.env
```

Sửa mật khẩu database trong `deploy/env/.env`, rồi:

```bash
make up
```

Mở `http://localhost:8080` → tạo tài khoản chủ sở hữu. API: `http://localhost:8080/api/docs`.
Windows 10/11: `docs/operations/windows-setup.md`.

| Lệnh | Tác dụng |
|---|---|
| `make up` / `make down` | Khởi động / dừng |
| `make dev` | Phát triển với hot reload |
| `make test` | Lint + test backend/frontend (không gọi API thật) |
| `make test-e2e` | Playwright E2E (cần stack đang chạy) |
| `make test-live` | Test với API thật – **chỉ khi được cho phép**, có trần chi phí |
| `make backup` / `make restore FILE=…` | Backup / khôi phục PostgreSQL |

## Tài liệu

| Tài liệu | Đường dẫn |
|---|---|
| Constitution | `.specify/memory/constitution.md` |
| Master Requirements | `docs/requirements/master-requirements.md` |
| Kiến trúc tổng thể | `docs/architecture/system-architecture.md` |
| Spec / plan / tasks E0 | `specs/001-foundation-ai-infrastructure/` |
| Spec E1 – Niche Discovery | `specs/002-niche-discovery/` |
| Spec E2 – Product & Affiliate Discovery | `specs/003-product-affiliate-discovery/` (vận hành: `docs/operations/products.md`) |
| Spec E3 – Keyword & Audience Research | `specs/004-keyword-audience-research/` (vận hành: `docs/operations/keywords.md`) |
| Vận hành (tiếng Việt) | `docs/operations/` |
| Kết quả kiểm chứng E0 | `specs/001-foundation-ai-infrastructure/checklists/verification.md` |

## Stack

Python 3.13 · FastAPI · SQLAlchemy 2.1 async + psycopg 3 · Alembic · Procrastinate (hàng đợi trên PostgreSQL) ·
anthropic/openai SDK · structlog · React + Vite + Tailwind + i18next (vi/en) · PostgreSQL 17 · Docker Compose.
