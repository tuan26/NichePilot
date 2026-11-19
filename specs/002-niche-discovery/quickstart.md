# Quickstart – Kiểm chứng E1 (sau khi được phép triển khai)

Tài liệu này mô tả cách kiểm chứng E1 **sau** `/speckit-implement`. Hiện chưa có mã E1 – mọi bước dưới đây ở trạng thái `NOT_TESTED`.
Không bước nào gọi API có phí; nguồn thật chỉ dùng khi chủ sở hữu đã bật ít nhất một nguồn tìm kiếm.

## 0. Điều kiện

- Stack E0 chạy được (`docs/operations/README.md`), migration tới `0010_discovery_seed`.
- `AI_PAID_CALLS_ENABLED=false` (mặc định) → AI dùng `MockAIProvider` ở development/test; kết quả AI gắn `MOCK`.
- Ngân sách E0 đã cấu hình ($3/ngày, $30/tháng).

## 1. Chạy hoàn toàn giả lập (không mạng) – kịch bản CI

```bash
cd backend && uv run pytest -m "discovery and not live_sources"
```

Kỳ vọng: `MockSearchAdapter` + `MockPageFetcher` (HTML cố định trong `tests/fixtures/discovery/`) + `MockAIProvider`; rào chắn socket
không ghi nhận kết nối; ngách tạo ra gắn `MOCK`, không xuất hiện trong bảng xếp hạng mặc định (`include_mock=false`).

## 2. Từ chối khi không có nguồn hợp lệ (FR-006e)

1. Đăng nhập dashboard → **Lượt khám phá** → Tạo lượt (thị trường `US`, không chọn lĩnh vực).
2. Với seed mặc định (mọi nguồn `UNVERIFIED`, tắt) → API trả 409 `NO_COMPLIANT_SEARCH_SOURCE`, UI hiển thị thông báo VI/EN và liên
   kết tới trang nguồn tìm kiếm. Không job nào được tạo, không lời gọi AI.

## 3. Bật nguồn và chạy lượt với nguồn thật (khi chủ sở hữu cho phép)

1. **Nguồn tìm kiếm**: chủ sở hữu đọc điều khoản (`tos_url`), cập nhật `compliance_status = ALLOWED` + `verified_at` +
   `verification_note`, rồi bật. Hoặc bật nguồn `UNVERIFIED` với `acknowledge_warning = true` (audit ghi cảnh báo).
2. `docker compose up -d searxng` (service nội bộ, không mở cổng ra ngoài).
3. Tạo lượt: `POST /api/v1/discovery/runs {"market":"US","max_candidates":5,"page_limit":40,"time_limit_minutes":15}`.
4. Quan sát màn hình 1: trạng thái job, trang đã thu thập/bỏ qua theo lý do, chi phí REAL/MOCK (REAL = $0 khi gọi có phí tắt).
5. Kỳ vọng: nguồn/bằng chứng `REAL`, trích đoạn đã che PII; phân tích AI là `MOCK` (không có API key) → ngách gắn `MOCK`. Đây **không**
   phải bằng chứng E1 hoạt động với Claude API thật.

## 4. Kiểm chứng giới hạn và độ bền

| Kịch bản | Cách làm | Kỳ vọng |
|---|---|---|
| Giới hạn trang | `page_limit = 10` | `PARTIAL_COMPLETED / PAGE_LIMIT_REACHED`, ngách thiếu bằng chứng → `INSUFFICIENT_EVIDENCE` |
| Giới hạn thời gian | `time_limit_minutes = 5` | `PARTIAL_COMPLETED / TIME_LIMIT_REACHED`; thời gian tạm dừng không tính |
| Tạm dừng/tiếp tục | `/api/v1/jobs/{id}/pause` → `resume` | Tiếp tục từ checkpoint, không thu thập lại URL đã có (`page_fetch_log`) |
| Kill worker | `docker compose kill worker` → start | Như trên; không ngách/bằng chứng trùng |
| Hết ngân sách | Ngân sách lượt nhỏ với mock có chi phí giả lập | `PAUSED_BUDGET` (E0), không tự tăng ngân sách |
| Tốc độ theo tên miền | 2 URL cùng tên miền trong fixture | Khoảng cách ≥ 2 s (hoặc Crawl-delay nếu lớn hơn) |

## 5. Bằng chứng, chấm điểm, quyết định

1. Màn hình 2: chuyển 3 tab (cơ hội nghiên cứu / ưu tiên affiliate / cần nghiên cứu thêm); mỗi dòng có Opportunity, Confidence,
   Coverage, trạng thái xác minh, Monetization; chú thích "không phải dự báo doanh thu".
2. Màn hình 3: pain point + bằng chứng (URL, trích đoạn đã che, thời điểm), điểm thành phần, phiên bản trọng số, tiêu chí `UNKNOWN`.
   So sánh với ví dụ tính tay ở `contracts/scoring-rubric.md` §3.
3. Ghi quyết định `WATCH` kèm lý do → audit `niche.decision_recorded`.
4. Tạo phiên bản trọng số mới với `recompute_existing = true` → job `discovery.recompute` (0 lời gọi AI), đánh giá mới tham chiếu
   phiên bản mới, đánh giá cũ giữ nguyên.

## 6. Xóa bằng chứng và khôi phục backup (FR-013e/f)

1. Xóa một bằng chứng của ngách đang đạt ngưỡng đúng 2 nhóm → ngách chuyển `INSUFFICIENT_EVIDENCE`, rời bảng xếp hạng chính.
2. `make backup` (backup tạo trước bước 1) → `make restore` từ bản cũ → `restore.sh` áp lại ledger → bằng chứng vẫn `ERASED`.
3. Kiểm tra log/checkpoint/audit không chứa trích đoạn đã xóa.

## 7. Giao diện

```bash
cd frontend && npm run lint && npm run typecheck && npm test && npx playwright test tests/e2e/discovery.spec.ts
```

Kỳ vọng: 3 màn hình có trạng thái đang tải/rỗng/lỗi, chuyển VI/EN, nhãn MOCK rõ ràng; `i18n-keys.test.ts` 100% khóa có bản dịch.

## 8. Truy vết

```bash
uv run --no-project python scripts/traceability_report.py --strict
```

Kỳ vọng: 100% FR Must của spec 001 và 002 có test `TC_*`/`TC_E1_*`.
