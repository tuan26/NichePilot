# NichePilot – Master Requirements (Tài liệu Yêu cầu Tổng thể)

| Thuộc tính | Giá trị |
|---|---|
| Phiên bản | 0.1.0 (Draft – chờ xác nhận) |
| Ngày tạo | 2026-11-18 |
| Tuân thủ | `.specify/memory/constitution.md` v1.0.0 |
| Phạm vi | Toàn bộ E0–E8, NFR, quy tắc nghiệp vụ, tiêu chí nghiệm thu MVP, lộ trình |
| Nguồn | Tài liệu "YÊU CẦU PHÁT TRIỂN DỰ ÁN NICHEPILOT" do chủ sở hữu cung cấp |

> Tên "NichePilot" là tên làm việc, chưa được xác nhận nhãn hiệu và tên miền.

---

## 1. Mục đích và phạm vi

NichePilot (Affiliate Automation OS – AAOS) là hệ thống AI Agent tự host, tự động hóa gần như toàn bộ
quy trình Affiliate Marketing quốc tế:

```
Khám phá ngách → Phân tích khách hàng → Tìm sản phẩm → Xác minh Affiliate Program
→ Nghiên cứu Keyword → Chiến lược → Bài viết/Video → Xuất bản → Doanh thu → Tối ưu
```

Hệ thống không chọn ngách chỉ dựa vào keyword hot; nó phải phát hiện thị trường nhỏ có nhu cầu thực,
khách hàng sẵn sàng trả tiền và có cơ hội hoa hồng.

### 1.1 Mô hình kinh doanh

| Giai đoạn | Mô hình |
|---|---|
| Hiện tại (MVP → GĐ4) | Chủ sở hữu tự dùng để kiếm tiền affiliate. Thị trường đầu tiên: Mỹ; mở rộng UK, CA, AU… Không giới hạn lĩnh vực. |
| Tương lai (GĐ5, tùy chọn) | Bán bản self-host, SaaS, multi-user, multi-workspace, billing. **Không triển khai trong MVP.** |

### 1.2 Tác nhân (Actors)

| Tác nhân | Mô tả |
|---|---|
| Chủ sở hữu (Owner) | Người dùng duy nhất trong MVP: cấu hình, chạy nghiên cứu, duyệt kết quả, phê duyệt hành động. |
| AI Agent | Các agent logic (mục 8) chạy trên Job Runtime chung. |
| Scheduler | Kích hoạt job theo lịch. |
| Hệ thống bên ngoài | Claude API, OpenAI API, SearXNG, website công khai, affiliate network, WordPress, YouTube, Postiz, Matomo… |

### 1.3 Quy ước

- **Mức ưu tiên:** `Must` (= "Bắt buộc"), `Should` (= "Nên có"), `Later` (= "Giai đoạn sau").
- **Giai đoạn:** `MVP` (GĐ1), `GĐ2`, `GĐ3`, `GĐ4`, `GĐ5`.
- **ID yêu cầu:** giữ nguyên ID gốc (`E0-01` … `E8-15`, `NFR-01` …) để không mất truy vết. Yêu cầu bổ
  sung được tách ra từ phần mô tả văn bản được đánh ID mới:
  `BR-xx` (quy tắc nghiệp vụ), `AI-xx` (AI provider/agent), `AUT-xx` (tự động hóa), `DATA-xx` (dữ liệu),
  `UI-xx` (giao diện chung), `QA-xx` (tình huống kiểm thử bắt buộc).
- **Kiểm thử (cột "KT"):** `U` unit, `I` integration, `A` API/contract, `E` end-to-end, `ACC` acceptance,
  `S` security, `M` kiểm tra thủ công có chủ đích (live API). Mỗi yêu cầu có ít nhất một loại.
- **Truy vết tới test case:** test case đặt mã `TC-<REQ-ID>-<nn>` (ví dụ `TC-E0-12-01`). Mỗi feature
  duy trì ma trận truy vết trong `specs/<feature>/` (spec → task → test). `/speckit-analyze` kiểm tra
  độ phủ trước khi triển khai.

---

## 2. Danh sách module

| Mã | Module | Giai đoạn | Spec Kit feature (dự kiến) |
|---|---|---|---|
| E0 | Foundation & AI Infrastructure | MVP | `specs/001-foundation-ai-infrastructure` |
| E1 | Autonomous Niche Discovery | MVP | `specs/002-niche-discovery` |
| E2 | Product & Affiliate Discovery | MVP | `specs/003-product-affiliate-discovery` |
| E3 | Keyword & Audience Research | MVP | `specs/004-keyword-audience-research` |
| E4 | Bilingual Dashboard | MVP | `specs/005-bilingual-dashboard` |
| E5 | AI Content Factory | GĐ2 | chưa tạo |
| E6 | AI Video Factory | GĐ2 | chưa tạo |
| E7 | Publishing & Distribution | GĐ3 | chưa tạo |
| E8 | Revenue Analytics & Optimization | GĐ3 | chưa tạo |

> Ghi chú phân tách: E4 phụ thuộc vào API của E0–E3. Phần khung frontend (đăng nhập, i18n, layout) nằm
> trong E0 (E0-01, E0-15); các trang nghiệp vụ nằm trong E4. Phạm vi chính xác của UI trong E0 là câu
> hỏi cần xác nhận (xem spec E0).

