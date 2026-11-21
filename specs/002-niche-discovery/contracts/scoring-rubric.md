# Scoring Rubric – E1 (phiên bản công thức 1)

Opportunity Score là **điểm ưu tiên nghiên cứu**, không phải dự báo doanh thu hay khả năng sinh lợi đã xác minh (FR-019c).
Mọi số dưới đây là tham số mặc định, cấu hình được qua phiên bản trọng số (`scoring_weights_versions`).

## 1. Ngưỡng bằng chứng (FR-013b, FR-015)

Bằng chứng **hợp lệ** cho ngưỡng (FR-013a, FR-013b): có đủ URL nguồn, trích đoạn (đã che), thời điểm thu thập và trạng thái xác minh
(thiếu bất kỳ trường nào → không tính), `purpose = PAIN_POINT`, `lifecycle_status = ACTIVE`, `redaction_status = REDACTED`,
`relevance ≥ 0,6`, `quality ≥ 0,5`, `copy_suspected = false`, `data_origin = REAL` (lượt mock: tính riêng, gắn MOCK).

**Nhóm độc lập**: hai bằng chứng cùng nhóm nếu cùng `registered_domain` (eTLD+1) **hoặc** khoảng cách Hamming SimHash ≤ 3 (bản sao
khác tên miền). Nhóm = thành phần liên thông.

Bổ sung khi triển khai US2 (2026-11-20, chỉ làm **chặt hơn** – gộp thêm nhóm, không bao giờ tách): (a) SimHash so trên cả trích đoạn
và toàn nguồn; (b) cùng `content_hash`; (c) tỉ lệ chứa shingle 3 từ `|A∩B| / min(|A|,|B|) ≥ 0,5` với trích đoạn ≥ 12 từ – vì test cho
thấy bản sao sửa 2–3 từ có Hamming SimHash = 5 (> 3) nên SimHash một mình bỏ sót; (d) hậu tố không có trong PSL (vd. `.example`) → eTLD+1
= 2 nhãn cuối. Nhóm tính trên mọi bằng chứng ACTIVE của ngách (kể cả bằng chứng không hợp lệ, thận trọng). Tham số `shingle_overlap_min`,
`min_tokens_for_overlap` đọc từ `evidence_rules` (mặc định 0,5 / 12 nếu phiên bản trọng số không có).

Kết luận (pain point, persona, findings) không dẫn ít nhất 1 `evidence_id` hợp lệ → `UNKNOWN` (FR-013, SC-004); một `evidence_id` lạ
→ loại toàn bộ đầu ra AI của ứng viên đó.

Đạt ngưỡng ⇔ số bằng chứng hợp lệ ≥ 2 **và** số nhóm độc lập ≥ 2 → `EVIDENCE_SUFFICIENT`; ngược lại `INSUFFICIENT_EVIDENCE`.

## 2. Thang chấm tiêu chí (AI đề xuất mức, mã kiểm tra)

Mỗi tiêu chí: mức ∈ {0, 25, 50, 75, 100} hoặc `null` (UNKNOWN/CONFLICTING), kèm lý do và `evidence_ids`. Mức không thuộc thang → đầu
ra bị loại.

| Tiêu chí (trọng số mặc định) | 0 | 25 | 50 | 75 | 100 |
|---|---|---|---|---|---|
| Mức độ vấn đề (25) | không thấy phàn nàn | phiền nhẹ, hiếm | lặp lại, có cách xử lý tạm | gây tốn thời gian/tiền, nhiều nguồn | nghiêm trọng, cấp bách, khách chủ động tìm giải pháp trả phí |
| Monetization (20) | không có sản phẩm/chương trình liên quan | sản phẩm có nhưng không thấy affiliate | tín hiệu affiliate gián tiếp | chương trình affiliate công khai cho sản phẩm liên quan | nhiều chương trình công khai, giá trị đơn hàng rõ |
| Khoảng trống thị trường (20) | giải pháp đầy đủ, được khen | khoảng trống nhỏ | phàn nàn về giải pháp hiện có | khoảng trống rõ ở một phân khúc | không có giải pháp phù hợp, nhu cầu rõ |
| Khả năng tiếp cận (15) | không tìm thấy nơi khách tụ tập | 1 kênh nhỏ | vài kênh | cộng đồng/kênh hoạt động rõ | nhiều kênh lớn, hoạt động, dễ tiếp cận |
| Cơ hội cạnh tranh (10) | bão hòa bởi đối thủ lớn | cạnh tranh cao | trung bình | ít nội dung chất lượng | gần như chưa có nội dung chuyên sâu |
| Độ ổn định nhu cầu (10) | nhất thời/đã qua | theo mùa mạnh | ổn định ngắn hạn | ổn định nhiều năm | nhu cầu bền vững, tăng |

