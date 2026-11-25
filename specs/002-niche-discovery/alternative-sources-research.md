# Nghiên cứu nguồn thay thế cho Niche Discovery (Q5) – 2026-11-25

Theo quyết định Q5 của chủ sở hữu (2026-11-25): **chỉ nghiên cứu điều khoản và khả năng tích hợp**. Không bật nguồn nào, không thu
thập dữ liệu live, không thay đổi mạng Default. Mọi nguồn dưới đây giữ `UNVERIFIED` trong registry (không ghi `/sources`).

## 0. Mức độ tin cậy của thông tin

| Ký hiệu | Nghĩa |
|---|---|
| **ĐÃ ĐỌC** | Đã đọc trực tiếp trang chính thức trong phiên này |
| **SNIPPET** | Chỉ thấy qua kết quả tìm kiếm web (đoạn trích của trang chính thức hoặc bài bên thứ ba) – **chưa đọc trang gốc, không được dùng để xác minh** |
| `UNKNOWN` | Chưa có thông tin |

Lý do phần lớn là SNIPPET/`UNKNOWN`: môi trường `nichepilot` chỉ mở 4 tên miền Wikimedia; công cụ đọc web không truy cập được
`hn.algolia.com`, `www.ycombinator.com`, `www.algolia.com`, `stackoverflow.co`, `docs.github.com`, `support.reddithelp.com`,
`docs.joinmastodon.org`, `join-lemmy.org` (lỗi DNS) và từ chối `stackoverflow.com`, `api.stackexchange.com`, `www.redditinc.com`.

## 1. Đánh giá từng nguồn

Thang "phù hợp Niche Discovery": Cao / Trung bình / Thấp – dựa trên loại nội dung (người dùng mô tả vấn đề, than phiền, hỏi giải
pháp) so với nguồn kiến thức chung (Wikipedia).

### 1.1 Hacker News – Algolia HN Search API (`hn.algolia.com/api`) + HN Firebase API (`hacker-news.firebaseio.com/v0/`)

| Tiêu chí | Đánh giá |
|---|---|
| Khả năng tìm pain point | **Trung bình–Cao** cho ngách B2B/dev tools/SaaS: "Ask HN", bình luận than phiền công cụ, "Show HN" có phản hồi. Thấp cho ngách tiêu dùng phổ thông, ngoài Mỹ/ngoài ngành công nghệ |
| Tính hợp lệ / độc lập | Một tên miền (`news.ycombinator.com`) → theo `evidence_rules` mọi bằng chứng HN cùng 1 nhóm độc lập; cần nguồn thứ hai để đạt ngưỡng 2 nhóm |
| Giới hạn API | Algolia: "10,000 requests per hour" mỗi IP (**SNIPPET** từ trang chính thức `hn.algolia.com/api`). Firebase: "There is currently no rate limit." (**ĐÃ ĐỌC** – github.com/HackerNews/API) |
| Chi phí | Không thấy yêu cầu key/thanh toán (Firebase: **ĐÃ ĐỌC**; Algolia: **SNIPPET**) |
| Điều khoản nội dung / AI | `UNKNOWN`. README GitHub ghi MIT – áp dụng cho mã/tài liệu, **không** chắc áp dụng cho nội dung bình luận người dùng. Chưa đọc điều khoản HN (`www.ycombinator.com/legal`) và điều khoản Algolia cho dịch vụ HN Search |
| Dùng với AI | Kỹ thuật phù hợp (JSON, có `created_at`, `objectID`, URL bài) – trích đoạn ngắn + che PII trước khi gửi AI. Quyền gửi nội dung cho AI bên thứ ba: `UNKNOWN` |
| Tích hợp | Adapter `http_json_api` hiện có dùng được (`url_template` cho `search?query=…&tags=…`); cần thêm ánh xạ trường `hits[]` – chưa làm |

### 1.2 Stack Exchange API (`api.stackexchange.com/2.3`)

