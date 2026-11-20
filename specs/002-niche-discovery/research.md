# Research: E1 – Autonomous Niche Discovery

**Ngày**: 2026-11-19, cập nhật 2026-11-20 (theo phê duyệt có điều kiện của chủ sở hữu) | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Quy ước: chỉ ghi là "đã xác minh" những gì đã đọc được từ trang chính thức trong phiên này, kèm URL và ngày. Điều gì chưa đọc
được ghi rõ `UNVERIFIED` / "chưa xác minh" – không điền từ trí nhớ (Constitution I).

**Giới hạn của phiên nghiên cứu**: môi trường agent chỉ truy cập được `github.com` và `www.microsoft.com`; các host còn lại
(policies.google.com, duckduckgo.com, search.brave.com, www.mojeek.com, mwmbl.org, about.marginalia-search.com,
meta.wikimedia.org, www.mediawiki.org, api.stackexchange.com, hn.algolia.com, docs.searxng.org, docs.crawl4ai.com,
www.rfc-editor.org) bị chính sách mạng chặn (lỗi DNS); www.startpage.com bị công cụ đọc web từ chối. Hai yêu cầu mở mạng cho
môi trường đều bị dịch vụ môi trường từ chối. Chủ sở hữu (2026-11-20) **không** đồng ý thay đổi mạng của môi trường dùng chung:
nguồn chưa xác minh giữ `UNVERIFIED`, việc xác minh làm sau trên môi trường có quyền truy cập phù hợp, và **không coi là lỗi
implementation**. Danh sách nguồn cần xác minh: [source-verification.md](./source-verification.md).

Truy cập được trong phiên 2026-11-20: PyPI JSON API (`pypi.org`), GitHub releases, Docker Hub (kéo image để đo tài nguyên) – dùng cho
R-12 (xác minh dependency). Mọi phép đo chạy trong môi trường tách biệt (scratchpad / container mạng nội bộ), không gửi truy vấn tìm
kiếm ra ngoài.

---

## R-01 – Hồ sơ tuân thủ nguồn (FR-006c…FR-006g)

**Decision** (cập nhật 2026-11-20): mỗi nguồn có một bản ghi `source_policies` (data-model §2): URL điều khoản, ngày xác minh, người
xác minh + căn cứ, **phương thức truy cập được phép**, **phạm vi sử dụng được phép**, giới hạn đã biết, trạng thái
`ALLOWED`/`UNVERIFIED`/`PROHIBITED`. Seed: **tất cả `UNVERIFIED`, tắt**. Quy tắc:
- Chỉ `ALLOWED` dùng được trong lượt **tự động** (lịch, đánh giá lại theo lịch). Hệ thống không bao giờ tự bật nguồn hay tự nâng
  trạng thái; không có đường mã nào đặt `ALLOWED` ngoài API cập nhật của chủ sở hữu (kèm căn cứ bắt buộc, audit).
- `UNVERIFIED`: chủ sở hữu có thể bật (cảnh báo + audit, Q4), nhưng chỉ dùng trong lượt chủ sở hữu khởi chạy thủ công với
  `include_unverified_sources = true`; bằng chứng mang `source_compliance = UNVERIFIED`. Agent **không** bật nguồn `UNVERIFIED` để
  chạy thử dữ liệu thật.
- `PROHIBITED`: CHECK ở DB + kiểm tra ở service + adapter từ chối.
- Có API miễn phí ≠ được phép cho mọi mục đích: `permitted_use_scope` phải ghi rõ phạm vi (ví dụ: nghiên cứu nội bộ, lưu trích đoạn,
  hiển thị kèm ghi nguồn); thiếu → không thể đặt `ALLOWED`.
- Không có nguồn hợp lệ → `NO_COMPLIANT_SEARCH_SOURCE` (FR-006e).

Kết quả xác minh 2026-11-19 (không đổi – chưa có căn cứ mới):

| Nguồn | Trạng thái | Ghi chú |
|---|---|---|
| Bing (Microsoft) | `UNVERIFIED` – tắt | Đọc được một phần Microsoft Services Agreement: §3.a.vi cấm "circumvent any restrictions…", ví dụ "impermissible scraping"; không định nghĩa "impermissible", không nói về meta-search |
| Google, DuckDuckGo, Brave Search, Mojeek, Startpage, Mwmbl, Marginalia, Wikipedia/MediaWiki API, Stack Exchange API, Hacker News (Algolia) | `UNVERIFIED` – tắt | **BLOCKED**: không đọc được điều khoản do mạng (Startpage: công cụ đọc web từ chối) |