---

## 3. Yêu cầu chức năng

### 3.1 E0 — Foundation & AI Infrastructure (MVP)

Mục tiêu: nền tảng kỹ thuật để các AI Agent và module hoạt động độc lập nhưng phối hợp trong một hệ thống.

| ID | Yêu cầu | Ưu tiên | KT | Liên quan |
|---|---|---|---|---|
| E0-01 | Khởi tạo cấu trúc dự án frontend/backend | Must | I | NFR-07 |
| E0-02 | Thiết lập FastAPI (API backend, OpenAPI, health check) | Must | A | — |
| E0-03 | Thiết lập PostgreSQL | Must | I | AC-15 |
| E0-04 | Thiết lập database migration (nâng/hạ phiên bản schema) | Must | I | NFR-13 |
| E0-05 | Tích hợp Claude API | Must | U, I, M | AC-02 |
| E0-06 | Thiết kế interface hỗ trợ OpenAI API (provider dự phòng) | Must | U, I | AI-07 |
| E0-07 | Xây dựng AI Tool Registry | Must | U, I | AI-03, NFR-14 |
| E0-08 | Quản lý Agent Job và trạng thái | Must | U, I, A | AUT-03 |
| E0-09 | Hỗ trợ chạy thủ công và theo lịch | Must | I, A | AC-13 |
| E0-10 | Retry, timeout và error handling | Must | U, I | AC-14, NFR-03 |
| E0-11 | Theo dõi token và chi phí API | Must | U, I | E8-09 |
| E0-12 | Giới hạn ngân sách ngày/tháng/job | Must | U, I | AC-03, NFR-06 |
| E0-13 | Structured logging | Must | U, I | NFR-09 |
| E0-14 | Audit log | Must | U, I, S | — |
| E0-15 | Authentication cho Dashboard | Must | A, S, E | — |
| E0-16 | Quản lý cấu hình và API key an toàn | Must | U, S | NFR-05 |
| E0-17 | Docker Compose | Must | I, M | AC-01, NFR-10 |
| E0-18 | Unit test và integration test | Must | — (meta) | AC-17 |
| E0-19 | Backup/restore database | Should | I, M | — |
| E0-20 | Agent checkpoint và resume | Should | I | NFR-03 |

**Yêu cầu AI Provider & Agent (bổ sung từ mô tả E0 và mục VIII):**

| ID | Yêu cầu | Ưu tiên | KT |
|---|---|---|---|
| AI-01 | Claude API là provider mặc định; không dùng model local | Must | U |
| AI-02 | Cấu hình model theo loại tác vụ (task type → provider + model + tham số) | Must | U |
| AI-03 | Hỗ trợ structured output có schema validation; output sai schema bị từ chối và thử lại có giới hạn | Must | U, I |
| AI-04 | Hỗ trợ tool calling qua Tool Registry, kiểm tra quyền tool theo agent | Must | U, I |
| AI-05 | Giới hạn số bước agent và số lần gọi API cho mỗi job; không vòng lặp vô hạn | Must | U |
| AI-06 | Không gửi dữ liệu nhạy cảm không cần thiết cho LLM (lọc secret/PII trước khi gửi) | Must | U, S |
| AI-07 | Không tự chuyển provider nếu chưa được cấu hình fallback rõ ràng | Must | U |
| AI-08 | Mỗi Agent khai báo: input/output schema, tool permissions, timeout, token budget, retry policy, error handling, logging, acceptance criteria | Must | U |
| AI-09 | Dùng chung AI Provider, Tool Registry và Job Runtime cho mọi agent (không bắt buộc mỗi agent một service) | Must | I |
| AI-10 | Nội dung web thu thập được xử lý như dữ liệu không tin cậy (chống prompt injection) | Must | U, S |

### 3.2 E1 — Autonomous Niche Discovery (MVP) — *module quan trọng nhất*

| ID | Yêu cầu | Ưu tiên | KT | Liên quan |
|---|---|---|---|---|
| E1-01 | Cấu hình quốc gia và thị trường mục tiêu | Must | A, U | E4-13 |
| E1-02 | Tìm ngách không giới hạn lĩnh vực | Must | I, ACC | AC-04 |
| E1-03 | AI tự đề xuất ngách và micro-niche | Must | I, ACC | AC-04 |
| E1-04 | Thu thập vấn đề khách hàng từ nguồn công khai | Must | I | BR-01 |
| E1-05 | Phân nhóm pain point | Must | U, I | AC-05 |
| E1-06 | Xác định buyer persona (cấp ngách) | Must | I | E3-09, AC-05 |
| E1-07 | Đánh giá mức độ nghiêm trọng của vấn đề | Must | U, I | BR-03 |
| E1-08 | Tìm giải pháp hiện có | Must | I | — |
| E1-09 | Phát hiện khoảng trống thị trường | Must | I | — |
| E1-10 | Đánh giá khả năng chi trả | Must | I | — |
| E1-11 | Đánh giá khả năng kiếm tiền affiliate | Must | I | BR-06 |
| E1-12 | Phân tích mức cạnh tranh (cấp ngách) | Must | I | E3-11 |
| E1-13 | Đánh giá khả năng tiếp cận khách hàng | Must | I | E3-10 |
| E1-14 | Chấm điểm cơ hội của ngách (Opportunity Score) | Must | U | BR-03, AC-06 |
| E1-15 | Tính mức độ tin cậy của kết quả (Confidence Score) | Must | U | BR-04, AC-06 |
| E1-16 | Phát hiện ngách trùng/tương đồng | Must | U, I | — |
| E1-17 | Lưu nguồn và thời gian xác minh | Must | I | DATA-03, AC-07 |
| E1-18 | Tạo báo cáo xếp hạng ngách | Must | I, ACC | AC-16 |
| E1-19 | Chạy nghiên cứu theo lịch | Must | I | E0-09, AC-13 |
| E1-20 | Đánh giá lại ngách theo dữ liệu mới | Should | I | E8-14 |

