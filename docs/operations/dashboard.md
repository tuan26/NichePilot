# Vận hành E4 – Bilingual Dashboard

Dashboard song ngữ (VI mặc định / EN) trên khung E0. Spec: `specs/005-bilingual-dashboard/`.

## 1. Các trang (menu điều hướng)

| Mục | Đường dẫn | Nội dung |
|---|---|---|
| Tổng quan | `/overview` | Số ngách/sản phẩm/keyword/job, chi phí hôm nay/tháng (REAL; MOCK tách riêng), 5 ngách hàng đầu kèm Confidence |
| Ngách | `/niches` | Bảng xếp hạng E1 (+ Xuất CSV) |
| Sản phẩm | `/products` | Ngách đủ điều kiện + tóm tắt E2 → trang sản phẩm theo ngách (+ Xuất CSV ở trang theo ngách) |
| Keyword | `/keywords` | Ngách đủ điều kiện + tóm tắt E3 → trang cluster theo ngách (+ Xuất CSV keyword ở chi tiết cluster) |
| Agent jobs | `/jobs`, `/jobs/{id}` | Danh sách/lọc job, chi tiết + các bước, tạm dừng/tiếp tục/hủy/thử lại; lịch chạy bật/tắt/xóa |
| Chi phí | `/costs` | Ngân sách, chi phí theo provider/model/loại job; REAL và MOCK tách riêng |
| Cài đặt | `/settings` | Múi giờ, ngôn ngữ giao diện mặc định, giới hạn agent, thị trường/ngôn ngữ nội dung/nghiên cứu, ngân sách; provider/model chỉ đọc |
| Nguồn dữ liệu | `/sources` | Chính sách nguồn E1 |
| Trạng thái | `/` | Trang trạng thái hệ thống E0 (trang đích sau đăng nhập, không đổi) |

## 2. Quy tắc

- Dữ liệu `MOCK` ẩn mặc định; bật "Hiện dữ liệu giả lập (MOCK)" để xem (có nhãn).
- Điểm luôn hiển thị kèm Confidence; Opportunity không phải dự báo doanh thu.
- Trang Cài đặt **không** có nút bật gọi API có phí, xác minh model, sửa giá hay kiểm tra kết nối provider (cấu hình qua biến môi trường /
  API E0 theo quy trình riêng). Lỗi validate hiển thị theo trường.
- CSV: UTF-8 có BOM (mở trực tiếp bằng Excel), ô bắt đầu bằng `= + - @` được thêm `'` để chống công thức; giá trị thiếu ghi `UNKNOWN`.
- Ngôn ngữ giao diện (nút VI/EN, ghi nhớ trên trình duyệt) độc lập với ngôn ngữ nội dung/nghiên cứu của dự án.

## 3. API bổ sung (chỉ đọc)

`GET /api/v1/dashboard/overview?include_mock=` và `GET /api/v1/dashboard/niches?include_mock=&limit=` (cổng erasure ledger – 503 khi sổ xóa
chưa áp dụng). Chi phí lấy từ `GET /api/v1/budget` và `/api/v1/costs/summary` của E0.
