# Research (Phase 0): E0 — Foundation & AI Infrastructure

**Ngày**: 2026-11-18 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Phiên bản và giấy phép dưới đây được **tra cứu trực tiếp trên PyPI/npm ngày 2026-11-18** (không dựa trí nhớ).
Phiên bản ghi trong bảng là phiên bản mới nhất tại thời điểm tra cứu; khi triển khai sẽ khóa (pin) bằng lockfile
(`uv.lock`, `package-lock.json`). Mỗi quyết định theo định dạng: Quyết định / Lý do / Phương án đã cân nhắc.

---

## R-01. Hàng đợi job và scheduler (Clarify Q4)

**Quyết định**: Dùng **Procrastinate 3.11** (MIT) làm lớp vận chuyển hàng đợi trên PostgreSQL, đặt sau một
interface nội bộ `JobQueue` để có thể thay bằng hàng đợi tự viết (`SELECT … FOR UPDATE SKIP LOCKED`) mà không đổi
nghiệp vụ. Bảng `agent_jobs` của NichePilot là **nguồn sự thật duy nhất** về trạng thái nghiệp vụ; Procrastinate chỉ
giữ "lượt thực thi" (execution ticket).

**Kết quả đánh giá Procrastinate** (kiểm tra mã nguồn gói 3.11.0 đã cài vào môi trường thử):

| Tiêu chí | Kết quả | Đáp ứng |
|---|---|---|
| Giấy phép | MIT | ✅ OSS thực sự |
| Bảo trì | Bản 3.11.0 phát hành 2026-11-11; Python ≥ 3.10 | ✅ |
| Hạ tầng | Chỉ cần PostgreSQL (4 bảng `procrastinate_*`), không Redis | ✅ Q4 |
| Chống trùng khi xếp hàng | `queueing_lock` (chỉ một job `todo` cùng khóa) | ✅ idempotency |
| Tuần tự hóa | `lock` (không chạy song song cùng khóa) | ✅ một job – một worker |
| Lịch | `periodic(cron=…)` + bảng `procrastinate_periodic_defers` chống defer trùng | ✅ (dùng cho "scheduler tick") |
| Worker chết | Heartbeat worker (mặc định 10 s) + `get_stalled_jobs` | ✅ phát hiện job bị bỏ dở |
| Hủy/abort | `cancel_job_by_id` + `job_context.should_abort()` | ✅ |
| Retry | `RetryStrategy` (max_attempts, backoff, retry_exceptions) | ✅ (retry lượt thực thi) |
| Timeout | Không có sẵn | ⚠️ tự áp dụng `asyncio.timeout` ở Job Runtime |
| Trạng thái tạm dừng / `PAUSED_BUDGET` | Không có | ⚠️ quản lý trong `agent_jobs` (thiết kế dưới) |
| Driver | psycopg 3 (LGPL-3.0, dùng dạng thư viện, không sửa đổi) | ✅ chấp nhận được; ghi nhận giấy phép |
| Lịch người dùng cấu hình (cron trong DB) | Periodic của Procrastinate khai báo trong mã | ⚠️ giải quyết bằng "scheduler tick" |

**Thiết kế tích hợp**:

- Mỗi lần job cần chạy (tạo mới, tiếp tục, retry) → defer một task Procrastinate `run_agent_job(job_id)` với
  `queueing_lock=f"agent_job:{job_id}"` và `lock=f"agent_job:{job_id}"`.
- Tạm dừng / `PAUSED_BUDGET` / hủy: Job Runtime kết thúc lượt thực thi sạch sẽ sau bước hiện tại và ghi trạng thái
  vào `agent_jobs`; tiếp tục = defer lượt mới, Runtime đọc checkpoint.
- **Scheduler tick**: một periodic task Procrastinate chạy mỗi phút, đọc `job_schedules`, dùng `croniter` tính các
  thời điểm đến hạn, tạo `agent_jobs` với `idempotency_key = schedule:{schedule_id}:{scheduled_for_iso}`; unique
  constraint trên `idempotency_key` đảm bảo **đúng một job mỗi thời điểm** kể cả nhiều worker/khởi động lại.
