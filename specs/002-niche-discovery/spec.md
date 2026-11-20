# Feature Specification: E1 – Autonomous Niche Discovery

**Feature Branch**: `claude/inspiring-wright-06dzhw` (thư mục spec: `specs/002-niche-discovery`)

**Created**: 2026-11-19

**Status**: Draft

**Input**: User description: "E1 — Autonomous Niche Discovery (module quan trọng nhất của MVP NichePilot). Chủ sở hữu chọn
thị trường/quốc gia mục tiêu (mặc định Mỹ), có thể không chọn lĩnh vực; AI tự khám phá ngách và micro-niche, thu thập
pain point từ nguồn công khai hợp lệ, đánh giá theo BR-03/BR-04, lưu bằng chứng, tạo báo cáo xếp hạng, chạy theo lịch. Tuân
thủ Niche-first, Evidence-first, Cost-aware; tái sử dụng kiến trúc E0; kiểm thử được hoàn toàn bằng mock; không gọi API có phí."

**Liên quan**: Master Requirements §3.2 (E1-01…E1-20), §4 (BR-01…BR-08, BR-10, BR-15), §5 (AUT-01, AUT-03…AUT-05), §6
(NFR-04, NFR-06, NFR-11, NFR-14, NFR-15), §7 (DATA-03, DATA-06), §9 (QA-05, QA-06, QA-07, QA-10); Constitution I–VI, IX, X, XII;
E0 (`specs/001-foundation-ai-infrastructure`, trạng thái `IMPLEMENTATION_COMPLETE / PENDING_EXTERNAL_VERIFICATION`).

## Clarifications

### Session 2026-11-19 (quyết định chủ sở hữu cho Q1–Q3 của /speckit-specify)

- Q: Nguồn dữ liệu thật trong E1? → A: Phương án A **bổ sung SearXNG**: kiến trúc Source Adapter thay thế được; E1 triển khai
  adapter tìm kiếm thật bằng **SearXNG** (tự host, mã nguồn mở) và adapter thu thập nội dung website công khai (ưu tiên
  **Crawl4AI** hoặc công cụ phù hợp được đánh giá trong plan); kiểm tra robots.txt, điều khoản sử dụng, giới hạn tốc độ; lưu URL,
  thời điểm thu thập, bằng chứng; có Mock Source Adapter cho kiểm thử; không cần API key tìm kiếm trả phí; không vượt CAPTCHA
  hay giới hạn truy cập; SearXNG không trả kết quả → ghi lỗi/thiếu dữ liệu, không tự tạo dữ liệu thay thế. Reddit API, YouTube
  API, Google Trends và nguồn chuyên biệt để feature sau. E1 MUST thu thập được dữ liệu thị trường thực tế (không chỉ chạy giả
  lập); khi chưa có Claude API key, phân tích của MockAIProvider chỉ dùng cho kiểm thử, không được coi là nghiên cứu AI thật.
- Q: Quy mô mặc định một lượt khám phá? → B: tối đa **20 ngách ứng viên/lượt**, hạn mức AI tối đa **$2/job**; cấu hình được theo
  từng lượt; không tự tăng ngân sách; giữ $3/ngày và $30/tháng của E0; vượt ngân sách → `PAUSED_BUDGET`, tiếp tục theo cơ chế E0;
  không đủ 20 ngách có bằng chứng → trả số lượng thực tế, không tạo ngách giả.
- Q: Giao diện E1? → B: API + **3 màn hình tối thiểu song ngữ** (mặc định tiếng Việt, chuyển được tiếng Anh): (1) danh sách lượt
  khám phá – lịch sử, trạng thái, chi phí, thao tác chạy/tạm dừng/hủy; (2) bảng xếp hạng ngách – ngách, Opportunity Score,
  Confidence Score, trạng thái xác minh, mức phù hợp affiliate; (3) chi tiết ngách – pain point, buyer persona, bằng chứng, nguồn,
  lý do chấm điểm, rủi ro, nút ghi quyết định. Giao diện đơn giản; có trạng thái loading/empty/error; có E2E cho luồng chính;
  không làm dashboard phân tích nâng cao (E4); không hiển thị dữ liệu mock như dữ liệu nghiên cứu thật.
- Ràng buộc chung nhắc lại: giữ kiến trúc E0; không dùng LLM local; Claude API chính, OpenAI dự phòng; không dùng Claude Pro
  hoặc Claude Code CLI làm backend; không gọi API có phí; không mở rộng sang E2–E8.

### Session 2026-11-19 (/speckit-clarify)

- Q: Hệ thống được phép dùng những máy tìm kiếm thượng nguồn nào qua SearXNG? → A: B (có bổ sung): mặc định chỉ bật nguồn có
  điều khoản cho phép truy vấn tự động theo phương thức tích hợp dự kiến; plan xác minh từng nguồn (điều khoản, API, giới hạn
  truy vấn, khả năng tích hợp SearXNG) và lưu URL điều khoản, ngày xác minh, trạng thái cho phép; nguồn chưa rõ điều khoản tắt;
  không vượt CAPTCHA/rate limit/cơ chế hạn chế; chủ sở hữu được thêm nguồn kèm cảnh báo + audit nhưng không được bật nguồn đã xác
  định bị cấm; không có nguồn hợp lệ → `NO_COMPLIANT_SEARCH_SOURCE`, không tạo dữ liệu thay thế; Source Adapter độc lập để bổ sung
  API tìm kiếm chính thức sau này.
- Q: Một ngách ứng viên cần tối thiểu bao nhiêu bằng chứng thật để vào bảng xếp hạng và được tính vào giới hạn 20 ngách? → A: B
  (có bổ sung): ≥ 2 bằng chứng pain point hợp lệ từ ≥ 2 nguồn độc lập; mỗi bằng chứng có URL, nội dung liên quan, thời điểm thu
  thập, trạng thái xác minh; khác tên miền nhưng sao chép cùng nội dung không tính là độc lập; AI đánh giá chất lượng, độ liên quan,
  tính độc lập (không chỉ đếm URL); không đạt → `INSUFFICIENT_EVIDENCE`, không xếp hạng, không tính vào 20, vẫn lưu để nghiên cứu/
  đánh giá lại; Opportunity và Confidence tính và hiển thị riêng; không tự tạo bằng chứng để đạt ngưỡng; không đủ 20 → trả số
  thực tế. Đạt ngưỡng bằng chứng ≠ có khả năng sinh lợi; khả năng kiếm tiền affiliate đánh giá riêng.
- Q: Mỗi lượt khám phá được chạy tối đa bao lâu và thu thập tối đa bao nhiêu trang? → A: B (có bổ sung): mặc định 90 phút,
  300 trang, mỗi tên miền ≤ 1 request/2 giây (mức trần; robots.txt/điều khoản/phản hồi máy chủ yêu cầu chậm hơn thì áp dụng mức
  chặt hơn), cấu hình được theo lượt; dừng sớm khi đủ bằng chứng hợp lệ; ưu tiên trang có khả năng cho bằng chứng pain point/
  persona/giải pháp, không crawl hàng loạt; phân bổ ngân sách crawl giữa các ngách, điều chỉnh theo chất lượng nhưng không vượt
  tổng; chạm giới hạn → dừng thu thập, lưu dữ liệu + checkpoint, đánh giá ngách đủ bằng chứng, ngách thiếu → `INSUFFICIENT_EVIDENCE`;
  kết quả `COMPLETED` / `PARTIAL_COMPLETED` kèm lý do (`TIME_LIMIT_REACHED`, `PAGE_LIMIT_REACHED`…); giới hạn thời gian/trang không
  thay giới hạn AI $2/job, $3/ngày, $30/tháng – chạm ngân sách → `PAUSED_BUDGET` (E0); lưu số liệu theo dõi; có test cho timeout,
  giới hạn trang, rate limiting, dừng sớm, kết thúc một phần, resume. Không tạo bằng chứng/ngách giả khi không đạt mục tiêu.
- Q: Khi một hoặc nhiều tiêu chí Opportunity là `UNKNOWN`, điểm cơ hội tính thế nào? → A: B (có bổ sung): chỉ dùng tiêu chí có dữ
  liệu hợp lệ, chuẩn hóa lại trọng số về 100%, không gán 0/100 cho `UNKNOWN`, tính bằng logic xác định; Coverage = tổng trọng số gốc
  của tiêu chí có dữ liệu, hiển thị cạnh Opportunity; Coverage < 60% → không có Opportunity chính thức, hiển thị
  `INSUFFICIENT_SCORING_DATA`; Confidence tính riêng, giảm khi thiếu dữ liệu quan trọng, không cao theo Opportunity; Monetization
  `UNKNOWN` vẫn tính được Opportunity nếu Coverage ≥ 60% nhưng gắn `MONETIZATION_UNVERIFIED`, không vào danh sách ưu tiên triển khai
  affiliate, vẫn ở danh sách nghiên cứu; xếp hạng chính thức cần đạt ngưỡng bằng chứng Q5 và Coverage ≥ 60%; tách bảng xếp hạng cơ
  hội nghiên cứu và danh sách ưu tiên triển khai affiliate; giao diện hiển thị Opportunity, Confidence, Coverage, tiêu chí `UNKNOWN`,
  trạng thái Monetization, giải thích điểm và dữ liệu thiếu; có test cho đủ/thiếu tiêu chí, Coverage = 60% và < 60%, Monetization
  `UNKNOWN`, dữ liệu mâu thuẫn/không hợp lệ, công thức chuẩn hóa và tính nhất quán thứ hạng. Opportunity cao không phải khả năng sinh
  lợi đã xác minh; không trình bày như dự báo doanh thu.
- Q: Thông tin cá nhân trong nội dung thu thập xử lý thế nào trước khi lưu bằng chứng và gửi AI? → A: C (có bổ sung): che PII
  (email, số điện thoại, @username, tên tác giả và thông tin nhận diện khác khi phát hiện được) bằng nhãn `[EMAIL]`, `[PHONE]`,
  `[USER]`, `[PERSON]` trước khi ghi database và trước khi gửi Claude/OpenAI; giữ nội dung pain point và ngữ cảnh; không lưu hồ sơ/
  liên hệ; không ghi PII chưa xử lý vào log, cache, checkpoint, báo cáo; không xử lý an toàn được → bỏ qua hoặc đánh dấu cần kiểm
  tra; chỉ lưu URL, thời điểm, trích đoạn đã che, trạng thái xác minh; hỗ trợ xóa/vô hiệu hóa bằng chứng theo yêu cầu hợp lệ, tính
  lại nguồn độc lập, Confidence và trạng thái xếp hạng (không đủ 2 nguồn → `INSUFFICIENT_EVIDENCE`), không dùng lại bằng chứng đã
  xóa, audit tối thiểu không chứa PII, chính sách cho cache và backup để dữ liệu đã xóa không quay lại sau restore; có test cho các
  điểm trên. Phát hiện PII không thể đúng 100% → kết hợp nhiều phương pháp, kiểm thử, và xử lý an toàn khi không chắc chắn.

