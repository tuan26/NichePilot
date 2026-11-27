# Đề xuất Product Scoring Rubric v2 – bản 2 (CHỜ CHỦ SỞ HỮU DUYỆT) – 2026-11-27

Chủ sở hữu đồng ý **hướng** cải tiến (2026-11-27) nhưng **chưa phê duyệt áp dụng vào runtime**. Rubric v1 (`contracts/scoring-rubric.md`)
vẫn đang hoạt động; trọng số 25/25/20/15/15 **không đổi**; Product Score hiện tại không bị tính lại. Mọi ngưỡng dưới đây là **mặc định đề
xuất, cấu hình được**, không phải số liệu thị trường đã xác minh.

## 1. Vấn đề của v1

| # | Vấn đề | Ví dụ |
|---|---|---|
| P1 | Một bảng ngưỡng % cho mọi loại sản phẩm | 8% hàng vật lý giá cao và 8% phần mềm bị chấm như nhau |
| P2 | Recurring được +25 cố định, không phân biệt điều khoản | recurring 3 tháng ≈ recurring 24 tháng |
| P3 | Chỉ xét %, không xét tiền thực nhận mỗi giao dịch | 50% của sản phẩm 5 USD xếp trên 10% của sản phẩm 300 USD |
| P4 | Cookie so với ngưỡng cố định 30 ngày | 7 ngày đủ cho hàng mua nhanh, quá ngắn cho phần mềm cần cân nhắc |

## 2. Nguyên tắc (theo yêu cầu chủ sở hữu 2026-11-27)

1. Phân biệt **hoa hồng một lần** và **recurring**.
2. Phân biệt **tỷ lệ hoa hồng** (%) và **giá trị tiền** (số tiền trên một giao dịch).
3. Phân biệt ba đại lượng – không bao giờ trộn lẫn:

   | Đại lượng | Định nghĩa | Nguồn | Dùng để chấm điểm? |
   |---|---|---|---|
   | **Hoa hồng giao dịch đầu tiên** | Tiền nhận được từ giao dịch đầu tiên của một khách giới thiệu: `tỷ lệ × giá kỳ thanh toán đầu` hoặc số tiền cố định | Điều khoản + giá đã có bằng chứng | **Có** (thành phần V) |
   | **Hoa hồng tối đa theo hợp đồng** | Trần trên một khách theo điều khoản: recurring = `tỷ lệ × giá kỳ × số kỳ được NÊU RÕ`; có trần tiền thì lấy trần | Điều khoản | **Không** – chỉ hiển thị, ghi rõ "tối đa theo hợp đồng, không phải doanh thu kỳ vọng" |
   | **Hoa hồng thực tế** | Tiền đã ghi nhận từ giao dịch thật | Dữ liệu commission thật (E8) | Không trong E2; luôn `UNKNOWN` tới khi có dữ liệu thật – không ước lượng |

4. **Không** coi số kỳ recurring là doanh thu chắc chắn; **không** dùng số kỳ để ước tính doanh thu kỳ vọng khi thiếu dữ liệu retention;
   không suy đoán conversion rate hay customer lifetime value.
5. Thiếu dữ liệu → `UNKNOWN`, giảm Coverage (và Confidence qua thành phần V của Confidence), không gán điểm giả.
6. Mỗi ngưỡng có **giải thích** và **khóa cấu hình** trong `product_scoring_weights.rubric` (phiên bản mới); đổi rubric = phiên bản mới.

## 3. Tiêu chí "Hấp dẫn chương trình affiliate" (25%, không đổi trọng số)

```
affiliate = clamp( floor25( trung bình các thành phần có dữ liệu {R, V} ) + bước_recurring + điều_chỉnh_cookie , 0, 100 )
Coverage của tiêu chí = 25 × (số thành phần R, V có dữ liệu) / 2
```

### 3.1 Thành phần R – tỷ lệ hoa hồng theo loại sản phẩm (P1)

Loại lấy từ `products.category`. Tỷ lệ dùng là tỷ lệ **giao dịch đầu tiên**; "lên tới X%" → cận dưới nếu có, không có → X rồi hạ một bậc.

| Loại (`rubric.rate_levels.<loại>`) | 100 | 75 | 50 | 25 | 0 | Giải thích |
|---|---|---|---|---|---|---|
| `SOFTWARE` | ≥ 30 | ≥ 20 | ≥ 15 | ≥ 10 | < 10 | Biên lợi nhuận phần mềm cao nên tỷ lệ chào thường cao hơn; dưới 10% là thấp với nhóm này |
| `PHYSICAL` | ≥ 15 | ≥ 10 | ≥ 6 | ≥ 3 | < 3 | Hàng vật lý có giá vốn/vận chuyển; tỷ lệ thấp hơn là bình thường, nên ngưỡng thấp hơn để không phạt oan |
| `DIGITAL` | ≥ 50 | ≥ 40 | ≥ 30 | ≥ 20 | < 20 | Sản phẩm số (khóa học, ebook) gần như không có giá vốn biên; tỷ lệ cao là phổ biến |
| `UNKNOWN` | dùng bảng chặt nhất (`DIGITAL`) | | | | | Thận trọng khi chưa xác định loại |

