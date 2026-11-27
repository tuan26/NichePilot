# Báo cáo hoàn tất E3 – Keyword & Audience Research (2026-11-27)

Nhánh: `feature/e3-keyword-audience` (tạo từ commit cuối E2, theo quy tắc "mỗi feature một nhánh" của chủ sở hữu). Spec:
`specs/004-keyword-audience-research/`. Đề xuất trạng thái: **`TECHNICAL_VERIFIED / EXTERNAL_VERIFICATION_PENDING`** (chờ chủ sở hữu nghiệm
thu). Mọi kiểm thử dùng dữ liệu `MOCK` – không thay cho bằng chứng thực tế.

## 1. Quy trình Spec Kit

| Bước | Kết quả | Commit |
|---|---|---|
| specify | FR-001…FR-032 (FR-031 Should, FR-032 Later), SC-001…SC-008; 1 câu hỏi nghiệp vụ (Q1) | `db49144` |
| clarify | Q1 = A (chủ sở hữu) + 5 mặc định kỹ thuật cấu hình được (session (b)); checklist 16/16 | `ecf4dd7` |
| plan | research R-01…R-10, data-model (8 bảng), openapi, internal-interfaces, scoring-rubric (ví dụ tính tay), quickstart; Constitution 12/12 PASS | `ecf4dd7` |
| tasks | T001–T041 (TDD, mã `TC_E3_*`) | `bfb7b49` |
| analyze | 0 CRITICAL / 0 HIGH; 1 thiếu sót trung bình đã sửa trước implement (FR-030 chưa có test → thêm TC_E3_FR030_01) | `bfb7b49` |
| implement + Test & Verify | toàn bộ T001–T041 | `61c4987` (+ commit tài liệu) |

Ghi chú trung thực: test unit thuần được viết cùng lúc với module (không có lần chạy "FAIL trước" được ghi lại cho từng test); test tích hợp
chạy sau khi có agent.

## 2. Yêu cầu đã hoàn thành (theo yêu cầu chủ sở hữu 2026-11-27)

| Yêu cầu chủ sở hữu | Cách đáp ứng | Test |
|---|---|---|
| Trọng số 30/20/20/15/15, cấu hình được, có version | `keyword_scoring_weights` v1 (migration 0014); `POST /keyword-scoring/weights` → phiên bản mới + `keywords.recompute` không AI; đánh giá cũ giữ (bất biến, trigger) | TC_E3_FR017_01…04, TC_E3_SC004_01 |
| Coverage ≥ 60%; `UNKNOWN` không gán điểm giả | Opportunity chỉ khi Coverage ≥ 60 ∧ có `fit`; tiêu chí thiếu → `null` + "còn thiếu" | TC_E3_FR018_01…02 |
| Opportunity ⟂ Confidence | hai hàm riêng; Confidence (S, D, F, O, V) không nhận Opportunity | TC_E3_FR019_01 |
| Không bịa Search Volume/CPC/KD | cột NULL + CHECK DB (có giá trị ⇒ bắt buộc nguồn, thời điểm, thị trường); schema AI không có trường chỉ số (`extra=forbid` → AI trả số liệu thì cả đầu ra bị loại); UI/báo cáo hiển thị `UNKNOWN` | TC_E3_FR009_01…04, TC_E3_SC002_01 |
| Keyword xuất phát từ ngách, pain point, persona, sản phẩm | mỗi keyword ≥ 1 `keyword_origins` thuộc ngách; origin lạ/ngách khác → loại cả keyword | TC_E3_FR005_01…03, TC_E3_SC001_01 |
| Ưu tiên long-tail + commercial phù hợp | cắt giảm ưu tiên LONG_TAIL; keyword commercial theo mẫu xác định cho mọi sản phẩm chưa loại (fit lấy từ mức E2 đã kiểm) | TC_E3_SC003_01, TC_E3_FR007_01 |
| Không mặc định ý định mua cao tốt hơn keyword giải quyết vấn đề | bảng intent: COMMERCIAL_INVESTIGATION 100; INFORMATIONAL gắn pain point 75 = TRANSACTIONAL 75; INFORMATIONAL chung 25; NAVIGATIONAL 0 | TC_E3_FR017_03 |

Phạm vi khác: SERP qua nguồn `ALLOWED` (FR-012), tóm tắt cấu trúc đối thủ ≤ 1000 ký tự/trích đoạn (FR-013, SC-007), content gap/kênh/cạnh
tranh do mã (FR-014, FR-015, FR-023), cluster xác định (FR-016), persona cụm + strategy có bằng chứng, loại tuyên bố "đã test" (FR-022,
FR-024, BR-11), quyết định có audit (FR-025), báo cáo JSON/Markdown VI/EN (FR-026), MOCK ẩn mặc định + từ chối production (FR-027), API + 2
màn hình (FR-028), AgentDefinition (FR-029), số liệu lượt (FR-030), theo dõi SERP (FR-031, Should). FR-032 (GSC/nguồn chỉ số) = Later –
không triển khai, có test xác nhận không có tích hợp.