Chi tiết URL chính thức, nội dung cần kiểm tra, mẫu ghi kết quả: [source-verification.md](./source-verification.md).

**Hệ quả**: sau khi triển khai, lượt dùng nguồn thật báo `NO_COMPLIANT_SEARCH_SOURCE` cho tới khi chủ sở hữu xác minh ít nhất một nguồn.
Kiểm thử tự động dùng adapter giả lập (MOCK) nên không bị chặn. Đây là trạng thái cấu hình, không phải lỗi implementation.

**Alternatives considered**: dùng engine mặc định của SearXNG – loại (Q4; R-02 cho thấy template mặc định có 353 engine và một số
engine tự kết nối ra ngoài lúc khởi động); điền trạng thái từ hiểu biết trước đó của mô hình – vi phạm Constitution I.

## R-02 – SearXNG: triển khai và tích hợp

**Decision**: image chính thức `searxng/searxng`, **không sửa mã**, ghim tag theo ngày (ví dụ `2026.11.18-b867c56a5`), service
`searxng` trong Compose (X1 đã duyệt), `mem_limit 256m`, chỉ trong mạng nội bộ Compose (không publish cổng). `settings.yml` do
NichePilot cung cấp, sinh từ `source_policies`:
- `use_default_settings.engines.keep_only: [<engine của nguồn đang bật>]` – rỗng khi chưa nguồn nào được bật → SearXNG không truy vấn
  engine nào; `search.formats: [html, json]`; `server.limiter: false`, `public_instance: false`, `image_proxy: false`;
  `server.secret_key` từ biến môi trường `SEARXNG_SECRET` (sinh lúc cài, không commit).
- Khi chủ sở hữu bật/tắt nguồn → service ghi lại `settings.yml` (volume cấu hình) và yêu cầu khởi động lại `searxng` (thao tác vận
  hành có hướng dẫn) – không cần sửa code (FR-006g). Adapter vẫn truyền `engines=` chỉ gồm nguồn hợp lệ cho lượt (phòng thủ 2 lớp).

**Đã xác minh 2026-11-20** (kéo image `searxng/searxng:2026.11.18-b867c56a5`, chạy trong mạng Docker `--internal`):
- Nhãn OCI `org.opencontainers.image.licenses = AGPL-3.0-or-later`, nguồn `https://github.com/searxng/searxng` (khớp xác minh
  GitHub 2026-11-19).
- Kích thước image ≈ 402 MB (Docker Hub báo ≈ 96 MB nén); **RAM nghỉ ≈ 103 MiB**, CPU ≈ 0,4% – phù hợp 4 core / 15 GB.
- `searx/settings.yml` mặc định: `search.formats` chỉ `html` (phải bật `json`), `server.limiter: false`, `public_instance: false`,
  `image_proxy: false`, `secret_key` bị ghi đè bởi `SEARXNG_SECRET`; 353 mục engine; `settings_loader.py` hỗ trợ
  `use_default_settings.engines.keep_only`.
- Với cấu hình mặc định, khi khởi động engine `radio browser` cố khởi tạo (kết nối mạng) → xác nhận phải dùng `keep_only`.
- Trên host không có IPv6, server `granian` lỗi "Address family not supported" → cần `GRANIAN_HOST=0.0.0.0` (ghi vào Compose/tài
  liệu vận hành; cần kiểm tra lại trên Windows/WSL2).
- `/healthz` trả `OK`. Truy vấn JSON thật **không** được thử (không có nguồn được phép).

Nghĩa vụ AGPL: dùng như dịch vụ riêng, không sửa mã → không phát sinh nghĩa vụ công bố mã NichePilot; nếu sửa SearXNG phải công bố
phần sửa. Ghi vào Technology Evaluation.

SearXNG lỗi/timeout → `SEARCH_UNAVAILABLE`/`NO_RESULTS` cho ứng viên (FR-006a); mọi nguồn hợp lệ lỗi → `NO_COMPLIANT_SEARCH_SOURCE`.

