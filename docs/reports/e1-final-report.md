# Báo cáo tổng kết E1 – Autonomous Niche Discovery (US3–US7 + Polish)

> Ngày: 2026-11-21. Nhánh `claude/inspiring-wright-06dzhw`.
> Commit: `a467fa3` (US3), `b0c82f5` (US4), `db4b959` (US5–US7), `b11fc2d` (Polish).
> Báo cáo US2 riêng: `docs/reports/e1-us2-report.md`. Bằng chứng kiểm chứng: `specs/002-niche-discovery/checklists/verification.md`.
>
> Mọi kết quả dùng nguồn giả lập và AI kịch bản/MockAIProvider (MOCK). Không có lời gọi API có phí. Không nguồn `UNVERIFIED` nào
> được bật. Không thay đổi cấu hình mạng. Không triển khai E2–E8.

## 1. Số task

Chủ sở hữu yêu cầu "làm hết", nên phần còn lại của E1 được thực hiện liền một mạch:

| Phase | Task | Trạng thái |
|---|---|---|
| US3 – chấm điểm, xếp hạng | T085–T099 (15) | Hoàn thành |
| US4 – chi phí, giới hạn, độ bền, nguồn | T100–T110 (11) | Hoàn thành |
| US5 – ngách trùng | T111–T114 (4) | Hoàn thành |
| US6 – báo cáo, quyết định | T115–T119 (5) | Hoàn thành |
| US7 – lịch, đánh giá lại | T120–T123 (4) | Hoàn thành |
| Polish | T124–T130 (7) | Hoàn thành; T130 §3 **BLOCKED** (chờ xác minh nguồn) |

`tasks.md`: 0 task chưa đánh dấu.

Về TDD: các test đơn vị thuần (scoring, dedup, risk, kiến trúc) và test vitest được viết trước và FAIL trước khi có mã. Một số
contract/integration test được viết sau hoặc cùng lúc với phần triển khai. Vài test còn phải sửa lại vì giả định ban đầu sai (mục 4).

## 2. Kết quả kiểm thử (local, 2026-11-21)

| Bước | Kết quả |
|---|---|
| ruff, ruff format, mypy, lint-imports | PASS |
| pytest backend | **505 passed**, 6 skipped (opt-in/BLOCKED), 0 failed |
| perf (opt-in) | PASS – p95 65 ms / 5.000 ngách; tính lại 1.000 ngách 13,8 s, 0 lời gọi AI |
| browser (opt-in) | PASS – đỉnh RSS Chromium ≈ 571 MB |
| Frontend lint / typecheck / vitest | PASS – 24 test |
| E2E E1 trên stack Docker thật | PASS |
| Secret scanning | Không có finding mới, baseline không đổi |
| Truy vết `--strict` | E0 58/58, **E1 59/59** FR Must có test |
| RAM stack lúc nghỉ | ≈ 460 MB |

Kết quả GitHub CI: xem mục 7.

## 3. Nội dung chính

- **US3:**
  - `scoring/opportunity.py`, `scoring/confidence.py` thuần, khớp ví dụ tính tay 60,71 / 66,00.
  - `EvaluationService.evaluate_and_store` là điểm duy nhất tạo đánh giá. Đánh giá bất biến; kết quả trùng đánh giá gần nhất thì không ghi thêm.
  - Phiên bản trọng số mới + `recompute_existing` → tính lại không dùng AI.
  - Ba danh sách xếp hạng; màn hình 2; phần lý do chấm điểm trên màn hình chi tiết.
  - Cờ rủi ro: `COMPLIANCE_SENSITIVE` (từ khóa), `LOW_EVIDENCE_FRESHNESS`, `MONETIZATION_RISK`.
- **US4:**
  - Phân bổ trang theo ứng viên; dừng sớm (`ALL_CANDIDATES_SUFFICIENT`).
  - Chạm `page_limit` vẫn phân tích dữ liệu đã có; hết thời gian thì không gửi lời gọi AI mới.
  - 429/503 thử lại ≤ 2 lần theo `Retry-After`; `Retry-After` dài hơn thời gian còn lại → bỏ tên miền.
  - Chống tạo bằng chứng trùng khi tiếp tục sau sự cố; job bị hủy → `stop_reason` `CANCELLED`.
  - API và màn hình quản lý nguồn: chỉ nguồn `ALLOWED` mới bật được; bật/tắt nguồn → sinh lại cấu hình SearXNG.
- **US5:**
  - Phát hiện ngách trùng: 41/42 cặp có nhãn đúng (97,6%), 0 lần gộp nhầm.
  - Trùng chắc chắn → liên kết vào ngách cũ; không chắc chắn → chờ chủ sở hữu xác nhận trên UI.
- **US6:**
  - Báo cáo theo lượt dạng JSON/Markdown, song ngữ, dữ liệu MOCK ẩn mặc định.
  - Quyết định của chủ sở hữu: 5 trạng thái, bắt buộc lý do, có audit, không ghi đè đề xuất AI.
- **US7:**
  - Lượt theo lịch dùng scheduler E0 nguyên trạng.
  - Không có nguồn ALLOWED → lượt dừng ngay ở `preflight` với 0 lời gọi AI.
  - `discovery.reevaluate` giữ lịch sử đánh giá và so sánh before/after.
- **Polish:**
  - E2E E1 và bước CI chạy trên stack mới.
  - Test kiến trúc, test i18n.
  - Profile `browser-fetcher` tùy chọn, tắt mặc định, không stealth.
  - Tài liệu vận hành.

## 4. Lỗi phát hiện và cách xử lý