### Session 2026-11-20 (chủ sở hữu phê duyệt có điều kiện Technical Plan E1)

- X1–X7 đồng ý. X4: erasure ledger lưu bền vững; khi restore phải áp dụng lại yêu cầu xóa **trước khi** dữ liệu được dùng hoặc trả qua
  API; không áp dụng đầy đủ được → restore **thất bại an toàn**; có test chứng minh dữ liệu đã xóa không xuất hiện lại. X8: chỉ thêm
  dependency sau khi xác minh giấy phép, phiên bản, tương thích; không tự cài model/thư viện nặng khi chưa đánh giá tài nguyên; không
  dùng dependency có giấy phép chưa rõ trong production.
- Công cụ thu thập: SearXNG (tìm kiếm OSS), `trafilatura` mặc định; Crawl4AI/Playwright tùy chọn cho trang cần JavaScript, không bật
  mặc định; ưu tiên giải pháp nhẹ cho CPU 4 core / RAM 15 GB.
- PII: spaCy + regex + phonenumbers; tiếng Anh dùng spaCy khi phù hợp; ngôn ngữ chưa hỗ trợ hoặc không chắc chắn → `NEEDS_REVIEW`;
  không gửi nội dung chưa xử lý an toàn cho AI; không lưu PII gốc vào DB/log/checkpoint; Presidio không bắt buộc; engine PII thay được
  qua interface chung.
- AI model: phân loại theo tác vụ (đơn giản → model tiết kiệm; phân tích phức tạp → model mạnh hơn khi cần); model ID và bảng giá phải
  xác minh trước khi gọi có phí; không hard-code model trong business logic; không tự bật API có phí; không dùng Claude Pro/Claude Code CLI.
- Nguồn: chỉ nguồn `ALLOWED` được chạy **tự động**; `UNVERIFIED` tắt mặc định và không được tự động bật để vượt kiểm tra; `PROHIBITED`
  không được dùng; không vượt CAPTCHA/rate limit/giới hạn truy cập; lưu URL điều khoản, ngày xác minh, phương thức truy cập được phép,
  phạm vi sử dụng; có API miễn phí không phải bằng chứng được phép dùng cho mọi mục đích; không có nguồn hợp lệ →
  `NO_COMPLIANT_SEARCH_SOURCE`. Thiết kế `SourceAdapter` hỗ trợ cả nguồn API chính thức, dữ liệu mở và dữ liệu được cấp phép sau này.
- Giới hạn mạng: không thay đổi mạng của môi trường dùng chung; nguồn chưa xác minh giữ `UNVERIFIED`; lập danh sách nguồn cần xác minh
  (URL chính thức + nội dung cần kiểm tra); cấu hình nguồn không cần sửa code; không tự xác nhận `ALLOWED` khi chưa có bằng chứng;
  không tự bật `UNVERIFIED` để chạy thử dữ liệu thật. Chưa xác minh được nguồn **không** phải lỗi implementation.

## User Scenarios & Testing *(mandatory)*

Tác nhân chính: **chủ sở hữu** (một người, tự host). Tác nhân phụ: **hệ thống** (job theo lịch, agent nghiên cứu).
Mọi kịch bản dưới đây phải chạy và kiểm thử được bằng nhà cung cấp AI giả lập và nguồn dữ liệu giả lập (dữ liệu gắn nhãn
`MOCK`), không cần API key, không phát sinh chi phí.

### User Story 1 - Khám phá ngách tự động khi chưa chọn lĩnh vực (Priority: P1)

Chủ sở hữu chọn thị trường (mặc định Mỹ, ngôn ngữ nghiên cứu theo thị trường) và bấm chạy một **lượt khám phá** mà không
chọn lĩnh vực nào. Hệ thống tự đề xuất danh sách ngách và micro-niche ứng viên từ nhiều lĩnh vực khác nhau, thu thập vấn đề
khách hàng từ nguồn công khai cho từng ứng viên, rồi trả về danh sách ngách có đủ các trường đầu ra bắt buộc (BR-07). Trường
nào không có dữ liệu được ghi `UNKNOWN`.

**Why this priority**: Đây là giá trị cốt lõi của toàn sản phẩm (Niche-first): chủ sở hữu không cần biết trước nên làm ngách
gì. Mọi module sau (E2 sản phẩm, E3 keyword) đều bắt đầu từ ngách được chọn ở đây.

**Independent Test**: Chạy một lượt khám phá với thị trường Mỹ, không chọn lĩnh vực, bằng AI và nguồn giả lập; kiểm tra lượt
chạy hoàn tất, sinh ra số ngách ứng viên trong giới hạn cấu hình, các ngách thuộc ít nhất 3 lĩnh vực khác nhau, mỗi ngách có
đủ 16 trường đầu ra bắt buộc (giá trị hoặc `UNKNOWN`) và mọi dữ liệu gắn `MOCK`.

**Acceptance Scenarios**:

1. **Given** ngân sách đã cấu hình và chưa chọn lĩnh vực, **When** chủ sở hữu chạy lượt khám phá cho thị trường Mỹ,
   **Then** hệ thống tạo một lượt khám phá có trạng thái theo dõi được và cuối cùng trả về danh sách ngách ứng viên, mỗi ngách
   có tên ngách, micro-niche, quốc gia, nhóm khách hàng, pain points, giải pháp hiện tại, khoảng trống thị trường, đối thủ,
   sản phẩm tiềm năng, khả năng kiếm tiền, kênh tiếp cận, Opportunity Score, Confidence Score, nguồn tham khảo, rủi ro, đề
   xuất tiếp tục/loại bỏ.
2. **Given** chủ sở hữu nhập lĩnh vực gợi ý (ví dụ "phần mềm cho tiệm sửa xe"), **When** chạy lượt khám phá, **Then** các ngách
   ứng viên tập trung vào lĩnh vực đó nhưng vẫn được đánh giá theo cùng quy tắc.
3. **Given** chưa cấu hình ngân sách (hạn mức bằng 0), **When** chủ sở hữu chạy lượt khám phá tốn phí, **Then** hệ thống từ
   chối và giải thích lý do (AUT-04), không tạo lời gọi AI nào.
4. **Given** một thuộc tính (ví dụ đối thủ) không tìm được bằng chứng, **When** lượt khám phá hoàn tất, **Then** thuộc tính đó
   ghi `UNKNOWN`, không có giá trị được tự tạo ra.
5. **Given** một ngách ứng viên chỉ có 1 bằng chứng pain point, hoặc 2 bằng chứng từ 2 tên miền nhưng cùng một nội dung sao
   chép, **When** lượt khám phá hoàn tất, **Then** ngách có trạng thái `INSUFFICIENT_EVIDENCE`, không xuất hiện trong bảng xếp hạng,
   không được tính vào giới hạn số ngách, và vẫn được lưu để nghiên cứu tiếp.
6. **Given** chỉ 7 ngách đạt ngưỡng bằng chứng trong giới hạn 20, **When** lượt khám phá hoàn tất, **Then** bảng xếp hạng có đúng 7
   ngách; hệ thống không tạo thêm ngách hay bằng chứng để đủ số.
7. **Given** lượt khám phá chạy bằng nhà cung cấp AI giả lập, **When** xem kết quả, **Then** mọi ngách, pain point, bằng chứng
   và báo cáo hiển thị nhãn dữ liệu giả lập và không xuất hiện trong báo cáo/xếp hạng mặc định (chỉ dữ liệu thật).

---

### User Story 2 - Pain point, buyer persona và bằng chứng có nguồn (Priority: P1)

Với mỗi ngách, chủ sở hữu xem các nhóm pain point (đã gom nhóm, có mức độ nghiêm trọng), buyer persona cấp ngách, giải pháp
hiện có và khoảng trống thị trường. Mỗi kết luận có trạng thái xác minh (`VERIFIED` / `INFERRED` / `UNKNOWN` /
`CONFLICTING`) và liên kết tới bằng chứng: nguồn (URL hoặc định danh), trích đoạn ngắn, thời điểm thu thập, thời điểm xác minh.

**Why this priority**: Evidence-first là nguyên tắc không thương lượng (Constitution I). Ngách không có bằng chứng thì
không có giá trị ra quyết định.

**Independent Test**: Với một lượt khám phá giả lập có dữ liệu nguồn cố định, kiểm tra mỗi pain point có ít nhất một bằng
chứng có nguồn và thời điểm, các bằng chứng trùng nội dung được gom về một nguồn, nhận định do AI suy luận gắn `INFERRED`,
và hai nguồn có giá trị khác nhau cho cùng thuộc tính tạo trạng thái `CONFLICTING` lưu đủ cả hai giá trị.

**Acceptance Scenarios**:

1. **Given** nguồn công khai cho biết người dùng phàn nàn về cùng một vấn đề bằng nhiều cách diễn đạt, **When** hệ thống
   phân tích, **Then** các phàn nàn được gom thành một nhóm pain point, có mức độ nghiêm trọng và số bằng chứng hỗ trợ.
2. **Given** hai nguồn đưa ra thông tin mâu thuẫn (QA-05), **When** lưu kết quả, **Then** thuộc tính được đánh dấu
   `CONFLICTING`, lưu mọi giá trị kèm nguồn, và Confidence Score của ngách giảm.
3. **Given** AI đưa ra một nhận định không có trích dẫn nguồn trực tiếp (ví dụ persona suy ra từ nhiều phàn nàn), **When**
   lưu, **Then** nhận định gắn `INFERRED` và tách biệt khỏi dữ liệu `VERIFIED`.
4. **Given** nội dung thu thập từ web chứa câu lệnh kiểu "bỏ qua hướng dẫn trước đó", **When** AI phân tích, **Then** nội dung
   chỉ được coi là dữ liệu; không có hành động nào ngoài phạm vi được cấp quyền xảy ra (prompt injection).
5. **Given** trích đoạn chứa email, số điện thoại, @username và tên tác giả, **When** lưu bằng chứng và gửi cho AI, **Then** các thông
   tin đó đã được thay bằng `[EMAIL]`, `[PHONE]`, `[USER]`, `[PERSON]` ở cả dữ liệu lưu và dữ liệu gửi AI; nội dung pain point vẫn
   giữ nguyên.
