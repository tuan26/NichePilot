# Danh sách nguồn cần xác minh – E1

**Ngày lập**: 2026-11-20 | Liên quan: FR-006c…FR-006g, research R-01, R-13

Trạng thái hiện tại của **mọi** nguồn: `UNVERIFIED`, tắt. Việc xác minh **BLOCKED** trong môi trường cloud hiện tại vì mạng không truy
cập được các trang điều khoản (chủ sở hữu không đồng ý mở rộng mạng của môi trường dùng chung, 2026-11-20). Xác minh sẽ làm sau trên
môi trường có quyền truy cập phù hợp. Chưa xác minh được **không** phải lỗi implementation; kiểm thử tự động dùng adapter giả lập.

Quy tắc: chỉ đặt `ALLOWED` khi đã đọc văn bản chính thức và ghi đủ các mục ở §2. Chỉ nguồn `ALLOWED` được dùng; `UNVERIFIED` và
`PROHIBITED` không bật được và không có cách bỏ qua (quyết định A1, 2026-11-20 (b)). Không suy từ trí nhớ, blog hay việc "có API miễn
phí". Văn bản cấm hoặc yêu cầu điều kiện không đáp ứng được → `PROHIBITED` (hoặc giữ `UNVERIFIED` kèm ghi chú nếu mơ hồ).

## 1. Danh sách nguồn

URL dưới đây là trang chính thức dự kiến cần đọc. URL có thể đã đổi: người xác minh ghi URL thực tế đã đọc.

| # | Nguồn | `adapter_type` dự kiến | Văn bản cần đọc (URL chính thức) | Trọng tâm cần kiểm tra |
|---|---|---|---|---|
| S1 | Wikipedia / MediaWiki API | `http_json_api` hoặc `searxng_engine` | https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use · https://meta.wikimedia.org/wiki/User-Agent_policy · https://www.mediawiki.org/wiki/API:Etiquette · https://www.mediawiki.org/wiki/API:Search | User-Agent bắt buộc; giới hạn tốc độ/đồng thời; giấy phép nội dung (CC BY-SA) và yêu cầu ghi nguồn khi lưu trích đoạn |
| S2 | Stack Exchange API | `http_json_api` | https://stackoverflow.com/legal/api-terms-of-use · https://api.stackexchange.com/docs/throttle · https://stackapps.com/help/api-authentication | Quota không key/có key; điều kiện đăng ký app; lưu trữ dữ liệu; ghi nguồn; giới hạn mục đích (có thể cấm dùng cho một số mục đích thương mại/AI) |
| S3 | Hacker News (Algolia API) | `http_json_api` | https://hn.algolia.com/api · https://www.ycombinator.com/legal (điều khoản HN) | Điều khoản dùng API; giới hạn tốc độ; quyền lưu trích đoạn bình luận |
| S4 | Mojeek | `searxng_engine` hoặc `http_json_api` (API trả phí – ngoài Q1 nếu cần key trả phí) | https://www.mojeek.com/about/terms · https://www.mojeek.com/services/search/web-search-api/ | Truy vấn tự động qua trang web có được phép không; API có gói miễn phí không; điều kiện thương mại |
| S5 | Marginalia Search | `http_json_api` / `searxng_engine` | https://about.marginalia-search.com/article/api/ | Key công khai dùng chung, giới hạn, điều kiện sử dụng |
| S6 | Mwmbl | `searxng_engine` | https://mwmbl.org (trang about/terms, kho mã chính thức) | Điều kiện truy cập tự động, giới hạn |
| S7 | DuckDuckGo | `searxng_engine` | https://duckduckgo.com/terms · https://duckduckgo.com/robots.txt | Truy vấn tự động/meta-search có bị cấm không |
| S8 | Brave Search | `searxng_engine` (API cần key – ngoài Q1 nếu trả phí) | https://search.brave.com/help/terms-of-service · https://api-dashboard.search.brave.com/terms-of-service | Cấm scraping trang web?; gói API miễn phí và giới hạn mục đích (ví dụ cấm lưu/huấn luyện AI) |
| S9 | Startpage | `searxng_engine` | https://www.startpage.com/en/terms-of-service/ | Truy vấn tự động |
| S10 | Google | `searxng_engine` | https://policies.google.com/terms · https://www.google.com/robots.txt | Truy vấn tự động trang kết quả |
| S11 | Bing (Microsoft) | `searxng_engine` | https://www.microsoft.com/en-us/servicesagreement (đọc một phần 2026-11-19) · https://www.bing.com/robots.txt | Định nghĩa "impermissible scraping" (§3.a.vi); meta-search |
| S12 | robots.txt (chuẩn) | – (quy tắc thu thập trang) | https://www.rfc-editor.org/rfc/rfc9309.html | Xử lý 4xx/5xx/không truy cập được của robots.txt; thời gian cache; kiểm tra lại R-04 |
| S13 | Tài liệu SearXNG | – (cấu hình) | https://docs.searxng.org/admin/settings/index.html | Đối chiếu cấu hình `keep_only`, `formats`, `limiter` (đã xác minh từ mã trong image 2026-11-20 – xác minh tài liệu chỉ để bổ sung) |