**Đầu ra bắt buộc của mỗi ngách (BR-07):** tên ngách, micro-niche, quốc gia, nhóm khách hàng, pain points,
giải pháp hiện tại, khoảng trống thị trường, đối thủ, sản phẩm tiềm năng, khả năng kiếm tiền, kênh tiếp
cận, Opportunity Score, Confidence Score, nguồn tham khảo, rủi ro, đề xuất tiếp tục/loại bỏ.

**Nguồn dữ liệu cho phép:** công cụ tìm kiếm (Google hoặc tương đương), Reddit và diễn đàn công khai,
website đánh giá phần mềm, cộng đồng chuyên ngành, YouTube, website sản phẩm, trang so sánh, Google Trends
và nguồn xu hướng khác, nguồn có API hợp lệ. Không giả định mọi nguồn có API miễn phí (BR-01).

### 3.3 E2 — Product & Affiliate Discovery (MVP)

| ID | Yêu cầu | Ưu tiên | KT | Liên quan |
|---|---|---|---|---|
| E2-01 | Tìm sản phẩm theo ngách và pain point | Must | I, ACC | AC-08 |
| E2-02 | Tìm website sản phẩm chính thức | Must | I | — |
| E2-03 | Tìm chương trình affiliate | Must | I | — |
| E2-04 | Xác minh chương trình affiliate | Must | I | BR-02 |
| E2-05 | Thu thập tỷ lệ hoa hồng | Must | U, I | BR-02 |
| E2-06 | Thu thập thời hạn cookie | Must | U, I | BR-02 |
| E2-07 | Thu thập phương thức thanh toán | Must | I | BR-02 |
| E2-08 | Kiểm tra điều kiện đăng ký từ Việt Nam | Must | I | BR-02 |
| E2-09 | Kiểm tra quốc gia được phép quảng bá | Must | I | — |
| E2-10 | Kiểm tra giới hạn quảng cáo (ví dụ cấm brand bidding, cấm coupon site) | Must | I | — |
| E2-11 | Thu thập giá và tính năng sản phẩm | Must | I | BR-02 |
| E2-12 | Xác định khách hàng mục tiêu của sản phẩm | Must | I | — |
| E2-13 | Loại bỏ sản phẩm trùng | Must | U, I | — |
| E2-14 | Chấm điểm sản phẩm | Must | U | BR-04 |
| E2-15 | Lưu nguồn và thời gian xác minh | Must | I | DATA-03, AC-07 |
| E2-16 | Theo dõi thay đổi điều khoản affiliate | Should | I | — |
| E2-17 | Tích hợp API affiliate network | Later | I | — |

Quy tắc: thuộc tính không tìm được lưu `UNKNOWN` (AC-09); không tự đăng ký tài khoản affiliate hoặc chấp
nhận điều khoản khi chưa được phê duyệt (BR-08, AC-19).

### 3.4 E3 — Keyword & Audience Research (MVP)

| ID | Yêu cầu | Ưu tiên | KT | Liên quan |
|---|---|---|---|---|
| E3-01 | Tạo keyword từ ngách và pain point | Must | I, ACC | AC-10 |
| E3-02 | Tìm long-tail keyword | Must | I | — |
| E3-03 | Tìm commercial-intent keyword | Must | I | — |
| E3-04 | Phân loại search intent | Must | U, I | AC-11 |
| E3-05 | Phân tích kết quả tìm kiếm (SERP) | Must | I | — |
| E3-06 | Phân tích nội dung đối thủ | Must | I | AC-11, BR-09 |
| E3-07 | Phân nhóm keyword (cluster) | Must | U, I | — |
| E3-08 | Phát hiện content gap | Must | I | — |
| E3-09 | Phân tích buyer persona (cấp keyword/cluster, mở rộng từ E1-06) | Must | I | E1-06 |
| E3-10 | Tìm cộng đồng và kênh tiếp cận | Must | I | E1-13 |
| E3-11 | Đánh giá mức cạnh tranh (cấp keyword) | Must | U, I | E1-12 |
| E3-12 | Chấm điểm keyword | Must | U | BR-04 |
| E3-13 | Đề xuất content strategy | Must | I, ACC | — |
| E3-14 | Tích hợp Google Search Console | Should | I | — |
| E3-15 | Theo dõi thay đổi SERP | Should | I | — |

Quy tắc: không bịa search volume, CPC hoặc keyword difficulty (BR-05).