6. **Given** một đoạn nội dung mà bước che PII không chắc chắn xử lý an toàn, **When** thu thập, **Then** đoạn đó bị bỏ qua hoặc đánh
   dấu "cần kiểm tra", không được lưu dạng chưa che và không được gửi cho AI.
7. **Given** chủ sở hữu xóa một bằng chứng theo yêu cầu hợp lệ và ngách liên quan chỉ còn 1 nguồn độc lập, **When** xác nhận xóa,
   **Then** bằng chứng không còn được dùng, nguồn độc lập và Confidence được tính lại, ngách chuyển `INSUFFICIENT_EVIDENCE` và rời bảng
   xếp hạng; audit ghi thao tác xóa mà không chứa nội dung đã xóa.
8. **Given** đã xóa bằng chứng sau thời điểm của một bản backup, **When** khôi phục từ bản backup đó, **Then** bằng chứng đã xóa không
   xuất hiện lại trong hệ thống đang hoạt động (yêu cầu xóa được áp dụng lại trước khi dữ liệu được sử dụng).

---

### User Story 3 - Chấm điểm cơ hội và độ tin cậy, xếp hạng ngách (Priority: P1)

Hệ thống chấm **Opportunity Score** cho mỗi ngách bằng 6 tiêu chí có trọng số theo BR-03 (mặc định: mức độ nghiêm trọng vấn
đề 25%, khả năng kiếm tiền 20%, khoảng trống thị trường 20%, khả năng tiếp cận khách hàng 15%, cơ hội cạnh tranh 10%, tính ổn
định nhu cầu 10%) và **Confidence Score** tách biệt theo BR-04 (số lượng, độ đa dạng, độ mới và độ nhất quán của bằng chứng).
Chủ sở hữu xem bảng xếp hạng, xem điểm thành phần và phiên bản trọng số đã dùng, và có thể đổi trọng số (tạo phiên bản mới).

**Why this priority**: Không có điểm thì không so sánh và chọn được ngách; điểm phải tái lập được và không bị nhầm giữa
"hấp dẫn" và "chắc chắn" (Constitution II).

**Independent Test**: Với bộ dữ liệu đánh giá cố định, kiểm tra điểm được tính đúng theo công thức (tính tay), lưu điểm
thành phần và phiên bản trọng số, tiêu chí `UNKNOWN` không được gán điểm giả mà làm giảm Confidence, và đổi trọng số tạo
phiên bản mới trong khi kết quả cũ vẫn tái lập được.

**Acceptance Scenarios**:

1. **Given** một ngách có điểm thành phần cho cả 6 tiêu chí, **When** chấm điểm, **Then** Opportunity Score bằng tổng có
   trọng số theo phiên bản trọng số hiện hành, và điểm thành phần cùng phiên bản trọng số được lưu.
2. **Given** tiêu chí "khả năng kiếm tiền" là `UNKNOWN`, **When** chấm điểm, **Then** tiêu chí đó không được gán điểm giả;
   Opportunity Score ghi rõ tiêu chí thiếu dữ liệu và Confidence Score giảm.
3. **Given** chủ sở hữu đổi trọng số với tổng khác 100%, **When** lưu, **Then** hệ thống từ chối.
4. **Given** chủ sở hữu đổi trọng số hợp lệ, **When** lưu, **Then** một phiên bản trọng số mới được tạo có audit; các điểm cũ
   giữ nguyên phiên bản cũ; chủ sở hữu có thể chấm lại theo phiên bản mới mà không gọi lại AI.
5. **Given** ngách có search volume thấp nhưng pain point nghiêm trọng và khả năng chi trả cao, **When** xếp hạng, **Then** ngách
   vẫn có thể xếp hạng cao (BR-15); search volume không phải điều kiện bắt buộc.
6. **Given** không tìm được chương trình affiliate phù hợp cho một ngách, **When** đánh giá, **Then** ngách được gắn cờ rủi ro
   monetization (BR-06).
7. **Given** ngách có tiêu chí "khoảng trống thị trường" (20%) là `UNKNOWN`, các tiêu chí khác có điểm, **When** chấm điểm, **Then**
   Coverage = 80% và Opportunity = tổng (điểm × trọng số gốc) của 5 tiêu chí còn lại chia 0,80; giao diện hiển thị Coverage 80% và
   tiêu chí thiếu.
8. **Given** Coverage đúng 60%, **When** chấm điểm, **Then** có Opportunity chính thức; **Given** Coverage 55%, **Then** không có
   Opportunity chính thức, ngách hiển thị `INSUFFICIENT_SCORING_DATA` và không vào bảng xếp hạng cơ hội.
9. **Given** tiêu chí Monetization là `UNKNOWN` và Coverage 80%, **When** chấm điểm, **Then** có Opportunity chính thức, ngách gắn
   `MONETIZATION_UNVERIFIED`, xuất hiện trong bảng xếp hạng cơ hội nghiên cứu nhưng không xuất hiện trong danh sách ưu tiên triển
   khai affiliate.

---

### User Story 4 - Kiểm soát chi phí và độ bền của lượt khám phá (Priority: P1)

Mỗi lượt khám phá có hạn mức chi phí riêng và chạy trên hạ tầng job của E0: giữ chỗ ngân sách trước mỗi lời gọi AI, tạm dừng
khi hết ngân sách, tiếp tục từ checkpoint, hủy được, chạy lại không tạo dữ liệu trùng. Khi nguồn dữ liệu bị giới hạn tần suất
hoặc không truy cập được, lượt khám phá xử lý có kiểm soát và ghi rõ dữ liệu thiếu.

**Why this priority**: Cost-aware là nguyên tắc không thương lượng (Constitution VI); nghiên cứu tự động dễ tiêu tốn
nhiều lời gọi AI và truy cập nguồn bên ngoài.

**Independent Test**: Chạy lượt khám phá giả lập với hạn mức nhỏ → tạm dừng `PAUSED_BUDGET` đúng lúc, không có lời gọi vượt
hạn mức; tiếp tục sau khi tăng hạn mức → không lặp bước đã xong; chạy lại cùng cấu hình → không tạo ngách/bằng chứng trùng;
nguồn giả lập trả lỗi giới hạn tần suất / không truy cập được → lượt khám phá vẫn hoàn tất với dữ liệu thiếu ghi `UNKNOWN`.

**Acceptance Scenarios**:

1. **Given** hạn mức lượt khám phá sắp hết, **When** lời gọi AI kế tiếp có chi phí ước tính vượt phần còn lại, **Then** lượt
   khám phá chuyển `PAUSED_BUDGET`, không gửi lời gọi đó, các ngách đã đánh giá xong được giữ lại.
2. **Given** lượt khám phá bị tạm dừng hoặc worker bị dừng đột ngột, **When** tiếp tục, **Then** công việc tiếp tục từ bước
   cuối đã hoàn tất, không đánh giá lại ngách đã xong.
3. **Given** chạy lại lượt khám phá đã hoàn tất (hoặc lịch chạy lại), **When** gặp ngách đã có, **Then** hệ thống không tạo bản
   ghi trùng mà cập nhật/đánh giá lại theo quy tắc phát hiện trùng (QA-10, E1-16).
4. **Given** công cụ tìm kiếm trả lỗi giới hạn tần suất (QA-06), **When** thu thập, **Then** hệ thống chờ và thử lại có giới
   hạn theo chính sách nguồn; quá giới hạn thì bỏ qua nguồn đó, ghi lại lý do, và Confidence phản ánh dữ liệu thiếu.
5. **Given** một trang web không truy cập được hoặc robots.txt không cho phép (QA-07, NFR-11), **When** thu thập, **Then** trang
   đó bị bỏ qua, không vượt rào cản, lý do được ghi nhận.
6. **Given** chủ sở hữu hủy lượt khám phá, **When** hủy, **Then** không phát sinh thêm lời gọi AI hay truy cập nguồn mới; dữ liệu
   đã thu thập được giữ lại có trạng thái rõ ràng.
7. **Given** lượt khám phá chạm 90 phút hoặc 300 trang, **When** đạt giới hạn, **Then** hệ thống dừng thu thập, lưu dữ liệu và
   checkpoint, đánh giá các ngách đủ bằng chứng, chuyển ngách thiếu sang `INSUFFICIENT_EVIDENCE`, và kết thúc với kết quả
   `PARTIAL_COMPLETED` kèm lý do `TIME_LIMIT_REACHED` hoặc `PAGE_LIMIT_REACHED`.
8. **Given** mọi ngách ứng viên đã đủ bằng chứng hợp lệ trước khi chạm giới hạn, **When** đánh giá xong, **Then** lượt khám phá
   kết thúc sớm với kết quả `COMPLETED`, không thu thập thêm trang chỉ để đủ số.
9. **Given** robots.txt của một tên miền yêu cầu `Crawl-delay` 10 giây, **When** thu thập từ tên miền đó, **Then** khoảng cách giữa
   hai yêu cầu ≥ 10 giây (mức chặt hơn được ưu tiên so với mặc định 2 giây).
10. **Given** lượt khám phá đang `PAUSED_BUDGET` do hết ngân sách AI trong khi còn thời gian/trang, **When** chủ sở hữu tiếp tục sau khi
    đủ ngân sách, **Then** lượt khám phá tiếp tục từ checkpoint với phần giới hạn thời gian/trang còn lại.

---

### User Story 5 - Phát hiện ngách trùng/tương đồng (Priority: P2)

Khi khám phá nhiều lần hoặc trong cùng một lượt, hệ thống nhận ra ngách trùng hoặc gần giống (cùng nhóm khách hàng và cùng
vấn đề cốt lõi, tên khác nhau) và gộp hoặc liên kết chúng thay vì tạo bản ghi mới.

**Why this priority**: Tránh lãng phí chi phí đánh giá lại và tránh bảng xếp hạng bị lặp; nhưng lượt khám phá đơn lẻ vẫn có
giá trị khi chưa có tính năng này.

**Independent Test**: Đưa vào các ngách ứng viên có tên khác nhưng cùng khách hàng và vấn đề → hệ thống đánh dấu trùng/tương
đồng, không tạo ngách mới; hai ngách thật sự khác nhau không bị gộp nhầm.

**Acceptance Scenarios**:

1. **Given** ngách "phần mềm đặt lịch cho tiệm cắt tóc" đã tồn tại, **When** lượt khám phá mới đề xuất "ứng dụng quản lý lịch
   hẹn barber shop", **Then** hệ thống nhận diện là trùng, liên kết bằng chứng mới vào ngách cũ.