- Stalled: khi worker khởi động và định kỳ, job `RUNNING` có lượt thực thi stalled → chuyển `RETRY_SCHEDULED` và defer
  lại; Runtime tiếp tục từ checkpoint (SC-006).
- Schema Procrastinate được áp dụng **trong Alembic migration** (chạy SQL schema đi kèm gói ở phiên bản đã pin); nâng
  cấp Procrastinate = thêm revision Alembic áp dụng file migration SQL tương ứng của gói.

**Phương án đã cân nhắc**:

- *Tự viết SKIP LOCKED*: ít phụ thuộc, toàn quyền kiểm soát; nhưng phải tự viết heartbeat, phát hiện stalled, cron
  dedup, LISTEN/NOTIFY – rủi ro lỗi đồng thời cao hơn. Giữ làm **phương án dự phòng** qua interface `JobQueue`.
- *Celery/RQ/ARQ + Redis/Valkey*: loại theo Q4 (thêm service, RAM; Redis đổi giấy phép).
- *APScheduler 3.11*: chỉ là scheduler, không giải quyết hàng đợi phân tán/chống trùng giữa nhiều worker.

---

## R-02. Ngôn ngữ, framework và truy cập dữ liệu backend

**Quyết định**: Python **3.13**; FastAPI 0.163 (MIT); Pydantic 2.14 + pydantic-settings 2.16 (MIT); SQLAlchemy 2.1
async (MIT) với driver **psycopg 3.3** (`postgresql+psycopg`); Alembic 1.20 (MIT); Uvicorn 0.54 (BSD-3).
Quản lý gói bằng **uv** (lockfile `uv.lock`).

**Lý do**: đúng stack bắt buộc; dùng chung một driver psycopg 3 với Procrastinate (một connection stack, async native);
Python 3.13 được mọi gói trên hỗ trợ (FastAPI/SQLAlchemy yêu cầu ≥ 3.11).

**Phương án đã cân nhắc**: asyncpg (Apache-2.0, nhanh hơn) – loại để tránh hai driver song song; Python 3.14 – chờ hệ
sinh thái ổn định hơn, nâng cấp sau.

## R-03. Tích hợp Claude API

**Quyết định**: SDK chính thức `anthropic` **2.10** (Apache-2.0), client async, Messages API, **vòng lặp agent tự viết**.

Chi tiết thiết kế (đối chiếu tài liệu Claude API hiện hành):

| Vấn đề | Quyết định |
|---|---|
| Kết quả có cấu trúc | Structured outputs (`output_config.format` qua helper parse của SDK với model Pydantic), sau đó **luôn validate lại** bằng Pydantic phía NichePilot trước khi lưu (FR-013) |
| Tool calling | Tool định nghĩa từ Tool Registry, `strict: true`, `tool_choice: auto` (model 5.5 không cho ép tool `any`/`tool`); quyền kiểm tra phía NichePilot trước khi thực thi (FR-022) |
| Effort/thinking | Thinking adaptive (không tắt được trên Opus/Sonnet 5.5); chi phí điều chỉnh bằng `effort` trong Model Task Profile |
| Refusal | `stop_reason == "refusal"` → bước `REFUSED`, lưu `stop_details.category` + `explanation`; **không** dùng server-side fallback, **không** đổi model/provider, không retry (FR-017, quyết định chủ sở hữu) |
| `max_tokens` cắt kết quả | Bước `TRUNCATED`, không lưu kết quả thiếu |
| Retry | SDK: `max_retries=0` để Job Runtime tự kiểm soát (ghi từng lần thử, kiểm tra ngân sách mỗi lần); Runtime retry 408/409/429/5xx/lỗi mạng với backoff + jitter, tôn trọng `retry-after`; không retry 400/401/403/404 |
| Timeout | Timeout theo Model Task Profile (mặc định 120 s/lời gọi); request dài dùng streaming + `get_final_message()` |
| Sampling | Không gửi `temperature`/`top_p`/`top_k`; không dùng assistant prefill |
| Prompt caching | `cache_control` cho system prompt + tool definitions ổn định; ghi `cache_read/cache_creation_input_tokens` |
| Ước tính chi phí trước gọi | `messages.count_tokens` (không tính phí) để biết token vào; chi phí tối đa = token vào × giá vào + `max_output_tokens` × giá ra; nếu count_tokens lỗi → ước tính bảo thủ (số ký tự ÷ 3) |
| Kiểm tra kết nối (FR-056) | `models.list()` – không phát sinh chi phí token |
| Xác thực (FR-019b) | Khởi tạo client với `api_key` **truyền tường minh** từ cấu hình NichePilot; SDK mặc định còn dò `ANTHROPIC_AUTH_TOKEN`, hồ sơ OAuth (`ant auth login`) và hồ sơ trên đĩa → adapter từ chối chạy nếu không có API key cấu hình, không bao giờ dựa vào cơ chế dò tìm đó; container không mount thư mục cấu hình người dùng; biến `ANTHROPIC_AUTH_TOKEN`/`ANTHROPIC_PROFILE` bị bỏ qua và cảnh báo khi phát hiện |
| Không dùng | Managed Agents (cần self-host + OpenAI dự phòng + ngân sách trước từng lời gọi); Tool Runner (cần chèn kiểm tra ngân sách/quyền/checkpoint mỗi bước) |