### 3.5 E4 — Bilingual Dashboard (MVP)

| ID | Yêu cầu | Ưu tiên | KT | Liên quan |
|---|---|---|---|---|
| E4-01 | Dashboard tiếng Việt và tiếng Anh | Must | E | AC-12 |
| E4-02 | Mặc định tiếng Việt | Must | E | — |
| E4-03 | Có nút chuyển VI/EN | Must | E | — |
| E4-04 | Ghi nhớ ngôn ngữ đã chọn | Must | E | — |
| E4-05 | Dịch menu, form, thông báo và lỗi | Must | U, E | UI-08 |
| E4-06 | Định dạng ngày tháng và số theo locale | Must | U | — |
| E4-07 | Ngôn ngữ giao diện độc lập với ngôn ngữ nội dung | Must | U, A | BR-10 |
| E4-08 | Trang Tổng quan | Must | E | — |
| E4-09 | Trang Niche Discovery | Must | E | E1 |
| E4-10 | Trang Product Discovery | Must | E | E2 |
| E4-11 | Trang Keyword Research | Must | E | E3 |
| E4-12 | Trang Agent Jobs | Must | E | E0-08 |
| E4-13 | Trang Settings | Must | E | E0-16 |
| E4-14 | Hiển thị nguồn và Confidence Score | Must | E | AC-07 |
| E4-15 | Hiển thị chi phí API | Must | E | E0-11 |
| E4-16 | Xuất báo cáo CSV/Excel | Should | I, E | — |
| E4-17 | Content Calendar | Later | E | E7-13 |
| E4-18 | Revenue Dashboard | Later | E | E8-10 |

**Cấu hình ngôn ngữ (BR-10):** dashboard mặc định tiếng Việt; thị trường mặc định Mỹ; ngôn ngữ nội dung
mặc định tiếng Anh; ngôn ngữ nghiên cứu theo thị trường; các cấu hình thay đổi độc lập.

**Yêu cầu UI chung (mục X):**

| ID | Yêu cầu | Ưu tiên | KT |
|---|---|---|---|
| UI-01 | Responsive (desktop ưu tiên, dùng được trên tablet/mobile) | Must | E |
| UI-02 | Không hiển thị thông tin kỹ thuật không cần thiết (stack trace, ID nội bộ) | Must | E |
| UI-03 | Bộ lọc, tìm kiếm, sắp xếp trên các danh sách | Must | E |
| UI-04 | Hiển thị trạng thái xử lý (job đang chạy, tiến độ) | Must | E |
| UI-05 | Có loading / error / empty states | Must | E |
| UI-06 | Xem được bằng chứng nguồn | Must | E |
| UI-07 | Xem được chi phí AI | Must | E |
| UI-08 | Hỗ trợ VI/EN đầy đủ, không chuỗi hard-code | Must | U, E |

Trang dự kiến toàn hệ thống (12 trang): Tổng quan, Khám phá ngách, Sản phẩm Affiliate, Nghiên cứu Keyword,
Khách hàng & đối thủ, Kế hoạch nội dung, Quản lý bài viết, Quản lý video, Lịch xuất bản, Phân tích doanh
thu, AI Jobs & Logs, Cài đặt. **MVP chỉ triển khai các trang phục vụ E0–E4.**

### 3.6 E5 — AI Content Factory (GĐ2)

| ID | Yêu cầu | Ưu tiên | KT |
|---|---|---|---|
| E5-01 | Tạo content plan | Must | I |
| E5-02 | Chọn keyword và search intent | Must | I |
| E5-03 | Nghiên cứu nguồn trước khi viết | Must | I |
| E5-04 | Tạo SEO outline | Must | I |
| E5-05 | Viết bài tiếng Anh (theo ngôn ngữ thị trường) | Must | I, ACC |
| E5-06 | Hỗ trợ bài review và comparison | Must | I |
| E5-07 | Hỗ trợ bài tutorial và alternatives | Must | I |
| E5-08 | Tạo SEO title và meta description | Must | U, I |
| E5-09 | Tạo CTA | Must | I |
| E5-10 | Chèn affiliate link | Must | U, I |
| E5-11 | Chèn affiliate disclosure | Must | U |
| E5-12 | Fact checking | Must | I |
| E5-13 | Kiểm tra nội dung trùng | Must | U, I |
| E5-14 | Lưu lịch sử phiên bản | Must | I |
| E5-15 | Tạo ảnh minh họa | Should | I |
| E5-16 | Tự cập nhật bài cũ | Should | I |

Quy tắc BR-11: không tạo review giả, không sao chép nội dung đối thủ, không tự khẳng định đã trải nghiệm
sản phẩm nếu chưa có bằng chứng.

### 3.7 E6 — AI Video Factory (GĐ2)

