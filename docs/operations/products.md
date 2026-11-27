# Vận hành E2 – Product & Affiliate Discovery

E2 tìm sản phẩm và chương trình affiliate cho một ngách E1 đủ điều kiện. Spec: `specs/003-product-affiliate-discovery/`.

## 1. Điều kiện chạy

- Ngách `EVIDENCE_SUFFICIENT` (ngưỡng E1: ≥ 2 bằng chứng pain point hợp lệ từ ≥ 2 nhóm nguồn độc lập), quyết định `PURSUE`, `WATCH` hoặc
  chưa quyết định. Ngách `INSUFFICIENT_EVIDENCE`, `REJECTED`, `HIDDEN` hoặc đã gộp bị từ chối (`NICHE_NOT_ELIGIBLE`).
- Có ít nhất một nguồn `ALLOWED` đang bật (như E1). Hiện **chưa có** nguồn nào `ALLOWED` → lượt bị từ chối `NO_COMPLIANT_SEARCH_SOURCE`.
- Ngân sách AI ngày/tháng đã cấu hình. Gọi API có phí vẫn tắt (`AI_PAID_CALLS_ENABLED=false`).
- Mỗi ngách chỉ có 1 lượt đang chạy (`PRODUCT_RUN_ACTIVE`). Không có chạy hàng loạt tự động: lịch `products.run` bắt buộc `niche_id`.

## 2. Chạy

- Giao diện: trang ngách → khối **Sản phẩm** → **Xem sản phẩm** → **Tìm sản phẩm**.
- API: `POST /api/v1/product-runs {"niche_id": "…"}` → job E0 `products.run` (tạm dừng/tiếp tục/hủy qua `/api/v1/jobs/{id}/…`).
- Theo dõi điều khoản (tùy chọn): bật **Theo dõi thay đổi điều khoản** trên chương trình, rồi tạo lịch `/api/v1/schedules` với
  `job_type = products.terms_check`, `params.program_id` (ví dụ hằng tuần). Hệ thống không tự tạo lịch.

## 3. Đọc kết quả

- **Trạng thái xác minh**: `VERIFIED` chỉ khi trích đoạn đến từ chính tên miền của sản phẩm/đơn vị vận hành chương trình; bên thứ ba →
  `INFERRED`; nguồn khác nhau → `CONFLICTING` (hiển thị mọi giá trị + nguồn); không có → `UNKNOWN`.
- **Số liệu** (giá, % hoa hồng, ngày cookie, ngưỡng thanh toán) chỉ được lưu khi con số xuất hiện trong trích đoạn được dẫn; ngược lại
  `UNKNOWN` (đếm trong `metrics.rejected_values`).
- **Sẵn sàng affiliate**: `READY_TO_PROMOTE` chỉ khi đăng ký từ Việt Nam `ALLOWED` **và** thị trường của ngách được phép quảng bá – cả
  hai `VERIFIED`. Đây là điều kiện tham gia, **không** phải khuyến nghị quảng bá.
- **Điểm**: Opportunity (5 tiêu chí 25/25/20/15/15, Coverage ≥ 60% và có tiêu chí phù hợp pain point) và Confidence tách biệt; không phải
  dự báo doanh thu. Đổi trọng số: `POST /api/v1/product-scoring/weights` (tạo phiên bản mới + tính lại không AI).
- Dữ liệu `MOCK` ẩn mặc định; bật "Hiện dữ liệu giả lập (MOCK)" để xem.

## 4. Không bao giờ

- Đăng ký tài khoản affiliate, đăng nhập mạng affiliate, gửi form, chấp nhận điều khoản (BR-08) – E2 không có chức năng này.
- Vượt robots.txt, CAPTCHA, trang yêu cầu đăng nhập, paywall – trang như vậy bị bỏ qua có lý do.

## 5. Dữ liệu demo (chỉ development)

```bash
docker compose -f deploy/docker-compose.yml --env-file deploy/env/.env exec -T api python -m nichepilot.jobs.discovery_demo_seed
```

```bash
docker compose -f deploy/docker-compose.yml --env-file deploy/env/.env exec -T api python -m nichepilot.jobs.products_demo_seed
```

Tạo 2 sản phẩm `[MOCK DEMO]` (một `READY_TO_PROMOTE`, một `ELIGIBILITY_UNVERIFIED`). Lệnh từ chối khi `APP_ENV=production`.