S12–S13 không phải nguồn dữ liệu; liệt kê vì đang chờ đọc tài liệu chính thức cùng đợt.

### Lần thử xác minh 2026-11-22 (quyết định D2: S2 Stack Exchange API hoặc S1 Wikipedia)

BLOCKED: mạng môi trường chặn `api.stackexchange.com`, `stackoverflow.com`, `stackapps.com`, `en.wikipedia.org`,
`foundation.wikimedia.org`, `meta.wikimedia.org`, `www.mediawiki.org` (proxy 403 / không phân giải DNS). Chưa đọc được văn bản nào →
không ghi hồ sơ, không đổi trạng thái nguồn.

### S1 Wikipedia (MediaWiki Action API) – hồ sơ xác minh NHÁP, 2026-11-22 (chưa bật)

Mạng: môi trường riêng `nichepilot` mở `en.wikipedia.org`, `foundation.wikimedia.org`, `www.mediawiki.org` (chủ sở hữu duyệt).
Văn bản đã đọc (bản wikitext gốc, `action=raw`):

| Văn bản | URL | Nội dung liên quan (trích nguyên văn) |
|---|---|---|
| Terms of Use (bản hiện hành, thay bản 2014–2023 từ 2023-06-07) | https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use | §4: cấm "automated uses of the Project Websites that are abusive or disruptive of the services, violate acceptable usage policies where available, or have not been approved by the Wikimedia community"; §7: CC BY-SA 4.0 (và GFDL), "these licenses do allow commercial uses"; ghi nguồn khi tái sử dụng: "Through hyperlink (where possible) or URL to the page or pages that you are reusing"; §12: dùng API phải tuân User-Agent Policy, Robot Policy và API:Etiquette (đưa vào bằng tham chiếu) |
| User-Agent Policy | https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy | "Scripts should use an informative User-Agent string with contact information, or they may be blocked without notice"; liên hệ là "an email address, a website, or a wiki user"; nên có chữ "bot"; không dùng UA trình duyệt hay UA chung chung |
| API Usage Guidelines (v1.0, 2024-08-26) | https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_API_Usage_Guidelines | phải: tuân User-Agent policy; "Follow rate limiting requests"; tuân giấy phép khi tái phát hành; robot policy "if your software is automatically consuming content at a large scale". Không được: kết nối đồng thời gây suy giảm dịch vụ, tốc độ cao bất thường, chia nhiều UA để che giấu |
| API:Etiquette | https://www.mediawiki.org/wiki/API:Etiquette | "There is no hard speed limit on read requests"; "Making your requests in series rather than in parallel"; dùng `maxlag` cho tác vụ không tương tác; lỗi `ratelimited` → tăng thời gian chờ (exponential backoff) |
| robots.txt | https://en.wikipedia.org/robots.txt | `User-agent: *` → `Disallow: /w/` (trang bài viết `/wiki/` được phép; "Friendly, low-speed bots are welcome viewing article pages"). Truy cập `api.php` được điều chỉnh bởi API Usage Guidelines/API:Etiquette (đã đọc) |

Chưa đọc: **Robot Policy** (wikitech.wikimedia.org – không nằm trong host được mở). Theo API Usage Guidelines, chính sách này áp dụng cho
tiêu thụ nội dung "at a large scale"; lượt E1 tối đa 300 trang, tuần tự, ≥ 2 s/tên miền.

