# Scoring Rubric – E2 (phiên bản công thức 1)

Product Opportunity Score là **điểm ưu tiên nghiên cứu**, không phải dự báo doanh thu (FR-031). Mọi ngưỡng dưới đây là mặc định trong
`product_scoring_weights` v1 (`rubric`), cấu hình được, có phiên bản. Thuộc tính đọc từ `attributes.resolve` (chỉ bằng chứng `ACTIVE`).
"Có dữ liệu" = trạng thái `VERIFIED`, `INFERRED`; `CONFLICTING` dùng **giá trị `VERIFIED`** nếu có, nếu không coi như `UNKNOWN`.

## 1. Tiêu chí và trọng số mặc định (Clarification Q2)

| Khóa | Tiêu chí | Trọng số | Cách tính |
|---|---|---|---|
| `fit` | Phù hợp pain point & buyer persona | 25 | AI đề xuất mức + mã kiểm tra (§2.1) |
| `affiliate` | Hấp dẫn chương trình affiliate | 25 | Xác định (§2.2) |
| `eligibility` | Khả năng tham gia & quảng bá hợp lệ | 20 | Xác định (§2.3) |
| `quality` | Uy tín & chất lượng sản phẩm | 15 | Xác định (§2.4) |
| `price_fit` | Giá phù hợp khả năng chi trả | 15 | AI đề xuất mức + mã kiểm tra (§2.5) |

Mức ∈ {0, 25, 50, 75, 100} hoặc `null` (UNKNOWN). Tiêu chí lấy từ **chương trình tốt nhất** của sản phẩm = chương trình có
`verification_status` cao nhất (VERIFIED > PARTIAL > UNVERIFIED > CLOSED), hòa → mức `affiliate` cao hơn.

## 2. Quy tắc mức

### 2.1 `fit` (AI, INFERRED)
Hợp lệ khi: mức ∈ thang, có lý do, ≥ 1 `evidence_id` ACTIVE trong tập đã đưa vào prompt, **và** cặp có ≥ 1 liên kết pain point có bằng
chứng ACTIVE. `persona_match = NO_MATCH` → mức tối đa 25. Không hợp lệ → `null`.

### 2.2 `affiliate` (từ `commission`, `cookie_days`)
`commission` không có dữ liệu → `null` (cookie một mình không đủ).

Mức cơ sở theo tỷ lệ hiệu dụng `r` (%):
- `percent`/`recurring`: `r = value`; khoảng `min–max` → `r = min`; "lên tới X" (`up_to`) → `r = X` rồi **trừ 25** (thận trọng).
- `fixed`: có giá sản phẩm (gói rẻ nhất có dữ liệu) → `r = 100·value/price`; không có giá → theo số tiền: ≥ 50 → 75, ≥ 20 → 50, ≥ 5 → 25, còn lại 0.
- `tiered`/`per_category`: dùng bậc/danh mục thấp nhất có số.

| r | ≥ 30 | ≥ 20 | ≥ 10 | ≥ 5 | < 5 |
|---|---|---|---|---|---|
| mức | 100 | 75 | 50 | 25 | 0 |

Điều chỉnh: `recurring` (hoặc `recurring_months` ≥ 6) +25; cookie có dữ liệu: < 30 ngày hoặc `session` −25, ≥ 60 ngày +0. Kẹp [0, 100].
**Hoa hồng cao không tự tạo khuyến nghị "chọn"** (FR-028a).

### 2.3 `eligibility` (từ `vn_eligibility`, `promotion_regions`, `ad_restrictions`; thị trường = `niches.country`)
- `market_ok` = `promotion_regions.global` hoặc `country ∈ include` và `country ∉ exclude`.
- `NOT_ALLOWED` hoặc `country ∈ exclude` → **0**.
- `vn_eligibility` và `promotion_regions` đều `UNKNOWN` → `null`.
- Cả hai có dữ liệu và thuận lợi: 100 nếu `ad_restrictions` có dữ liệu với ≤ 1 mã; 75 nếu ≥ 2 mã hoặc `ad_restrictions` UNKNOWN. Nếu một
  trong hai chỉ `INFERRED` → tối đa 50.
- Một có dữ liệu thuận lợi, một `UNKNOWN` → 50.

### 2.4 `quality` (xác định)
Điểm thành phần: `official_website` VERIFIED (+1); ≥ 3 `feature` có dữ liệu (+1); số nhóm tên miền độc lập (≠ `official_domain`) có
`third_party_mention` positive: 1 nhóm (+1), ≥ 2 nhóm (+2); có ≥ 1 mention negative từ ≥ 2 nhóm (−1). Tổng t (kẹp 0–4) → mức `25·t`.
Không có website, tính năng hay mention nào → `null`.

### 2.5 `price_fit` (AI, INFERRED)
Hợp lệ khi mức ∈ thang, có lý do, ≥ 1 `evidence_id` ACTIVE, `price` có dữ liệu **và** `buyer_personas.attributes.ability_to_pay` không
`UNKNOWN`. Ngược lại `null`.

