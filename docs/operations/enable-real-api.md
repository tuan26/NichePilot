# Bật API thật (Anthropic/OpenAI) – chỉ khi chủ sở hữu cho phép

> Trạng thái hiện tại của E0: **chưa có lời gọi API thật nào**. Mọi test tự động dùng MockAIProvider hoặc transport
> HTTP giả lập. Tích hợp Claude/OpenAI API thật: **CHƯA KIỂM CHỨNG** (SC-003).
>
> Không dùng tài khoản Claude Pro, OAuth token, cookie hay Claude Code CLI làm backend – chỉ API key chính thức.

## 1. Điều kiện trước khi gọi có phí (FR-019c)

Gateway chặn mọi lời gọi có phí cho tới khi **đủ cả bốn**:

1. `AI_PAID_CALLS_ENABLED=true` (mặc định `false`).
2. API key hợp lệ trong `deploy/env/.env` hoặc Docker secret.
3. Model của tác vụ **đã xác minh** (`ai_models.verified = true`, có nguồn) và có khả năng tác vụ cần
   (structured output / tool calling / effort). Nếu chưa → `MODEL_NOT_VERIFIED`.
4. Bảng giá của model **đã xác minh** (`model_pricing.verified = true`). Nếu chưa → `PRICING_NOT_VERIFIED`.

Ngân sách mặc định ($3/ngày, $30/tháng, $2/job) vẫn áp dụng; hệ thống không tự tăng ngân sách, không tự đổi/nâng model.

## 2. Các bước

1. Điền `ANTHROPIC_API_KEY` trong `deploy/env/.env`, để **trống** `AI_PROVIDER_OVERRIDE`, khởi động lại `api` và `worker`.
2. Kiểm tra kết nối (Models API – không tính phí):
   `POST /api/v1/providers/anthropic/test-connection` → `OK`.
3. Đối chiếu catalog với Models API (không tính phí, không xác minh giá):
   `POST /api/v1/providers/anthropic/verify-models`. Models API không công bố khả năng tool calling → nếu tác vụ cần tool,
   xác nhận thủ công: `PUT /api/v1/models/{id}/verification` với `verification_source` là trang tài liệu chính thức.
4. Đối chiếu giá ở mục 3 với trang giá chính thức tại thời điểm bật, rồi thêm phiên bản giá đã xác minh:
   `POST /api/v1/model-pricing` (`verified: true`, `source_note` BẮT BUỘC có URL nguồn chính thức và ngày xác minh
   YYYY-MM-DD – thiếu một trong hai → 422; DB cũng chặn). Điền đủ giá cache read và cache write 5 phút. Bản giá cũ giữ nguyên.
   Chính sách tính chi phí và công thức giữ chỗ: `specs/001-foundation-ai-infrastructure/checklists/verification.md`.
5. Chỉ khi chủ sở hữu đồng ý chi phí: đặt `AI_PAID_CALLS_ENABLED=true`, khởi động lại `worker`, chạy job
   `system.diagnostic` (ước tính < $0.01 với Haiku 5.5) và đối chiếu `cost_usd` với usage × bảng giá (SC-003, lệch ≤ 1%).
6. Ghi kết quả vào mục "Tích hợp provider thật" của báo cáo; đặt lại `AI_PAID_CALLS_ENABLED=false` nếu chưa dùng tiếp.

Bộ test live (`make test-live`) chỉ chạy thủ công khi có key + `AI_PAID_CALLS_ENABLED=true` + `NICHEPILOT_LIVE_MAX_USD`.

## 3. Nghiên cứu model và giá (T128 – chưa gọi API, chờ chủ sở hữu xác nhận)

Nguồn: trang chính thức `https://platform.claude.com/docs/en/about-claude/pricing` (đọc ngày 2026-11-18). Giá USD/MTok,
API first-party. Đây là **tham khảo để chủ sở hữu xác nhận** – trong database các bản giá seed vẫn `verified = false`.