Điều kiện kỹ thuật trước khi bật (đối chiếu mã):
- Adapter `http_json_api`: đã bổ sung `url_template` (dựng URL `/wiki/{title}`) và `error_key` (lỗi `maxlag`/`ratelimited` trong body →
  backoff theo `Retry-After`/lũy thừa, thử lại có giới hạn) – test `test_http_json_api_adapter.py`.
- Cấu hình dự kiến: `base_url = https://en.wikipedia.org/w/api.php`, `query_template = action=query&list=search&srsearch={query}&format=json&srlimit=10&maxlag=5`,
  `result_mapping = {items: query.search, title: title, snippet: snippet}`, `url_template = https://en.wikipedia.org/wiki/{title}`,
  `error_key = error`, `rate_limit_per_minute = 30`.
- **Còn thiếu: User-Agent có thông tin liên hệ thật** (`DISCOVERY_USER_AGENT`) – UA hiện tại không có email/website → chưa đủ điều kiện bật.
- Phạm vi sử dụng dự kiến: nghiên cứu nội bộ; lưu trích đoạn ≤ 1000 ký tự đã che PII kèm URL bài viết (ghi nguồn bằng hyperlink); báo cáo có
  thông báo giấy phép CC BY-SA 4.0 cho trích đoạn Wikipedia; không phân phối lại hàng loạt.

## 2. Nội dung bắt buộc ghi cho mỗi nguồn (khớp cột `source_policies`)

| Mục | Cột | Ví dụ ghi |
|---|---|---|
| URL điều khoản đã đọc | `tos_url` | URL thực tế |
| Ngày xác minh | `verified_at` | 2026-12-01 |
| Người xác minh | `verified_by` | chủ sở hữu |
| Căn cứ | `verification_note` | Trích nguyên văn điều khoản liên quan (≤ 1000 ký tự) + mục/đoạn |
| Phương thức truy cập được phép | `allowed_access_methods` | `OFFICIAL_API` / `SEARXNG_ENGINE` / `DATASET_DOWNLOAD` |
| Phạm vi sử dụng được phép | `permitted_use_scope` | ví dụ: "nghiên cứu nội bộ; lưu trích đoạn ≤ 1000 ký tự kèm ghi nguồn; không phân phối lại" |
| Giới hạn đã biết | `known_limits` | ví dụ: "≤ 1 req/s, cần User-Agent có liên hệ" |
| Yêu cầu xác thực | `config.auth_env_var` | tên biến môi trường (không ghi giá trị) |
| Kết luận | `compliance_status` | `ALLOWED` / `UNVERIFIED` / `PROHIBITED` |

## 3. Cách cập nhật sau khi xác minh (không cần sửa code)

1. Dashboard → **Nguồn dữ liệu** (hoặc `PUT /api/v1/sources/{id}`) nhập các mục §2; API từ chối `ALLOWED` nếu thiếu `verified_at`,
   `verification_note`, `allowed_access_methods` hoặc `permitted_use_scope` (422 `SOURCE_VERIFICATION_INCOMPLETE`); bật nguồn chưa
   `ALLOWED` → 409 `SOURCE_NOT_ALLOWED`.
2. Bật nguồn → hệ thống sinh lại `settings.yml` của SearXNG (với `searxng_engine`) và hướng dẫn khởi động lại `searxng`.
3. Audit `source.updated` ghi trạng thái trước/sau.
4. Cập nhật bảng R-01 trong research.md (hoặc báo cáo vận hành) bằng kết quả đã ghi.

## 4. Mục BLOCKED do giới hạn mạng (tổng hợp)

| Mục | Ảnh hưởng | Không phải lỗi implementation vì |
|---|---|---|
| Xác minh S1–S11 | Lượt dùng nguồn thật báo `NO_COMPLIANT_SEARCH_SOURCE`; SC-013 (thu thập thật ≥ 80% ứng viên) chưa kiểm chứng được | Hành vi đúng theo FR-006e; kiểm thử dùng adapter giả lập |
| Đọc RFC 9309 (S12) | Quy tắc 4xx/5xx robots.txt dùng phương án thận trọng (R-04) cho tới khi xác minh | Phương án thận trọng không vi phạm robots.txt |
| Tài liệu SearXNG (S13) | Không – cấu hình đã xác minh từ mã trong image chính thức | – |
| Thử truy vấn JSON thật qua SearXNG | Chưa kiểm chứng định dạng phản hồi thật của từng engine | Không được phép truy vấn nguồn chưa xác minh |