| Tiêu chí | Đánh giá |
|---|---|
| Khả năng tìm pain point | **Trung bình–Cao** cho ngách có site chuyên đề (Stack Overflow, Super User, Home Improvement, Personal Finance, Webmasters…): câu hỏi lặp lại = nhu cầu thật; điểm/lượt xem đo mức độ |
| Tính hợp lệ / độc lập | Nhiều site trên các tên miền khác nhau (stackoverflow.com, superuser.com, *.stackexchange.com) – eTLD+1 `stackexchange.com` gom nhiều site vào 1 nhóm |
| Giới hạn API | 300 req/ngày/IP không key; 10.000/ngày với app key; phản hồi có `quota_remaining`, `backoff` (**SNIPPET**, nguồn bên thứ ba – chưa đọc `api.stackexchange.com/docs/throttle`) |
| Chi phí | App key miễn phí (**SNIPPET**); cần đăng ký app trên stackapps.com – `UNKNOWN` điều kiện |
| Điều khoản nội dung / AI | **Rủi ro CAO.** Theo SNIPPET (bài báo/blog, không phải văn bản gốc): Acceptable Use Policy được cho là cấm thu thập tự động để "developing, building, training, testing, indexing, benchmarking, or improving" AI/LLM; API không tự cấp quyền dùng làm corpus AI; dùng thương mại được hướng tới liên hệ Stack Overflow; data dump 2024 loại trừ thương mại + huấn luyện LLM. Nội dung CC BY-SA yêu cầu ghi nguồn. **Chưa đọc văn bản gốc** |
| Dùng với AI | Việc NichePilot gửi trích đoạn cho Claude/OpenAI để phân tích (không huấn luyện) có thuộc phạm vi cấm hay không: `UNKNOWN` – cần đọc AUP + API Terms gốc, có thể cần hỏi Stack Overflow |
| Tích hợp | `http_json_api` dùng được (`/search/advanced?q=…&site=…`); phản hồi gzip; tôn trọng `backoff` – adapter đã có backoff theo `Retry-After`, cần thêm đọc trường `backoff` trong body – chưa làm |

### 1.3 GitHub Issues / Discussions (REST Search API `api.github.com`)

| Tiêu chí | Đánh giá |
|---|---|
| Khả năng tìm pain point | **Trung bình** – chỉ cho ngách phần mềm/dev tools/self-hosted (feature request, issue "+1" nhiều) |
| Tính hợp lệ / độc lập | Cùng tên miền github.com → 1 nhóm |
| Giới hạn API | Search: 30 req/phút có xác thực, 10 req/phút không xác thực; search code 10/phút, bắt buộc xác thực (**SNIPPET** từ `docs.github.com/en/rest/search/search`) |
| Chi phí | Miễn phí với token cá nhân/GitHub App (cần chủ sở hữu tạo token – credential, không lưu DB/repo) |
| Điều khoản nội dung / AI | `UNKNOWN` – chưa đọc GitHub Terms of Service / Acceptable Use Policies (mục "Information Usage Restrictions", API Terms) |
| Dùng với AI | `UNKNOWN` |

### 1.4 Reddit Data API

| Tiêu chí | Đánh giá |
|---|---|
| Khả năng tìm pain point | **Cao** (subreddit theo ngách, than phiền trực tiếp) |
| Giới hạn / chi phí | 100 truy vấn/phút/OAuth client miễn phí; thương mại cần thỏa thuận riêng; giá `UNKNOWN` (**SNIPPET**, blog bên thứ ba) |
| Điều khoản AI | Theo SNIPPET (TechCrunch, SEJ, blog): không được dùng nội dung để huấn luyện ML/AI khi chưa có đồng ý bằng văn bản; Public Content Policy 2024 "use now requires a contract" cho truy cập thương mại; một blog nói từ 11/2025 truy cập API mới cần Reddit duyệt (**chưa xác minh**) |
| Kết luận sơ bộ | **Không đề xuất** cho giai đoạn này: khả năng cao cần hợp đồng/duyệt thủ công, NichePilot là công cụ nghiên cứu thương mại |

### 1.5 Mastodon / Lemmy (fediverse)

Điều khoản do **từng instance** tự đặt; API công khai có giới hạn riêng mỗi máy chủ; nhiều instance cấm thu thập cho AI. Khả năng tìm
pain point: Thấp–Trung bình (dữ liệu phân tán, tìm kiếm toàn văn thường hạn chế). Toàn bộ chi tiết `UNKNOWN`. **Không đề xuất** lúc này.

## 2. Nguồn có thể trở thành `ALLOWED`

**Hiện tại: không nguồn nào đủ điều kiện `ALLOWED`.** Thiếu văn bản điều khoản gốc cho mọi nguồn.