2. **Given** hai ngách cùng lĩnh vực nhưng khác nhóm khách hàng, **When** so sánh, **Then** không bị coi là trùng.
3. **Given** hệ thống không chắc chắn hai ngách có trùng không, **When** so sánh, **Then** đánh dấu "có thể tương đồng" để chủ
   sở hữu quyết định, không tự gộp.

---

### User Story 6 - Báo cáo xếp hạng và quyết định của chủ sở hữu (Priority: P2)

Chủ sở hữu xem báo cáo xếp hạng ngách của một lượt khám phá hoặc toàn bộ project (bằng tiếng Việt hoặc tiếng Anh theo ngôn
ngữ giao diện), lọc theo điểm và độ tin cậy, xem chi tiết từng ngách cùng bằng chứng, và ghi quyết định: tiếp tục, theo dõi,
hoặc loại bỏ (chế độ REVIEW – AI chỉ đề xuất, chủ sở hữu quyết định).

**Why this priority**: Báo cáo là đầu ra mà chủ sở hữu dùng để chọn ngách cho E2/E3 (E1-18, AC-16); quyết định được ghi nhận
giúp E2/E3 biết ngách nào được theo đuổi.

**Independent Test**: Sau lượt khám phá giả lập, lấy báo cáo xếp hạng → sắp xếp đúng theo điểm, hiển thị cả hai điểm và
các trường bắt buộc, mặc định loại dữ liệu `MOCK` (chỉ hiện khi yêu cầu rõ); ghi quyết định cho một ngách → có audit, trạng thái
ngách thay đổi, đề xuất của AI vẫn được lưu riêng.

**Acceptance Scenarios**:

1. **Given** project có ngách thật và ngách giả lập, **When** lấy báo cáo xếp hạng mặc định, **Then** chỉ ngách thật xuất hiện;
   ngách giả lập chỉ xuất hiện khi chủ sở hữu yêu cầu rõ và luôn có nhãn.
2. **Given** báo cáo xếp hạng, **When** chủ sở hữu xem một ngách, **Then** thấy điểm thành phần, phiên bản trọng số, mọi kết luận
   kèm trạng thái xác minh và liên kết tới bằng chứng.
3. **Given** AI đề xuất "tiếp tục" cho một ngách, **When** chủ sở hữu ghi quyết định "loại bỏ" kèm lý do, **Then** quyết định được
   lưu cùng audit (ai, khi nào, trước/sau), đề xuất của AI không bị ghi đè.

---

### User Story 7 - Nghiên cứu theo lịch và đánh giá lại (Priority: P3)

Chủ sở hữu tạo lịch chạy khám phá định kỳ (dùng scheduler của E0) và/hoặc lịch đánh giá lại các ngách đang theo dõi khi có
dữ liệu mới (E1-19, E1-20). Lịch tốn phí bị từ chối khi chưa cấu hình ngân sách.

**Why this priority**: Tự động hóa giúp phát hiện ngách mới và thay đổi theo thời gian, nhưng chạy thủ công đã đủ cho giá trị
ban đầu.

**Independent Test**: Tạo lịch khám phá với ngân sách đã cấu hình → đến hạn tạo đúng một lượt khám phá; tạo lịch khi ngân sách
bằng 0 → bị từ chối; đánh giá lại một ngách đang theo dõi với bằng chứng mới → điểm mới được lưu thành một lần đánh giá mới, lịch
sử điểm cũ còn nguyên.

**Acceptance Scenarios**:

1. **Given** lịch khám phá hằng tuần đã bật, **When** đến hạn, **Then** đúng một lượt khám phá được tạo (kể cả khi khởi động lại).
2. **Given** ngân sách chưa cấu hình, **When** bật lịch khám phá, **Then** hệ thống từ chối với thông báo rõ ràng.
3. **Given** ngách đang ở trạng thái "theo dõi", **When** đánh giá lại, **Then** tạo lần đánh giá mới với điểm, phiên bản trọng
   số và bằng chứng mới; lần đánh giá cũ được giữ để so sánh.

---

### Edge Cases

- Hai bài viết ở hai tên miền khác nhau có cùng nội dung (bài đăng lại, aggregator) → tính là một nguồn; ngách có thể rơi
  xuống `INSUFFICIENT_EVIDENCE`.
- Ngách `INSUFFICIENT_EVIDENCE` được đánh giá lại và có thêm bằng chứng độc lập → chuyển vào bảng xếp hạng ở lần đánh giá mới.
- Máy chủ nguồn trả 429/503 kèm `Retry-After` dài hơn thời gian còn lại của lượt → bỏ nguồn đó, ghi lý do, không chờ vượt giới hạn.
- Chạm 90 phút đúng lúc đang chờ một lời gọi AI → lời gọi đang dở được xử lý theo quy tắc E0 (không gửi lời gọi mới), rồi kết
  thúc `PARTIAL_COMPLETED`.
- Worker dừng đột ngột giữa lượt → tiếp tục từ checkpoint, số trang/thời gian đã dùng được giữ, không thu thập lại trang đã có.
- Ngách đủ bằng chứng (Q5) nhưng Coverage < 60% → nằm ở "cần nghiên cứu thêm" với `INSUFFICIENT_SCORING_DATA`; đánh giá lại khi có
  thêm dữ liệu.
- Hai nguồn cho điểm khác nhau cho cùng tiêu chí (`CONFLICTING`) → tiêu chí coi như `UNKNOWN` khi tính Opportunity cho tới khi được
  phân xử; Coverage và Confidence giảm tương ứng.
- Đổi trọng số làm Coverage của một ngách vượt hoặc rơi dưới 60% → kết quả mới chỉ áp dụng ở lần chấm lại theo phiên bản mới.
- Trang có nhiều PII đan xen vào nội dung vấn đề (ví dụ câu chuyện cá nhân) → che PII, nếu không tách được an toàn thì bỏ đoạn
  đó; ngách có thể thiếu bằng chứng → `INSUFFICIENT_EVIDENCE`.
- Yêu cầu xóa trỏ tới bằng chứng đang được một lượt khám phá chạy sử dụng → lượt đó không dùng bằng chứng đã xóa ở bước kế tiếp;
  đánh giá đã lưu được tính lại.
- Khôi phục backup cũ hơn một yêu cầu xóa → yêu cầu xóa được áp dụng lại trước khi hệ thống phục vụ dữ liệu.
- Lượt khám phá không tìm được ngách nào đủ bằng chứng → hoàn tất với kết quả rỗng và lý do, không bịa ngách.
- Không có nguồn tìm kiếm `ALLOWED` nào được bật, hoặc chủ sở hữu tắt hết → lượt khám phá báo `NO_COMPLIANT_SEARCH_SOURCE`, không
  tạo ngách từ kiến thức của AI.
- Chủ sở hữu cố bật một nguồn `PROHIBITED` → bị từ chối, có thông báo lý do.
- Mọi nguồn đều lỗi (mất internet, rate limit toàn bộ) → lượt khám phá kết thúc có trạng thái lỗi/thiếu dữ liệu rõ ràng, không
  có kết luận nào được đánh dấu `VERIFIED`.
- Một nguồn trả nội dung rất dài → chỉ lưu trích đoạn ngắn có giới hạn (BR-09), không lưu nguyên văn.
- Cùng một nội dung xuất hiện ở nhiều URL (bản sao, tham số tracking) → gom về một nguồn, không đếm trùng làm tăng Confidence.
- Bằng chứng quá cũ → Confidence giảm theo độ mới; vẫn hiển thị thời điểm thu thập.
- AI trả kết quả sai định dạng → thử lại có giới hạn rồi đánh dấu lỗi bước đó, không lưu dữ liệu sai (E0 FR-013).
- AI từ chối trả lời một ngách nhạy cảm → ngách đó ghi trạng thái từ chối, không tự đổi model, các ngách khác tiếp tục.
- Ngách liên quan đến lĩnh vực bị hạn chế (y tế, tài chính, nội dung người lớn, cờ bạc…) → gắn cờ rủi ro tuân thủ; không tự loại
  bỏ, chủ sở hữu quyết định.
- Thị trường không phải Mỹ (ví dụ Việt Nam) → ngôn ngữ nghiên cứu theo thị trường; ngôn ngữ giao diện và ngôn ngữ báo cáo độc lập
  (BR-10).
- Đổi trọng số trong khi một lượt khám phá đang chạy → lượt đó dùng phiên bản trọng số tại thời điểm bắt đầu.
- Chủ sở hữu xóa/ẩn một ngách → bằng chứng vẫn giữ để tái lập; ngách không xuất hiện trong báo cáo mặc định.

## Requirements *(mandatory)*

### Functional Requirements

**Thiết lập và khởi chạy**

- **FR-001**: Hệ thống MUST cho phép chọn thị trường/quốc gia mục tiêu cho lượt khám phá (mặc định theo project – Mỹ) và
  ngôn ngữ nghiên cứu (mặc định theo thị trường), độc lập với ngôn ngữ giao diện và ngôn ngữ nội dung. *(E1-01, BR-10)*
- **FR-002**: Chủ sở hữu MUST chạy được lượt khám phá **không chọn lĩnh vực**; lĩnh vực gợi ý là tùy chọn. Khi không chọn, các
  ngách ứng viên MUST không bị giới hạn vào một lĩnh vực định trước. *(E1-02, E1-03, AC-04)*
- **FR-003**: Mỗi lượt khám phá MUST có cấu hình rõ ràng (thị trường, ngôn ngữ nghiên cứu, lĩnh vực gợi ý nếu có, số ngách ứng
  viên tối đa, hạn mức chi phí, phiên bản trọng số) được lưu lại để tái lập. Mặc định: tối đa **20 ngách ứng viên** và hạn mức
  AI **$2** mỗi lượt (bằng hạn mức job của E0), thời gian tối đa **90 phút**, tối đa **300 trang** thu thập, mỗi tên miền tối đa
  **1 request/2 giây**; chỉnh được theo từng lượt nhưng hạn mức AI không vượt hạn mức ngày; hệ thống MUST NOT tự
  tăng ngân sách. Không đủ số ngách có bằng chứng → trả về số lượng thực tế, MUST NOT tạo thêm ngách. *(Clarification Q2)*
- **FR-004**: Lượt khám phá tốn phí MUST bị từ chối khi ngân sách ngày/tháng chưa được cấu hình hoặc bằng 0, và khi hạn mức của
  lượt vượt hạn mức ngày. *(AUT-04)*

**Thu thập và phân tích**