Hoa hồng cố định (`fixed`) không có thành phần R, chỉ có V.

### 3.2 Thành phần V – tiền thực nhận ở giao dịch đầu tiên (P3)

`V_amount = tỷ lệ × giá kỳ thanh toán đầu của gói rẻ nhất có bằng chứng` (hoặc số tiền cố định). Khác tiền tệ với ngưỡng → `UNKNOWN`
(không quy đổi tỷ giá). Thiếu giá với kiểu % → `UNKNOWN`.

| `rubric.first_payment_levels` (USD) | 100 | 75 | 50 | 25 | 0 | Giải thích |
|---|---|---|---|---|---|---|
| Mặc định | ≥ 50 | ≥ 20 | ≥ 10 | ≥ 5 | < 5 | Mức tiền đủ bù công tạo một nội dung review; dưới 5 USD/giao dịch khó bù chi phí nội dung |

### 3.3 Recurring (P2) – chỉ là đặc tính điều khoản, không phải doanh thu

- `bước_recurring = +25` CHỈ khi kiểu `recurring` **và** điều khoản nêu rõ số kỳ ≥ `rubric.recurring_min_stated_periods` (mặc định 6) –
  phản ánh điều khoản có lợi hơn, **không** nhân số kỳ vào điểm.
- Recurring không nêu số kỳ → `bước_recurring = 0`, cờ `RECURRING_DURATION_UNKNOWN`.
- Hoa hồng tối đa theo hợp đồng (§2) chỉ hiển thị cho chủ sở hữu, không vào điểm.

### 3.4 Cookie theo chu kỳ mua hàng (P4)

- `rubric.purchase_cycle_days.<loại>` – giả định cấu hình được, ghi rõ trong báo cáo: `PHYSICAL` 7 (hàng phổ thông thường mua trong vài
  ngày), `DIGITAL` 7, `SOFTWARE` 30 (thường có thời gian dùng thử/cân nhắc), `UNKNOWN` → không đánh giá cookie.
- `cookie ≥ chu kỳ` → 0; `cookie < chu kỳ` hoặc `session` → −25. Cookie `UNKNOWN` → 0 và ghi vào "còn thiếu".

## 4. Đánh giá tác động (dữ liệu kiểm thử MOCK – chỉ so sánh công thức, không phải kết quả thật)

| Sản phẩm | Dữ liệu | v1 affiliate / Opportunity | v2: R / V / bước recurring / affiliate / Opportunity |
|---|---|---|---|
| StockPal (fixture, `SOFTWARE`) | 30% recurring, nêu 12 tháng, 19/tháng, cookie 60 | 100 / 88,24 | 100 / 5,7 → 25 / +25 / floor25(62,5)=50 → 75 / **80,88** |
| ShelfAlert (demo, `SOFTWARE`) | 30% recurring, nêu 12 tháng, 15/tháng, cookie 60 | 100 / 83,82 | 100 / 4,5 → 0 / +25 / 50 → 75 / **76,47** |
| CrumbCount (demo, `SOFTWARE`) | 20% một lần, 8/tháng, cookie 30 | 75 / 63,46 | 75 / 1,6 → 0 / 0 / floor25(37,5) = 25 / giảm |

Hoa hồng tối đa theo hợp đồng (chỉ hiển thị): StockPal 0,30 × 19 × 12 = 68,4; ShelfAlert 54 – **không** dùng trong điểm.
Thứ tự hai sản phẩm demo không đổi. Trước khi kích hoạt: báo cáo so sánh v1/v2 chỉ đọc trên toàn bộ dữ liệu hiện có.

## 5. Kế hoạch triển khai sau khi được duyệt (không làm trước)

1. Phiên bản trọng số **mới, không active**: giữ 25/25/20/15/15, `rubric.formula_version = 2` + tham số §3.
2. `scoring/criteria.affiliate`: nhánh `formula_version = 2`; giữ nhánh v1 để tái lập điểm cũ (SC-004 E2).
3. Hiển thị ba đại lượng §2 trên chi tiết chương trình (hoa hồng thực tế = `UNKNOWN`).
4. Test: ví dụ §4, mọi trường hợp thiếu dữ liệu, v1 tái lập không đổi; báo cáo so sánh → chủ sở hữu duyệt → kích hoạt.

## 6. Cần chủ sở hữu quyết định

1. Ba đại lượng §2 và việc chỉ chấm điểm hoa hồng giao dịch đầu tiên?
2. Bảng ngưỡng §3.1, §3.2 (kèm giải thích) và chu kỳ mua hàng §3.4?
3. Bước recurring +25 khi số kỳ nêu rõ ≥ 6?