**Rủi ro**: SDK đã lên major 2.x; khi triển khai phải đối chiếu tên hàm/tham số với tài liệu SDK 2.x chính thức (không
đoán API). Test hợp đồng adapter dùng test double + một smoke test thủ công với key thật.

## R-04. Chọn model theo tác vụ (yêu cầu bổ sung 2, 3)

**Quyết định**: Bảng `model_task_profiles` ánh xạ `task_type` → provider, model, effort, giới hạn token, timeout,
retry schema. Agent chỉ khai báo `task_type`; **không có tên model trong business logic**. Bộ mặc định (seed migration,
chủ sở hữu sửa được qua API) ưu tiên chi phí:

| task_type | Mục đích | Model mặc định | Effort | max_output_tokens |
|---|---|---|---|---|
| `system.diagnostic` | Job chẩn đoán E0 | `claude-haiku-5-5` | low | 1 024 |
| `extract.simple` | Trích xuất/phân loại đơn giản (dùng từ E1) | `claude-haiku-5-5` | low | 4 096 |
| `analyze.standard` | Phân tích/tổng hợp thông thường (E1–E3) | `claude-sonnet-5-5` | medium | 16 000 |
| `reason.complex` | Lập kế hoạch/đánh giá phức tạp (E1–E3) | `claude-opus-5-5` | medium | 32 000 |

**Xác minh bắt buộc (điều kiện phê duyệt)**: bảng `ai_models` (data-model §5a) lưu model ID + khả năng + nguồn xác minh;
seed với `verified = false`. Xác minh model ID/khả năng bằng Models API của provider (`models.retrieve`/`models.list` –
không tính phí, trả `max_input_tokens`, `max_tokens`, `capabilities`) hoặc chủ sở hữu xác nhận kèm nguồn. Giá **không** có
API chính thức → chủ sở hữu nhập từ trang giá chính thức, ghi `source_note`. Gateway chặn lời gọi có phí khi model hoặc giá
chưa xác minh. Không dùng alias tự nâng cấp; đổi model chỉ bằng cách sửa profile (có audit).

Giá tham khảo (giá công bố của Anthropic, bản tài liệu cache 2026-11-03, USD/1M token vào – ra): Haiku 5.5 $0.10 –
$0.50 (prompt ≤ 100K; $0.50 – $2.50 khi vượt), Sonnet 5.5 $2 – $10, Opus 5.5 $4 – $20; cache read Sonnet 5.5 $0.10,
Opus 5.5 $0.20. **Bảng giá seed phải được xác minh lại với trang giá chính thức tại thời điểm triển khai**; giá cache
write và cache read của Haiku 5.5 chưa xác minh → nhập khi triển khai, nếu chưa xác minh được thì model đó bị chặn job
tốn phí theo FR (bảng giá thiếu → không chạy). Bảng giá hỗ trợ **giá theo ngưỡng độ dài prompt** (Haiku 5.5).

