# Vận hành E1 – Autonomous Niche Discovery

> Trạng thái: E1 đã triển khai đủ US1–US7 + Polish (`specs/002-niche-discovery/tasks.md`). Mọi nguồn dữ liệu seed hiện `UNVERIFIED` –
> không được dùng; lượt khám phá với nguồn thật sẽ trả `NO_COMPLIANT_SEARCH_SOURCE` cho tới khi chủ sở hữu xác minh nguồn (SC-013 BLOCKED).

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

## 5. Xóa bằng chứng (US2 – FR-013e)

- Giao diện: màn hình chi tiết ngách (`/niches/{id}`) → "Xóa bằng chứng" → nhập lý do → xác nhận (tùy chọn xóa toàn bộ nguồn).
  API: `POST /api/v1/evidence/{evidence_id}/erase` `{reason, scope: EVIDENCE|SOURCE}`.
- Thứ tự: ghi sổ (fsync) → transaction DB (xóa nội dung, audit `evidence.erased` chỉ có định danh + lý do, tính lại ngưỡng các ngách
  liên quan ngay) → job `discovery.recompute` (không gọi AI).
- `503 ERASURE_LEDGER_WRITE_FAILED`: không ghi được sổ (đĩa đầy, quyền volume) – **chưa có gì bị xóa**; sửa volume rồi thử lại.
- `503 ERASURE_LEDGER_NOT_APPLIED` sau một lần xóa lỗi giữa chừng: sổ đi trước DB. Chạy
  `docker compose run --rm migrate` (hoặc `python -m nichepilot.jobs.erasure_ledger --strict`) để áp dụng nốt.
- Nội dung trùng `content_hash` (trích đoạn hoặc cả trang) đã xóa sẽ bị bỏ khi thu thập lại (`page_fetch_log.reason = ERASED_CONTENT`),
  kể cả khi xuất hiện trên tên miền khác.

## 6. Quản lý nguồn (US4 – FR-006c/d/g)

- Màn hình `/sources` hoặc API `GET/POST /api/v1/sources`, `PUT /api/v1/sources/{id}`. Nguồn mới luôn `UNVERIFIED` + tắt.
- Chỉ nguồn `ALLOWED` (đủ: ngày xác minh, căn cứ, phương thức truy cập, phạm vi sử dụng – `source-verification.md` §2) mới bật được;
  không có tùy chọn bỏ qua cảnh báo. Rời `ALLOWED` → tự tắt.
- Bật/tắt nguồn `searxng_engine` → backend sinh lại `settings.yml` (volume `searxng-config`, file base mount read-only tại
  `/opt/nichepilot/searxng/settings.base.yml`) và trả `requires_service_restart: true` → chạy `docker compose restart searxng`.
- Backend ghi vào volume riêng `searxng-generated` (user `app`); SearXNG mount read-only và sao chép `settings.yml` khi khởi động
  (`depends_on: migrate` để volume được khởi tạo với quyền `app`). Đã kiểm chứng trên stack thật 2026-11-21 (bật nguồn → file sinh lại
  → `restart searxng` → `/etc/searxng/settings.yml` có engine mới, `/healthz` OK). Trước đó thiết kế dùng chung volume `searxng-config`
  bị lỗi quyền ghi (PermissionError) – phát hiện khi chạy E2E trên stack thật.

## 7. PII engine

- Mặc định `PII_ENGINE=regex-phone` (regex email/điện thoại/@username/URL hồ sơ + nhận diện nguy cơ tên người). Đoạn có nguy cơ chứa tên
  người hoặc ngôn ngữ chưa hỗ trợ → `NEEDS_REVIEW`: không lưu, không gửi AI (`metrics.needs_review_segments`).
- spaCy (`spacy-en-sm`) chỉ ở image dev với `INSTALL_PII_NER=true`; production chỉ chấp nhận engine trong `PII_APPROVED_ENGINES`
  (quyết định I2 – chưa phê duyệt).
- URL hồ sơ cá nhân/URL chứa PII bị loại ngay trong tool (`source.query`, chuyển hướng ở `page.fetch`) nên không vào `tool_executions`.

## 8. Chấm điểm, xếp hạng, báo cáo

- Trọng số: `/api/v1/scoring/weights` (tổng 100, đủ 6 tiêu chí); `recompute_existing=true` → job `discovery.recompute` (0 lời gọi AI).
- Màn hình `/niches` (3 danh sách), `/niches/{id}` (lý do chấm điểm, bằng chứng, quyết định, ngách có thể trùng).
- Báo cáo theo lượt: `GET /api/v1/discovery/runs/{id}/report?format=markdown&lang=vi|en` (MOCK ẩn mặc định, `include_mock=true` để xem).
- Opportunity là điểm ưu tiên nghiên cứu, **không** phải dự báo doanh thu; đạt ngưỡng bằng chứng ≠ sinh lợi.

## 9. Profile tùy chọn `browser-fetcher` (TẮT mặc định – quyết định I1)

- Dùng khi trang công khai cần JavaScript. Không stealth, không Crawl4AI/patchright; robots + khoảng cách tên miền vẫn áp dụng.
- Bật: build backend `--build-arg INSTALL_BROWSER_FETCHER=true`; trong `.env`: `PAGE_FETCHER=browser`,
  `BROWSER_WS_ENDPOINT=ws://browser-fetcher:3000/`; `docker compose --profile browser-fetcher up -d`.
- Dependency: nhóm tùy chọn `browser` = `playwright==1.63.0` (Apache-2.0) + `pyee 13.0.1` (MIT). Image `deploy/browser-fetcher`
  dựa trên `mcr.microsoft.com/playwright:v1.63.0-noble` (Apache-2.0).
- Đo 2026-11-21 (Chromium cục bộ, trang fixture): đỉnh RSS ≈ 571 MB khi render 1 trang. Image `browser-fetcher`: NOT_TESTED (chưa build –
  image nền lớn, không cần cho cấu hình mặc định).

## 10. Đánh giá lại và lịch

- `POST /api/v1/niches/{id}/reevaluate` → job `discovery.reevaluate` (giữ đánh giá cũ, kết quả job có `comparison` before/after).
- Lịch: dùng scheduler E0 (`job_schedules.job_type = discovery.run` hoặc `discovery.reevaluate`); không có nguồn ALLOWED → lượt dừng ở
  `preflight` (0 lời gọi AI); ngân sách chưa cấu hình → scheduler không tạo job.
