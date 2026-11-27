# Đề xuất Product Scoring Rubric v2 (CHỜ CHỦ SỞ HỮU DUYỆT) – 2026-11-27

Theo yêu cầu chủ sở hữu (2026-11-27) sau khi nghiệm thu E2. **Chưa triển khai**: rubric v1 (`contracts/scoring-rubric.md`) vẫn đang
chạy; trọng số 25/25/20/15/15 giữ nguyên. Mọi ngưỡng dưới đây là **đề xuất mặc định cấu hình được**, không phải số liệu thị trường đã
xác minh.

## 1. Vấn đề của v1

| # | Vấn đề | Ví dụ |
|---|---|---|
| P1 | Một bảng ngưỡng % hoa hồng cho mọi loại sản phẩm | 8% cho hàng vật lý giá cao và 8% cho phần mềm bị chấm như nhau |
| P2 | Recurring chỉ được cộng điểm cố định +25 | 20% recurring 3 tháng và 20% recurring 24 tháng gần như cùng mức |
| P3 | Chỉ xét tỷ lệ %, không xét giá trị hoa hồng thực tế | 50% của sản phẩm 5 USD xếp trên 10% của sản phẩm 300 USD |
| P4 | Cookie chỉ so với ngưỡng cố định 30 ngày | 7 ngày là đủ cho hàng mua nhanh nhưng quá ngắn cho phần mềm cần cân nhắc |

## 2. Nguyên tắc v2

- Không suy đoán conversion rate, customer lifetime value hay số tháng khách ở lại. Chỉ dùng số liệu được nêu trong trích đoạn.
- Thiếu dữ liệu → thành phần `UNKNOWN`, giảm Coverage (và Confidence qua thành phần V), không gán điểm giả.
- Mọi ngưỡng nằm trong `product_scoring_weights.rubric` (phiên bản mới), không hard-code; đổi rubric = tạo phiên bản mới + tính lại.

## 3. Tiêu chí "Hấp dẫn chương trình affiliate" (25%) – tách 2 thành phần

`affiliate = mức thấp hơn (floor về bội số 25) của trung bình các thành phần có dữ liệu`; Coverage của tiêu chí = 25 × (số thành phần có
dữ liệu / 2). Ví dụ chỉ có tỷ lệ, chưa có giá → tiêu chí đóng góp 12,5 điểm Coverage.

### 3.1 Thành phần R – tỷ lệ theo loại sản phẩm (P1)

Loại lấy từ `products.category` (đã có trong E2). Ngưỡng đề xuất (% → mức):

| Loại | 100 | 75 | 50 | 25 | 0 |
|---|---|---|---|---|---|
| `SOFTWARE` | ≥ 30 | ≥ 20 | ≥ 15 | ≥ 10 | < 10 |
| `PHYSICAL` | ≥ 15 | ≥ 10 | ≥ 6 | ≥ 3 | < 3 |
| `DIGITAL` (khóa học, ebook…) | ≥ 50 | ≥ 40 | ≥ 30 | ≥ 20 | < 20 |
| `UNKNOWN` | dùng bảng chặt nhất (`DIGITAL`) – thận trọng | | | | |

Hoa hồng cố định (`fixed`) không có thành phần R (chỉ có V). "Lên tới X%" → dùng cận dưới nếu có, không có thì X rồi hạ một bậc (giữ từ v1).

### 3.2 Thành phần V – giá trị hoa hồng thực tế mỗi khách giới thiệu (P2, P3)

`EV` (đơn vị tiền của giá; chỉ tính khi cùng tiền tệ):

