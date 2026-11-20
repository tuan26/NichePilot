# Vận hành E1 – Autonomous Niche Discovery

> Trạng thái: đang triển khai theo `specs/002-niche-discovery/tasks.md` (Phase 1 → US1). Tài liệu đầy đủ (T127) bổ sung ở Phase
> Polish. Mọi nguồn dữ liệu hiện `UNVERIFIED` – không được dùng; lượt khám phá dùng nguồn thật sẽ trả `NO_COMPLIANT_SEARCH_SOURCE`.

## 1. Cấu hình bắt buộc

| Biến (`deploy/env/.env`) | Ý nghĩa |
|---|---|
| `SEARXNG_SECRET` | Secret của SearXNG – **bắt buộc**, sinh ngẫu nhiên khi cài (`openssl rand -hex 32`), không commit. Thiếu → `docker compose` dừng với thông báo rõ |
| `SEARXNG_URL` | Địa chỉ nội bộ, mặc định `http://searxng:8080` |
| `PII_ENGINE` / `PII_APPROVED_ENGINES` | Bộ che PII; production chỉ chấp nhận engine trong danh sách phê duyệt (mặc định `regex-phone`) |

## 2. SearXNG (dịch vụ nội bộ)

- Image ghim `searxng/searxng:2026.11.18-b867c56a5` (AGPL-3.0-or-later, không sửa mã), không publish cổng, `mem_limit 256m`.
- Lần khởi động đầu dùng `deploy/searxng/settings.base.yml`: **không engine** (`keep_only: []`), **không plugin** (`plugins: {}`).
  Kiểm chứng 2026-11-20 trong mạng Docker `--internal`: `/healthz` OK, truy vấn JSON trả rỗng, không có kết nối ra ngoài.
- Lý do `plugins: {}`: plugin `tracker_url_remover` của SearXNG tự tải danh sách ClearURLs từ `cdn.jsdelivr.net`/`clearurls.xyz` khi
  khởi tạo, kể cả khi `active: false` – là kết nối ra ngoài không qua nguồn `ALLOWED` nào.
- Host không có IPv6: cần `GRANIAN_HOST=0.0.0.0` (đã đặt trong Compose).

## 3. Dependency (X8 – đã kiểm tra 2026-11-20)

Dependency production mới (ghim trong `backend/uv.lock`):

| Gói | Phiên bản | Giấy phép |
|---|---|---|
| trafilatura | 2.3.1 | Apache-2.0 |
| protego | 0.7.0 | BSD-3-Clause |
| phonenumbers | 9.0.43 | Apache-2.0 |
| rapidfuzz | 3.14.6 | MIT |
| tldextract | 5.4.0 | BSD-3-Clause |
| pyyaml | 6.0.x | MIT (đã có trong nhóm dev của E0; nay dùng ở runtime để sinh `settings.yml` SearXNG) |

Phụ thuộc bắc cầu (đọc từ metadata sau khi cài): certifi 2026.10.23 (MPL-2.0), charset-normalizer 3.5.2 (MIT), courlan 1.5.0
(Apache-2.0), dateparser 1.5.1 (BSD-3-Clause), filelock 4.2.12 (MIT), htmldate 1.11.0 (Apache-2.0), idna 3.20 (BSD-3-Clause), jusText
3.0.2 (BSD-2-Clause), lxml 6.1.3 (BSD-3-Clause), python-dateutil 4.0.0 (BSD-3-Clause), pytz 2026.6 (MIT), regex 2026.11.19 (Apache-2.0 AND
CNRI-Python), requests 2.34.2 (Apache-2.0), requests-file 3.0.1 (Apache-2.0), tzdata 2026.6 (Apache-2.0), tzlocal 5.4.5 (MIT), urllib3
2.8.0 (MIT). Không gói nào có giấy phép không rõ.

Không có trong dependency E1: crawl4ai, playwright-stealth, patchright (quyết định I1).

**Nhóm tùy chọn `pii-ner`** (spaCy 3.8.18): chỉ cài khi build image dev với `--build-arg INSTALL_PII_NER=true`; model
`en_core_web_sm-3.8.0` tải từ URL ghim và kiểm tra SHA-256 `1932429d…0fb85` lúc build. Stage `runtime` (production) không bao giờ cài.
Chưa được phê duyệt cho production (quyết định I2).

**Kích thước image** (đo 2026-11-20, `docker image inspect`):

| Image | Trước E1 | Sau E1 |
|---|---|---|
| `runtime` (production) | 628 MB | 821 MB (+193 MB; không có spaCy/Crawl4AI/Playwright – đã kiểm tra bằng `importlib`) |
| `dev` + `INSTALL_PII_NER=true` | – | NOT_MEASURED (không build để tránh cài thư viện nặng không cần thiết; đo trong venv tách biệt: +291 MB, RSS 151 MB – research R-05) |

## 4. Erasure ledger và restore (X4)

- Sổ `ledger.jsonl` nằm trong volume `erasure-ledger` (không trong dump PostgreSQL); `make backup` sao kèm một bản sổ.
- Service `migrate` chạy `alembic upgrade head && python -m nichepilot.jobs.erasure_ledger --strict`; lỗi → api/worker không chạy.
- `make restore`: khôi phục DB rồi đặt `erasure_ledger_state = BLOCKED`, sau đó tự chạy `apply_erasure_ledger --strict`. Lỗi (sổ thiếu,
  hỏng, cũ hơn DB, lệch `ledger_id`) → `make` thất bại, dữ liệu nghiên cứu E1 vẫn bị chặn (API 503 `ERASURE_LEDGER_NOT_APPLIED`).
- Kiểm tra: `GET /api/v1/discovery/status` → `erasure_ledger.status`.
