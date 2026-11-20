# Danh sách nguồn cần xác minh – E1

**Ngày lập**: 2026-11-20 | Liên quan: FR-006c…FR-006g, research R-01, R-13

Trạng thái hiện tại của **mọi** nguồn: `UNVERIFIED`, tắt. Việc xác minh **BLOCKED** trong môi trường cloud hiện tại vì mạng không truy
cập được các trang điều khoản (chủ sở hữu không đồng ý mở rộng mạng của môi trường dùng chung, 2026-11-20). Xác minh sẽ làm sau trên
môi trường có quyền truy cập phù hợp. Chưa xác minh được **không** phải lỗi implementation; kiểm thử tự động dùng adapter giả lập.

Quy tắc: chỉ đặt `ALLOWED` khi đã đọc văn bản chính thức và ghi đủ các mục ở §2. Không suy từ trí nhớ, blog hay việc "có API miễn
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
   `verification_note`, `allowed_access_methods` hoặc `permitted_use_scope`.
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