| ID | Yêu cầu | Ưu tiên | KT |
|---|---|---|---|
| E6-01 | Tạo video script | Must | I |
| E6-02 | Tạo hook mở đầu | Must | I |
| E6-03 | Chia scene | Must | U, I |
| E6-04 | Tạo giọng đọc tiếng Anh | Must | I |
| E6-05 | Tạo hoặc thu thập visual assets | Must | I |
| E6-06 | Ghép video, audio và hình ảnh | Must | I |
| E6-07 | Tạo subtitle | Must | I |
| E6-08 | Render MP4 16:9 | Must | I |
| E6-09 | Render MP4 9:16 | Must | I |
| E6-10 | Kiểm tra chất lượng video | Must | I |
| E6-11 | Lưu thông tin bản quyền assets | Must | U, I |
| E6-12 | Tạo thumbnail | Should | I |
| E6-13 | Tạo video demo phần mềm | Should | I |
| E6-14 | Tạo Shorts từ video dài | Should | I |
| E6-15 | Hỗ trợ video template | Should | I |

Hỗ trợ dạng video: demo, tutorial, comparison, faceless explainer. Quy tắc BR-12: không tạo hình ảnh hoặc
video giả mạo trải nghiệm thực tế của sản phẩm.

### 3.8 E7 — Publishing & Distribution (GĐ3)

| ID | Yêu cầu | Ưu tiên | KT |
|---|---|---|---|
| E7-01 | Kết nối WordPress | Must | I |
| E7-02 | Tạo draft bài viết | Must | I |
| E7-03 | Đăng bài theo lịch | Must | I |
| E7-04 | Kết nối YouTube API | Must | I |
| E7-05 | Upload video và metadata | Must | I |
| E7-06 | Quản lý affiliate link | Must | U, I |
| E7-07 | Kiểm tra link trước khi đăng | Must | U, I |
| E7-08 | Quản lý trạng thái xuất bản | Must | U |
| E7-09 | Retry khi đăng thất bại | Must | U, I |
| E7-10 | Chống đăng trùng | Must | U, I |
| E7-11 | Hỗ trợ REVIEW/AUTO | Must | U, I |
| E7-12 | Tích hợp Postiz | Should | I |
| E7-13 | Quản lý Content Calendar | Should | E |

**Vòng đời nội dung (BR-13):** `DRAFT → VALIDATING → READY → APPROVED → SCHEDULED → PUBLISHED`;
trạng thái lỗi/ngoại lệ: `NEEDS_REVIEW`, `FAILED`, `CANCELLED`, `BLOCKED_BY_POLICY`.

### 3.9 E8 — Revenue Analytics & Optimization (GĐ3)

| ID | Yêu cầu | Ưu tiên | KT |
|---|---|---|---|
| E8-01 | Theo dõi traffic | Must | I |
| E8-02 | Theo dõi affiliate click | Must | I |
| E8-03 | Theo dõi hiệu quả theo niche | Must | I |
| E8-04 | Theo dõi hiệu quả theo sản phẩm | Must | I |
| E8-05 | Theo dõi hiệu quả theo keyword | Must | I |
| E8-06 | Import conversion | Must | I |
| E8-07 | Theo dõi commission | Must | U, I |
| E8-08 | Tính EPC và conversion rate | Must | U |
| E8-09 | Theo dõi chi phí AI (tái sử dụng dữ liệu E0-11) | Must | I |
| E8-10 | Dashboard doanh thu | Must | E |
| E8-11 | AI phân tích nội dung kém hiệu quả | Should | I |
| E8-12 | AI đề xuất tối ưu CTA | Should | I |
| E8-13 | AI đề xuất keyword mới | Should | I |
| E8-14 | AI đánh giá lại niche | Should | I |
| E8-15 | Phân tích ROI | Should | U, I |

Quy tắc BR-14: không coi affiliate click là sale; không coi pending commission là doanh thu đã nhận.

---

## 4. Quy tắc nghiệp vụ (Business Rules)

| ID | Quy tắc | Áp dụng | KT |
|---|---|---|---|
| BR-01 | Chỉ thu thập từ nguồn công khai hoặc API hợp lệ; tôn trọng robots.txt, ToS, rate limit; không giả định API miễn phí | E1–E3 | U, I |
| BR-02 | Thuộc tính không xác minh được lưu `UNKNOWN`; suy luận AI gắn `INFERRED`; nguồn mâu thuẫn gắn `CONFLICTING` kèm mọi giá trị | E1–E3 | U |
| BR-03 | Opportunity Score ngách = tổng có trọng số của 6 tiêu chí: Mức độ nghiêm trọng vấn đề 25%, Khả năng kiếm tiền 20%, Khoảng trống thị trường 20%, Khả năng tiếp cận khách hàng 15%, Cơ hội cạnh tranh 10%, Tính ổn định nhu cầu 10%. Trọng số cấu hình được, tổng = 100%, có phiên bản | E1 | U |
| BR-04 | Confidence Score tách biệt hoàn toàn với Opportunity Score; phản ánh số lượng, độ đa dạng, độ mới và độ nhất quán của bằng chứng; tiêu chí `UNKNOWN` làm giảm Confidence chứ không được gán điểm giả | E1–E3 | U |
| BR-05 | Không bịa search volume, CPC, keyword difficulty, số liệu thị trường; nếu không có nguồn dữ liệu hợp lệ thì hiển thị `UNKNOWN` | E1, E3 | U |
| BR-06 | Ngách không có chương trình affiliate phù hợp phải gắn cờ rủi ro monetization | E1, E2 | U |
| BR-07 | Mỗi ngách phải có đủ trường đầu ra liệt kê ở mục 3.2 (trường thiếu dữ liệu = `UNKNOWN`) | E1 | U, ACC |
| BR-08 | Không tự đăng ký affiliate, chấp nhận điều khoản hay xuất bản khi chưa có approval; MVP vô hiệu hóa hoàn toàn | Toàn hệ thống | I, ACC |
| BR-09 | Phân tích nội dung đối thủ chỉ để rút ra cấu trúc/khoảng trống; không lưu trữ hoặc tái xuất bản nguyên văn quá mức trích dẫn | E3, E5 | U |
| BR-10 | Ngôn ngữ giao diện, ngôn ngữ nghiên cứu, ngôn ngữ nội dung là 3 cấu hình độc lập (mặc định VI / theo thị trường / EN) | E4, E1–E5 | U, A |
| BR-11 | Nội dung không có review giả, không sao chép, không tuyên bố trải nghiệm không có bằng chứng; luôn có affiliate disclosure | E5 | U, I |
| BR-12 | Video không giả mạo trải nghiệm sản phẩm; lưu nguồn và giấy phép của mọi asset | E6 | U |
| BR-13 | Vòng đời nội dung theo state machine ở mục 3.8; chuyển trạng thái không hợp lệ bị từ chối | E7 | U |
| BR-14 | Click ≠ sale; pending commission ≠ doanh thu đã nhận | E8 | U |
| BR-15 | Keyword hot không phải điều kiện bắt buộc; ngách search volume thấp vẫn có thể xếp hạng cao | E1 | U |

