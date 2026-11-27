# Scoring Rubric – E3 Keyword (công thức 1)

Keyword Opportunity là **điểm ưu tiên nghiên cứu**, không phải dự báo traffic/doanh thu (FR-021). Ngưỡng nằm trong `keyword_scoring_weights.rubric`
v1, cấu hình được. Search Volume/CPC/KD **không** là tiêu chí (luôn `UNKNOWN` trong E3).

## 1. Tiêu chí và trọng số (Clarification Q1)

| Khóa | Tiêu chí | Trọng số | Nguồn mức |
|---|---|---|---|
| `fit` | Phù hợp pain point/persona/sản phẩm | 30 | AI đề xuất + mã kiểm |
| `intent_value` | Giá trị theo search intent | 20 | Xác định |
| `competition` | Cơ hội cạnh tranh quan sát được | 20 | Xác định từ SERP |
| `content_gap` | Khoảng trống nội dung | 15 | Xác định từ trang đối thủ |
| `demand` | Bằng chứng nhu cầu | 15 | Xác định từ bằng chứng E1 + SERP |

Mức ∈ {0, 25, 50, 75, 100} hoặc `null`.

## 2. Quy tắc

- **fit**: hợp lệ khi mức ∈ thang, có lý do, keyword có ≥ 1 origin hợp lệ, `evidence_ids` ⊆ bằng chứng ACTIVE của pain point/sản phẩm gốc. Ngược
  lại `null`.
- **intent_value** (`rubric.intent_value`): `COMMERCIAL_INVESTIGATION` 100; `INFORMATIONAL` với loại `PROBLEM`/`SOLUTION` 75; `TRANSACTIONAL` 75;
  `INFORMATIONAL` khác 25; `NAVIGATIONAL` 0. (Không mặc định ý định mua cao hơn keyword giải quyết vấn đề – Q1.)
- **competition**: chỉ khi có SERP. `weak` = kết quả loại `forum`/`qa` + trang đối thủ đã phân tích không phủ pain point chính của cluster; `share =
  weak / số kết quả`. share ≥ 0,5 → 100; ≥ 0,3 → 75; ≥ 0,2 → 50; > 0 → 25; = 0 → 0. Không có SERP → `null`.
- **content_gap**: chỉ khi có ≥ 1 trang đối thủ phân tích. `ratio = #pain point gốc chưa được trang nào phủ / #pain point gốc` (keyword gốc sản phẩm:
  dùng pain point liên kết sản phẩm–ngách ở E2). ratio ≥ 0,75 → 100; ≥ 0,5 → 75; ≥ 0,25 → 50; > 0 → 25; 0 → 0. Không có trang → `null`.
- **demand**: `n` = số nhóm nguồn độc lập của bằng chứng ACTIVE thuộc pain point gốc (E1, `evidence_count`) + số kết quả SERP loại `forum`/`qa`.
  n ≥ 6 → 100; ≥ 4 → 75; ≥ 3 → 50; ≥ 1 → 25; 0 → `null`.

## 3. Opportunity, Coverage, Confidence

```
V = {i : level_i ≠ null};  Coverage = Σ_{V} w_i
Opportunity = Σ level_i·w_i / Σ_{V} w_i  nếu Coverage ≥ 60 ∧ fit ∈ V, ngược lại null (INSUFFICIENT_SCORING_DATA)
```

Confidence (không nhận Opportunity):

| Thành phần | Công thức | Trọng số |
|---|---|---|
| S | 1 nếu có quan sát SERP, 0 nếu không | 0,25 |
| D | min(1, số tên miền khác nhau trong bằng chứng dùng / 4) | 0,20 |
| F | trung bình max(0, 1 − tuổi_ngày / 180) của bằng chứng | 0,15 |
| O | tỷ lệ tiêu chí có dữ liệu quan sát (competition, content_gap, demand từ SERP) / 3 | 0,20 |
| V | Coverage / 100 | 0,20 |

### Ví dụ tính tay (test `TC_E3_FR017_*`, `TC_E3_FR019_*`)
fit 75, intent `INFORMATIONAL`+`PROBLEM` → 75, competition share 0,4 → 75, content_gap ratio 0,5 → 75, demand n = 3 → 50.
Coverage 100; Opportunity = (75·30 + 75·20 + 75·20 + 75·15 + 50·15)/100 = (2250+1500+1500+1125+750)/100 = **71,25**.
Không có SERP: competition, content_gap null, demand n = 2 (chỉ E1) → 25 → Coverage = 30+20+15 = 65 → Opportunity = (2250+1500+375)/65 = **63,46**.
Bỏ thêm fit → `INSUFFICIENT_SCORING_DATA`.
Confidence (có SERP, 3 tên miền, tuổi TB 36 ngày, O = 3/3, Coverage 100): 100 × (0,25 + 0,15 + 0,12 + 0,20 + 0,20) = **92,00**.

## 4. Cluster

Opportunity cluster = trung bình Opportunity keyword `SCORED` (2 số lẻ); Confidence = trung bình; không có keyword `SCORED` → cluster "cần nghiên
cứu thêm". Xếp hạng: Opportunity giảm, hòa → Confidence; `REJECTED` không vào danh sách xếp hạng.
