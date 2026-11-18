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
   `POST /api/v1/model-pricing` (`verified: true`, `source_note` ghi URL + ngày đối chiếu). Bản giá cũ được giữ nguyên.
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

- Seed để trống `cache_write_per_mtok` và cache read của Haiku; khi để trống, bộ tính chi phí dùng giá input thường – **thấp
  hơn** giá cache write thật (1.25×). E0 chưa bật prompt caching nên chưa ảnh hưởng; khi thêm bản giá đã xác minh hãy
  điền đủ cache write (5 phút) và cache read.
- Với Haiku prompt > 100K, giá cache read/write cũng tăng; bộ tính chi phí hiện chỉ đổi giá input/output theo ngưỡng.
  E0 không gửi prompt > 100K (job chẩn đoán vài trăm token). Ghi nhận để xử lý trước khi E1+ dùng prompt dài.

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