## 3. Opportunity, Coverage, Confidence

```
V = {i : level_i ≠ null}
Coverage    = Σ_{i∈V} w_i
Opportunity = Σ_{i∈V} level_i·w_i / Σ_{i∈V} w_i     nếu Coverage ≥ coverage_min (60) ∧ fit ∈ V; ngược lại null
scoring_status = SCORED | INSUFFICIENT_SCORING_DATA
missing = thuộc tính bắt buộc UNKNOWN (official_website, price, feature, target_customer, commission, cookie_days, payment,
          vn_eligibility, promotion_regions, ad_restrictions) ∪ tiêu chí null
```

Confidence (không nhận Opportunity làm đầu vào):

| Thành phần | Công thức (0–1) | Trọng số |
|---|---|---|
| A | #thuộc tính bắt buộc `VERIFIED` / 10 | 0,30 |
| D | min(1, số tên miền nguồn khác nhau / 4) | 0,20 |
| F | trung bình max(0, 1 − tuổi_ngày/365) theo `collected_at` | 0,15 |
| K | 1 − #CONFLICTING / #thuộc tính có dữ liệu hoặc CONFLICTING (không có → 0) | 0,15 |
| V | Coverage / 100 | 0,20 |

`Confidence = round(100 × Σ C·w, 2)`.

### Ví dụ tính tay (test `TC_E2_FR027_*`, `TC_E2_FR029_*`)
fit 75, affiliate: percent 30% recurring + cookie 30 ngày → 100+25 → 100, eligibility: VN ALLOWED VERIFIED + US trong include VERIFIED +
ad_restrictions [NO_BRAND_BIDDING] → 100, quality: website VERIFIED + 4 tính năng + 1 nhóm positive → t = 3 → 75, price_fit null.
Coverage = 25+25+20+15 = 85; Opportunity = (75·25 + 100·25 + 100·20 + 75·15)/85 = (1875+2500+2000+1125)/85 = 7500/85 = **88,24**.
Bỏ thêm affiliate (commission UNKNOWN) → Coverage 60 = ngưỡng → Opportunity = (1875+2000+1125)/60 = **83,33**.
Bỏ thêm quality → Coverage 45 < 60 → `INSUFFICIENT_SCORING_DATA`.

Confidence: 7/10 VERIFIED (A = 0,7), 3 tên miền (D = 0,75), tuổi TB 73 ngày (F = 0,8), 0 CONFLICTING (K = 1), Coverage 85 (V = 0,85) →
100 × (0,21 + 0,15 + 0,12 + 0,15 + 0,17) = **80,00**.

## 4. Trạng thái sẵn sàng affiliate của cặp (FR-026)

Từ chương trình tốt nhất (§1) và `country` của ngách:

| Điều kiện (theo thứ tự) | readiness_status |
|---|---|
| Không có chương trình liên kết | `NO_PROGRAM` |
| Mọi chương trình `CLOSED` | `PROGRAM_CLOSED` |
| Không có chương trình `VERIFIED`/`PARTIAL` | `AFFILIATE_UNVERIFIED` |
| `vn_eligibility = NOT_ALLOWED` hoặc `country ∈ exclude` (có dữ liệu) | `NOT_ELIGIBLE` |
| `vn_eligibility = ALLOWED` **VERIFIED** ∧ `market_ok` **VERIFIED** | `READY_TO_PROMOTE` |
| còn lại | `ELIGIBILITY_UNVERIFIED` |

Cờ: mọi trạng thái ≠ `READY_TO_PROMOTE` → `MONETIZATION_RISK`; `market_ok` sai → `MARKET_NOT_ALLOWED`; `promotion_regions` UNKNOWN →
`MARKET_UNKNOWN`. Tóm tắt ngách: `MONETIZATION_RISK` cấp ngách khi không có cặp nào `READY_TO_PROMOTE`.

## 5. Khuyến nghị AI (FR-028a, FR-033)

`SELECT` chỉ được giữ khi: `READY_TO_PROMOTE` ∧ `fit` hợp lệ ∧ `scoring_status = SCORED`; ngược lại mã đặt `UNKNOWN` (lý do mã:
`NOT_READY_TO_PROMOTE`, `FIT_UNKNOWN`, `INSUFFICIENT_SCORING_DATA`). `REJECT` luôn được giữ (chỉ là đề xuất; chủ sở hữu quyết định).

## 6. Danh sách (FR-032)

| Danh sách | Điều kiện | Sắp xếp |
|---|---|---|
| Xếp hạng | `SCORED` ∧ `decision_status ≠ REJECTED` ∧ (REAL hoặc bật hiện MOCK) ∧ sản phẩm chưa bị gộp | Opportunity giảm, hòa → Confidence |
| Cần nghiên cứu thêm | `INSUFFICIENT_SCORING_DATA` | Confidence giảm |
