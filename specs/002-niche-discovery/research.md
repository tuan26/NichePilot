# Research: E1 – Autonomous Niche Discovery

**Ngày**: 2026-11-19 | **Spec**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Quy ước: chỉ ghi là "đã xác minh" những gì đã đọc được từ trang chính thức trong phiên này, kèm URL và ngày. Điều gì chưa đọc
được ghi rõ `UNVERIFIED` / "chưa xác minh" – không điền từ trí nhớ (Constitution I).

**Giới hạn của phiên nghiên cứu**: môi trường agent chỉ truy cập được `github.com` và `www.microsoft.com`; các host còn lại
(policies.google.com, duckduckgo.com, search.brave.com, www.mojeek.com, mwmbl.org, about.marginalia-search.com,
meta.wikimedia.org, www.mediawiki.org, api.stackexchange.com, hn.algolia.com, docs.searxng.org, docs.crawl4ai.com,
www.rfc-editor.org) bị chính sách mạng chặn (lỗi DNS); www.startpage.com bị công cụ đọc web từ chối. Hai yêu cầu mở mạng cho
môi trường đều bị dịch vụ môi trường từ chối. Vì vậy **R-01 là điều kiện chặn trước khi bật nguồn tìm kiếm thật** (xem R-01).

---

## R-01 – Hồ sơ tuân thủ máy tìm kiếm thượng nguồn cho SearXNG (FR-006c…FR-006f)

**Decision**: Mỗi máy tìm kiếm thượng nguồn có một bản ghi `search_source_policies` (URL điều khoản, ngày xác minh, phương thức
tích hợp, giới hạn đã biết, trạng thái `ALLOWED`/`UNVERIFIED`/`PROHIBITED`). Seed ban đầu: **tất cả `UNVERIFIED`, tắt**. Chỉ
chuyển `ALLOWED` sau khi đọc được điều khoản chính thức (chủ sở hữu hoặc agent khi được mở mạng), ghi audit. Khi không có nguồn
`ALLOWED` nào được bật, lượt khám phá báo `NO_COMPLIANT_SEARCH_SOURCE` (FR-006e) – không tạo dữ liệu thay thế.

Kết quả xác minh trong phiên này (2026-11-19):

| Nguồn (engine SearXNG) | URL điều khoản / tài liệu | Đọc được? | Nội dung liên quan | Trạng thái đề xuất |
|---|---|---|---|---|
| Bing (Microsoft) | https://www.microsoft.com/en-us/servicesagreement | Có (một phần, ~40/132 nghìn ký tự đọc nguyên văn) | Mục 3.a.vi: "Don't circumvent any restrictions on access to, usage, or availability of the Services", kèm ví dụ "impermissible scraping"; mục 3.a.v: "automating inauthentic activity". Không có điều khoản nói rõ cho phép hay cấm meta-search gửi truy vấn tự động; "impermissible" không được định nghĩa | `UNVERIFIED` (không đủ căn cứ cho `ALLOWED`; chưa đủ căn cứ ghi `PROHIBITED`) – tắt |
| Google | https://policies.google.com/terms, https://www.google.com/robots.txt | Không (mạng) | – | `UNVERIFIED` – tắt |
| DuckDuckGo | https://duckduckgo.com/terms, https://duckduckgo.com/robots.txt | Không (mạng) | – | `UNVERIFIED` – tắt |
| Brave Search | https://search.brave.com/help/terms-of-service | Không (mạng) | – | `UNVERIFIED` – tắt |
| Mojeek | https://www.mojeek.com/about/terms, https://www.mojeek.com/services/search/web-search-api/ | Không (mạng) | – | `UNVERIFIED` – tắt |
| Startpage | https://www.startpage.com/en/terms-of-service/ | Không (công cụ từ chối) | – | `UNVERIFIED` – tắt |
| Mwmbl | https://mwmbl.org | Không (mạng) | – | `UNVERIFIED` – tắt |
| Marginalia Search | https://about.marginalia-search.com/article/api/ | Không (mạng) | – | `UNVERIFIED` – tắt |
| Wikipedia (MediaWiki API) | https://meta.wikimedia.org/wiki/User-Agent_policy, https://www.mediawiki.org/wiki/API:Etiquette | Không (mạng) | – | `UNVERIFIED` – tắt |
| Stack Exchange API | https://api.stackexchange.com/docs/throttle, https://stackapps.com/help/api-authentication | Không (mạng/công cụ) | – | `UNVERIFIED` – tắt |
| Hacker News (Algolia API) | https://hn.algolia.com/api | Không (mạng) | – | `UNVERIFIED` – tắt |