| # | Lỗi | Phát hiện bởi | Xử lý |
|---|---|---|---|
| 1 | Công thức trùng của rubric tự gộp nhầm "freelance designers" ↔ "freelance photographers" (sim 0,867) | Bộ cặp có nhãn | Thêm điều kiện: cả hai thành phần ≥ 0,80 mới được tự gộp; đã ghi vào rubric §5 |
| 2 | Chạm giới hạn trang thì kết thúc ngay, bỏ qua bước phân tích (trái FR-030d) | Phân tích khi viết T101 | Dừng thu thập nhưng vẫn chạy extract/assess |
| 3 | Lượt theo lịch không có nguồn vẫn gọi AI đề xuất ứng viên | Viết T120 | `preflight` kiểm tra nguồn trước |
| 4 | Một `evidence_id` không phải UUID trong tiêu chí làm sập phép tính lại | Test hiệu năng | Lọc ID không hợp lệ |
| 5 | **Stack thật:** backend không ghi được `settings.yml` SearXNG (PermissionError trên volume dùng chung) | E2E trên Docker | Tách volume `searxng-generated` cho backend, SearXNG mount read-only và sao chép lúc khởi động. Đã kiểm chứng end-to-end |
| 6 | **Stack thật:** API cache sức khỏe sổ 60 s nên có thể vẫn phục vụ dữ liệu sau khi sổ bị BLOCKED | Quickstart §6 | Trạng thái DB đọc mỗi request; thêm test hồi quy `TC_E1_FR013f_14` |
| 7 | Secret scanner bắt dương tính giả trong test nguồn | `check_secrets.py` | Đổi literal trong test; **không** thêm vào baseline |
| 8 | Test ngân sách giả định sai số lời gọi (lời gọi `extract` giữ chỗ nhỏ hơn) | Test FAIL | Sửa test để kiểm tra bất biến: không có lời gọi nào vượt hạn mức |
| 9 | Script tự động ngắt dòng làm hỏng 2 f-string | ruff | Sửa tay |
| 10 | **CI đỏ ở run #46 (US4) và #48 (Polish)**: secret scanner bắt dương tính giả trong file test MỚI. `check_secrets.py` ở local chỉ quét file git đã theo dõi, mà file mới lúc đó chưa `git add` nên lọt | GitHub CI | #46: đổi literal (sửa ở #47). #48: E2E E1 đọc mật khẩu từ `E2E_OWNER_PASSWORD`, CI sinh ngẫu nhiên. Không thêm gì vào baseline. Từ nay chạy secret scan SAU `git add` |

## 5. Thay đổi chạm vào E0

- Thêm mã lỗi:
  - `SOURCE_NOT_FOUND`, `SIMILARITY_NOT_FOUND`, `SIMILARITY_ALREADY_RESOLVED`.
  - `TASK_TYPE_NOT_ALLOWED`, `ERASURE_LEDGER_WRITE_FAILED` (đã có từ US2).
- `contracts/configuration.md` của E0: thêm biến `DISCOVERY_SOURCE_MODE`, `PAGE_FETCHER`.
- `deploy/docker-compose.yml`:
  - Volume `searxng-generated`; SearXNG `depends_on: migrate`.
  - Mount file base settings vào backend; profile `browser-fetcher`.
- `backend/Dockerfile`: tham số build `INSTALL_BROWSER_FETCHER` (mặc định false).
- `.github/workflows/ci.yml`: thêm bước E2E E1 chạy trên stack mới.
- `frontend/playwright.config.ts`: tách bộ test theo biến `E2E_SUITE`.

Không sửa Job Runtime, Scheduler, AIGateway, BudgetService, Tool Registry hay MockAIProvider.

## 6. BLOCKED / NOT_TESTED

- **SC-013 / quickstart §3 – BLOCKED:** chưa có nguồn ALLOWED.
- **API Claude/OpenAI thật – NOT_TESTED.**
- **E2E màn hình chi tiết + ghi quyết định – NOT_TESTED:** MockAIProvider trả 0 ứng viên nên không có ngách để mở. Đã được kiểm thử bằng contract test và vitest.
- **Chưa kiểm trên stack thật – NOT_TESTED:**
  - `docker compose kill worker`.
  - Dừng PostgreSQL 20 s.
  - Cả hai đều đã kiểm bằng integration test.
- **Image `browser-fetcher` – NOT_TESTED:** chưa build. Đã kiểm fetcher với Chromium cục bộ.
- **PII:**
  - spaCy chưa phê duyệt (I2).
  - Danh sách từ khóa lĩnh vực nhạy cảm chỉ có tiếng Anh, có thể bỏ sót/nhầm, và chỉ gắn cờ.
- **Gộp ngách:** không trộn bằng chứng của ngách bị gộp vào ngách giữ lại (giữ nguyên để truy vết).
- **Chuẩn hóa tên cho dedup:** chuẩn hóa bằng mã, không dùng lời gọi AI `discovery.normalize`.
- **Windows/WSL2 – NOT_TESTED.**

## 7. GitHub CI

| Run | Commit | Kết quả |
|---|---|---|
| #45 | `a467fa3` US3 | success |
| #46 | `b0c82f5` US4 | **failure** – secret scanner (dương tính giả trong test nguồn); sửa ở #47 |
| #47 | `db4b959` US5–US7 | success |
| #48 / #49 | `b11fc2d` Polish / `0594e66` docs | **failure** – secret scanner (mật khẩu E2E E1) |
| [#50](https://github.com/tuan26/NichePilot/actions/runs/44922598589) | `44b3d9d` | **success** – cả 6 job xanh: backend, frontend, secrets, traceability, smoke, e2e. Job e2e chạy cả bộ E0 (us1) và bộ E1 (discovery) trên stack mới |

Commit chỉ thêm báo cáo sau run #50 sẽ chạy CI lại; mã nguồn không đổi.