---

## 5. Tự động hóa (REVIEW / AUTO / Scheduler)

| ID | Yêu cầu | Ưu tiên | GĐ | KT |
|---|---|---|---|---|
| AUT-01 | Chế độ REVIEW: AI nghiên cứu/tạo/đề xuất; hành động bên ngoài chờ phê duyệt khi chính sách yêu cầu | Must | MVP (khung), GĐ3 (đầy đủ) | U, I |
| AUT-02 | Chế độ AUTO: chỉ thực hiện hành động đã cấu hình và cấp quyền; không bỏ qua ngân sách, chính sách nền tảng, giới hạn API, quyền truy cập, kiểm tra chất lượng, phê duyệt bắt buộc | Must | GĐ3 | U, I |
| AUT-03 | Scheduler: chạy thủ công, theo lịch, chạy lại job lỗi, tạm dừng, tiếp tục, hủy, xem lịch sử | Must | MVP | I, A |
| AUT-04 | Không tự động chạy job tốn phí khi chưa cấu hình ngân sách | Must | MVP | U, I |
| AUT-05 | Chạy lại job không tạo dữ liệu trùng (idempotency) | Must | MVP | I |

---

## 6. Yêu cầu phi chức năng

| ID | Nhóm | Yêu cầu | Tiêu chí đo | KT |
|---|---|---|---|---|
| NFR-01 | Hiệu năng | Chạy trên CPU 4 core, RAM 15 GB | Stack MVP chạy ổn định với tổng RAM container ≤ 6 GB ở trạng thái nghỉ (mục tiêu, xác nhận trong plan) | M |
| NFR-02 | Khả dụng | Không yêu cầu GPU | Không có dependency GPU trong image | I |
| NFR-03 | Tin cậy | Retry, timeout, checkpoint | Job bị gián đoạn tiếp tục được từ bước cuối hoàn thành | I |
| NFR-04 | Dữ liệu | Không bịa dữ liệu hoặc bằng chứng | 100% kết luận có evidence hoặc `UNKNOWN` | U, ACC |
| NFR-05 | Bảo mật | Bảo vệ API keys và thông tin đăng nhập | 0 secret xuất hiện trong log, response, git | S |
| NFR-06 | Chi phí | Giới hạn ngân sách AI | 0 lời gọi tốn phí được thực hiện khi ngân sách đã hết | U, I |
| NFR-07 | Kiến trúc | Module độc lập, dễ thay thế | Provider thay được qua cấu hình/adapter, không sửa nghiệp vụ | U |
| NFR-08 | Kiểm thử | Unit, integration, end-to-end | Mỗi requirement Must có ≥ 1 test | — |
| NFR-09 | Vận hành | Structured logging, monitoring | Log dạng JSON có correlation ID (job_id, request_id); có health endpoint | U |
| NFR-10 | Triển khai | Docker Compose, self-host | Một lệnh khởi động toàn bộ stack MVP | M |
| NFR-11 | Tuân thủ | Tôn trọng ToS, bản quyền, affiliate policy | Có kiểm tra robots.txt; có cờ chính sách | U |
| NFR-12 | Đa ngôn ngữ | Dashboard VI/EN | 100% chuỗi UI có bản dịch ở cả 2 ngôn ngữ (kiểm tra tự động) | U |
| NFR-13 | Bảo trì | Có tài liệu và migration | Migration up/down chạy sạch; README vận hành | I |
| NFR-14 | An toàn AI | Giới hạn tool calling và hành động bên ngoài | Tool ngoài danh sách quyền bị từ chối | U |
| NFR-15 | Chất lượng | Có nguồn, confidence và validation | Mọi output AI qua schema validation | U |

---

## 7. Yêu cầu dữ liệu