- **FR-005**: Hệ thống MUST thu thập vấn đề khách hàng chỉ từ nguồn công khai hoặc API hợp lệ, tôn trọng robots.txt, điều khoản
  sử dụng và giới hạn tần suất; MUST NOT vượt paywall, CAPTCHA hay đăng nhập trái phép; MUST NOT giả định nguồn có API miễn phí.
  *(E1-04, BR-01, NFR-11)*
- **FR-006**: Mỗi loại nguồn dữ liệu bên ngoài (công cụ tìm kiếm, diễn đàn/cộng đồng, trang đánh giá, video, xu hướng, website
  sản phẩm/so sánh) MUST được truy cập qua một giao diện thay thế được, có phiên bản giả lập dùng cho phát triển/kiểm thử, và
  có chính sách truy cập riêng (giới hạn tần suất, số lần thử lại, thời gian chờ). Nguồn **thật** trong E1: (a) tìm kiếm qua một
  máy tìm kiếm tổng hợp **tự host, mã nguồn mở** (SearXNG), không cần API key trả phí; (b) thu thập nội dung trang web công khai
  bằng HTTP client + `trafilatura` (mặc định, không cần trình duyệt); trình thu thập có trình duyệt cho trang cần JavaScript là tùy
  chọn, tắt mặc định (plan). Adapter giả lập dùng cho kiểm thử. Reddit API,
  YouTube API, Google Trends và nguồn chuyên biệt ngoài phạm vi E1. *(Clarification Q1)*
- **FR-006a**: Khi nguồn tìm kiếm không trả kết quả hoặc không khả dụng, hệ thống MUST ghi nhận lỗi/trạng thái thiếu dữ liệu cho
  bước đó và MUST NOT tự tạo dữ liệu thay thế (kể cả nhờ AI "đoán" nguồn). *(Clarification Q1, Constitution I)*
- **FR-006b**: E1 MUST thu thập được dữ liệu thị trường **thực tế** từ nguồn thật (không phụ thuộc vào AI có phí ở bước thu thập).
  Phân tích bằng nhà cung cấp AI giả lập trên dữ liệu thật MUST được gắn nhãn giả lập và MUST NOT được coi là nghiên cứu AI thật;
  nguồn và bằng chứng thu thập thật vẫn giữ nguồn gốc thật. *(Clarification Q1)*
- **FR-006c**: Mỗi nguồn dữ liệu bên ngoài (máy tìm kiếm mà SearXNG truy vấn, API chính thức, nguồn dữ liệu mở hoặc dữ liệu được cấp
  phép) MUST có hồ sơ tuân thủ gồm: URL điều khoản sử dụng, ngày xác minh, người xác minh và căn cứ (trích đoạn/ghi chú), **phương
  thức truy cập được phép**, **phạm vi sử dụng được phép**, giới hạn truy vấn đã biết, và trạng thái (`ALLOWED` / `UNVERIFIED` /
  `PROHIBITED`). `ALLOWED` chỉ được gán khi có căn cứ đã ghi; có API miễn phí MUST NOT được coi là căn cứ cho phép dùng cho mọi mục
  đích. `UNVERIFIED` tắt mặc định; `PROHIBITED` MUST NOT bật được dưới bất kỳ hình thức nào. *(Clarification Q4, 2026-11-20,
  Constitution X, NFR-11)*
- **FR-006d**: Chỉ nguồn `ALLOWED` được dùng trong lượt chạy **tự động** (theo lịch, đánh giá lại theo lịch). Hệ thống MUST NOT tự
  bật nguồn `UNVERIFIED` hay tự nâng trạng thái nguồn. Chủ sở hữu MAY bật nguồn `UNVERIFIED` (cảnh báo rủi ro điều khoản trước khi
  bật, audit ai/khi nào/nguồn/trạng thái trước-sau); nguồn đó chỉ được dùng trong lượt **do chủ sở hữu khởi chạy thủ công** có chọn rõ
  "dùng nguồn chưa xác minh" cho lượt đó, và bằng chứng thu được MUST mang dấu nguồn `UNVERIFIED`. *(Clarification Q4, 2026-11-20)*
- **FR-006e**: Khi không có nguồn `ALLOWED` nào được bật và khả dụng (và lượt không được chủ sở hữu chọn dùng nguồn chưa xác minh),
  lượt khám phá MUST dừng bước tìm kiếm với mã `NO_COMPLIANT_SEARCH_SOURCE` hiển thị cho chủ sở hữu, MUST NOT tạo dữ liệu thay thế.
  *(Clarification Q4, 2026-11-20)*
- **FR-006f**: Hệ thống MUST NOT tự động vượt CAPTCHA, giới hạn tần suất hay cơ chế hạn chế truy cập của bất kỳ nguồn nào; gặp các
  cơ chế này → dừng truy cập nguồn đó và ghi lý do. *(Clarification Q4, Constitution X)*
- **FR-006g**: Nguồn MUST được truy cập qua `SourceAdapter` chung, hỗ trợ các loại: engine của SearXNG, API chính thức, nguồn dữ liệu
  mở, dữ liệu được cấp phép. Thêm/bật/tắt/cập nhật hồ sơ tuân thủ của một nguồn thuộc loại adapter đã có MUST thực hiện được bằng cấu
  hình (API/giao diện), không cần sửa code; thông tin xác thực của nguồn (nếu có) chỉ tham chiếu tới biến môi trường/secret, không lưu
  giá trị trong database. *(Clarification 2026-11-20, Constitution VIII, X)*
- **FR-007**: Hệ thống MUST gom các phàn nàn/vấn đề tương tự thành nhóm pain point, mỗi nhóm có mô tả, số bằng chứng hỗ trợ và
  mức độ nghiêm trọng (thang điểm xác định trong plan, có tiêu chí rõ ràng). *(E1-05, E1-07)*
- **FR-008**: Hệ thống MUST xác định buyer persona cấp ngách (nhóm khách hàng, bối cảnh, mục tiêu, rào cản, khả năng chi trả),
  mỗi thuộc tính có trạng thái xác minh. *(E1-06, E1-10)*
- **FR-009**: Hệ thống MUST tìm giải pháp hiện có (sản phẩm/dịch vụ/cách làm thủ công) và xác định khoảng trống thị trường có
  bằng chứng hoặc `INFERRED`. *(E1-08, E1-09)*
- **FR-010**: Hệ thống MUST đánh giá khả năng kiếm tiền affiliate ở cấp ngách dựa trên bằng chứng công khai (ví dụ sự tồn tại
  của chương trình affiliate hoặc sản phẩm có affiliate), và MUST gắn cờ rủi ro monetization khi không tìm thấy chương trình
  phù hợp. Đánh giá chi tiết sản phẩm/chương trình thuộc E2. *(E1-11, BR-06)*
- **FR-011**: Hệ thống MUST đánh giá mức cạnh tranh và khả năng tiếp cận khách hàng ở cấp ngách (kênh nơi khách hàng thảo luận,
  mật độ đối thủ) chỉ từ bằng chứng thu thập được hoặc `UNKNOWN`; MUST NOT tạo search volume, CPC, keyword difficulty hay số
  liệu thị trường. *(E1-12, E1-13, BR-05)*
- **FR-012**: Nội dung thu thập từ bên ngoài MUST được coi là dữ liệu không tin cậy, MUST NOT được thực thi như chỉ thị; agent
  nghiên cứu chỉ dùng được tool đã đăng ký trong danh sách quyền của nó, không có tool có tác động bên ngoài. *(Constitution V,
  NFR-14, BR-08)*

- **FR-012a**: Nội dung thu thập MUST qua bước che thông tin cá nhân (PII) **trước** khi ghi vào database và **trước** khi gửi tới
  bất kỳ nhà cung cấp AI nào (qua interface PII engine thay thế được; E1 dùng regex + `phonenumbers` + spaCy cho tiếng Anh): email → `[EMAIL]`, số điện thoại → `[PHONE]`, @username/tên tài khoản → `[USER]`, tên tác giả/người được
  nhắc tên → `[PERSON]`, và các định danh cá nhân khác phát hiện được; giữ nội dung pain point và ngữ cảnh cần thiết. Bước che PII
  MUST kết hợp nhiều phương pháp (mẫu xác định + nhận diện ngữ cảnh) và có kiểm thử với bộ mẫu PII phổ biến. *(Clarification Q8,
  Constitution V)*
- **FR-012b**: Nội dung PII chưa xử lý MUST NOT xuất hiện trong log, cache, checkpoint, báo cáo, audit hay dữ liệu gửi AI; nội dung thô
  chỉ tồn tại tạm thời trong bộ nhớ của bước thu thập. Khi bước che PII không chắc chắn xử lý an toàn, đoạn nội dung MUST bị bỏ qua hoặc
  đánh dấu "cần kiểm tra" (`NEEDS_REVIEW` – không lưu dạng chưa che, không gửi AI). Ngôn ngữ chưa có bộ nhận diện tên người →
  `NEEDS_REVIEW`. *(Clarification Q8, 2026-11-20)*
- **FR-012c**: Hệ thống MUST NOT dùng thông tin cá nhân để xây dựng hồ sơ cá nhân hay danh sách liên hệ. *(Clarification Q8)*
**Bằng chứng và trạng thái xác minh**

- **FR-013**: Mọi kết luận (ngách, pain point, persona, giải pháp, khoảng trống, đối thủ, monetization, kênh tiếp cận) MUST
  gắn với bằng chứng gồm nguồn (URL hoặc định danh), trích đoạn ngắn có giới hạn độ dài, thời điểm thu thập và thời điểm xác
  minh – hoặc mang trạng thái `UNKNOWN`. *(E1-17, DATA-03, NFR-04)*
- **FR-013a**: Mỗi bằng chứng MUST có URL nguồn, nội dung liên quan (trích đoạn **đã che PII**), thời điểm thu thập và trạng thái
  xác minh; MUST NOT lưu toàn bộ nội dung trang khi không cần thiết. *(Clarification Q5, Q8)*
- **FR-013b**: Ngưỡng bằng chứng để một ngách vào bảng xếp hạng chính: **≥ 2 bằng chứng pain point hợp lệ từ ≥ 2 nguồn độc lập**.
  Bằng chứng "hợp lệ" = có đủ trường FR-013a, được đánh giá là liên quan tới pain point của ngách và đạt chất lượng tối thiểu; hai
  nguồn "độc lập" = khác tên miền **và** không phải bản sao/bản gần giống của cùng một nội dung. Kiểm tra trùng nội dung, đếm
  nguồn độc lập và so ngưỡng MUST là logic xác định trong mã; AI đánh giá độ liên quan, chất lượng và dấu hiệu sao chép như một
  nhận định có nhãn `INFERRED` kèm lý do, đầu vào cho logic xác định (không chỉ đếm URL). *(Clarification Q5, Constitution III)*
