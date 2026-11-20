# Quickstart – Kiểm chứng E1 (sau khi được phép triển khai)

Tài liệu này mô tả cách kiểm chứng E1 **sau** `/speckit-implement`. Hiện chưa có mã E1 – mọi bước dưới đây ở trạng thái `NOT_TESTED`.
Không bước nào gọi API có phí; nguồn thật chỉ dùng khi chủ sở hữu đã bật ít nhất một nguồn tìm kiếm.

## 0. Điều kiện

- Nguồn thật: mọi nguồn hiện `UNVERIFIED` (xác minh BLOCKED do mạng – [source-verification.md](./source-verification.md)); §3 chỉ
  chạy được sau khi chủ sở hữu xác minh. Các mục khác dùng adapter giả lập.

- Stack E0 chạy được (`docs/operations/README.md`), migration tới `0010_discovery_seed`.
- `AI_PAID_CALLS_ENABLED=false` (mặc định) → AI dùng `MockAIProvider` ở development/test; kết quả AI gắn `MOCK`.
- Ngân sách E0 đã cấu hình ($3/ngày, $30/tháng).

## 1. Chạy hoàn toàn giả lập (không mạng) – kịch bản CI

```bash
cd backend && uv run pytest -m "discovery and not live_sources"
```

Kỳ vọng: `MockSourceAdapter` + `MockPageFetcher` (HTML cố định trong `tests/fixtures/discovery/`) + `MockAIProvider`; rào chắn socket
không ghi nhận kết nối; ngách tạo ra gắn `MOCK`, không xuất hiện trong bảng xếp hạng mặc định (`include_mock=false`).

## 2. Từ chối khi không có nguồn hợp lệ (FR-006e)

1. Đăng nhập dashboard → **Lượt khám phá** → Tạo lượt (thị trường `US`, không chọn lĩnh vực).
2. Với seed mặc định (mọi nguồn `UNVERIFIED`, tắt) → API trả 409 `NO_COMPLIANT_SEARCH_SOURCE`, UI hiển thị thông báo VI/EN và liên
   kết tới trang nguồn tìm kiếm. Không job nào được tạo, không lời gọi AI.

## 3. Bật nguồn và chạy lượt với nguồn thật (chỉ sau khi chủ sở hữu xác minh – hiện BLOCKED)

1. **Nguồn**: chủ sở hữu xác minh theo [source-verification.md](./source-verification.md) §2, rồi `PUT /api/v1/sources/{id}` với
   `compliance_status = ALLOWED`, `verified_at`, `verification_note`, `allowed_access_methods`, `permitted_use_scope`, `enabled = true`.
   Thiếu mục → 422 `SOURCE_VERIFICATION_INCOMPLETE`. Agent/kiểm thử tự động **không** thực hiện bước này.
2. Khởi động lại `searxng` khi phản hồi có `requires_service_restart = true` (cấu hình `keep_only` được sinh lại từ policy).
3. Kiểm tra lượt theo lịch chỉ dùng nguồn `ALLOWED`: tạo lịch E0 `job_type = discovery.run` → `sources` của lượt chỉ có `ALLOWED`.
   Nguồn `UNVERIFIED` (nếu chủ sở hữu tự bật, có cảnh báo) chỉ xuất hiện trong lượt thủ công có `include_unverified_sources = true`;
   bằng chứng có `source_compliance = UNVERIFIED`.
4. Tạo lượt: `POST /api/v1/discovery/runs {"market":"US","max_candidates":5,"page_limit":40,"time_limit_minutes":15}`.
5. Quan sát màn hình 1: trạng thái job, trang đã thu thập/bỏ qua theo lý do, chi phí REAL/MOCK (REAL = $0 khi gọi có phí tắt).
6. Kỳ vọng: nguồn/bằng chứng `REAL`, trích đoạn đã che PII; phân tích AI là `MOCK` (không có API key) → ngách gắn `MOCK`. Đây **không**
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
2. Restore bản backup tạo **trước** bước 1 vào database trống (api/worker dừng) → `restore.sh` chạy
   `apply_erasure_ledger --strict` → bằng chứng vẫn `ERASED`; khởi động api/worker → `GET /api/v1/niches/{id}` không có trích đoạn.
3. **Thất bại an toàn** (môi trường thử, không phải dữ liệu thật):

| Kịch bản | Kỳ vọng |
|---|---|
| Đổi tên file ledger rồi restore | `restore.sh` thoát ≠ 0, `erasure_ledger_state.status = BLOCKED`; khởi động stack → `migrate` lỗi, api/worker không chạy |
| Sửa một dòng ledger (hỏng hash chain) | Như trên, log nêu `seq` bị hỏng (không in nội dung) |
| Ledger cũ hơn DB (`applied_seq` > seq cuối) | Như trên |
| Ép API chạy khi `BLOCKED` | Endpoint dữ liệu E1 trả 503 `ERASURE_LEDGER_NOT_APPLIED`; `/api/v1/system/status` báo `erasure_ledger` lỗi; `/health` vẫn `ok` |
| Ghi ledger thành công, DB lỗi giữa chừng | Lần chạy `apply_erasure_ledger` kế tiếp hoàn tất xóa |

4. Kiểm tra log/checkpoint/audit/ledger không chứa trích đoạn đã xóa.

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