| ID | Yêu cầu | Ưu tiên | KT |
|---|---|---|---|
| DATA-01 | Khóa chính UUID; foreign key; unique constraint; `created_at`/`updated_at` cho mọi bảng | Must | I |
| DATA-02 | Mọi thay đổi schema qua migration; chỉ tạo bảng cần cho feature đang triển khai | Must | I |
| DATA-03 | Truy vết nguồn: kết luận → `research_evidence` → `research_sources` (URL, thời điểm thu thập, thời điểm xác minh, nội dung trích) | Must | I |
| DATA-04 | Chuỗi liên kết niche → product → keyword → content → publication → revenue | Must (theo GĐ) | I |
| DATA-05 | Backup/restore database (= E0-19) | Should | I, M |
| DATA-06 | Mọi dữ liệu nghiệp vụ thuộc một `project` (chuẩn bị cho multi-workspace mà không triển khai multi-tenant) | Must | I |

Danh sách bảng dự kiến (tạo dần theo feature):

| Nhóm | Bảng | Feature tạo dự kiến |
|---|---|---|
| Hệ thống | `users`, `settings`, `agent_jobs`, `job_steps`, `tool_executions`, `ai_usage_logs`, `audit_logs`, `approval_requests`, `integration_connections` | E0 (riêng `approval_requests`, `integration_connections` có thể để tới khi cần) |
| Nghiên cứu thị trường | `projects`, `niches`, `niche_evaluations`, `pain_points`, `buyer_personas`, `research_sources`, `research_evidence`, `competitors` | E0 (`projects`, `research_sources`, `research_evidence` – hạ tầng bằng chứng dùng chung) + E1 |
| Sản phẩm | `products`, `affiliate_programs`, `affiliate_applications`, `affiliate_links` | E2 (`affiliate_links` – GĐ2/3) |
| Keyword | `keywords`, `keyword_clusters`, `market_research_reports` | E3 (`market_research_reports` có thể từ E1) |
| Nội dung | `content_plans`, `articles`, `article_versions`, `video_projects`, `video_scenes`, `media_assets`, `publications` | E5–E7 |
| Phân tích | `analytics_events`, `conversion_records`, `commission_records`, `revenue_reports`, `optimization_recommendations` | E8 |

---

## 8. AI Agent (logic)

| Agent | Nhiệm vụ | Feature | GĐ |
|---|---|---|---|
| AI Manager | Điều phối toàn hệ thống (MVP: điều phối pipeline nghiên cứu xác định; GĐ4: tăng cường tự chủ) | E0/E1 | MVP (tối thiểu) |
| Niche Discovery Agent | Tìm và đánh giá ngách | E1 | MVP |
| Audience Research Agent | Phân tích khách hàng | E1/E3 | MVP |
| Product Discovery Agent | Tìm sản phẩm | E2 | MVP |
| Affiliate Verification Agent | Xác minh chương trình affiliate | E2 | MVP |
| Keyword Research Agent | Tìm và đánh giá keyword | E3 | MVP |
| Content Strategy Agent | Lập kế hoạch nội dung (MVP: chỉ đề xuất strategy E3-13) | E3/E5 | MVP/GĐ2 |
| Article Writer Agent | Tạo bài viết | E5 | GĐ2 |
| Fact Checker Agent | Kiểm tra nguồn và tuyên bố | E5 | GĐ2 |
| Video Agent | Tạo video | E6 | GĐ2 |
| Publishing Agent | Xuất bản | E7 | GĐ3 |
| Analytics Agent | Phân tích dữ liệu | E8 | GĐ3 |
| Optimization Agent | Đề xuất cải thiện | E8 | GĐ3/4 |

Mỗi agent tuân theo AI-08. Không bắt buộc mỗi agent là một service hay model riêng (AI-09).

---

## 9. Tình huống kiểm thử bắt buộc

| ID | Tình huống | Feature chịu trách nhiệm chính |
|---|---|---|
| QA-01 | Claude API timeout | E0 |
| QA-02 | Claude API trả dữ liệu sai schema | E0 |
| QA-03 | Không tìm thấy sản phẩm | E2 |
| QA-04 | Affiliate program không xác minh được | E2 |
| QA-05 | Nguồn dữ liệu mâu thuẫn | E1, E2 |
| QA-06 | Search engine bị rate limit | E1 (adapter search) |
| QA-07 | Crawl thất bại | E1 (adapter crawl) |
| QA-08 | Database tạm thời mất kết nối | E0 |
| QA-09 | Job bị hủy | E0 |
| QA-10 | Job chạy lại không tạo trùng | E0 (cơ chế), E1–E3 (áp dụng) |
| QA-11 | Vượt ngân sách AI | E0 |
| QA-12 | Dashboard chuyển đổi VI/EN | E0 (khung), E4 |
| QA-13 | Không có dữ liệu (empty state) | E4 |
| QA-14 | Không có internet | E0 |
| QA-15 | API key sai hoặc hết hạn | E0 |

Loại test cho mỗi feature: unit, integration, API, error handling, validation, security phù hợp,
end-to-end khi cần, acceptance. Mock chỉ dùng trong test và phải phân biệt rõ.

---

## 10. Tiêu chí nghiệm thu MVP và truy vết