**Alternatives**: API tìm kiếm trả phí – loại (Q1); scrape trực tiếp trang kết quả tìm kiếm – loại (ToS, CAPTCHA).

## R-03 – Thu thập nội dung trang (Constitution VII)

**Decision** (chủ sở hữu duyệt 2026-11-20): **mặc định** HTTP client của worker (httpx, đã có trong E0) + `trafilatura` – không trình
duyệt, không container mới. **Tùy chọn** cho trang cần JavaScript: `PlaywrightPageFetcher` dùng Playwright (Apache-2.0) + Chromium
trong container riêng thuộc Compose profile `browser-fetcher`, **tắt mặc định**; NichePilot kiểm tra robots.txt/tốc độ trước khi gọi.

**Crawl4AI: không dùng trong E1** (giữ là phương án được đánh giá). Lý do đã xác minh 2026-11-20 từ metadata PyPI `crawl4ai 0.9.5`:
phụ thuộc bắt buộc gồm `playwright-stealth` và `patchright` (công cụ che dấu trình duyệt tự động để tránh bị phát hiện bot) – mâu thuẫn
trực tiếp với FR-006f (không vượt cơ chế hạn chế truy cập) và NFR-11; thêm `unclecode-litellm==1.81.13` (bản fork ghim của LiteLLM),
`aiosqlite`, `pillow`, `numpy` – nặng và thừa. README còn mâu thuẫn về yêu cầu ghi công (xác minh 2026-11-19). Theo X8 ("không dùng
dependency có điều kiện giấy phép chưa rõ trong production"), Crawl4AI không đủ điều kiện. Playwright trực tiếp đáp ứng nhu cầu
"trang cần JavaScript" với giấy phép rõ ràng và không có thành phần lẩn tránh.

- `trafilatura 2.3.1` (2026-10-06), Apache-2.0, Python ≥ 3.10, wheel chạy được trên 3.13 – chi tiết R-12.
- Playwright `1.65.2` (2026-11-14), Apache-2.0; chỉ cài trong image `browser-fetcher`, **không** cài vào image worker mặc định. Tài
  nguyên Chromium chưa đo (chưa cần) → đo khi chủ sở hữu bật profile (task riêng, không chặn E1).

**Alternatives**: Crawl4AI (loại, lý do trên); Scrapy (thừa cho 300 trang/lượt).

## R-04 – robots.txt, tốc độ truy cập, CAPTCHA (FR-005, FR-030a, FR-031)

**Decision**:
- Đọc `robots.txt` một lần mỗi tên miền mỗi lượt (lưu cache 24 giờ trong `domain_access_state`), phân tích bằng `protego`
  (BSD-3-Clause, R-12). Lý do không dùng `urllib.robotparser`: theo mô tả chính thức của protego trên PyPI (đọc 2026-11-20), CPython
  chỉ bổ sung wildcard và quy tắc ưu tiên khớp dài nhất của RFC 9309 trong dòng 3.14 – E0 chạy Python 3.13. User-Agent riêng `NichePilotResearchBot/<version> (+liên hệ cấu hình
  được)`. robots.txt không lấy được: lỗi 4xx → coi như không có giới hạn; lỗi 5xx/mạng → **không thu thập** tên miền đó trong lượt
  (thận trọng). Quy định chính xác của RFC 9309 về 4xx/5xx **chưa xác minh** (www.rfc-editor.org bị chặn) – task đầu tiên đọc lại
  RFC và điều chỉnh nếu khác.
- Khoảng cách tối thiểu giữa hai yêu cầu cùng tên miền = max(mức trần lượt (mặc định 2 s), `Crawl-delay` của robots.txt,
  `Retry-After` gần nhất). 429/503 → tăng khoảng cách và thử lại tối đa 2 lần trong giới hạn thời gian còn lại; quá → bỏ tên miền
  cho lượt, lý do `RATE_LIMITED`.
- Phát hiện CAPTCHA/chặn bot (403 kèm dấu hiệu challenge, trang xác minh) → dừng tên miền đó, lý do `ACCESS_RESTRICTED`; không thử
  vượt. Không gửi cookie/đăng nhập; không theo paywall.
- Trạng thái tên miền lưu trong DB để giữ đúng khoảng cách sau khi worker khởi động lại.

## R-05 – Che PII (FR-012a…FR-012c, Q8, quyết định 2026-11-20)

**Decision**: interface `PiiEngine` (thay thế được – ví dụ Presidio sau này) với cài đặt E1 `RegexSpacyPiiEngine`, chạy **trong bộ nhớ
ngay sau khi trích nội dung**, trước mọi ghi DB/log/checkpoint và trước khi gửi AI:
1. Bỏ metadata tác giả từ trích xuất (`author` của trafilatura không được lưu).
2. Regex: email → `[EMAIL]`; `@handle`, `u/…`, `/user/…`, URL hồ sơ cá nhân → `[USER]`; "Posted by/by <Name>" → `[PERSON]`.
3. `phonenumbers` (Apache-2.0) với vùng mặc định = thị trường của lượt → `[PHONE]`.
4. Tiếng Anh: spaCy `en_core_web_sm` (chỉ thành phần `ner`; loại parser/tagger/lemmatizer) → thực thể `PERSON` → `[PERSON]`.
5. Ngôn ngữ chưa có model hoặc kết quả không chắc chắn (model chưa nạp được, heuristic tên người còn khớp) → đoạn `NEEDS_REVIEW`: lưu
   bản đã che nhưng **không** tính vào ngưỡng, **không** gửi AI.
6. Kiểm tra lại sau khi che: còn khớp mẫu email/điện thoại → `UNSAFE` → bỏ đoạn (`page_fetch_log.reason = PII_UNSAFE`).
- Hàm tạo prompt AI chỉ nhận kiểu `RedactedText` có `status = REDACTED`; log chỉ ghi số lượng thay thế; checkpoint chỉ chứa ID/hash.
- Vị trí: che PII **trong handler** của tool `page.fetch`/`source.query` (lớp `tools/privacy`), vì Tool Registry E0 lưu output tool vào
  bảng `tool_calls` và `redact_payload` chỉ che secret (kiểm tra `backend/src/nichepilot/tools/registry.py`, 2026-11-20).
- Giới hạn: không đạt 100% (Q8) → bộ mẫu kiểm thử (SC-016) + xóa theo yêu cầu (R-09).

**Đánh giá tài nguyên đã đo (2026-11-20, venv tách biệt Python 3.13)**: spaCy 3.8.18 + model `en_core_web_sm` 3.8.0 thêm ≈ 291 MB vào
site-packages (65 MB → 356 MB, gồm numpy, thinc, blis, typer…); nạp model chỉ `ner` ≈ 0,9 s; **RSS ≈ 151 MB**; ≈ 0,04 s cho đoạn
4.560 ký tự; nhận đúng 2/2 tên người trong mẫu. 300 trang/lượt → ước tính < 30 s CPU cho bước NER. Kết luận: phù hợp 4 core / 15 GB
nếu chỉ nạp trong worker.

**Điều kiện theo X8**: model tải từ GitHub releases (`explosion/spacy-models`, wheel 12,8 MB, không có trên PyPI) → **không** tải lúc
chạy; cài trong Dockerfile worker từ URL ghim phiên bản + kiểm tra SHA-256. METADATA của wheel ghi `License: MIT`; file
`LICENSES_SOURCES` ghi dữ liệu huấn luyện OntoNotes 5 "commercial (licensed by Explosion)" và WordNet 3.0 License (cho phép). Cần chủ
sở hữu chấp nhận ghi chú nguồn dữ liệu này trước khi dùng production (xem R-12).

**Alternatives**: Presidio (MIT) – không bắt buộc trong E1, cắm được qua `PiiEngine`; chỉ regex – không đủ cho tên người.

## R-06 – Ngưỡng bằng chứng và tính độc lập (FR-013b, FR-015, Q5)

**Decision** (logic xác định trong mã):
- Chuẩn hóa nội dung trích đoạn (bỏ khoảng trắng, chữ thường, bỏ dấu câu) → **SimHash 64-bit**; hai bằng chứng có khoảng cách
  Hamming ≤ 3 hoặc cùng `content_hash` thuộc cùng **nhóm độc lập**. Nhóm độc lập còn gộp theo tên miền đã đăng ký (eTLD+1).
- Ngách đạt ngưỡng khi có ≥ 2 bằng chứng pain point **hợp lệ** thuộc ≥ 2 nhóm độc lập khác nhau. Hợp lệ = đủ trường FR-013a,
  `redaction_status = REDACTED`, `lifecycle_status = ACTIVE`, và đánh giá của AI (INFERRED) đạt `relevance ≥ 0.6` và
  `quality ≥ 0.5` (thang 0–1, cấu hình được, có phiên bản cùng trọng số).
- AI chấm `relevance`, `quality`, `copy_suspected` kèm lý do (structured output); `copy_suspected = true` → bằng chứng không được
  tính là nhóm độc lập mới.

## R-07 – Opportunity, Coverage, Confidence (FR-017…FR-020, Q7)

**Opportunity** (đã chốt ở spec FR-019): thang điểm mỗi tiêu chí 0–100; `Opportunity = Σ(s_i·w_i)/Σw_i` trên tiêu chí hợp lệ;
`Coverage = Σw_i` (trọng số gốc, %); Coverage < ngưỡng (mặc định 60%) → `INSUFFICIENT_SCORING_DATA`. Thang chấm từng tiêu chí
(mô tả 5 mức 0/25/50/75/100 với tiêu chí rõ ràng) ghi trong `contracts/scoring-rubric.md`; AI đề xuất mức kèm lý do và bằng chứng,
mã kiểm tra mức thuộc thang và tính tổng.

**Confidence** (đề xuất, có phiên bản `confidence_formula_version = 1`, tham số cấu hình được) – các thành phần 0–1:
| Thành phần | Công thức | Trọng số |
|---|---|---|
| N – số lượng | min(1, số nhóm độc lập / 6) | 0,25 |
| Q – chất lượng | trung bình `quality` của bằng chứng hợp lệ | 0,20 |
| D – đa dạng | min(1, số loại nguồn khác nhau / 3) | 0,15 |
| F – độ mới | trung bình max(0, 1 − tuổi(ngày)/730) | 0,15 |
| K – nhất quán | 1 − (số tiêu chí `CONFLICTING`) / (số tiêu chí có dữ liệu hoặc mâu thuẫn) | 0,15 |
| V – độ phủ | Coverage / 100 | 0,10 |

`Confidence = 100 × Σ(thành phần × trọng số)`; ngách `INSUFFICIENT_EVIDENCE` → giới hạn trần 30. Không dùng Opportunity làm đầu vào
(FR-020). Lưu từng thành phần để tái lập.

**Rationale**: đáp ứng BR-04 (số lượng, đa dạng, độ mới, nhất quán) + Q7 (chất lượng, độ đầy đủ); xác định, kiểm thử được bằng tay.

## R-08 – Phát hiện trùng/tương đồng (FR-022, SC-010)

**Decision**: AI chuẩn hóa mỗi ngách thành (`customer_group`, `core_problem`) ngắn (INFERRED). Mã tính:
`similarity = 0,6 × token_set_ratio(core_problem) + 0,4 × token_set_ratio(customer_group)` (thư viện `rapidfuzz`, MIT – xác minh
khi thêm), trên văn bản chuẩn hóa (chữ thường, bỏ stopword, rút gọn số nhiều đơn giản). ≥ 0,85 → **trùng** (liên kết vào ngách sẵn
có); 0,60–0,85 → **có thể tương đồng** (chờ chủ sở hữu); < 0,60 → khác. Ngưỡng cấu hình được; hiệu chỉnh trên bộ cặp kiểm thử có
nhãn (≥ 40 cặp) để đạt SC-010 (≥ 90% đúng, 0 gộp nhầm "không trùng" – vì gộp tự động chỉ ở ngưỡng cao).

**Alternatives**: embedding vector (không có model embedding miễn phí; Claude API không cung cấp embedding; không dùng LLM local) –
để sau; để AI tự quyết định trùng – vi phạm Constitution III.

## R-09 – Xóa bằng chứng và áp dụng lại sau khi khôi phục backup (FR-013e, FR-013f, X4 có điều kiện)

**Decision**:
- **Ghi sổ trước, DB sau**: `erase()` ghi dòng vào **erasure ledger** (JSONL append-only, fsync file + thư mục) rồi mới chạy transaction
  DB (`lifecycle_status = ERASED`, `excerpt/value = NULL`, URL → `erased:<sha256>`, `evidence_erasure_requests`, audit). DB lỗi → dòng
  sổ vẫn còn và sẽ được áp dụng ở lần kiểm tra kế tiếp (idempotent) → không có yêu cầu xóa nào chỉ nằm trong DB.
- **Định dạng sổ**: dòng đầu là genesis `{ledger_id, created_at}`; mỗi dòng `{seq, target_type, target_id, content_hash, url_hash,
  erased_at, prev_hash, hash}` với `hash = sha256(prev_hash ‖ payload)` → phát hiện mất/sửa dòng. Không chứa nội dung/PII.
- **Lưu bền vững**: volume riêng `erasure-ledger` (không nằm trong dump PostgreSQL); `backup.sh` sao thêm một bản sổ vào thư mục backup;
  bản sổ sống là nguồn chuẩn, restore không bao giờ ghi đè sổ sống bằng bản cũ hơn.
- **Trạng thái trong DB**: bảng `erasure_ledger_state` (một dòng: `ledger_id`, `applied_seq`, `applied_hash`, `status` ∈ {`OK`,
  `BLOCKED`}).
- **Áp dụng trước khi phục vụ**: lệnh `python -m nichepilot.jobs.erasure_ledger --strict` chạy (1) trong service `migrate` sau
  `alembic upgrade` – api/worker phụ thuộc `migrate` `service_completed_successfully`, nên lỗi → api/worker không khởi động; (2) trong
  `restore.sh` ngay sau `pg_restore`, trong cùng quy trình (api/worker đang dừng).
- **Thất bại an toàn** (thoát mã ≠ 0, đặt `status = BLOCKED`, ghi log vận hành): sổ không tồn tại nhưng DB có `ledger_id`/yêu cầu xóa;
  `ledger_id` không khớp; chuỗi hash hỏng; `applied_seq` trong DB > seq cuối của sổ (sổ cũ hơn DB); lỗi khi áp dụng bất kỳ dòng nào
  (toàn bộ trong một transaction, rollback). Khởi tạo sổ mới khi DB đã có `ledger_id` chỉ bằng lệnh thủ công có xác nhận rõ ràng, audit.
- **Phòng thủ lớp 2**: API khi khởi động và định kỳ (60 s) so `applied_seq/applied_hash` với đuôi sổ; lệch hoặc `BLOCKED` → mọi endpoint
  dữ liệu E1 trả 503 `ERASURE_LEDGER_NOT_APPLIED`, `/api/v1/system/status` báo thành phần `erasure_ledger` lỗi; worker không nhận job
  E1. `/health` (liveness) không đổi.
- Sau xóa: job `discovery.recompute` tính lại ngưỡng/Confidence/xếp hạng (không gọi AI). `content_hash`/`url_hash` chặn thu thập lại.
- Cache: E1 không có cache nội dung ngoài DB; nội dung thô chỉ trong bộ nhớ (R-05).

**Kiểm thử bắt buộc** (TC_E1_FR013f_*): restore backup cũ hơn yêu cầu xóa → bằng chứng vẫn `ERASED`, API không trả trích đoạn; sổ thiếu
→ restore thoát ≠ 0, API 503; chuỗi hash bị sửa → thất bại; lỗi giữa chừng → rollback, `BLOCKED`; API không phục vụ dữ liệu E1 trước khi
áp dụng xong; ghi sổ thành công + DB lỗi → lần áp dụng sau hoàn tất xóa.

## R-10 – AI: Model Task Profile, chi phí, mock (FR-028, Constitution VI)

**Decision**: thêm task type (dữ liệu seed, không đổi kiến trúc): `discovery.candidates` (đề xuất ngách ứng viên), `discovery.extract`
(trích pain point/persona/giải pháp từ trích đoạn đã che PII), `discovery.assess` (đánh giá tiêu chí, độc lập, monetization),
`discovery.normalize` (chuẩn hóa cho dedup). Mặc định model tiết kiệm (Haiku 5.5) cho `extract`/`normalize`, Sonnet 5.5 cho
`candidates`/`assess` – vẫn `verified = false` cho tới khi chủ sở hữu xác minh; gọi có phí vẫn tắt.
Model chỉ là **dữ liệu seed** của Model Task Profile (E0): business logic chỉ nêu task type, không chứa model ID (kiểm tra bằng test
grep model ID trong `modules/discovery` và `jobs/agents`). Đổi model qua API Model Task Profile, có audit (quyết định 2026-11-20).

Ước tính chi phí một lượt (20 ứng viên, giá tham khảo chưa xác minh từ `enable-real-api.md` §3): ~20 lời gọi `extract` (≈ 6k token vào,
1k ra, Haiku) + ~20 `assess` (≈ 8k vào, 1,5k ra, Sonnet) + vài lời gọi khác ≈ 20×$0,0011 + 20×$0,031 + ~$0,05 ≈ **$0,7** < $2. Đây là
ước tính, không phải số đo; giữ chỗ ngân sách của E0 bảo đảm không vượt hạn mức.

Không có API key → MockAIProvider: kết quả gắn `MOCK`; nguồn/bằng chứng thu thập thật vẫn `REAL`; ngách/đánh giá sinh từ phân tích mock
là `MOCK` và bị loại khỏi báo cáo mặc định (FR-006b, FR-016).

## R-11 – Chạy job dài trên Job Runtime E0

**Decision**: `NicheDiscoveryAgent` (job type `discovery.run`) với `max_steps = 240`, `max_ai_calls = 120`, `timeout_s = 5400 + 600`
(90 phút + biên cho bước đánh giá cuối), checkpoint sau mỗi bước. Thời gian/trang đã dùng lưu trong checkpoint; thời gian tạm dừng
(PAUSED/PAUSED_BUDGET) không tính. Đây là cấu hình **định nghĩa agent** mà E0 đã hỗ trợ – không đổi Job Runtime. Kết quả
`COMPLETED`/`PARTIAL_COMPLETED` lưu ở `discovery_runs.outcome`; job E0 kết thúc `SUCCEEDED` (FR-030d). Đánh giá lại: job type
`discovery.reevaluate`; tính lại không gọi AI: `discovery.recompute`.

## R-12 – Xác minh dependency (X8, 2026-11-20)

Nguồn: PyPI JSON API (`https://pypi.org/pypi/<tên>/json`, đọc 2026-11-20); giấy phép bắc cầu đọc từ metadata sau khi cài trong venv
tách biệt Python 3.13 (scratchpad, không phải project). "Tương thích" = có wheel cài được trên CPython 3.13 Linux và `requires_python`
cho phép 3.13. Tương thích Windows/WSL2: chạy trong container Linux nên như trên; **chưa kiểm thử** trên Windows.

| Gói | Phiên bản mới nhất (ngày) | Giấy phép | Python | Phụ thuộc trực tiếp (giấy phép) | Kết luận |
|---|---|---|---|---|---|
| trafilatura | 2.3.1 (2026-10-06) | Apache-2.0 | ≥ 3.10 | certifi (MPL-2.0), charset-normalizer (MIT), courlan (Apache-2.0), htmldate (Apache-2.0 → dateparser BSD-3, python-dateutil BSD-3, regex Apache-2.0 AND CNRI-Python, tzlocal MIT, pytz MIT), jusText (BSD-2), lxml (BSD-3), lxml_html_clean (BSD-3), urllib3 (MIT) | Đạt – mặc định |
| protego | 0.7.0 (2026-09-21) | BSD-3-Clause | ≥ 3.10 | không | Đạt |
| phonenumbers | 9.0.43 (2026-11-06) | Apache-2.0 | ≥ 2.5 | không | Đạt (dữ liệu metadata lớn ~ vài chục MB – đã tính trong 65 MB base) |
| rapidfuzz | 3.14.6 (2026-08-30) | MIT | ≥ 3.11 | không | Đạt |
| tldextract | 5.4.0 (2026-10-03) | BSD-3-Clause | ≥ 3.10 | idna (BSD-3), requests (Apache-2.0), requests-file (Apache-2.0), filelock (MIT) | Đạt có điều kiện: mặc định tải Public Suffix List lúc chạy → bắt buộc `suffix_list_urls=()` dùng snapshot đóng gói (không gọi mạng; test rào chắn socket) |
| spacy | 3.8.18 (2026-10-26) | MIT | ≥ 3.10, < 3.16 | thinc, cymem, preshed, murmurhash, srsly, wasabi, catalogue, confection, weasel, spacy-legacy, spacy-loggers (MIT); blis (BSD); numpy (BSD-3 AND 0BSD AND MIT AND Zlib AND CC0-1.0); typer, rich, pydantic (MIT); smart_open, cloudpathlib (MIT); tqdm (MPL-2.0 AND MIT); Jinja2 (BSD) | Đạt – nặng (R-05: +291 MB, RSS ~151 MB); chỉ cài vào image worker |
| en_core_web_sm (model) | 3.8.0 (GitHub releases) | MIT (METADATA) + ghi chú dữ liệu huấn luyện | – | – | **Chờ chủ sở hữu chấp nhận** ghi chú OntoNotes 5 "commercial (licensed by Explosion)" trước production; dev/test dùng được |
| playwright (tùy chọn) | 1.65.2 (2026-11-14) | Apache-2.0 | ≥ 3.10 | greenlet (MIT) | Đạt – chỉ profile `browser-fetcher` |
| crawl4ai | 0.9.5 (2026-10-14) | Apache-2.0 | ≥ 3.10 | gồm `playwright-stealth`, `patchright`, `unclecode-litellm==1.81.13` | **Không dùng** (R-03) |
| SearXNG (image) | 2026.11.18-b867c56a5 | AGPL-3.0-or-later | – | – | Đạt – service riêng, không sửa mã (R-02) |

Giấy phép MPL-2.0 (certifi, tqdm) là copyleft cấp file – dùng không sửa đổi không phát sinh nghĩa vụ công bố mã NichePilot; certifi đã
có trong E0 qua httpx. Không gói nào có giấy phép không rõ, trừ ghi chú dữ liệu của model spaCy.

Tổng tài nguyên dự kiến thêm vào cấu hình mặc định: image worker +~290 MB (spaCy + model) +~65 MB (các gói nhẹ); RAM worker +~150–200 MB
khi nạp NER; container SearXNG ~103 MiB nghỉ. Ước tính tổng RAM nghỉ E0 (324–361 MB) + E1 ≈ 0,6–0,7 GB < 3 GB (SC-002 E0). Phiên bản
cụ thể được ghim trong `uv.lock` khi triển khai; mỗi lần nâng cấp xác minh lại bảng này.

## R-13 – SourceAdapter tổng quát (FR-006g, quyết định 2026-11-20)

**Decision**: tách **loại adapter** (code, ít, có test) khỏi **nguồn** (dữ liệu cấu hình, nhiều, thêm không cần sửa code):

| `adapter_type` | Dùng cho | Cấu hình (`source_policies.config`, không secret) | Trạng thái E1 |
|---|---|---|---|
| `searxng_engine` | máy tìm kiếm qua SearXNG | `engine_name`, `categories`, `language_map` | Triển khai |
| `http_json_api` | API chính thức dạng REST/JSON công khai | `base_url`, `query_template`, `result_mapping` (JSONPath: url, title, snippet, published_at), `rate_limit`, `auth_env_var` (tên biến môi trường, tùy chọn) | Triển khai khung + test bằng mock; chưa nguồn thật nào được bật |
| `open_dataset` | dữ liệu mở dạng file (CSV/JSONL) đã tải về volume | `path`, `license_url`, `field_mapping` | Interface + mock; triển khai khi có bộ dữ liệu cụ thể |
| `licensed_data` | dữ liệu được cấp phép | như `open_dataset` + `license_reference` | Interface; chưa triển khai |

- Mọi adapter trả `SourceResult` chung (`hits` + `source_status`) và gắn `source_policy_id`, `source_compliance` vào bằng chứng.
- `auth_env_var` chỉ lưu **tên** biến môi trường; giá trị đọc từ môi trường lúc chạy, không lưu DB, không trả qua API, không log.
- Thêm nguồn mới thuộc loại có sẵn = `POST /api/v1/sources` + xác minh + bật (audit). Loại adapter mới cần code (và spec) – ngoài E1.
- Reddit/YouTube/Google Trends vẫn ngoài phạm vi E1 (Q1); chỉ là ví dụ sau này cho `http_json_api`/adapter riêng.