**Hệ quả**: với cấu hình mặc định hiện tại, lượt khám phá dùng nguồn thật sẽ báo `NO_COMPLIANT_SEARCH_SOURCE` cho tới khi ít
nhất một nguồn được xác minh `ALLOWED`. Đây là hành vi đúng theo Q4, nhưng **chưa đáp ứng được yêu cầu "E1 phải thu thập dữ liệu
thị trường thực tế"** cho tới khi xác minh xong. Đề xuất cho chủ sở hữu (chọn một):

1. Cho phép các host trong bảng trên ở Network access của môi trường (Allowed domains) → agent đọc lại điều khoản và cập nhật
   bảng + seed trước `/speckit-tasks`; hoặc
2. Chủ sở hữu tự đọc điều khoản và gửi kết luận (URL + ngày + trích đoạn) → agent ghi vào seed.

Ưu tiên xác minh các nguồn có **API chính thức công khai** (Wikipedia/MediaWiki API, Stack Exchange API, Hacker News Algolia API,
Mojeek API, Marginalia API) vì đây là các nguồn có khả năng cao nhất có điều khoản cho phép truy cập tự động theo phương thức tích
hợp dự kiến. Máy tìm kiếm web tổng quát (Google, Bing, DuckDuckGo, Brave, Startpage) chỉ bật khi điều khoản cho phép rõ ràng.

**Rationale**: Q4 yêu cầu chỉ bật nguồn đã xác minh; ghi `UNVERIFIED` khi chưa đọc được là cách duy nhất không bịa kết luận.

**Alternatives considered**: (a) dùng cấu hình engine mặc định của SearXNG – bị loại theo Q4; (b) điền trạng thái từ hiểu biết
trước đó của mô hình – vi phạm Constitution I.

## R-02 – SearXNG: triển khai và tích hợp

**Decision**: Chạy image SearXNG chính thức, **không sửa mã**, như service `searxng` trong Docker Compose profile `research` (tắt mặc
định, bật khi dùng nguồn thật), `mem_limit` 256m, chỉ mở trong mạng nội bộ Compose (không publish cổng). File `settings.yml` do
NichePilot cung cấp: bật định dạng `json`, `keep_only` danh sách engine ứng viên trong bảng R-01, tắt mọi engine khác, `limiter`
không cần (chỉ worker nội bộ truy cập). Adapter `SearxngSearchAdapter` gửi `GET /search?format=json&q=…&engines=<danh sách
ALLOWED đang bật>&language=…` → **phòng thủ hai lớp**: SearXNG chỉ có engine ứng viên, và mỗi truy vấn chỉ nêu engine `ALLOWED`.

- Giấy phép: **AGPL-3.0** – đã xác minh tại https://github.com/searxng/searxng (2026-11-19): "This project is licensed under the GNU
  Affero General Public License (AGPL-3.0)". Dùng như dịch vụ riêng, không sửa mã → không phát sinh nghĩa vụ công bố mã của
  NichePilot; nếu sau này sửa SearXNG thì phải công bố phần sửa cho người dùng mạng. Ghi vào Technology Evaluation (Constitution VII).
- Cách bật `formats: [html, json]`, cấu trúc `settings.yml`, tham số `engines` và limiter: **chưa xác minh từ docs.searxng.org** (bị
  chặn) → task triển khai đầu tiên của nhóm này là đọc tài liệu chính thức (hoặc mã nguồn trên GitHub, truy cập được) và ghi lại.
- SearXNG không trả kết quả / lỗi / timeout → bước tìm kiếm ghi `SEARCH_UNAVAILABLE` hoặc `NO_RESULTS` cho ứng viên đó (FR-006a);
  mọi engine `ALLOWED` lỗi → `NO_COMPLIANT_SEARCH_SOURCE` cho lượt (FR-006e).

**Alternatives**: API tìm kiếm trả phí (Brave/Bing API) – loại theo Q1 (không key trả phí); scrape trực tiếp trang tìm kiếm – loại
(ToS, CAPTCHA).

## R-03 – Thu thập nội dung trang: Crawl4AI và phương án nhẹ hơn (Constitution VII)