| Model ID | Input | Output | Cache write 5 phút | Cache write 1 giờ | Cache read | Ghi chú |
|---|---|---|---|---|---|---|
| `claude-haiku-5-5` (prompt ≤ 100.000 token) | 0.10 | 0.50 | 0.125 | 0.20 | 0.01 | Giá theo độ dài prompt |
| `claude-haiku-5-5` (prompt > 100.000 token) | 0.50 | 2.50 | 0.625 | 1.00 | 0.05 | Ngưỡng tính cả cache read/write |
| `claude-sonnet-5-5` | 2.00 | 10.00 | 2.50 | 4.00 | 0.10 | Toàn bộ 1M context cùng giá |
| `claude-opus-5-5` | 4.00 | 20.00 | 5.00 | 8.00 | 0.20 | Toàn bộ 1M context cùng giá |

Phụ phí khác theo trang giá: `inference_geo` chỉ-US nhân 1.1 (E0 không dùng); fast mode (Opus 5.5) $8/$40 (E0 không dùng).

Đối chiếu với seed `0005_seed_ai`: input/output/ngưỡng 100K của Haiku và cache read của Sonnet/Opus **khớp**. Điểm cần
chủ sở hữu xử lý khi thêm bản giá đã xác minh:

- Seed để trống `cache_write_per_mtok` (và cache read của Haiku). Chính sách tính chi phí (C3): cache write chưa có giá
  → **2× giá input** của bậc áp dụng (= giá ghi cache 1 giờ, mức cao nhất; không bao giờ dùng giá input thường); cache
  read chưa có giá → giá input (luôn cao hơn giá cache read chính thức). Khi thêm bản giá đã xác minh hãy điền đủ cache
  write (5 phút) và cache read để chi phí ghi nhận sát thực tế.
- Độ dài prompt dùng để chọn bậc giá = input + cache read + cache write (theo trang giá). Trên ngưỡng (Haiku 5.5 > 100K),
  schema chưa có giá cache bậc cao nên cache read tính bằng giá input bậc cao và cache write bằng 2× giá đó – cao hơn giá
  chính thức (bảo thủ).
- Giữ chỗ ngân sách tính mỗi token prompt theo mức cao nhất trong input / cache read / cache write → không thấp hơn chi phí
  thực. Lời gọi có phí bị chặn (`COST_ESTIMATE_UNAVAILABLE`) nếu không đếm được token đầu vào hoặc bảng giá có giá 0.

Khả năng (theo tài liệu chính thức, cần xác nhận lại bằng `verify-models`):

| Model | Structured outputs | Tool use | Effort | Ghi chú API ảnh hưởng adapter |
|---|---|---|---|---|
| Haiku 5.5 | Có | Có | `low`…`max`, mặc định `medium` | Thinking thích ứng bật mặc định; không prefill |
| Sonnet 5.5 | Có | Có (không hỗ trợ `tool_choice` `any`/`tool` – adapter dùng `auto`) | `low`…`max` | `thinking: disabled` trả 400 |
| Opus 5.5 | Có | Có (không hỗ trợ `tool_choice` ép buộc – adapter dùng `auto`) | `low`…`max`, mặc định `medium` | Thinking không tắt được |

OpenAI (provider dự phòng): catalog seed **chưa có model OpenAI nào**; model ID, giá và khả năng = **UNKNOWN**. Chủ sở hữu
phải thêm model (`POST /api/v1/models`) và giá đã xác minh trước khi cấu hình fallback.

## 4. Chính sách tính phí khi lỗi (FR-047) – đề xuất cho `billing.error_responses_not_billed_verified`

Kết quả tra cứu tài liệu chính thức (2026-11-18):

- Trang lỗi `https://platform.claude.com/docs/en/api/errors` mô tả mã lỗi 400/401/402/403/404/409/413/429/500/504/529
  nhưng **không có câu nào** khẳng định phản hồi lỗi không bị tính phí → chính sách = **UNKNOWN**.