- **FR-013c**: Ngách không đạt ngưỡng MUST có trạng thái `INSUFFICIENT_EVIDENCE`: được lưu cùng bằng chứng đã có để nghiên cứu và
  đánh giá lại, MUST NOT xuất hiện trong bảng xếp hạng chính, MUST NOT được tính vào giới hạn số ngách của lượt khám phá. Hệ thống
  MUST NOT tạo, suy diễn hay "mượn" bằng chứng để đạt ngưỡng. *(Clarification Q5, Constitution I)*
- **FR-013d**: Đạt ngưỡng bằng chứng không có nghĩa là ngách sinh lợi: khả năng kiếm tiền affiliate (FR-010) và Opportunity Score
  (FR-017) được đánh giá riêng; Opportunity Score và Confidence Score MUST được tính và hiển thị riêng biệt. *(Clarification Q5, BR-04)*
- **FR-013e**: Chủ sở hữu MUST xóa hoặc vô hiệu hóa được một bằng chứng (hoặc toàn bộ bằng chứng của một nguồn) theo yêu cầu hợp lệ.
  Sau khi xóa: bằng chứng MUST NOT được dùng ở bất kỳ phân tích nào sau đó; số nguồn độc lập, Confidence và trạng thái xếp hạng của các
  ngách liên quan MUST được tính lại (không còn đủ ngưỡng FR-013b → `INSUFFICIENT_EVIDENCE`); audit ghi thao tác tối thiểu (ai, khi
  nào, định danh bằng chứng/nguồn, lý do) không chứa nội dung đã xóa. *(Clarification Q8)*
- **FR-013f**: Hệ thống MUST có chính sách bảo đảm bằng chứng đã xóa không quay lại hệ thống đang hoạt động: bản sao trong cache bị
  xóa cùng lúc; sổ yêu cầu xóa (erasure ledger) MUST được lưu bền vững ngoài database; sau khi khôi phục từ backup, mọi yêu cầu xóa MUST
  được áp dụng lại **trước khi** dữ liệu được sử dụng hoặc trả qua API; nếu không áp dụng đầy đủ được (sổ thiếu, hỏng, lỗi ghi), quá
  trình restore MUST thất bại an toàn (dịch vụ không phục vụ dữ liệu) và báo lỗi rõ. Có kiểm thử chứng minh dữ liệu đã xóa không xuất
  hiện lại. *(Clarification Q8, 2026-11-20, E0 FR-073)*
- **FR-014**: Trạng thái xác minh MUST theo BR-02: `VERIFIED` chỉ khi có nguồn trực tiếp; nhận định do AI suy luận gắn `INFERRED`;
  không xác minh được gắn `UNKNOWN` (không giá trị); nguồn mâu thuẫn gắn `CONFLICTING` và lưu mọi giá trị kèm nguồn. *(BR-02, QA-05)*
- **FR-015**: Nguồn trùng nội dung (cùng nội dung chuẩn hóa ở nhiều URL, kể cả khác tên miền) MUST được gom về một nguồn và
  không được đếm lặp khi tính ngưỡng bằng chứng (FR-013b) hay Confidence.
- **FR-016**: Mọi dữ liệu sinh từ nhà cung cấp AI giả lập hoặc nguồn giả lập MUST mang nhãn `MOCK`, MUST bị loại khỏi báo cáo,
  xếp hạng và thống kê mặc định, và chỉ hiển thị khi yêu cầu rõ ràng kèm nhãn. *(Constitution I, E0 FR-018(g))*

**Chấm điểm**

- **FR-017**: Opportunity Score MUST là tổng có trọng số của 6 tiêu chí BR-03 (mặc định 25/20/20/15/10/10); mỗi tiêu chí có
  thang điểm và tiêu chí chấm được tài liệu hóa; việc tính điểm MUST là logic xác định (không giao cho AI tính tổng). *(E1-14,
  BR-03, Constitution III)*
- **FR-018**: Trọng số MUST cấu hình được, tổng đúng 100%, có phiên bản; mỗi lần đánh giá MUST lưu phiên bản trọng số và điểm
  thành phần; đổi trọng số tạo phiên bản mới có audit, không sửa kết quả cũ; chấm lại theo phiên bản mới MUST không cần gọi
  lại AI. *(BR-03, Constitution II)*
- **FR-019**: Tiêu chí `UNKNOWN` MUST NOT được gán điểm giả (không gán 0, 100 hay giá trị mặc định). Opportunity Score MUST được
  tính bằng logic xác định chỉ trên các tiêu chí có dữ liệu hợp lệ, với trọng số được chuẩn hóa lại về 100%:
  `Opportunity = Σ(điểm_i × w_i) / Σ w_i` (i thuộc tiêu chí có dữ liệu hợp lệ, `w_i` là trọng số gốc của phiên bản đang dùng).
  Tiêu chí có dữ liệu hợp lệ = có điểm thành phần dựa trên bằng chứng `VERIFIED` hoặc nhận định `INFERRED` có lý do; tiêu chí chỉ có
  dữ liệu `CONFLICTING` chưa phân xử hoặc không hợp lệ được coi như `UNKNOWN`. AI chỉ đề xuất điểm thành phần kèm lý do và bằng chứng;
  kết quả cuối cùng do mã tính. *(BR-03, BR-04, Clarification Q7, Constitution III)*
- **FR-019a**: **Coverage** = tổng trọng số gốc của các tiêu chí có dữ liệu hợp lệ (0–100%) MUST được lưu và hiển thị cạnh Opportunity
  Score. Coverage < 60% → không có Opportunity Score chính thức; ngách hiển thị `INSUFFICIENT_SCORING_DATA` và không được xếp hạng theo
  Opportunity. Ngưỡng 60% cấu hình được, có phiên bản cùng trọng số. *(Clarification Q7)*
- **FR-019b**: Khi tiêu chí Monetization là `UNKNOWN` (hoặc không có tín hiệu affiliate đã xác minh), ngách MUST mang nhãn
  `MONETIZATION_UNVERIFIED`; vẫn được tính Opportunity khi Coverage ≥ 60% và vẫn xuất hiện trong bảng xếp hạng cơ hội nghiên cứu,
  nhưng MUST NOT xuất hiện trong danh sách ưu tiên triển khai affiliate. *(Clarification Q7, BR-06)*
- **FR-019c**: Opportunity Score MUST NOT được trình bày như dự báo doanh thu hay khả năng sinh lợi đã xác minh; giao diện và báo cáo
  MUST kèm chú thích này. *(Clarification Q7, Constitution I)*
- **FR-020**: Confidence Score MUST được tính riêng, độc lập với Opportunity Score (không dùng Opportunity làm đầu vào), phản ánh chất
  lượng, tính độc lập, độ mới, độ nhất quán và độ đầy đủ của bằng chứng; MUST giảm khi thiếu dữ liệu quan trọng (Coverage thấp, tiêu
  chí `UNKNOWN`), khi có `CONFLICTING`, bằng chứng cũ hoặc ít nguồn độc lập. *(E1-15, BR-04, Clarification Q7)*
- **FR-021**: Search volume thấp hoặc không có MUST NOT tự động loại ngách hay chặn ngách khỏi xếp hạng cao. *(BR-15)*

**Phát hiện trùng, báo cáo, quyết định**

- **FR-022**: Hệ thống MUST phát hiện ngách trùng/tương đồng (cùng nhóm khách hàng và vấn đề cốt lõi) trong cùng lượt và giữa các
  lượt; trùng chắc chắn → liên kết vào ngách sẵn có; không chắc chắn → đánh dấu "có thể tương đồng" chờ chủ sở hữu, không tự gộp.
  Logic so sánh cuối cùng MUST là mã xác định (AI chỉ có thể đề xuất). *(E1-16)*
- **FR-023**: Mỗi ngách trong bảng xếp hạng MUST có đủ 16 trường đầu ra BR-07; trường thiếu dữ liệu MUST là `UNKNOWN`. *(BR-07)*
- **FR-024**: Hệ thống MUST tạo báo cáo xếp hạng ngách theo lượt khám phá và theo project gồm hai danh sách tách biệt:
  (a) **bảng xếp hạng cơ hội nghiên cứu** – ngách `EVIDENCE_SUFFICIENT` có Coverage ≥ 60%, xếp theo Opportunity Score; (b) **danh sách
  ưu tiên triển khai affiliate** – tập con của (a) không mang `MONETIZATION_UNVERIFIED` hoặc cờ rủi ro monetization. Ngách
  `INSUFFICIENT_EVIDENCE` hoặc `INSUFFICIENT_SCORING_DATA` nằm ở danh sách "cần nghiên cứu thêm", không có thứ hạng Opportunity.
  Sắp xếp được theo Opportunity Score và Confidence Score, lọc theo ngưỡng, xuất được ở dạng đọc được bởi người (song ngữ VI/EN theo ngôn ngữ giao diện cho phần nhãn
  và tiêu đề; nội dung trích dẫn giữ ngôn ngữ gốc). *(E1-18, AC-16)*
- **FR-025**: AI MUST chỉ đề xuất "tiếp tục/loại bỏ" kèm lý do; chủ sở hữu ghi quyết định (tiếp tục / theo dõi / loại bỏ) kèm lý
  do; quyết định có audit và không ghi đè đề xuất của AI. *(AUT-01, Constitution IV)*
- **FR-026**: E1 MUST cung cấp API cho mọi chức năng và **3 màn hình tối thiểu song ngữ** (mặc định tiếng Việt, chuyển được tiếng
  Anh), mọi chuỗi qua hệ thống i18n: (1) **Danh sách lượt khám phá** – lịch sử, trạng thái, kết quả (`COMPLETED`/`PARTIAL_COMPLETED` +
  lý do), chi phí (tách thật/giả lập), thao tác chạy/tạm dừng/tiếp tục/hủy; (2) **Bảng xếp hạng ngách** – ngách, Opportunity Score,
  Confidence Score, Coverage (%), trạng thái xác minh, trạng thái Monetization (`MONETIZATION_UNVERIFIED`/cờ rủi ro), chuyển giữa bảng
  cơ hội nghiên cứu / danh sách ưu tiên affiliate / cần nghiên cứu thêm; (3) **Chi tiết ngách** – pain point, buyer persona, bằng chứng
  và nguồn, lý do chấm điểm (điểm thành phần, phiên bản trọng số, Coverage, tiêu chí `UNKNOWN`, dữ liệu còn thiếu), rủi ro, nút ghi
  quyết định. Mỗi màn hình MUST có trạng thái đang tải, rỗng và lỗi; dữ liệu giả lập MUST được gắn nhãn rõ và không trình bày như
  nghiên cứu thật; Opportunity kèm chú thích không phải dự báo doanh thu (FR-019c); không có biểu đồ/phân tích nâng cao (E4). Luồng
  chính MUST có kiểm thử end-to-end. *(Clarification Q3, Q7, FR-060 E0, NFR-12)*

