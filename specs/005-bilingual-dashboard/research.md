# Research – E4 Bilingual Dashboard (Phase 0)

Ngày 2026-11-28. Không có `NEEDS CLARIFICATION`. Không thêm dependency, service, bảng hay tool.

## R-01. Tổng hợp Tổng quan bằng 1 endpoint chỉ đọc
- **Decision**: `GET /api/v1/dashboard/overview?include_mock=` trả bộ đếm (ngách theo `evidence_status`, `decision_status`; sản phẩm, cặp
  `READY_TO_PROMOTE`; keyword, cluster; job theo trạng thái + số lỗi 7 ngày) và ≤ 5 ngách hàng đầu (Opportunity giảm dần, kèm Confidence).
  Chi phí lấy từ `GET /api/v1/budget` (E0) – đã tách REAL/MOCK, không nhân bản logic ngân sách.
- **Rationale**: tránh N lời gọi API từ trình duyệt; tái dùng nguồn chi phí duy nhất (Constitution VI).
- **Alternatives**: gọi API từng module từ frontend – chậm, trùng logic lọc MOCK.

## R-02. Danh sách nghiên cứu theo ngách
- **Decision**: `GET /api/v1/dashboard/niches?include_mock=&limit=` – mỗi dòng: ngách (tên, quốc gia, trạng thái bằng chứng/quyết định,
  Opportunity/Confidence từ đánh giá E1 mới nhất), tóm tắt E2 (số sản phẩm, số sẵn sàng, `has_run`), tóm tắt E3 (số keyword, cluster,
  long-tail, cluster tốt nhất theo Opportunity, `has_run`). Một truy vấn SQL với subquery tổng hợp; chỉ ngách chưa gộp; đủ điều kiện E2/E3
  đánh dấu `eligible`. Dùng cho trang Sản phẩm và Keyword toàn cục.
- **Rationale**: FR-010/011 không cần luồng mới; chỉ đọc bảng E1–E3.

## R-03. Module `modules/dashboard`
- **Decision**: module chỉ đọc, chỉ SQL `text()` trên bảng (không import module nghiệp vụ khác) → import-linter: không module nào import
  `dashboard`; `dashboard` không ghi bảng (test). Gate erasure ledger (`LedgerGate`) cho cả 2 endpoint vì có dữ liệu nghiên cứu.
- **Điểm cluster tốt nhất**: dùng đánh giá keyword mới nhất – trung bình SCORED của cluster tính trong SQL (giống `cluster_scores`).

## R-04. Điều hướng
- **Decision**: `Layout` thêm `<nav>` (prop `nav` mặc định bật khi đã đăng nhập) với 9 mục; `aria-current="page"` cho mục khớp đường dẫn;
  trang đăng nhập/khởi tạo không có menu. Route mới: `/overview`, `/products`, `/keywords`, `/jobs`, `/jobs/:jobId`, `/costs`, `/settings`.
  `/` giữ nguyên trang Trạng thái E0 (E2E E0 không đổi).

## R-05. CSV
- **Decision**: tiện ích frontend `lib/csv.ts`: `toCsv(headers, rows)` – quote RFC 4180, BOM `﻿`, tiền tố `'` cho ô bắt đầu
  `= + - @ \t \r`; `downloadCsv(name, csv)` qua Blob. Bảng: xếp hạng ngách (E1), sản phẩm theo ngách (E2), keyword theo ngách (E3 – từ chi
  tiết cluster). Không endpoint mới.

## R-06. Định dạng locale
- **Decision**: dùng `formatDateTime`/`formatNumber` (E0) + thêm `formatMoney` (USD, 2–6 chữ số thập phân) và `formatPercent` trong
  `src/i18n/index.ts`; test VI (`1.234,5`) / EN (`1,234.5`).

## R-07. Settings chỉ đọc phần có phí
- **Decision**: trang hiển thị `GET /providers`, `GET /models`, `GET /model-profiles` chỉ đọc; không render nút test-connection/verify/
  pricing (test kiểm tra không có lời gọi POST tới các endpoint đó từ module trang).
