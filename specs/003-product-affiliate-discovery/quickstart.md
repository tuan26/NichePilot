# Quickstart – kiểm chứng E2 Product & Affiliate Discovery

Mọi kịch bản dùng `MockAIProvider`/AI giả lập theo kịch bản và nguồn giả lập (`data_origin = MOCK`). Không gọi API có phí, không truy
cập mạng ngoài. Kết quả MOCK **không** phải kết quả nghiên cứu; SC-008 giữ `BLOCKED`.

## 1. Kiểm thử tự động

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -m products
```

```bash
cd frontend && npm run lint && npm run typecheck && npm test
```

```bash
uv run --no-project python backend/scripts/traceability_report.py --strict
```

Kỳ vọng: mọi test `TC_E2_*` PASS; truy vết E2 0 FR Must thiếu test.

## 2. Kịch bản tích hợp chính (test `tests/integration/products/`)

| # | Kịch bản | Kỳ vọng | Yêu cầu |
|---|---|---|---|
| 1 | Ngách MOCK đủ bằng chứng, nguồn mock `ALLOWED`, 3 trang sản phẩm + 2 trang điều khoản | Sản phẩm liên kết pain point; thuộc tính có trạng thái/nguồn; chương trình `VERIFIED` khi trang thuộc `operator_domain` | FR-011…FR-024 |
| 2 | Trang bên thứ ba ghi hoa hồng khác trang chính thức | `commission` = `CONFLICTING`, đủ 2 giá trị + nguồn | FR-008, QA-05 |
| 3 | AI trả hoa hồng "45%" không có trong trích đoạn | Thuộc tính `UNKNOWN`, `rejected_values` +1 | FR-009, SC-001 |
| 4 | Ngách `INSUFFICIENT_EVIDENCE` / `REJECTED` | 409 `NICHE_NOT_ELIGIBLE` | FR-001 |
| 5 | Không có nguồn `ALLOWED` | 422 `NO_COMPLIANT_SEARCH_SOURCE`; job theo lịch kết thúc 0 lời gọi AI | FR-006 |
| 6 | Chạy lại lượt / tiếp tục sau sự cố | 0 sản phẩm, chương trình, nguồn, bằng chứng trùng | FR-005, SC-003 |
| 7 | Điều khoản không nêu Việt Nam | `vn_eligibility` UNKNOWN → `ELIGIBILITY_UNVERIFIED`, không `READY_TO_PROMOTE` | FR-022, FR-026 |
| 8 | Xóa bằng chứng hoa hồng (E1 erase) | Lần đọc tiếp theo tính lại điểm, `affiliate` = null | R-06 |
| 9 | Trang điều khoản đổi hoa hồng (terms_check) | Phiên bản 2 + `changes`; lỗi truy cập không xóa giá trị cũ | FR-040 |
| 10 | Toàn bộ request ra ngoài trong test | Chỉ GET qua `source.query`/`page.fetch`/`robots.fetch` | FR-025, SC-002 |

## 3. Xem thử giao diện bằng dữ liệu MOCK (development)

```bash
docker compose -f deploy/docker-compose.yml --env-file deploy/env/.env exec -T api python -m nichepilot.jobs.discovery_demo_seed
```

```bash
docker compose -f deploy/docker-compose.yml --env-file deploy/env/.env exec -T api python -m nichepilot.jobs.products_demo_seed
```

Dashboard → Bảng xếp hạng → bật "Hiện dữ liệu giả lập (MOCK)" → ngách `[MOCK DEMO]` → tab **Sản phẩm** → 2 sản phẩm `[MOCK DEMO]`:
một `READY_TO_PROMOTE`, một `ELIGIBILITY_UNVERIFIED`; chi tiết hiển thị thuộc tính kèm trạng thái/nguồn, Coverage, thông tin còn thiếu,
chú thích "không phải dự báo doanh thu". Chuyển EN → toàn bộ chuỗi tiếng Anh.

## 4. E2E (Playwright, `E2E_SUITE=discovery`)

Sau 2 lệnh seed: mở sản phẩm MOCK → ghi quyết định "Theo dõi" kèm lý do → điểm không đổi → EN.