**Vận hành, chi phí, độ bền**

- **FR-027**: Lượt khám phá MUST chạy như job của E0: có trạng thái, tạm dừng/tiếp tục/hủy, checkpoint sau mỗi bước, tiếp tục từ
  bước cuối hoàn tất, không lặp bước đã xong. *(AUT-03, E0 FR-030…FR-036)*
- **FR-028**: Mọi lời gọi AI của E1 MUST đi qua AI Gateway và cơ chế giữ chỗ ngân sách của E0; vượt hạn mức lượt/ngày/tháng →
  `PAUSED_BUDGET`, không gửi lời gọi; kết quả đã có được giữ. Lượt khám phá MUST dùng Model Task Profile (ưu tiên model tiết kiệm
  cho thu thập/trích xuất, model mạnh hơn chỉ cho bước suy luận cần thiết), không hard-code model. *(NFR-06, Constitution VI)*
- **FR-029**: Chạy lại lượt khám phá, chạy theo lịch, hoặc tiếp tục sau sự cố MUST NOT tạo ngách, pain point, nguồn hay bằng chứng
  trùng. *(AUT-05, QA-10)*
- **FR-030**: Nguồn bị giới hạn tần suất MUST được thử lại có giới hạn với thời gian chờ theo chính sách nguồn; quá giới hạn thì bỏ
  qua nguồn đó, ghi lý do, tiếp tục với nguồn khác. *(QA-06)*
- **FR-030a**: Tốc độ truy cập mặc định là **mức trần** 1 request/2 giây cho mỗi tên miền; khi robots.txt (`Crawl-delay`), điều
  khoản nguồn hoặc phản hồi máy chủ (ví dụ `Retry-After`, mã 429/503) yêu cầu chậm hơn, hệ thống MUST áp dụng mức chặt hơn; MUST NOT
  tự vượt CAPTCHA hay cơ chế hạn chế truy cập. *(Clarification Q6)*
- **FR-030b**: Ngân sách thu thập (số trang) MUST được phân bổ giữa các ngách ứng viên, có thể điều chỉnh theo chất lượng dữ liệu
  (ngách thiếu bằng chứng được ưu tiên thêm) nhưng tổng MUST NOT vượt giới hạn của lượt. Trang được chọn theo khả năng cung cấp bằng
  chứng pain point, persona, giải pháp hiện tại; MUST NOT crawl hàng loạt chỉ để đạt số trang. *(Clarification Q6)*
- **FR-030c**: Khi mọi ngách ứng viên đã đủ bằng chứng hợp lệ (hoặc đã có quyết định không thể đạt), lượt khám phá MUST được kết
  thúc sớm, không cần dùng hết thời gian/số trang. *(Clarification Q6)*
- **FR-030d**: Khi chạm giới hạn thời gian hoặc số trang, hệ thống MUST dừng thu thập, lưu dữ liệu và checkpoint, tiếp tục đánh giá
  các ngách đủ bằng chứng, chuyển ngách thiếu sang `INSUFFICIENT_EVIDENCE`. Kết quả lượt khám phá MUST phân biệt `COMPLETED` và
  `PARTIAL_COMPLETED` kèm lý do (`TIME_LIMIT_REACHED`, `PAGE_LIMIT_REACHED`, `NO_COMPLIANT_SEARCH_SOURCE`, `SOURCES_UNAVAILABLE`…);
  đây là kết quả nghiệp vụ của lượt khám phá, ghi kèm job E0 (job vẫn theo vòng đời E0, không đổi state machine của E0).
  *(Clarification Q6)*
- **FR-030e**: Giới hạn thời gian/số trang MUST NOT thay thế giới hạn ngân sách AI ($2/lượt-job, $3/ngày, $30/tháng); chạm ngân sách
  AI → `PAUSED_BUDGET` theo E0, tiếp tục từ checkpoint với phần giới hạn thời gian/trang còn lại (thời gian tạm dừng không tính vào
  90 phút). *(Clarification Q6, Constitution VI)*
- **FR-031**: Trang không truy cập được, bị robots.txt chặn hoặc trả lỗi MUST bị bỏ qua có ghi lý do, không làm hỏng cả lượt
  khám phá. *(QA-07, NFR-11)*
- **FR-032**: Mỗi lượt khám phá MUST ghi nhận: số lời gọi AI, chi phí (tách REAL/MOCK), số trang đã thu thập (thành công/thất bại,
  kèm lý do bỏ qua), thời gian thực thi, số nguồn độc lập, số ngách ứng viên, số ngách đủ bằng chứng, số ngách
  `INSUFFICIENT_EVIDENCE`, kết quả (`COMPLETED`/`PARTIAL_COMPLETED`) và lý do dừng. *(Constitution VI, NFR-09)*
- **FR-033**: Chủ sở hữu MUST tạo được lịch khám phá định kỳ và lịch đánh giá lại ngách đang theo dõi qua scheduler của E0; lịch
  tốn phí bị từ chối khi chưa cấu hình ngân sách. *(E1-19, AUT-04)*
- **FR-034** *(Should)*: Hệ thống SHOULD đánh giá lại ngách theo dữ liệu mới, tạo lần đánh giá mới (điểm, phiên bản trọng số, bằng
  chứng) và giữ lịch sử đánh giá cũ để so sánh. *(E1-20)*
- **FR-035**: Ngách thuộc lĩnh vực nhạy cảm/hạn chế MUST được gắn cờ rủi ro tuân thủ trong trường "rủi ro"; hệ thống không tự loại.
- **FR-036**: Thay đổi cấu hình E1 (trọng số, nguồn, chính sách truy cập) và quyết định của chủ sở hữu MUST được ghi audit log
  không chứa secret. *(Constitution X)*

### Key Entities *(include if feature involves data)*

- **Lượt khám phá (Discovery Run)**: một lần chạy nghiên cứu; thị trường, ngôn ngữ nghiên cứu, lĩnh vực gợi ý (tùy chọn), giới
  hạn số ngách và chi phí, phiên bản trọng số, liên kết tới job E0, trạng thái, thống kê (FR-032), nhãn nguồn gốc dữ liệu.
- **Ngách (Niche)**: tên, micro-niche, quốc gia, nhóm khách hàng, trạng thái bằng chứng (`EVIDENCE_SUFFICIENT` /
  `INSUFFICIENT_EVIDENCE`), trạng thái quyết định (ứng viên / theo dõi / tiếp tục / loại bỏ / ẩn), đề
  xuất của AI và quyết định của chủ sở hữu, cờ rủi ro (monetization, tuân thủ), liên kết tới các lượt khám phá đã phát hiện nó.
- **Lần đánh giá ngách (Niche Evaluation)**: điểm thành phần 6 tiêu chí (giá trị hoặc `UNKNOWN`), Opportunity Score, Confidence
  Score và các yếu tố cấu thành, phiên bản trọng số, thời điểm; nhiều lần đánh giá cho một ngách.
- **Nhóm pain point (Pain Point)**: mô tả, mức độ nghiêm trọng, số bằng chứng, trạng thái xác minh; thuộc một ngách.
- **Buyer Persona**: nhóm khách hàng, bối cảnh, mục tiêu, rào cản, khả năng chi trả; mỗi thuộc tính có trạng thái xác minh.
- **Đối thủ / giải pháp hiện có (Competitor)**: tên/định danh, loại giải pháp, điểm mạnh/yếu có bằng chứng; thuộc một ngách.
- **Phiên bản trọng số (Scoring Weights Version)**: 6 trọng số (tổng 100%), số phiên bản, người tạo, thời điểm.
- **Nguồn (Research Source)** và **Bằng chứng (Research Evidence)**: hạ tầng dùng chung của E0 (URL/định danh chuẩn hóa, loại nguồn,
  hash nội dung, thời điểm thu thập; trích đoạn **đã che PII**, trạng thái xác minh, thời điểm xác minh, job thu thập). Bổ sung cho E1:
  trạng thái che PII (đã che / cần kiểm tra), trạng thái hiệu lực (đang dùng / đã xóa theo yêu cầu – không còn trích đoạn), đánh giá
  liên quan/chất lượng của AI (`INFERRED` + lý do).
- **Hồ sơ nguồn (Source Policy)**: loại nguồn/adapter, URL điều khoản, ngày xác minh, căn cứ, phương thức truy cập và phạm vi sử dụng
  được phép, giới hạn đã biết, trạng thái `ALLOWED`/`UNVERIFIED`/`PROHIBITED`, bật/tắt, xác nhận cảnh báo; cấu hình không chứa secret.
- **Yêu cầu xóa bằng chứng (Evidence Erasure Request)**: định danh bằng chứng hoặc nguồn, lý do, người thực hiện, thời điểm; không chứa
  nội dung đã xóa; dùng để áp dụng lại sau khi khôi phục backup.
- **Quy tắc dữ liệu (Q5)**: bằng chứng thiếu URL, trích đoạn, thời điểm thu thập hoặc trạng thái xác minh không được tính vào
  ngưỡng; nguồn độc lập xác định theo tên miền + nội dung chuẩn hóa (bản sao/gần giống gom một nguồn); đánh giá liên quan/chất
  lượng của AI lưu kèm bằng chứng với nhãn `INFERRED` và lý do; ngách chỉ vào bảng xếp hạng khi trạng thái bằng chứng là
  `EVIDENCE_SUFFICIENT`.
- **Quy tắc dữ liệu (Q6)**: lượt khám phá lưu giới hạn đã áp dụng (thời gian, số trang, tốc độ mỗi tên miền), phần đã dùng và còn
  lại, kết quả (`COMPLETED`/`PARTIAL_COMPLETED`) và lý do dừng; mỗi lần truy cập trang lưu tên miền, thời điểm, kết quả (thành
  công/thất bại/bỏ qua) và lý do; trang đã thu thập thành công không bị thu thập lại khi tiếp tục hoặc chạy lại trong cùng lượt.