| ID | Tiêu chí | Requirement liên quan | Feature |
|---|---|---|---|
| AC-01 | Khởi động hệ thống trên Windows | E0-17, NFR-01, NFR-10 | E0 |
| AC-02 | Claude API hoạt động | E0-05, AI-01 | E0 |
| AC-03 | Có giới hạn chi phí AI | E0-11, E0-12, NFR-06 | E0 |
| AC-04 | AI tự tìm ngách khi chưa chọn ngành | E1-02, E1-03 | E1 |
| AC-05 | Ngách có pain point và buyer persona | E1-05, E1-06 | E1 |
| AC-06 | Có Opportunity Score và Confidence Score | E1-14, E1-15, BR-03, BR-04 | E1 |
| AC-07 | Có nguồn bằng chứng | E1-17, E2-15, DATA-03, E4-14 | E0, E1, E2, E4 |
| AC-08 | AI tìm sản phẩm affiliate phù hợp | E2-01…E2-04 | E2 |
| AC-09 | Thông tin chưa xác minh đánh dấu UNKNOWN | BR-02 | E1–E3 |
| AC-10 | AI tìm keyword theo niche | E3-01…E3-03 | E3 |
| AC-11 | Có phân tích intent và đối thủ | E3-04, E3-06 | E3 |
| AC-12 | Dashboard tiếng Việt/Anh | E4-01…E4-07 | E0, E4 |
| AC-13 | Chạy thủ công và theo lịch | E0-09, E1-19, AUT-03 | E0, E1 |
| AC-14 | Có logging và retry | E0-10, E0-13 | E0 |
| AC-15 | Dữ liệu lưu PostgreSQL | E0-03 | E0 |
| AC-16 | Có báo cáo nghiên cứu | E1-18, E3-13 | E1, E3 |
| AC-17 | Có automated tests | E0-18, NFR-08 | Tất cả |
| AC-18 | Có end-to-end test thực tế | NFR-08 | E4 (luồng đầy đủ) |
| AC-19 | Không tự đăng ký affiliate hoặc xuất bản trong MVP | BR-08 | Tất cả |
| AC-20 | Có hướng dẫn vận hành và cấu hình | NFR-13 | E0 (khởi tạo), mọi feature cập nhật |

---

## 11. Lộ trình sản phẩm (Product Roadmap)

| Giai đoạn | Phạm vi | Mục tiêu / Điều kiện hoàn thành |
|---|---|---|
| GĐ1 – MVP | E0 → E1 → E2 → E3 → E4 | Cấu hình thị trường Mỹ, chạy AI nghiên cứu tự động, nhận danh sách ngách, sản phẩm, keyword kèm bằng chứng và điểm. Đạt AC-01…AC-20. |
| GĐ2 | E5, E6 | Tạo bài viết SEO và video có kiểm chứng, lưu phiên bản; chưa xuất bản tự động. |
| GĐ3 | E7, E8 | Xuất bản qua API hợp lệ có REVIEW/AUTO; theo dõi traffic, click, conversion, commission. |
| GĐ4 | Tối ưu tự động, đa thị trường, AI Manager mạnh hơn | Tối ưu dựa trên dữ liệu thực. |
| GĐ5 (tùy chọn) | Multi-user, multi-workspace, licensing, SaaS, billing | Chỉ khi chủ sở hữu yêu cầu. |

Thứ tự trong MVP: mỗi feature đi đủ vòng Spec Kit; không bắt đầu feature tiếp theo khi feature trước
chưa qua Test & Verify.

---

## 12. Ngoài phạm vi MVP (tường minh)

- Xuất bản bài viết/video/social; đăng ký affiliate tự động; tạo nội dung (E5–E8).
- Multi-user, multi-tenant, SaaS, billing.
- LLM chạy local, yêu cầu GPU.
- Mua dữ liệu keyword trả phí (Ahrefs/Semrush…) – chỉ xem xét khi được phê duyệt riêng.
- Vượt paywall, CAPTCHA, đăng nhập trái phép vào nền tảng.

## 13. Giả định và rủi ro chính

| # | Giả định / Rủi ro | Ảnh hưởng | Hướng xử lý |
|---|---|---|---|
| R-01 | Không có nguồn search volume/CPC miễn phí đáng tin cậy | E1, E3 thiếu số liệu định lượng | Hiển thị `UNKNOWN`; dùng tín hiệu định tính (SERP, cộng đồng, xu hướng); cân nhắc GSC/nguồn trả phí sau |
| R-02 | Reddit/YouTube/Google hạn chế truy cập tự động | Thiếu bằng chứng | Dùng API chính thức nếu có, SearXNG làm meta-search, tôn trọng ToS |
| R-03 | Chi phí LLM cho nghiên cứu nhiều bước | Vượt ngân sách | Ngân sách cứng, cache, chọn model theo tác vụ |
| R-04 | Thông tin affiliate thay đổi thường xuyên | Dữ liệu cũ | Lưu thời điểm xác minh; E2-16 theo dõi thay đổi |
| R-05 | Môi trường Windows + Docker Desktop tiêu tốn RAM | Hiệu năng | Giới hạn tài nguyên container, Compose profiles |
| R-06 | Chủ sở hữu ở Việt Nam, nhiều chương trình hạn chế quốc gia | Không đăng ký được | E2-08 kiểm tra điều kiện, gắn cờ rủi ro |