| Thứ tự ưu tiên đề xuất | Nguồn | Lý do | Điều kiện để đề xuất `ALLOWED` |
|---|---|---|---|
| 1 | Hacker News (Algolia + Firebase) | Không key, không phí, giới hạn rộng, pain point B2B/dev rõ | Đọc điều khoản HN/YC + điều khoản dịch vụ HN Search của Algolia; không có điều cấm truy cập tự động/gửi nội dung cho AI; ghi `/sources` + chủ sở hữu duyệt |
| 2 | Stack Exchange API | Pain point chất lượng, nhiều lĩnh vực | Đọc API Terms + AUP gốc; xác nhận phân tích bằng AI (không huấn luyện) được phép; có thể cần hỏi Stack Overflow; app key do chủ sở hữu đăng ký |
| 3 | GitHub Search API | Dễ tích hợp, giới hạn rõ | Đọc ToS/AUP; chủ sở hữu tạo token; phạm vi hẹp (ngách phần mềm) |
| – | Reddit, Mastodon/Lemmy | Rủi ro điều khoản/hợp đồng | Hoãn |

Lưu ý ngưỡng bằng chứng: mỗi nguồn trên chủ yếu là **một** eTLD+1 → chỉ tạo 1 nhóm độc lập. Muốn đạt `EVIDENCE_SUFFICIENT` (≥ 2 nhóm)
bằng dữ liệu thật cần **ít nhất hai nguồn** được duyệt (ví dụ HN + Stack Exchange), hoặc thêm tìm kiếm web (S4–S11, đang `UNVERIFIED`).
SC-013 vẫn `BLOCKED`.

## 3. Tên miền tối thiểu cần mở (chỉ môi trường `nichepilot`, chờ chủ sở hữu duyệt)

**Giai đoạn A – chỉ đọc điều khoản/tài liệu (không gọi API dữ liệu):**

| Nguồn | Tên miền | Mục đích |
|---|---|---|
| HN | `hn.algolia.com` | Trang tài liệu API `/api` (giới hạn, điều kiện) |
| HN | `www.ycombinator.com` | Điều khoản HN (`/legal`) |
| HN | `www.algolia.com` | Điều khoản dịch vụ Algolia (nếu `/api` dẫn tới) – chỉ yêu cầu nếu cần |
| Stack Exchange | `api.stackexchange.com` | `/docs/throttle`, `/docs/authentication`, tài liệu endpoint |
| Stack Exchange | `stackoverflow.com` | `/legal/api-terms-of-use`, `/legal/acceptable-use-policy` |
| Stack Exchange | `stackapps.com` | Điều kiện đăng ký app key – chỉ yêu cầu nếu cần |
| GitHub | `docs.github.com` | ToS, Acceptable Use Policies, tài liệu Search API |

**Giai đoạn B – gọi API dữ liệu (chỉ sau khi nguồn được duyệt `ALLOWED`):** `hn.algolia.com`, `hacker-news.firebaseio.com`,
`api.stackexchange.com`, `api.github.com` – không yêu cầu bây giờ.

Không cần mở cho Reddit/Mastodon/Lemmy (đề xuất hoãn).

## 4. Nguồn tham khảo (kết quả tìm kiếm – SNIPPET)

- https://hn.algolia.com/api
- https://github.com/HackerNews/API (ĐÃ ĐỌC)
- https://apis.io/rate-limits/stackexchange/stackexchange-rate-limits/
- https://it176131.github.io/2024/03/09/stack-overflow-api.html
- https://stackoverflow.blog/2024/09/30/ongoing-community-data-protection/
- https://www.devclass.com/development/2024/07/30/stack-exchange-restricts-access-to-dump-of-user-contributed-data-critics-complain-this-contradicts-license/1625192
- https://wiki.archiveteam.org/index.php/Stack_Overflow
- https://www.techbloat.com/?p=1950639 (độ tin cậy thấp)
- https://docs.github.com/en/rest/search/search
- https://techcrunch.com/2024/05/09/reddit-locks-down-its-public-data-in-new-content-policy-says-use-now-requires-a-contract
- https://www.searchenginejournal.com/reddit-paid-api/485172/
- https://www.redditapis.com/blogs/reddit-api-commercial-use-licensing-explained-2026 (blog bên thứ ba)