Ước tính chi phí một job chẩn đoán (≈ 2 000 token vào, 500 token ra, Haiku 5.5): ≈ $0.0005.

**Phương án đã cân nhắc**: một model cho mọi tác vụ (đơn giản nhưng tốn kém, trái yêu cầu bổ sung 3); định tuyến tự động
theo độ khó (phức tạp, khó kiểm chứng – để GĐ4).

## R-05. Provider dự phòng OpenAI

**Quyết định**: SDK `openai` 3.54 (Apache-2.0) sau cùng interface `LLMProvider`. Dự phòng **tắt mặc định**; bật bằng
cấu hình `fallback_provider`/`fallback_model` trong Model Task Profile, **chỉ** kích hoạt với lỗi kỹ thuật thuộc danh
sách cấu hình (mặc định: `PROVIDER_UNAVAILABLE` sau khi hết retry, `NETWORK_ERROR` không áp dụng vì thường lỗi chung).
Không kích hoạt cho `REFUSED`, `AUTH_ERROR`, `BAD_REQUEST`, `SCHEMA_INVALID`, `BUDGET`. Lời gọi dự phòng vẫn qua kiểm
tra ngân sách và được ghi `is_fallback = true`.

## R-06. Ngân sách và an toàn đồng thời (Clarify Q1)

**Quyết định**: Mô hình **đặt chỗ – quyết toán** (reservation/settlement), bổ sung trạng thái `UNCERTAIN` theo điều kiện
phê duyệt (chi tiết vòng đời, công thức và tính nguyên tử: data-model §11; bảng phân loại: internal-interfaces §1):

1. Trong một transaction: `pg_advisory_xact_lock(<budget_lock_key>)` → tính chi tiêu ngày/tháng/job = tổng chi phí
   thực (`ai_usage_logs`) + tổng đặt chỗ `ACTIVE` → nếu `ước tính tối đa > phần còn lại` của bất kỳ ngân sách nào →
   trả `BudgetExceeded` (job → `PAUSED_BUDGET`, lưu ngân sách bị chạm và số liệu) → ngược lại tạo `budget_reservations`.
2. Ngay trước khi gửi: ghi `sent_at` (commit riêng) – mốc phân biệt "chắc chắn chưa gửi" và "có thể đã gửi".
3. Sau lời gọi: có usage → `SETTLED` theo chi phí thực (kể cả job đã bị hủy trong lúc chờ); chắc chắn không tính phí →
   `RELEASED`; không xác định → `UNCERTAIN`, giữ nguyên phần giữ chỗ trong chi tiêu, chỉ chủ sở hữu đối soát được
   (`POST /budget/reservations/{id}/resolve`, có audit). Không có cơ chế tự giải phóng `UNCERTAIN`.
4. Reservation treo: tác vụ `sweep_stale` mỗi phút – `ACTIVE` quá `expires_at` → `RELEASED` nếu `sent_at` NULL, ngược lại
   `UNCERTAIN(WORKER_LOST)`.
5. **Chính sách tính phí khi lỗi**: việc provider có tính phí cho phản hồi lỗi (4xx/5xx/429) hay không phải được xác minh
   từ tài liệu chính thức trước khi coi là `NOT_BILLED`; cho tới khi xác minh, các phản hồi lỗi bị coi là `UNCERTAIN`
   (bảo thủ). Đây là việc cần làm trước khi bật `AI_PAID_CALLS_ENABLED` (tasks.md).
6. Ngày/tháng tính theo múi giờ cấu hình (`Asia/Ho_Chi_Minh`); reservation tính vào kỳ của thời điểm tạo.
7. Mặc định $3/ngày, $30/tháng, $2/job; chặn thay đổi làm job trần > ngân sách ngày; không tự tăng, không tự đổi model.

Độ vượt tối đa lý thuyết = 0 (vì đặt chỗ theo chi phí tối đa và tuần tự hóa bằng advisory lock); thực tế chỉ có thể lệch
nếu bảng giá sai hoặc ước tính token vào thấp hơn thực tế (phát hiện qua cảnh báo `BUDGET_RESERVATION_OVERRUN`).
Kiểm thử: integration test với 2 tiến trình × 10 coroutine tranh chấp trên PostgreSQL thật (SC-004).