| Kiểu hoa hồng | Công thức | Ghi chú |
|---|---|---|
| Một lần, % | `rate × giá tham chiếu` | Giá tham chiếu = gói rẻ nhất có dữ liệu, kỳ thanh toán đầu |
| Recurring, % | `rate × giá kỳ × N` | `N` = số kỳ **được nêu** trong điều khoản (vd. "12 months"), trần `max_recurring_periods` (mặc định 12). **Không nêu** → `N = 1` + cờ `RECURRING_DURATION_UNKNOWN` (không giả định khách ở lại) |
| Cố định | `số tiền` | |
| Theo bậc / theo danh mục | dùng bậc thấp nhất có số | thận trọng |
| Thiếu giá (với kiểu %) | V = `UNKNOWN` | Không ước lượng giá |

Ngưỡng đề xuất (USD, cấu hình theo tiền tệ): ≥ 100 → 100; ≥ 50 → 75; ≥ 20 → 50; ≥ 5 → 25; < 5 → 0.

### 3.3 Cookie theo chu kỳ mua hàng (P4)

- `purchase_cycle_days` theo loại sản phẩm là **tham số cấu hình** (mặc định đề xuất: `PHYSICAL` 7, `DIGITAL` 7, `SOFTWARE` 30, `UNKNOWN` →
  không đánh giá cookie). Đây là giả định cấu hình được, ghi rõ trong báo cáo – không phải dữ liệu đã xác minh.
- Điều chỉnh: `cookie_days ≥ chu kỳ` → 0; `< chu kỳ` hoặc `session` → hạ một bậc (−25). Cookie `UNKNOWN` → không điều chỉnh, ghi
  `cookie_days` vào "còn thiếu".

## 4. Đánh giá tác động trên dữ liệu kiểm thử (MOCK – chỉ để so sánh công thức)

| Sản phẩm (fixture/demo) | Dữ liệu | v1 affiliate / Opportunity | v2: R / V / affiliate / Opportunity |
|---|---|---|---|
| StockPal (`SOFTWARE`) | 30% recurring 12 tháng, giá 19/tháng, cookie 60 ngày | 100 / 88,24 | R 100; EV = 0,30 × 19 × 12 = 68,4 → V 75; affiliate 75; Opportunity (75·25+75·25+100·20+75·15)/85 = **80,88** |
| ShelfAlert demo (`SOFTWARE`) | 30% recurring 12 tháng, giá 15/tháng, cookie 60 ngày | 100 / 83,82 | R 100; EV 54 → V 75; affiliate 75; Opportunity **76,47** |
| CrumbCount demo (`SOFTWARE`) | 20% một lần, giá 8/tháng, cookie 30 ngày | 75 / 63,46 | R 75; EV 1,6 → V 0; affiliate floor(37,5) = 25; Opportunity giảm |

Thứ tự xếp hạng hai sản phẩm demo không đổi; điểm affiliate thận trọng hơn khi giá trị hoa hồng thực tế nhỏ. Trước khi kích hoạt sẽ chạy
lại báo cáo so sánh v1/v2 trên toàn bộ dữ liệu hiện có (chỉ đọc) để chủ sở hữu xem thay đổi thứ hạng.

## 5. Kế hoạch triển khai sau khi được duyệt (không làm trước)

1. Thêm `rubric.formula_version = 2` + tham số §3 vào một phiên bản trọng số **mới, không active**.
2. Sửa `scoring/criteria.affiliate` theo §3 (giữ nhánh v1 cho `formula_version = 1` để tái lập điểm cũ – SC-004 E2).
3. Test: ví dụ tính tay §4, mọi trường hợp thiếu dữ liệu, tái lập v1 không đổi.
4. Báo cáo so sánh v1/v2 → chủ sở hữu duyệt → kích hoạt qua `POST /api/v1/product-scoring/weights` (đã có).

## 6. Cần chủ sở hữu quyết định

1. Duyệt cách tách R/V và quy tắc Coverage một nửa cho tiêu chí affiliate?
2. Duyệt các bảng ngưỡng §3.1, §3.2 và chu kỳ mua hàng mặc định §3.3 (hoặc đưa ngưỡng khác)?
3. Trần số kỳ recurring (`max_recurring_periods`, đề xuất 12)?
