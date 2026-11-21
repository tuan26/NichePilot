# Checklist kiểm chứng E1 (T129, T130) – 2026-11-21

Môi trường: container Linux (cloud session), Docker 29, Postgres 17 (testcontainers và Compose). Mọi phân tích AI dùng
`MockAIProvider`/AI kịch bản (MOCK); mọi nguồn dùng adapter giả lập. **Không có lời gọi API có phí; không nguồn `UNVERIFIED` nào được
bật.** PASS dưới đây không chứng minh nguồn thật hay Claude/OpenAI API thật.

## T129 – Quality gate

| Bước | Kết quả |
|---|---|
| `ruff check` / `ruff format --check` | PASS |
| `mypy` (strict cho core/ai/jobs) | PASS – 106 file |
| `lint-imports` | PASS – 4 contract |
| `pytest` backend (mặc định) | PASS – 505 passed, 6 skipped (BLOCKED/opt-in), 0 failed |
| `pytest -m perf` (`NICHEPILOT_RUN_PERF=1`) | PASS – `GET /niches` p95 = 65 ms (5.000 ngách); tính lại 1.000 ngách 13,8 s, 0 lời gọi AI |
| `pytest -m browser` (`NICHEPILOT_RUN_BROWSER=1`) | PASS – trang cần JS render được, UA nhận diện được, PII vẫn che; đỉnh RSS Chromium ≈ 571 MB |
| `pytest -m pii_ner` | NOT_TESTED (spaCy chưa phê duyệt – I2; không cài) |
| `pytest -m live_sources` (SC-013) | **BLOCKED** – chưa có nguồn ALLOWED |
| Frontend `lint` / `typecheck` / `test` | PASS – 24 test vitest |
| Playwright E2E E1 (`E2E_SUITE=discovery`) trên stack Docker thật | PASS (local) – tạo lượt 2 thao tác, xếp hạng 3 tab, nguồn, VI/EN |
| Playwright E2E E0 (`us1-*`) | Chạy trên GitHub CI (cần DB trống riêng) |
| `check_secrets.py` | PASS – không finding mới, baseline không đổi |
| `traceability_report.py --strict` | PASS – E0 58/58, E1 59/59 FR Must có test |
| `docker stats` stack nghỉ | api 149 MB, worker 137 MB, searxng 96 MB, postgres 68 MB, web 10 MB – tổng ≈ 460 MB |

## T130 – Quickstart trên stack Docker thật (mock)

| Mục | Kết quả | Bằng chứng / ghi chú |
|---|---|---|
| §1 Giả lập hoàn toàn | PASS | `pytest -m discovery` – rào chắn socket không ghi nhận kết nối ra ngoài |
| §2 Không có nguồn hợp lệ | PASS | `POST /discovery/runs` → 409 `NO_COMPLIANT_SEARCH_SOURCE` (stack thật) |
| §3 Nguồn thật | **BLOCKED – chờ xác minh nguồn** | Không phải lỗi implementation. Một phần đã kiểm: bật nguồn seed `UNVERIFIED` → 409 `SOURCE_NOT_ALLOWED`; nguồn TEST giả lập ALLOWED → `settings.yml` sinh lại, `restart searxng` → SearXNG nạp engine mới, `/healthz` OK |
| §4 Giới hạn/độ bền | PASS (test tích hợp) | page/time limit, pause/resume, crash worker (hủy tiến trình + phục hồi job treo), ngân sách, khoảng cách tên miền. `docker compose kill worker` trên stack thật: NOT_TESTED (lượt mock kết thúc trong vài giây) |
| §5 Chấm điểm/quyết định | PASS (contract test) | 60,71 khớp ví dụ tính tay; trọng số v2 → 64,29, 0 lời gọi AI. Trên stack thật MockAIProvider trả 0 ứng viên → không có ngách để mở chi tiết (NOT_TESTED ở E2E) |
| §6 Xóa + restore | PASS | Contract/integration test xóa, restore mô phỏng. Stack thật: `make backup` → DB trống + sổ bị mất → `make restore` thoát ≠ 0, `BLOCKED/LEDGER_MISSING`, `migrate` lỗi → api/worker không chạy; khôi phục sổ → `make up` → OK, `GET /discovery/runs` 200 |
| §6b PII engine | PASS (test) | `NEEDS_REVIEW` không lưu/không gửi AI; production từ chối engine chưa duyệt (test E1 Phase 2) |
| §6c Hiệu năng | PASS | xem T129 |
| §6d Lỗi mạng/DB | PASS (test) | mất DB giữa bước → phục hồi, 0 trùng; mọi nguồn lỗi → `SOURCES_UNAVAILABLE`. Dừng PostgreSQL 20 s trên stack thật: NOT_TESTED |
| §7 Giao diện | PASS | vitest + E2E E1 |
| §8 Truy vết | PASS | xem T129 |

## Lỗi phát hiện khi chạy trên stack thật (đã sửa)

1. Ghi `settings.yml` SearXNG bị `PermissionError` (volume dùng chung thuộc user SearXNG) → volume riêng `searxng-generated` cho backend,
   SearXNG mount read-only và sao chép lúc khởi động.
2. API cache sức khỏe sổ 60 s → có thể phục vụ dữ liệu sau khi sổ bị đánh dấu BLOCKED → nay đọc trạng thái DB mỗi request, chỉ cache
   phần đọc file sổ (test `TC_E1_FR013f_14`).

## Windows / API thật

Windows (WSL2) và Claude/OpenAI API thật: **NOT_TESTED**.