Đã xác minh (2026-11-19):
- **Crawl4AI** – https://github.com/unclecode/crawl4ai: Apache-2.0 ("attribution is recommended"; một mục khác ghi "you must include
  one of the following attribution methods" – **mâu thuẫn trong README**, cần chủ sở hữu quyết định có ghi công hay không), bản
  mới nhất v0.9.5 (14/10/2026), **cần trình duyệt** (`crawl4ai-setup` cài browser; Playwright Chromium), có Docker image chính
  thức `unclecode/crawl4ai` chạy với `--shm-size=1g`, server cần `CRAWL4AI_API_TOKEN`. Tùy chọn tôn trọng robots.txt **không thấy
  trong README** (chưa xác minh). Yêu cầu RAM khuyến nghị: chưa xác minh (docs bị chặn).
- **trafilatura** – https://github.com/adbar/trafilatura: Apache-2.0 (từ v1.8.0; bản cũ GPLv3+), trích nội dung chính từ HTML
  (extractor riêng + jusText/readability-lxml dự phòng); README không nhắc tới trình duyệt (suy luận: không cần trình duyệt).

**Decision**: **Fetcher mặc định nhẹ**: HTTP client của worker (httpx, đã có) + `trafilatura` để trích nội dung chính – không cần
trình duyệt, chạy trong worker, không thêm container. **Crawl4AI là adapter tùy chọn** cho trang cần JavaScript: service `crawl4ai`
trong Compose profile `browser-crawler` (tắt mặc định), chỉ bật khi chủ sở hữu chọn; khi bật, NichePilot tự kiểm tra robots.txt
và tốc độ **trước khi** gọi Crawl4AI (không phụ thuộc tùy chọn của Crawl4AI). Cả hai dùng chung interface `PageFetcher`.

**Rationale**: Crawl4AI kéo theo Chromium (RAM lớn, `shm 1g`) trái nguyên tắc "công cụ nặng chỉ bật khi cần" và mục tiêu RAM
≤ 3 GB của E0; phần lớn trang diễn đàn/đánh giá/blog trả HTML tĩnh. **Cần chủ sở hữu duyệt**: chủ sở hữu "ưu tiên Crawl4AI hoặc
công cụ phù hợp" – plan đề xuất trafilatura làm mặc định, Crawl4AI tùy chọn.

**Alternatives**: Crawl4AI mặc định (nặng, luôn có Chromium); Playwright trực tiếp (nặng tương tự); Scrapy (khung crawl lớn, thừa
cho mức 300 trang/lượt).

## R-04 – robots.txt, tốc độ truy cập, CAPTCHA (FR-005, FR-030a, FR-031)

**Decision**:
- Đọc `robots.txt` một lần mỗi tên miền mỗi lượt (lưu cache 24 giờ trong `domain_access_state`), dùng `urllib.robotparser`
  (thư viện chuẩn Python, có `can_fetch` và `crawl_delay`) với User-Agent riêng `NichePilotResearchBot/<version> (+liên hệ cấu hình
  được)`. robots.txt không lấy được: lỗi 4xx → coi như không có giới hạn; lỗi 5xx/mạng → **không thu thập** tên miền đó trong lượt
  (thận trọng). Quy định chính xác của RFC 9309 về 4xx/5xx **chưa xác minh** (www.rfc-editor.org bị chặn) – task đầu tiên đọc lại
  RFC và điều chỉnh nếu khác.
- Khoảng cách tối thiểu giữa hai yêu cầu cùng tên miền = max(mức trần lượt (mặc định 2 s), `Crawl-delay` của robots.txt,
  `Retry-After` gần nhất). 429/503 → tăng khoảng cách và thử lại tối đa 2 lần trong giới hạn thời gian còn lại; quá → bỏ tên miền
  cho lượt, lý do `RATE_LIMITED`.
- Phát hiện CAPTCHA/chặn bot (403 kèm dấu hiệu challenge, trang xác minh) → dừng tên miền đó, lý do `ACCESS_RESTRICTED`; không thử
  vượt. Không gửi cookie/đăng nhập; không theo paywall.
- Trạng thái tên miền lưu trong DB để giữ đúng khoảng cách sau khi worker khởi động lại.

## R-05 – Che PII (FR-012a…FR-012c, Q8)