- **Quy tắc dữ liệu (Q7)**: mỗi lần đánh giá lưu điểm thành phần (hoặc `UNKNOWN`) kèm lý do và bằng chứng, trọng số gốc, phiên bản
  trọng số, ngưỡng Coverage, Coverage, Opportunity (hoặc `INSUFFICIENT_SCORING_DATA`), Confidence và các yếu tố cấu thành, nhãn
  `MONETIZATION_UNVERIFIED`; mọi giá trị đủ để tính lại kết quả bằng tay.
- **Quy tắc dữ liệu (Q8)**: chỉ trích đoạn đã che PII được ghi vào database; bằng chứng "cần kiểm tra" không được dùng cho ngưỡng hay
  điểm cho tới khi được xử lý; bằng chứng đã xóa giữ lại định danh và hash (không còn nội dung) để chống thu thập lại cùng nội dung
  và để áp dụng lại yêu cầu xóa sau restore.
- **Báo cáo xếp hạng (Ranking Report)**: ảnh chụp danh sách ngách đã xếp hạng của một lượt hoặc project tại một thời điểm, kèm phiên
  bản trọng số và bộ lọc đã dùng.
- **Chính sách nguồn (Source Policy)**: loại nguồn, trạng thái tuân thủ (`ALLOWED`/`UNVERIFIED`/`PROHIBITED`), URL điều khoản,
  ngày xác minh, phương thức tích hợp, bật/tắt, giới hạn tần suất, số lần thử lại, thời gian chờ, yêu cầu tuân thủ.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Chủ sở hữu khởi chạy được một lượt khám phá không chọn lĩnh vực chỉ với tối đa 3 thao tác (chọn thị trường – xác
  nhận cấu hình – chạy) và nhận danh sách ngách xếp hạng khi lượt chạy hoàn tất. *(AC-04)*
- **SC-002**: Trong lượt khám phá không chọn lĩnh vực, các ngách ứng viên thuộc ít nhất 3 lĩnh vực khác nhau (kiểm tra với bộ dữ
  liệu kiểm thử chuẩn).
- **SC-003a**: 100% ngách trong bảng xếp hạng có ≥ 2 bằng chứng pain point hợp lệ từ ≥ 2 nguồn độc lập; 100% ngách không đạt
  ngưỡng có trạng thái `INSUFFICIENT_EVIDENCE` và không được xếp hạng; trong bộ kiểm thử có bản sao nội dung khác tên miền, 0 cặp
  bản sao được tính là hai nguồn độc lập. *(Clarification Q5)*
- **SC-003**: 100% ngách trong báo cáo có đủ 16 trường đầu ra bắt buộc (giá trị hoặc `UNKNOWN`). *(BR-07)*
- **SC-004**: 100% kết luận được hiển thị có ít nhất một bằng chứng có nguồn và thời điểm thu thập, hoặc mang trạng thái `UNKNOWN`;
  0 số liệu search volume/CPC/keyword difficulty/thị trường do hệ thống tự tạo. *(AC-07, AC-09, NFR-04)*
- **SC-005a**: Trong bộ kiểm thử chấm điểm (đủ 6 tiêu chí; thiếu 1 và nhiều tiêu chí; Coverage đúng 60% và dưới 60%; Monetization
  `UNKNOWN`; dữ liệu mâu thuẫn/không hợp lệ): 100% Opportunity khớp công thức chuẩn hóa tính tay, 100% Coverage đúng, 100% trường hợp
  Coverage < 60% không có Opportunity chính thức, 100% ngách `MONETIZATION_UNVERIFIED` không có mặt trong danh sách ưu tiên affiliate,
  và thứ tự xếp hạng nhất quán qua các lần tính lại. *(Clarification Q7)*
- **SC-005**: Opportunity Score của 100% ngách trong bộ kiểm thử khớp với tính toán thủ công theo công thức và phiên bản trọng số đã
  lưu; chấm lại theo phiên bản trọng số mới không phát sinh lời gọi AI nào. *(AC-06)*
- **SC-006**: Trong 100% kịch bản kiểm thử vượt hạn mức, không có lời gọi tốn phí nào được gửi vượt hạn mức lượt/ngày/tháng, và
  các ngách đã đánh giá trước khi tạm dừng được giữ nguyên. *(NFR-06)*
- **SC-007**: Chạy lại cùng một lượt khám phá (hoặc tiếp tục sau sự cố) tạo 0 bản ghi trùng cho ngách, pain point, nguồn và bằng
  chứng trong 100% kịch bản kiểm thử. *(QA-10)*
- **SC-008**: Các tình huống nguồn mâu thuẫn, giới hạn tần suất và thu thập thất bại (QA-05, QA-06, QA-07) có kiểm thử tự động và
  đều đạt; trong các tình huống đó lượt khám phá vẫn hoàn tất với dữ liệu thiếu được ghi `UNKNOWN`.
- **SC-009**: 100% dữ liệu sinh từ nguồn/AI giả lập mang nhãn giả lập và 0 bản ghi giả lập xuất hiện trong báo cáo/xếp hạng mặc định.
- **SC-010**: Phát hiện trùng đạt tối thiểu 90% chính xác trên bộ cặp ngách kiểm thử có nhãn (trùng / không trùng), và 0 trường hợp
  tự gộp hai ngách được gắn nhãn "không trùng".
- **SC-011**: 100% yêu cầu E1 mức Must truy vết được tới ít nhất một test; toàn bộ test tự động chạy không cần API key và 0 lời gọi
  mạng tới nhà cung cấp/nguồn thật.
- **SC-012**: Với cấu hình mặc định, chi phí AI thực tế của một lượt khám phá không vượt hạn mức đã cấu hình cho lượt đó, và chi phí
  được báo cáo tách REAL/MOCK. *(chỉ kiểm chứng phần chi phí thật khi chủ sở hữu cho phép gọi API thật)*

- **SC-015**: Trong 100% kịch bản kiểm thử: lượt khám phá không vượt giới hạn thời gian và số trang đã cấu hình; khoảng cách giữa
  hai yêu cầu tới cùng tên miền không nhỏ hơn mức trần đã cấu hình hoặc mức chặt hơn do nguồn yêu cầu; dừng sớm khi đủ bằng chứng
  cho kết quả `COMPLETED`; chạm giới hạn cho `PARTIAL_COMPLETED` đúng lý do; tiếp tục từ checkpoint không thu thập lại trang đã có.
  *(Clarification Q6)*
- **SC-016**: Trên bộ mẫu PII kiểm thử (email, số điện thoại nhiều định dạng, @username, tên tác giả): 100% mẫu bị che trong dữ liệu
  lưu và dữ liệu gửi AI; 0 mẫu PII chưa che trong database, log, checkpoint; sau khi xóa bằng chứng, 100% ngách liên quan được tính lại
  đúng và bằng chứng đã xóa không xuất hiện lại sau khi khôi phục backup cũ hơn yêu cầu xóa; sổ xóa thiếu/hỏng → restore thất bại, API
  không trả dữ liệu. *(Clarification Q8, 2026-11-20)*
- **SC-017**: 100% lượt chạy tự động chỉ dùng nguồn `ALLOWED`; 0 nguồn được hệ thống tự bật hoặc tự nâng trạng thái; 0 nguồn
  `PROHIBITED` được dùng; mọi bằng chứng từ nguồn `UNVERIFIED` mang dấu nguồn tương ứng. *(Clarification 2026-11-20)*
- **SC-013**: Khi nguồn thật được bật và có Internet, một lượt khám phá thu thập được nguồn thật (URL, thời điểm thu thập, trích
  đoạn) cho ít nhất 80% ngách ứng viên được đề xuất, mà không cần API key trả phí; nguồn không truy cập được/bị chặn được ghi
  lý do, 0 trường hợp vượt CAPTCHA hay robots.txt. *(Clarification Q1)*
- **SC-014**: Chủ sở hữu hoàn thành luồng "chạy lượt khám phá → xem bảng xếp hạng → mở chi tiết ngách → ghi quyết định" trên giao
  diện bằng tiếng Việt và tiếng Anh; 3 màn hình đều có trạng thái đang tải, rỗng, lỗi; luồng này có kiểm thử end-to-end đạt.
  *(Clarification Q3)*

## Assumptions

- E0 là nền tảng: AI Gateway, budget reservation, Job Runtime (checkpoint, pause/resume/cancel, retry), scheduler, Tool
  Registry, EvidenceService, audit log, i18n và xác thực được tái sử dụng nguyên trạng; E1 không thay đổi kiến trúc E0. Mọi
  thay đổi cần thiết ở E0 (nếu phát sinh) được nêu trong plan và chờ phê duyệt.
- Chủ sở hữu là người dùng duy nhất; dữ liệu thuộc project mặc định (DATA-06).
- Chế độ REVIEW là mặc định và duy nhất trong E1: AI nghiên cứu và đề xuất; không có hành động bên ngoài (đăng ký, xuất bản, gửi
  dữ liệu ra ngoài ngoài truy vấn đọc tới nguồn công khai).
- Lời gọi API có phí vẫn tắt mặc định; E1 được phát triển và kiểm thử hoàn toàn bằng nhà cung cấp AI và nguồn dữ liệu giả lập.
  Kết quả với dữ liệu giả lập chỉ chứng minh logic, không phải kết quả nghiên cứu thật.
- Đánh giá khả năng kiếm tiền trong E1 ở cấp ngách (có/không có tín hiệu affiliate công khai); xác minh chương trình và sản phẩm cụ
  thể thuộc E2; keyword, search intent và phân tích nội dung đối thủ chi tiết thuộc E3.
- Thang điểm từng tiêu chí, công thức xử lý tiêu chí `UNKNOWN` trong Opportunity Score, công thức Confidence Score và ngưỡng phát
  hiện trùng được xác định trong plan (có tài liệu và test), cấu hình được khi hợp lý.
- Ngôn ngữ nghiên cứu mặc định theo thị trường (Mỹ → tiếng Anh); trích dẫn giữ ngôn ngữ gốc; nhãn báo cáo theo ngôn ngữ giao diện.
- Trích đoạn bằng chứng giới hạn độ dài (theo giới hạn hiện có của E0 cho trích đoạn); không lưu nguyên văn trang.
- Máy tìm kiếm tổng hợp tự host (SearXNG) và công cụ thu thập web chạy như dịch vụ tùy chọn trong Docker Compose (bật bằng
  profile khi dùng nguồn thật), có giới hạn tài nguyên; đánh giá giấy phép, tài nguyên và rủi ro điều khoản sử dụng của các máy
  tìm kiếm thượng nguồn nằm trong plan (Constitution VII).
- Không triển khai E2–E8 trong feature này.