- Trang refusal `https://platform.claude.com/docs/en/build-with-claude/refusals-and-fallback` (mục "How refusals are
  billed"): refusal (HTTP 200, `stop_reason: "refusal"`) xảy ra trước khi có output **bị tính phí** khi `category` là
  `bio`, `frontier_llm` hoặc `reasoning_extraction`; refusal giữa chừng stream được tính phí bình thường. Danh sách
  category có thể thay đổi. Gateway hiện ghi mọi refusal là `BILLED` với chi phí = usage trả về × bảng giá
  (bảo thủ: có thể ghi cao hơn thực tế với category không bị tính phí); không retry, không fallback, không đổi model.
- Server tool web search lỗi không bị tính phí (không dùng trong E0).
- OpenAI: chưa tra cứu được nguồn chính thức trong phiên này → **UNKNOWN**.

**Đề xuất**: giữ `billing.error_responses_not_billed_verified = {"anthropic": false, "openai": false}`. Hệ quả: lời gọi
đã gửi mà nhận phản hồi lỗi được ghi `UNCERTAIN` (không tự giải phóng); sau 3 reservation UNCERTAIN, job chuyển
`PAUSED_BUDGET` chờ đối soát. Cách này an toàn về chi phí nhưng cần chủ sở hữu đối chiếu trang usage của provider. Chỉ
đổi sang `true` khi có văn bản chính thức (hoặc xác nhận của bộ phận hỗ trợ) – đổi qua `PATCH /api/v1/settings` (có audit).

## 5. Kịch bản kiểm thử Claude API thật (chỉ khi chủ sở hữu cho phép)

Mục tiêu: kiểm chứng AC-02 và SC-003. Chi phí ước tính < $0.01 (job chẩn đoán với Haiku 5.5). Trước khi bắt đầu, ghi lại
quyết định cho phép (người, ngày, hạn mức chi phí).

| Bước | Thao tác | Tiêu chí đạt |
|---|---|---|
| L1 | Điền `ANTHROPIC_API_KEY` (key API chính thức), để trống `AI_PROVIDER_OVERRIDE`, giữ `AI_PAID_CALLS_ENABLED=false`, khởi động lại `api`/`worker` | `GET /api/v1/providers`: anthropic `configured = true`, chỉ hiện `key_hint` |
| L2 | `POST /api/v1/providers/anthropic/test-connection` | `OK` (Models API, không tính phí); có audit `provider.connection_tested` |
| L3 | `POST /api/v1/providers/anthropic/verify-models` | Model của profile `system.diagnostic` = `VERIFIED`; nếu cần tool calling, xác nhận thủ công bằng `PUT /api/v1/models/{id}/verification` kèm URL tài liệu |
| L4 | `POST /api/v1/model-pricing` cho model đó với `verified: true`, `source_note` = URL trang giá chính thức + ngày xác minh | 201; thiếu URL hoặc ngày → 422 |
| L5 | Tạo job khi `AI_PAID_CALLS_ENABLED=false` | Job `FAILED` với `PAID_CALLS_DISABLED`, không có usage `REAL` |
| L6 | Đặt `AI_PAID_CALLS_ENABLED=true`, khởi động lại `worker`, tạo job `system.diagnostic` | `SUCCEEDED`, `data_origin = REAL`, 3 bước; usage có token, `cost_usd`, `provider_request_id` |
| L7 | Đối chiếu `cost_usd` với trang usage của Anthropic (theo `provider_request_id`/thời điểm) | Lệch ≤ 1% (SC-003); ghi số liệu |
| L8 | (Tùy chọn, có trần) `NICHEPILOT_LIVE_MAX_USD=0.05 make test-live` | 2 test live PASS; kết quả trong `live-results.jsonl` |
| L9 | Đặt lại `AI_PAID_CALLS_ENABLED=false`, khởi động lại `worker` | Job mới bị chặn `PAID_CALLS_DISABLED` |

Quay lui khi có sự cố: đặt `AI_PAID_CALLS_ENABLED=false` (hoặc xóa `ANTHROPIC_API_KEY`) và khởi động lại `worker`; reservation
`UNCERTAIN` (nếu có) đối soát với trang usage rồi `POST /api/v1/budget/reservations/{id}/resolve`. Thu hồi key trên Anthropic
Console nếu nghi lộ.

Ghi kết quả L1–L9 (thời điểm, model, request ID, chi phí, độ lệch) vào mục "Tích hợp provider thật" của
`specs/001-foundation-ai-infrastructure/checklists/verification.md`. Trước khi có kết quả này, AC-02 và SC-003 giữ trạng thái
`NOT_TESTED`.