**Decision**: pipeline nhiều lớp, chạy **trong bộ nhớ ngay sau khi trích nội dung**, trước mọi ghi DB/log/checkpoint và trước gửi AI:
1. Bỏ metadata tác giả từ trích xuất (trafilatura trả `author`/`hostname` → không lưu `author`).
2. Mẫu xác định: email → `[EMAIL]`; số điện thoại (thư viện `phonenumbers`, Apache-2.0 – cần xác minh giấy phép khi thêm) →
   `[PHONE]`; `@handle`, `u/…`, `/user/…`, `by <Name>`/`Posted by` → `[USER]`/`[PERSON]`; URL hồ sơ cá nhân trong nội dung → `[USER]`.
3. Nhận diện tên người theo ngữ cảnh: với ngôn ngữ nghiên cứu tiếng Anh, mô hình NER nhỏ (spaCy `en_core_web_sm`, MIT – cần xác
   minh khi thêm) đánh `PERSON` → `[PERSON]`; ngôn ngữ chưa có NER → heuristic (chuỗi viết hoa liền nhau sau dấu hiệu chữ ký/lời
   chào) và nếu còn nghi ngờ → đoạn đánh dấu `NEEDS_REVIEW`.
4. Kiểm tra lại sau khi che: còn khớp mẫu email/điện thoại → coi là không an toàn → bỏ đoạn hoặc `NEEDS_REVIEW` (FR-012b).
- Log chỉ ghi số lượng thay thế theo loại, không ghi nội dung. Checkpoint chỉ chứa ID/hash, không chứa văn bản thô.
- Giới hạn đã biết (Q8): không đạt 100%; đo bằng bộ mẫu kiểm thử (SC-016) và cho chủ sở hữu xóa theo yêu cầu (R-09).

**Alternatives**: Microsoft Presidio (MIT, nặng hơn, nhiều phụ thuộc) – để dự phòng nếu bộ mẫu kiểm thử cho thấy cần; chỉ regex –
không đủ cho tên người.

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

## R-09 – Xóa bằng chứng và áp dụng lại sau khi khôi phục backup (FR-013e, FR-013f)

**Decision**:
- Xóa = cập nhật `research_evidence`: `lifecycle_status = ERASED`, `excerpt = NULL`, `erased_at`; giữ `id`, `source_id`,
  `content_hash` (để không thu thập lại cùng nội dung). Xóa theo nguồn → mọi bằng chứng của nguồn đó + `research_sources.url` thay bằng
  dạng băm. Ghi `evidence_erasure_requests` (định danh, hash, lý do, người, thời điểm) và audit (không nội dung).
- Sau xóa: job `discovery.recompute` tính lại ngưỡng/Confidence/xếp hạng của ngách liên quan (không gọi AI).
- **Sổ xóa ngoài database**: mỗi yêu cầu xóa đồng thời được ghi (append-only, JSONL, chỉ ID + hash + thời điểm) vào file trong volume
  riêng `erasure-ledger` (không nằm trong bản dump PostgreSQL). Sau mọi lần restore, service `migrate` (đã chạy trước api/worker)
  chạy bước `apply-erasure-ledger`: áp dụng lại mọi yêu cầu trong sổ chưa có trong DB → dữ liệu đã xóa không quay lại trước khi hệ
  thống phục vụ. `deploy/scripts/restore.sh` in nhắc và quy trình vận hành ghi rõ phải giữ volume `erasure-ledger`.
- Bản sao trong cache: E1 không có cache nội dung ngoài DB; nội dung thô chỉ trong bộ nhớ (R-05).

**Cần chủ sở hữu duyệt**: đây là mở rộng quy trình backup/restore của E0 (thêm volume và bước sau restore).

## R-10 – AI: Model Task Profile, chi phí, mock (FR-028, Constitution VI)

**Decision**: thêm task type (dữ liệu seed, không đổi kiến trúc): `discovery.candidates` (đề xuất ngách ứng viên), `discovery.extract`
(trích pain point/persona/giải pháp từ trích đoạn đã che PII), `discovery.assess` (đánh giá tiêu chí, độc lập, monetization),
`discovery.normalize` (chuẩn hóa cho dedup). Mặc định model tiết kiệm (Haiku 5.5) cho `extract`/`normalize`, Sonnet 5.5 cho
`candidates`/`assess` – vẫn `verified = false` cho tới khi chủ sở hữu xác minh; gọi có phí vẫn tắt.

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