Search volume thấp/không có **không** làm giảm điểm tự động (FR-021).

## 3. Opportunity, Coverage, Confidence

```
V = {i : score_i ≠ null}
Coverage    = Σ_{i∈V} w_i                       (trọng số gốc, %)
Opportunity = Σ_{i∈V} s_i·w_i / Σ_{i∈V} w_i      nếu Coverage ≥ 60, ngược lại null (INSUFFICIENT_SCORING_DATA)
```

Confidence (0–100), không nhận Opportunity làm đầu vào:

| Thành phần | Công thức (0–1) | Trọng số |
|---|---|---|
| N | min(1, số nhóm độc lập / 6) | 0,25 |
| Q | trung bình `quality` của bằng chứng hợp lệ (0 nếu không có) | 0,20 |
| D | min(1, số loại nguồn khác nhau / 3) (diễn đàn, bài viết, trang đánh giá, hỏi-đáp, video, khác) | 0,15 |
| F | trung bình max(0, 1 − tuổi_ngày/730); tuổi theo `published_at`, thiếu thì `collected_at` | 0,15 |
| K | 1 − (#CONFLICTING / #tiêu chí có dữ liệu hoặc CONFLICTING); không có tiêu chí nào → 0 | 0,15 |
| V | Coverage / 100 | 0,10 |

`Confidence = round(100 × ΣC·w, 2)`; nếu `INSUFFICIENT_EVIDENCE` → `min(Confidence, 30)`.

### Ví dụ tính tay (dùng làm test `TC_E1_FR019_*`)

Tiêu chí: severity 75 (VERIFIED), monetization null (UNKNOWN), gap 50, reach 75, competition 25, stability null.
V = {severity 25, gap 20, reach 15, competition 10} → Coverage = 70 ≥ 60.
Opportunity = (75·25 + 50·20 + 75·15 + 25·10)/70 = (1875+1000+1125+250)/70 = 4250/70 = **60,71**.
Monetization null → `MONETIZATION_UNVERIFIED`, không vào danh sách ưu tiên affiliate.

Bằng chứng hợp lệ: 4, nhóm độc lập 3, quality trung bình 0,7, 2 loại nguồn, tuổi trung bình 365 ngày (F = 0,5), 0 CONFLICTING.
N = 0,5; Q = 0,7; D = 0,6667; F = 0,5; K = 1; V = 0,7 →
Confidence = 100 × (0,125 + 0,14 + 0,1 + 0,075 + 0,15 + 0,07) = **66,00**.

Nếu bỏ thêm reach (null): Coverage = 55 < 60 → Opportunity null, `INSUFFICIENT_SCORING_DATA` (Confidence vẫn tính, V = 0,55).

## 4. Danh sách xếp hạng (FR-024)

Đạt ngưỡng bằng chứng **không** có nghĩa là ngách sinh lợi (FR-013d): `EVIDENCE_SUFFICIENT` chỉ cho phép ngách vào bảng cơ hội nghiên cứu;
danh sách ưu tiên affiliate còn đòi hỏi `SIGNALS_FOUND`; báo cáo/UI luôn kèm chú thích `discovery.opportunity.disclaimer`.


| Danh sách | Điều kiện | Sắp xếp |
|---|---|---|
| Cơ hội nghiên cứu | EVIDENCE_SUFFICIENT ∧ SCORED ∧ REAL ∧ decision ≠ HIDDEN/REJECTED | Opportunity giảm dần, hòa → Confidence |
| Ưu tiên affiliate | danh sách trên ∧ `SIGNALS_FOUND` ∧ không `MONETIZATION_RISK` | như trên |
| Cần nghiên cứu thêm | INSUFFICIENT_EVIDENCE ∨ INSUFFICIENT_SCORING_DATA | Confidence giảm dần |

## 5. Trùng/tương đồng (FR-022)

`sim = 0,6 · token_set_ratio(core_problem) + 0,4 · token_set_ratio(customer_group)` (rapidfuzz, 0–1) trên dạng chuẩn hóa
(`discovery.normalize`) cùng `country` và cùng `data_origin`.
`sim ≥ 0,85` → trùng chắc chắn: gộp vào ngách cũ, liên kết lượt mới. `0,60 ≤ sim < 0,85` → `niche_similarity POSSIBLE` chờ chủ sở hữu.