**Phương án đã cân nhắc**: kiểm tra sau khi gọi (vi phạm Constitution VI); khóa hàng `SELECT … FOR UPDATE` trên bảng
tổng hợp (cần bảng counter riêng, dễ lệch); advisory lock được chọn vì đơn giản và đúng cho số worker nhỏ.

## R-07. Xác thực và phiên (FR-052, FR-053)

**Quyết định**: Single-owner, username + password; băm **Argon2id** (`argon2-cffi` 25.1, MIT); phiên lưu **phía server**
(bảng `auth_sessions`, cookie chứa token ngẫu nhiên 256-bit, DB chỉ lưu SHA-256 của token) – cookie `HttpOnly`,
`SameSite=Lax`, `Secure` khi HTTPS; hết hạn sau 12 giờ không hoạt động; **CSRF** dạng double-submit (cookie
`np_csrf` + header `X-CSRF-Token`) cho mọi request thay đổi dữ liệu; khóa 15 phút sau 5 lần sai.

**Lý do**: thu hồi phiên được ngay (logout, đổi mật khẩu), không có token dài hạn trong localStorage (an toàn XSS hơn
JWT). **Phương án đã cân nhắc**: JWT (khó thu hồi), reverse-proxy auth (thêm thành phần), OAuth (thừa cho một người dùng).

## R-08. Secrets (Clarify Q2)

**Quyết định**: `pydantic-settings` đọc từ biến môi trường, file `.env` và Docker secrets (`/run/secrets/*`, ưu tiên
secrets file khi có). Kiểu `SecretStr` cho mọi secret. Lớp redaction của structlog che giá trị trùng với secret đã nạp và
các mẫu khóa phổ biến (`sk-ant-…`, `sk-…`, `Bearer …`). API chỉ trả `configured: true/false` + `hint: "…abcd"` (4 ký tự
cuối). Bảng `settings` có danh sách khóa cấm (`*key*`, `*secret*`, `*token*`, `*password*`) – từ chối lưu. CI chạy
`detect-secrets` (Apache-2.0) chặn commit secret; `.gitignore` đã loại `.env`.

## R-09. Structured logging & audit

**Quyết định**: `structlog` 26.1 (MIT/Apache-2.0) xuất JSON ra stdout (Docker thu thập); context vars `request_id`,
`job_id`, `step_id`, `user_id`; processor redaction (R-08). Audit log là bảng append-only, chặn `UPDATE/DELETE` bằng
trigger PostgreSQL; ghi trong cùng transaction với thay đổi được audit. Giữ log ứng dụng 90 ngày (Docker log rotation
cấu hình kích thước) – không tự xóa audit log trong MVP.

## R-10. Frontend (khung E0, Clarify Q3)

**Quyết định**: React 19.3, Vite 8.3, Tailwind CSS 4.3, shadcn (CLI 4.23, sinh mã component vào repo), i18next 27 +
react-i18next 18 + i18next-browser-languagedetector 8, TanStack Query 5, React Router 8, Zod 4 (validate form) – tất cả MIT;
TypeScript 7.0 (Apache-2.0). Vitest 5 (unit), Playwright 1.65 (E2E). Ngôn ngữ: `vi` mặc định, lưu `localStorage` và đồng
bộ `users.ui_locale` khi đăng nhập. Script CI so sánh khóa `vi.json`/`en.json` (SC-010).

**Rủi ro**: TypeScript 7 (bản native) còn mới; nếu plugin ESLint/Vite chưa tương thích khi triển khai thì pin TypeScript
6.x – không ảnh hưởng thiết kế.

## R-11. Docker Compose & Windows (Clarify Q5)

**Quyết định**:

- `deploy/docker-compose.yml` (production-like): `postgres` (image `postgres:17-alpine`, đã kiểm tra tồn tại trên
  registry), `api`, `worker` (cùng image backend, multi-stage, user không phải root), `web` (Caddy 2 phục vụ SPA đã build
  + reverse proxy `/api`). Giới hạn `mem_limit`/`cpus`; healthcheck; `migrate` chạy như one-shot service trước `api`/`worker`.
