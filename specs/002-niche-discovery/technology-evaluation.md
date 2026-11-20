# Technology Evaluation – E1 (Constitution VII)

**Ngày**: 2026-11-20 | Nguồn dữ kiện: research R-02, R-03, R-05, R-12 (PyPI JSON API, GitHub, Docker Hub, đo trong môi trường tách biệt).
Điều gì chưa xác minh được ghi rõ "chưa xác minh". Mọi công nghệ dưới đây được đánh giá theo đủ 7 tiêu chí của Constitution VII: giấy phép,
tình trạng bảo trì, khả năng tích hợp, tài nguyên, khả năng thương mại hóa, rủi ro bảo mật, khả năng thay thế.

## 1. Công nghệ được dùng trong E1

| Công nghệ | Giấy phép | Bảo trì | Tích hợp | Tài nguyên | Thương mại hóa | Rủi ro bảo mật & giảm thiểu | Thay thế |
|---|---|---|---|---|---|---|---|
| **SearXNG** (image chính thức `2026.11.18-b867c56a5`, không sửa mã) | AGPL-3.0-or-later (nhãn OCI; README GitHub) – **copyleft mạng**, ghi rõ theo Constitution VII | Bản dựng hằng ngày (tag 2026-11-18, 2026-11-19 trên Docker Hub) | HTTP JSON API nội bộ (`/search?format=json`), cấu hình `settings.yml` (`keep_only`) | Image ≈ 402 MB; RAM nghỉ ≈ 103 MiB; CPU ≈ 0,4% (đo) | Dùng như dịch vụ riêng không sửa mã → không phát sinh nghĩa vụ công bố mã NichePilot; nếu sửa SearXNG phải công bố phần sửa cho người dùng mạng. Không phân phối lại image đã sửa | Engine mặc định tự kết nối ra ngoài khi khởi động → `keep_only` rỗng mặc định; chỉ mạng nội bộ, không publish cổng; `SEARXNG_SECRET` ngoài repo; limiter tắt chỉ vì không lộ ra ngoài | `SourceAdapter` → thay bằng `http_json_api` (API chính thức) mà không đổi nghiệp vụ |
| **trafilatura 2.3.1** | Apache-2.0 (deps: Apache-2.0, BSD-2/3, MIT, MPL-2.0 cấp file) | Bản 2026-10-06; deps courlan 2026-11-16, htmldate 2026-10-02 | Thư viện Python, gọi trong handler `page.fetch` | Nằm trong +65 MB nhóm gói nhẹ; không cần trình duyệt | Cho phép thương mại; MPL-2.0 (certifi, tqdm) không yêu cầu công bố mã khi không sửa | Phân tích HTML không tin cậy: giới hạn 3 MB, chỉ `text/html`, timeout 20 s, không thực thi JS; lxml cập nhật bản vá | `PageFetcher` interface → readability/jusText hoặc trình trích xuất khác |
| **protego 0.7.0** | BSD-3-Clause | Bản 2026-09-21 | Thư viện thuần Python | Rất nhỏ | Cho phép | Phân tích robots.txt không tin cậy – thư viện không thực thi mã; lỗi phân tích → thận trọng (không thu thập) | `urllib.robotparser` khi nâng Python ≥ 3.14 |
| **phonenumbers 9.0.43** | Apache-2.0 | Bản 2026-11-06 (cập nhật metadata thường xuyên) | Thư viện | Dữ liệu metadata vài chục MB (trong 65 MB) | Cho phép | Không I/O mạng | Regex theo quốc gia (kém chính xác) |
| **rapidfuzz 3.14.6** | MIT | Bản 2026-08-30 | Thư viện (C extension, wheel 3.13) | Nhỏ | Cho phép | Không I/O | `difflib` chuẩn (chậm hơn) |
| **tldextract 5.4.0** | BSD-3-Clause (deps requests, filelock, idna, requests-file) | Bản 2026-10-03 | Thư viện | Nhỏ | Cho phép | Mặc định tải Public Suffix List lúc chạy → **bắt buộc** `suffix_list_urls=()` dùng snapshot đóng gói; test dưới rào chắn socket | `publicsuffixlist` hoặc snapshot PSL tự quản |
| **Playwright 1.65.2** (tùy chọn, profile `browser-fetcher`, tắt mặc định) | Apache-2.0 (greenlet MIT); Chromium BSD-3 và giấy phép thành phần | Bản 2026-11-14 | `PageFetcher` riêng trong container riêng | Chưa đo (chỉ đo khi chủ sở hữu bật); ước tính vài trăm MB RAM/trang | Cho phép | Trình duyệt chạy nội dung không tin cậy → container riêng, không mount dữ liệu, giới hạn RAM; **không** dùng stealth/patch chống phát hiện bot | Bỏ profile; chỉ trang HTML tĩnh |
| **SimHash tự viết** | Mã NichePilot | – | Hàm thuần | Không đáng kể | – | Không I/O | Thư viện SimHash/MinHash |

## 2. Công nghệ được đánh giá nhưng KHÔNG dùng / chưa phê duyệt

| Công nghệ | Kết luận | Lý do (7 tiêu chí – điểm quyết định) |
|---|---|---|
| **Crawl4AI 0.9.5** | **Loại khỏi E1** (quyết định I1) – không phải dependency, không có trong compose/image/tasks | Rủi ro bảo mật/tuân thủ: phụ thuộc bắt buộc `playwright-stealth`, `patchright` (chống phát hiện bot) trái FR-006f, NFR-11; giấy phép: README mâu thuẫn về ghi công; tài nguyên: Chromium + `unclecode-litellm` fork, numpy, pillow; thay thế: Playwright trực tiếp |
| **spaCy 3.8.18 + `en_core_web_sm` 3.8.0** | **Chưa phê duyệt cho production** (I2); chỉ dev/test qua nhóm tùy chọn `pii-ner` khi chủ sở hữu bật cờ | Giấy phép: thư viện MIT, model MIT nhưng dữ liệu OntoNotes "commercial (licensed by Explosion)" – điều kiện thương mại chưa xác minh; bảo trì: bản 2026-10-26; tích hợp: `PiiEngine`; tài nguyên: +291 MB, RSS 151 MB (đo); bảo mật: không I/O mạng khi model cài sẵn; thay thế: gazetteer công cộng / NER khác (research R-05) |
| **Microsoft Presidio** | Không bắt buộc trong E1 | Khung MIT nhưng vẫn cần bộ nhận diện tên có giấy phép rõ; cắm được qua `PiiEngine` sau này |
| API tìm kiếm trả phí (Brave/Bing API…) | Không dùng (Q1) | Cần key trả phí; điều khoản chưa xác minh |
| Scrapy | Không dùng | Thừa cho 300 trang/lượt |

## 3. Kết luận

Mọi dependency production của E1 có giấy phép OSI rõ ràng (Apache-2.0/BSD/MIT; MPL-2.0 cấp file; AGPL-3.0 cho SearXNG như dịch vụ riêng đã
ghi nghĩa vụ). Không dependency nào có điều kiện giấy phép chưa rõ trong production. Công cụ nặng (trình duyệt) chỉ bật qua Compose profile
khi cần. Nhóm `pii-ner` chỉ dev/test cho tới khi chủ sở hữu phê duyệt.
