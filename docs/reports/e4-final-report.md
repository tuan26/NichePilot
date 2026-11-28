# Báo cáo hoàn tất E4 – Bilingual Dashboard (2026-11-28)

Nhánh: `feature/e4-bilingual-dashboard` (tạo từ nhánh E3 vì phụ thuộc API E3). Spec: `specs/005-bilingual-dashboard/`. Đề xuất trạng thái:
**`TECHNICAL_VERIFIED / EXTERNAL_VERIFICATION_PENDING`** – chờ chủ sở hữu nghiệm thu. Kiểm thử bằng dữ liệu `MOCK`.

## 1. Quy trình Spec Kit

| Bước | Kết quả |
|---|---|
| specify | FR-001…FR-023 (FR-020 Should, FR-021 Later), SC-001…SC-006; master E4-01…E4-18 |
| clarify | 5 mặc định kỹ thuật, không câu hỏi nghiệp vụ mới (Clarifications 2026-11-28); checklist đạt |
| plan | research R-01…R-07, data-model (không bảng mới), openapi (2 endpoint chỉ đọc), quickstart; Constitution 12/12 PASS |
| tasks / analyze | T001–T013; 0 CRITICAL/HIGH; 1 thiếu sót (FR-021 chưa có test) sửa trước implement |
| implement + verify | toàn bộ T001–T013 |

Các mặc định đã áp dụng (anh/chị có thể đổi): Tổng quan ở `/overview` (giữ `/` là trang Trạng thái E0); CSV UTF-8 BOM thay cho `.xlsx`;
Settings chỉ sửa cấu hình không bí mật, provider/model/giá **chỉ đọc**; trang Sản phẩm/Keyword toàn cục dẫn sang trang theo ngách; Agent Jobs
không tạo job/lịch mới.

## 2. Đã làm

- Backend: module chỉ đọc `modules/dashboard` + `GET /api/v1/dashboard/overview`, `GET /api/v1/dashboard/niches` (ledger gate, MOCK ẩn mặc
  định). Hợp đồng import-linter: dashboard không phụ thuộc module nghiệp vụ, không ai import dashboard.
- Frontend: menu điều hướng 9 mục (`aria-current`), trang Tổng quan, Product Discovery, Keyword Research, Agent Jobs (+ chi tiết), Chi phí,
  Cài đặt; nút Xuất CSV ở bảng xếp hạng ngách, sản phẩm theo ngách, keyword theo cluster; `formatMoney`/`formatPercent`; lỗi validate theo
  trường (ApiError thêm `errors`, bổ sung tương thích ngược); khóa i18n `dashboard.*`, `nav.*` VI/EN.

## 3. Kết quả kiểm thử (local)

| Cổng | Kết quả |
|---|---|
| ruff / format / mypy / lint-imports (8 hợp đồng) | PASS |
| pytest backend toàn bộ | **661 passed, 0 failed**, 13 skipped (perf cần cờ; live = BLOCKED) |
| Test E4 backend | 9 integration/contract + 1 perf (3 endpoint p95 < 500 ms với 500 ngách/500 job) |
| Frontend lint / typecheck / test / build | PASS – 55/55 (E4: 19 test mới) |
| Truy vết `--strict` | E0 58/58 · E1 59/59 · E2 42/42 · E3 31/31 · **E4 22/22** |
| Playwright E2E (thêm test E4) | chạy trong CI – xem §4 |

## 4. CI

Xem kết quả CI của commit implement E4 (cập nhật ở cuối báo cáo).

## 5. Thay đổi kiến trúc / điểm chạm (bổ sung)

W1 đăng ký router `dashboard`; W2 `Layout` có menu (chỉ trang sau đăng nhập; trang E0 giữ nội dung, E2E E0 không đổi); W3 nút Xuất CSV trên 3
view E1–E3; W4 profile truy vết E4 + test danh sách openapi; W5 2 hợp đồng import-linter; `router.tsx` tách `routes.tsx` (để test route);
`ApiError.errors` (tùy chọn). Không bảng, migration, dependency, service mới.

## 6. Chi phí

**0 USD.** Không gọi API có phí, không bật nguồn, không đổi cấu hình mạng, không xuất bản.

## 7. Chưa xác minh thực tế

- AC-18 "end-to-end thực tế" với nguồn `ALLOWED` thật + AI thật (chỉ có E2E MOCK).
- Hiển thị với dữ liệu REAL khối lượng lớn ngoài phép thử hiệu năng.
- Windows (AC-01).

## 8. Cần chủ sở hữu

1. Nghiệm thu E4 `TECHNICAL_VERIFIED` → mở đường cho E5–E8 (MOCK/sandbox) theo lộ trình.
2. Xác nhận/đổi các mặc định §1.
3. Vẫn chờ: Product Rubric v2 bản 2; phương án PR bản 2 (PR cho E3, E4 sẽ mở theo phương án được duyệt).