- `deploy/docker-compose.dev.yml` (override): mount mã nguồn, `uvicorn --reload`, worker tự khởi động lại khi đổi mã
  (`watchfiles`), Vite dev server có HMR.
- Windows: Docker Desktop backend WSL2, mã nguồn clone **trong filesystem WSL** (`~/code/nichepilot`), giới hạn RAM WSL
  bằng `.wslconfig` (đề xuất 8 GB), hướng dẫn xử lý lỗi (line ending CRLF – `.gitattributes`, cổng bị chiếm, WSL hết
  RAM, đồng hồ lệch sau sleep).
- Backup: service `backup` (profile `ops`) chạy `pg_dump -Fc` theo lịch, giữ 7 bản; `make restore FILE=…`.

**Phương án đã cân nhắc**: PostgreSQL 18 (mới hơn) – chọn 17 cho tương thích công cụ/thư viện; nâng cấp sau qua
`pg_upgrade`. Nginx thay Caddy – tương đương; Caddy cấu hình ngắn, tự HTTPS khi cần.

## R-12. Chiến lược kiểm thử

**Quyết định**:

| Lớp | Công cụ | Ghi chú |
|---|---|---|
| Unit | pytest 9.2, pytest-asyncio 1.5 | Ngân sách, state machine, redaction, phân loại lỗi, Tool permission, cron |
| Integration | testcontainers 4.15 (PostgreSQL 17 thật) | Migration up/down, repository, hàng đợi, scheduler tick, stalled, đồng thời ngân sách |
| API/contract | httpx 0.28 + so khớp `contracts/openapi.yaml` | Auth, CSRF, mã lỗi |
| LLM | `MockAIProvider` (kịch bản dựng sẵn) + `FakeLLMProvider` – **test double đặt trong `backend/tests/fakes/`** | Mô phỏng timeout, 429, 401, sai schema, refusal, truncated, usage xác định; test xác nhận 0 lời gọi mạng tới provider thật |
| HTTP adapter | respx 0.23 | Kiểm tra adapter Claude/OpenAI ở mức HTTP không gọi mạng thật |
| Live (thủ công) | `pytest -m live` + biến `NICHEPILOT_LIVE_MAX_USD` (mặc định $0.05) | Không chạy trong CI mặc định |
| E2E | Playwright | Khởi tạo tài khoản, đăng nhập, khóa tài khoản, chuyển VI/EN, trang trạng thái |
| Chất lượng | ruff 0.17, mypy 2.4 (strict cho `core/`, `ai/`, `jobs/`), ESLint, `tsc` | Cổng trước merge |
| Bảo mật | detect-secrets, test đảm bảo không secret trong log/response | SC-008 |

CI: GitHub Actions (Linux) – chạy lint, type check, unit, integration (Docker có sẵn trên runner), E2E với stack Compose.

## R-13. Prompt injection & dữ liệu nhạy cảm gửi LLM

**Quyết định**: Mọi kết quả tool đưa vào ngữ cảnh được bọc trong khối dữ liệu có nhãn `untrusted_content` và system prompt
nêu rõ không thực thi chỉ thị trong đó; quyền tool được quyết định **ở mã nguồn** (không thể thay đổi bởi nội dung model);
hàm `sanitize_for_llm()` loại secret đã nạp và mẫu khóa trước khi gửi; MVP không có tool tác động bên ngoài (FR-023).

---

## R-14. Phát triển không phí API: MockAIProvider và công tắc gọi có phí

**Bối cảnh**: chủ sở hữu dùng Claude Pro qua Claude Code để phát triển, chưa có API key; Claude Pro không phải API
backend (không có API key, điều khoản dùng cho cá nhân tương tác). Constitution v1.1.0 cho phép mock ngoài test với rào chắn.

**Quyết định**:

- **Chọn provider**: `Model Task Profile.provider ∈ {anthropic, openai, mock}`; biến môi trường
  `AI_PROVIDER_OVERRIDE` (ví dụ `mock`) ép mọi tác vụ dùng một provider – tiện cho dev mà không sửa từng profile.
  `.env.example` cho dev đặt `AI_PROVIDER_OVERRIDE=mock`. Khi có key: xóa override (hoặc đặt `anthropic`), điền
  `ANTHROPIC_API_KEY`, bật `AI_PAID_CALLS_ENABLED=true` → không sửa mã.
