# Báo cáo hoàn tất E2 – Product & Affiliate Discovery (2026-11-27)

**Trạng thái**: `TECHNICAL_VERIFIED` / `EXTERNAL_VERIFICATION_PENDING` (Constitution 1.2.0). **Không** phải `PRODUCTION_VERIFIED`.
Toàn bộ kiểm thử dùng nguồn giả lập + AI giả lập (`MOCK`); chưa kiểm chứng với nguồn `ALLOWED` thật hay Claude/OpenAI API thật.

## 1. Quy trình Spec Kit

| Bước | Kết quả |
|---|---|
| specify | `spec.md`: 5 user story, FR-001…FR-041 (+026, 028a, 029a), SC-001…SC-008 |
| clarify | Q1, Q2 chủ sở hữu quyết định; Coverage 60%, đánh giá theo cặp (sản phẩm, ngách), rubric cấu hình được |
| plan | research R-01…R-11, data-model (9 bảng), openapi, internal-interfaces, scoring-rubric, quickstart; Constitution Check 12/12 PASS |
| tasks | 66 task, TDD |
| analyze | 0 CRITICAL; 2 HIGH (C1 thiếu test FR-039, F1 trích dẫn field) + 4 MEDIUM – đã xử lý trước implement |
| implement | 66/66 task |

## 2. Yêu cầu đã hoàn thành

| Nhóm | Yêu cầu | Nội dung chính |
|---|---|---|
| Đầu vào, lượt | FR-001…FR-005 | Ngách đủ điều kiện (Q1), job E0 có checkpoint, ngân sách E0, 1 lượt hoạt động/ngách, idempotent |
| Nguồn, bằng chứng | FR-006…FR-010 | Chỉ nguồn `ALLOWED`, robots/tốc độ/che PII của E1; thuộc tính = bằng chứng có nguồn; `VERIFIED` theo tên miền; số liệu phải có trong trích đoạn |
| Sản phẩm | FR-011…FR-016 | Liên kết pain point, website chính thức, giá theo gói, tính năng, khách hàng mục tiêu, gộp trùng, cờ lĩnh vực nhạy cảm |
| Chương trình | FR-017…FR-026 | 7 thuộc tính có cấu trúc, trạng thái chương trình, không chức năng đăng ký, 6 trạng thái sẵn sàng (`READY_TO_PROMOTE`…) |
| Chấm điểm | FR-027…FR-031 | 5 tiêu chí 25/25/20/15/15 (Q2), Coverage 60%, Confidence tách biệt, khuyến nghị không dựa vào hoa hồng, không phải dự báo doanh thu |
| Báo cáo, UI | FR-032…FR-039 | Báo cáo JSON/Markdown VI/EN, quyết định + audit, tóm tắt trên trang ngách E1, 2 màn hình song ngữ, MOCK ẩn mặc định, metrics, AgentDefinition |
| Should/Later | FR-040, FR-041 | Theo dõi điều khoản + phiên bản + cảnh báo; nguồn qua adapter (API mạng affiliate chưa làm – Later) |

## 3. Kết quả kiểm thử (local, 2026-11-27)

| Bộ kiểm thử | Kết quả |
|---|---|
| Backend toàn bộ (`uv run pytest`) | PASS – 596 passed, 9 skipped (perf chạy riêng; 2 test live `BLOCKED`: SC-013 E1, SC-008 E2), 0 failed |
| Test E2 (`-m products`): unit 42, integration/contract 41 | PASS |
| Hiệu năng (`NICHEPILOT_RUN_PERF=1`): lượt MOCK < 5 phút; danh sách 500 sản phẩm p95 < 500 ms | PASS |
| SC-008 (nguồn thật + AI thật) | **BLOCKED** – chưa có nguồn `ALLOWED`; không đánh dấu PASS bằng MOCK |
| Frontend: oxlint, tsc, Vitest (30 test, gồm 7 test E2) | PASS |
| Playwright bộ `discovery` trên stack Docker cục bộ (3 test, gồm luồng E2 MOCK) | PASS |
| ruff, ruff format, mypy (131 file), lint-imports (5 hợp đồng), check_secrets | PASS |
| Truy vết `--strict`: E2 42/42 FR mức Must có test tự động | PASS (SC-008 `LIVE_ONLY`) |

## 4. Thay đổi kiến trúc / điểm chạm E0–E1 (đều là bổ sung)

| # | Điểm chạm | Ghi chú |
|---|---|---|
| Y1 | Đăng ký 3 agent + router E2 | Không đổi hành vi E0/E1 |
| Y2 | 6 mã lỗi mới | `NICHE_NOT_ELIGIBLE`, `PRODUCT_RUN_ACTIVE`, `PRODUCT_RUN_NOT_FOUND`, `PRODUCT_NOT_FOUND`, `PROGRAM_NOT_FOUND`, `PRODUCT_WEIGHTS_INVALID` |
| Y3 | Khối "Sản phẩm" trên trang chi tiết ngách E1 | Chỉ hiển thị; test kiểm bảng E1 không đổi |
| Y4 | `traceability_report.py`: spec 003; sửa regex dòng `*(Should)*` | Hết cảnh báo FR-034 E1 |
| Y5 | import-linter: E0/E1 không import `modules.products` | 5/5 hợp đồng giữ |
| Y6 | `PageCollector` lặp lại logic tải trang của E1 | Nợ kỹ thuật có chủ đích: không sửa agent E1 đã nghiệm thu |
| – | Test E0/E1 liệt kê spec/bảng/hợp đồng được bổ sung E2 | `test_openapi_contract`, `test_migrations`, `test_traceability_report` – mở rộng, không nới kiểm tra |
| – | Migration `0011_products`, `0012_products_seed` | Trigger bất biến `product_evaluations`; up/down sạch |

Không thêm dependency, service hay image.

## 5. Chi phí phát sinh

**0 USD.** Không có lời gọi API có phí; mọi lời gọi AI trong test dùng AI giả lập (chi phí ghi vào `cost_mock_usd`).

## 6. Vấn đề còn lại / cần chủ sở hữu

1. **Nguồn dữ liệu thật**: chưa nguồn nào `ALLOWED` → E2 chưa chạy được với dữ liệu thật (SC-008 `BLOCKED`), như E1 (SC-013).
2. **AI thật**: Claude API chưa bật – trích xuất/đánh giá thật chưa kiểm chứng (`EXTERNAL_VERIFICATION_PENDING`).
3. **Rubric mặc định** (ngưỡng hoa hồng 30/20/10/5%, cookie < 30 ngày −25, v.v. – `contracts/scoring-rubric.md` §2): Claude đề xuất,
   cấu hình được trong `product_scoring_weights.rubric`; đề nghị chủ sở hữu rà soát.
4. API mạng affiliate (E2-17) là Later – cần khóa API và xác minh điều khoản từng mạng.
5. Nợ kỹ thuật Y6 (gộp `PageCollector` với E1) – làm khi có test hồi quy đầy đủ.

## 7. Feature tiếp theo

E3 – Keyword & Audience Research (`specs/004-keyword-audience-research`), theo cơ chế tự tiếp tục A4: E2 đạt `TECHNICAL_VERIFIED`, không
còn CRITICAL/HIGH, không cần API key/quyền mới, không phát sinh chi phí. Lưu ý E3: không bịa search volume/CPC (BR-05) – nguồn số liệu
keyword thật cần quyết định của chủ sở hữu ở bước clarify.