## 3. Kết quả kiểm thử (local, 2026-11-27)

| Cổng | Kết quả |
|---|---|
| `ruff check`, `ruff format --check`, `mypy` (152 file), `lint-imports` (6 hợp đồng) | PASS |
| `pytest` toàn bộ backend | **653 passed, 0 failed**, 12 skipped (perf cần cờ, live = BLOCKED) |
| Test E3 riêng | 36 unit + 22 integration/contract = 58 test; perf E3 2/2 PASS (`NICHEPILOT_RUN_PERF=1`) |
| Frontend `lint`, `typecheck`, `test` | PASS – 36/36 (E3: 6 test mới) |
| Truy vết `--strict` | E0 58/58, E1 59/59, E2 42/42, **E3 31/31** FR Must; SC-008 E3 `LIVE_ONLY` |
| Secret scan (`check_secrets.py`) | không có finding mới ngoài baseline |
| Playwright E2E (thêm test E3) | chạy trong CI – xem §4 |
| `TC_E3_SC008_01` (nguồn + AI thật) | **BLOCKED** – không có nguồn `ALLOWED`, không gọi AI thật; KHÔNG tính là PASS |

## 4. CI

CI #84 (`61c4987`): traceability, secrets, frontend PASS; backend/smoke/e2e – xem cập nhật cuối báo cáo (§9).

## 5. Thay đổi kiến trúc / điểm chạm E0–E2 (đều là bổ sung)

| # | Điểm chạm | Ghi chú |
|---|---|---|
| Z1 | Đăng ký 3 agent + router E3 | chỉ thêm dòng |
| Z2 | 4 mã lỗi mới (`KEYWORD_*`) + xuất `error-codes.json` | không đổi mã cũ |
| Z3 | Khối **Keyword** trên trang ngách E1 | chỉ đọc, không đổi hành vi E1/E2 |
| Z4 | `traceability_report.py` profile E3 | – |
| Z5 | Hợp đồng import-linter: E0/E1/E2 không import `modules.keywords` | KEPT |
| Z6 | `PageCollector` (E2) nhận tham số `subject_type` (mặc định `product_run`) | hành vi E2 giữ nguyên – test E2 vẫn PASS |
| Z7 | Test danh sách E0/E1 (migration, openapi, traceability) thêm E3; `conftest` dọn bảng E3 | – |

Không thêm dependency, service, image hay tool mới. Migration mới: `0013_keywords`, `0014_keywords_seed` (lên/xuống sạch).

## 6. Chi phí phát sinh

**0 USD.** Không gọi API có phí (AI = provider giả lập trong test; `AI_PAID_CALLS_ENABLED=false`), không bật nguồn `UNVERIFIED`, không đổi
cấu hình mạng, không dùng Claude Pro/Claude Code CLI làm backend, không xuất bản gì.

## 7. Chưa được xác minh thực tế

- Chất lượng keyword/intent/strategy với **AI thật** (chưa từng gọi).
- SERP và trang đối thủ với **nguồn `ALLOWED` thật** (chưa có nguồn nào `ALLOWED`; Wikipedia vẫn `UNVERIFIED`) → SC-008 `BLOCKED`.
- Search Volume/CPC/KD: chưa có nguồn hợp lệ → luôn `UNKNOWN` (đúng thiết kế; FR-032 Later cần quyền truy cập/API key mới).
- Ngưỡng rubric (cạnh tranh 0,5/0,3/0,2; gap 0,75/0,5/0,25; nhu cầu 6/4/3/1) là mặc định cấu hình được, chưa hiệu chỉnh trên dữ liệu thật.
- Windows (AC-01) chưa kiểm thử.

## 8. Cần chủ sở hữu

1. Nghiệm thu E3 `TECHNICAL_VERIFIED / EXTERNAL_VERIFICATION_PENDING` (theo A4: E4 chỉ bắt đầu sau khi E3 đạt Technical Verify – đề nghị
   chủ sở hữu xác nhận trước khi chuyển E4 vì vẫn còn 2 đề xuất chờ duyệt bên dưới).
2. Rà soát ngưỡng rubric keyword mặc định (§7).
3. Các đề xuất đang chờ (không làm gì cho tới khi duyệt): Product Rubric v2 bản 2; phương án PR bản 2. Khi phương án PR được duyệt: mở PR
   cho E3 với head `feature/e3-keyword-audience` (base theo phương án được chọn). Claude không merge, không force-push.

## 9. Cập nhật CI

(điền sau khi CI #84 hoàn tất)
