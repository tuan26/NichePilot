# Vận hành E3 – Keyword & Audience Research

E3 nghiên cứu keyword và audience cho một ngách E1 đủ điều kiện, dựa trên pain point, buyer persona và sản phẩm E2.
Spec: `specs/004-keyword-audience-research/`.

## 1. Điều kiện chạy

- Ngách đủ điều kiện theo cùng quy tắc E2 (`EVIDENCE_SUFFICIENT`, chưa `REJECTED`/`HIDDEN`/gộp) – ngược lại `NICHE_NOT_ELIGIBLE`.
- Ngân sách AI ngày/tháng đã cấu hình (`BUDGET_NOT_CONFIGURED`). Gọi API có phí vẫn tắt (`AI_PAID_CALLS_ENABLED=false`).
- Mỗi ngách chỉ 1 lượt đang chạy (`KEYWORD_RUN_ACTIVE`). Lịch `keywords.run` bắt buộc `niche_id`.
- **Không bắt buộc nguồn `ALLOWED`**: thiếu nguồn → keyword vẫn được sinh từ dữ liệu nội bộ, bước SERP/đối thủ/kênh bị bỏ qua với
  `PARTIAL_COMPLETED / NO_COMPLIANT_SEARCH_SOURCE`; các tiêu chí phụ thuộc SERP là `UNKNOWN` (Coverage thấp hơn). Hiện **chưa có** nguồn
  nào `ALLOWED`.

## 2. Chạy

- Giao diện: trang ngách → khối **Keyword** → **Xem keyword & audience** → **Nghiên cứu keyword**.
- API: `POST /api/v1/keyword-runs {"niche_id": "…"}` → job E0 `keywords.run` (tạm dừng/tiếp tục/hủy qua `/api/v1/jobs/{id}/…`).
  Giới hạn mặc định: 60 keyword, SERP cho 10 keyword ưu tiên, 3 trang đối thủ/SERP, 60 trang, 30 phút (tham số của lượt).
- Theo dõi SERP (tùy chọn): bật **Theo dõi thay đổi SERP** trên cluster, rồi tạo lịch `/api/v1/schedules` với
  `job_type = keywords.serp_check`, `params.cluster_id`. Hệ thống không tự tạo lịch; job này không gọi AI.

## 3. Đọc kết quả

- **Nguồn gốc**: mỗi keyword dẫn tới ≥ 1 pain point, thuộc tính persona hoặc sản phẩm của ngách; keyword không có nguồn gốc hợp lệ bị loại.
- **Search Volume / CPC / KD**: luôn `UNKNOWN` khi không có nguồn dữ liệu keyword hợp lệ. DB từ chối ghi giá trị không kèm nguồn, thời
  điểm và thị trường; AI không được phép trả các chỉ số này. Volume thấp/UNKNOWN không loại keyword.
- **Intent**: `INFERRED` (AI/mẫu) hoặc `VERIFIED` khi loại trang trên SERP quan sát phù hợp intent.
- **SERP**: thứ tự quan sát từ nguồn `ALLOWED` tại thời điểm thu thập – không phải thứ hạng chính thức.
- **Điểm**: Keyword Opportunity (fit 30, intent 20, cạnh tranh quan sát 20, content gap 15, bằng chứng nhu cầu 15; Coverage ≥ 60% và có
  `fit`) và Confidence tách biệt. Keyword giải quyết vấn đề (informational gắn pain point) được chấm ngang transactional. Không phải dự báo
  traffic/doanh thu. Đổi trọng số: `POST /api/v1/keyword-scoring/weights` (phiên bản mới + tính lại không AI).
- **Persona cụm, strategy**: AI suy luận, mỗi thuộc tính cần bằng chứng, thiếu → `UNKNOWN`; câu "đã test/đã dùng thử" không bằng chứng
  bị loại. Không xuất bản nội dung tự động.
- Dữ liệu `MOCK` ẩn mặc định; bật "Hiện dữ liệu giả lập (MOCK)" để xem.

## 4. Dữ liệu demo (chỉ development)

```bash
docker compose -f deploy/docker-compose.yml --env-file deploy/env/.env exec -T api python -m nichepilot.jobs.keywords_demo_seed
```

Cần chạy `discovery_demo_seed` và `products_demo_seed` trước. Lệnh từ chối khi `APP_ENV=production`, idempotent, mọi bản ghi `MOCK`.

## 5. Sự cố thường gặp

| Hiện tượng | Nguyên nhân | Xử lý |
|---|---|---|
| `PARTIAL_COMPLETED / NO_COMPLIANT_SEARCH_SOURCE` | Chưa có nguồn `ALLOWED` | Bình thường ở trạng thái hiện tại; SERP/gap/kênh `UNKNOWN` |
| Cluster ở "Cần nghiên cứu thêm" | Coverage < 60% hoặc thiếu `fit` hợp lệ | Bổ sung bằng chứng pain point/sản phẩm hoặc nguồn `ALLOWED` |
| `serp_check` ghi `last_check_error` | Nguồn tắt / không có kết quả | Quan sát cũ được giữ nguyên |
| 503 `ERASURE_LEDGER_NOT_APPLIED` | Sổ xóa bằng chứng chưa áp dụng | Xem vận hành E1 |