- **Kịch bản mock** (`mock_scenario`): `success`, `timeout` (trước khi gửi), `timeout_after_send`, `rate_limit`,
  `schema_invalid`, `provider_error`, `auth_error`, `refusal`, `truncated`, `budget_heavy` (usage giả lập lớn để chạm ngân sách), cùng dạng
  `fail_n_then_success:<kịch bản>:<n>` để kiểm thử retry/checkpoint. Chọn theo tham số job (chỉ hợp lệ khi provider là
  mock), mặc định theo `MOCK_AI_DEFAULT_SCENARIO=success`.
- **Kết quả mock**: sinh từ JSON Schema của output (giá trị tối thiểu hợp lệ, chuỗi có tiền tố `[MOCK]`), xác định
  (deterministic theo seed = job_id + seq) để test lặp lại được. Không bao giờ chứa số liệu thị trường giả dạng thật.
- **Đánh dấu**: cột `data_origin` (`REAL`/`MOCK`) trên `agent_jobs`, `job_steps`, `ai_usage_logs`,
  `tool_executions`, `research_sources`, `research_evidence`; API trả `data_origin`; frontend hiển thị nhãn
  "Dữ liệu giả lập / Simulated". Báo cáo/xếp hạng (E1+) lọc `data_origin = REAL` theo mặc định.
- **Ngân sách**: bảng giá giả lập riêng (`provider = mock`, giá cấu hình được, mặc định bằng giá Haiku 5.5 để số liệu
  hợp lý); chi tiêu được tính theo `data_origin` – chi tiêu MOCK chỉ so với hạn mức khi kiểm tra lời gọi MOCK, chi tiêu
  REAL chỉ so với lời gọi REAL; cùng mã kiểm tra ngân sách → kiểm thử đầy đủ cơ chế mà không lẫn chi phí thật.
- **Rào chắn production (hai tầng)**: tầng cấu hình – khi `APP_ENV=production`, khởi động thất bại nếu
  `AI_PROVIDER_OVERRIDE=mock` hoặc có profile `provider=mock`; tầng runtime – AI Gateway, API cập nhật profile và tham số
  `mock_scenario` đều từ chối mock khi production (không có đường chọn mock động).
- **Không tính là kiểm thử thật**: bộ test có marker `mock`; báo cáo kiểm thử tách mục "tích hợp provider thật" chỉ đánh
  dấu đạt khi test `live` chạy thành công.
- **Công tắc có phí**: `AI_PAID_CALLS_ENABLED` (mặc định `false`) – kiểm tra trong AI Gateway ngay trước khi gửi,
  sau kiểm tra ngân sách; `models.list` (kiểm tra kết nối) không bị chặn vì không tính phí. Test live cần đồng thời
  `-m live`, key thật, `AI_PAID_CALLS_ENABLED=true` và `NICHEPILOT_LIVE_MAX_USD`.
- **Phân biệt với test double**: `MockAIProvider` (mã sản phẩm, `src/nichepilot/ai/providers/mock.py`) dùng cho chạy
  dev; `FakeLLMProvider` trong `tests/fakes/` vẫn dùng cho unit test cần điều khiển chi tiết từng phản hồi.

**Phương án đã cân nhắc**: dùng Claude Code CLI/phiên Claude Pro làm backend (loại – vi phạm yêu cầu, không phù hợp tự
động hóa, rủi ro điều khoản); chỉ dùng test double trong test (loại – không khởi động/demo được hệ thống khi chưa có key);
proxy ghi/phát lại phản hồi thật (loại – chưa có phản hồi thật để ghi).

## Tóm tắt: không còn mục NEEDS CLARIFICATION

Mọi ẩn số trong Technical Context đã được giải quyết. Các điểm cần chủ sở hữu xác nhận thêm (không chặn plan) được liệt kê
trong `plan.md` mục "Điểm cần xác nhận".
