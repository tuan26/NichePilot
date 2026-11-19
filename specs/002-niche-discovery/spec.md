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
5. **Given** lượt khám phá chạy bằng nhà cung cấp AI giả lập, **When** xem kết quả, **Then** mọi ngách, pain point, bằng chứng
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

- Lượt khám phá không tìm được ngách nào đủ bằng chứng → hoàn tất với kết quả rỗng và lý do, không bịa ngách.
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
  viên tối đa, hạn mức chi phí, phiên bản trọng số) được lưu lại để tái lập. Mức mặc định: [NEEDS CLARIFICATION: quy mô mặc định
  của một lượt khám phá – số ngách ứng viên tối đa và hạn mức chi phí mỗi lượt?]
- **FR-004**: Lượt khám phá tốn phí MUST bị từ chối khi ngân sách ngày/tháng chưa được cấu hình hoặc bằng 0, và khi hạn mức của
  lượt vượt hạn mức ngày. *(AUT-04)*

**Thu thập và phân tích**

- **FR-005**: Hệ thống MUST thu thập vấn đề khách hàng chỉ từ nguồn công khai hoặc API hợp lệ, tôn trọng robots.txt, điều khoản
  sử dụng và giới hạn tần suất; MUST NOT vượt paywall, CAPTCHA hay đăng nhập trái phép; MUST NOT giả định nguồn có API miễn phí.
  *(E1-04, BR-01, NFR-11)*
- **FR-006**: Mỗi loại nguồn dữ liệu bên ngoài (công cụ tìm kiếm, diễn đàn/cộng đồng, trang đánh giá, video, xu hướng, website
  sản phẩm/so sánh) MUST được truy cập qua một giao diện thay thế được, có phiên bản giả lập dùng cho phát triển/kiểm thử, và
  có chính sách truy cập riêng (giới hạn tần suất, số lần thử lại, thời gian chờ). Nguồn thật được hỗ trợ trong E1:
  [NEEDS CLARIFICATION: những nguồn dữ liệu thật nào cần có trong E1 (và có chấp nhận nguồn tốn phí/cần API key không)?]
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

**Bằng chứng và trạng thái xác minh**

- **FR-013**: Mọi kết luận (ngách, pain point, persona, giải pháp, khoảng trống, đối thủ, monetization, kênh tiếp cận) MUST
  gắn với bằng chứng gồm nguồn (URL hoặc định danh), trích đoạn ngắn có giới hạn độ dài, thời điểm thu thập và thời điểm xác
  minh – hoặc mang trạng thái `UNKNOWN`. *(E1-17, DATA-03, NFR-04)*
- **FR-014**: Trạng thái xác minh MUST theo BR-02: `VERIFIED` chỉ khi có nguồn trực tiếp; nhận định do AI suy luận gắn `INFERRED`;
  không xác minh được gắn `UNKNOWN` (không giá trị); nguồn mâu thuẫn gắn `CONFLICTING` và lưu mọi giá trị kèm nguồn. *(BR-02, QA-05)*
- **FR-015**: Nguồn trùng nội dung (cùng nội dung chuẩn hóa ở nhiều URL) MUST được gom về một nguồn và không được đếm lặp khi
  tính Confidence.
- **FR-016**: Mọi dữ liệu sinh từ nhà cung cấp AI giả lập hoặc nguồn giả lập MUST mang nhãn `MOCK`, MUST bị loại khỏi báo cáo,
  xếp hạng và thống kê mặc định, và chỉ hiển thị khi yêu cầu rõ ràng kèm nhãn. *(Constitution I, E0 FR-018(g))*

**Chấm điểm**

- **FR-017**: Opportunity Score MUST là tổng có trọng số của 6 tiêu chí BR-03 (mặc định 25/20/20/15/10/10); mỗi tiêu chí có
  thang điểm và tiêu chí chấm được tài liệu hóa; việc tính điểm MUST là logic xác định (không giao cho AI tính tổng). *(E1-14,
  BR-03, Constitution III)*
- **FR-018**: Trọng số MUST cấu hình được, tổng đúng 100%, có phiên bản; mỗi lần đánh giá MUST lưu phiên bản trọng số và điểm
  thành phần; đổi trọng số tạo phiên bản mới có audit, không sửa kết quả cũ; chấm lại theo phiên bản mới MUST không cần gọi
  lại AI. *(BR-03, Constitution II)*
- **FR-019**: Tiêu chí có giá trị `UNKNOWN` MUST NOT được gán điểm giả; Opportunity Score MUST ghi rõ tiêu chí thiếu dữ liệu và
  cách xử lý (công thức cụ thể quyết định trong plan, áp dụng nhất quán); thiếu dữ liệu MUST làm giảm Confidence. *(BR-04)*
- **FR-020**: Confidence Score MUST tách biệt hoàn toàn với Opportunity Score và phản ánh số lượng, độ đa dạng loại nguồn, độ mới
  và độ nhất quán của bằng chứng (giảm khi `CONFLICTING`, `UNKNOWN`, bằng chứng cũ hoặc ít nguồn). *(E1-15, BR-04)*
- **FR-021**: Search volume thấp hoặc không có MUST NOT tự động loại ngách hay chặn ngách khỏi xếp hạng cao. *(BR-15)*

**Phát hiện trùng, báo cáo, quyết định**

- **FR-022**: Hệ thống MUST phát hiện ngách trùng/tương đồng (cùng nhóm khách hàng và vấn đề cốt lõi) trong cùng lượt và giữa các
  lượt; trùng chắc chắn → liên kết vào ngách sẵn có; không chắc chắn → đánh dấu "có thể tương đồng" chờ chủ sở hữu, không tự gộp.
  Logic so sánh cuối cùng MUST là mã xác định (AI chỉ có thể đề xuất). *(E1-16)*
- **FR-023**: Mỗi ngách MUST có đủ 16 trường đầu ra BR-07; trường thiếu dữ liệu MUST là `UNKNOWN`. *(BR-07)*
- **FR-024**: Hệ thống MUST tạo báo cáo xếp hạng ngách theo lượt khám phá và theo project, sắp xếp được theo Opportunity Score và
  Confidence Score, lọc theo ngưỡng, xuất được ở dạng đọc được bởi người (song ngữ VI/EN theo ngôn ngữ giao diện cho phần nhãn
  và tiêu đề; nội dung trích dẫn giữ ngôn ngữ gốc). *(E1-18, AC-16)*
- **FR-025**: AI MUST chỉ đề xuất "tiếp tục/loại bỏ" kèm lý do; chủ sở hữu ghi quyết định (tiếp tục / theo dõi / loại bỏ) kèm lý
  do; quyết định có audit và không ghi đè đề xuất của AI. *(AUT-01, Constitution IV)*
- **FR-026**: Giao diện của E1 trong MVP: [NEEDS CLARIFICATION: E1 có cần màn hình dashboard (danh sách lượt khám phá, bảng xếp
  hạng, chi tiết ngách) hay chỉ cần API và báo cáo xuất file, để E4 làm dashboard đầy đủ?]

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
- **FR-031**: Trang không truy cập được, bị robots.txt chặn hoặc trả lỗi MUST bị bỏ qua có ghi lý do, không làm hỏng cả lượt
  khám phá. *(QA-07, NFR-11)*
- **FR-032**: Mỗi lượt khám phá MUST ghi nhận: số lời gọi AI, chi phí (tách REAL/MOCK), số nguồn đã truy cập/bỏ qua và lý do, số
  ngách ứng viên, số ngách đạt đủ trường. *(Constitution VI, NFR-09)*
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
- **Ngách (Niche)**: tên, micro-niche, quốc gia, nhóm khách hàng, trạng thái (ứng viên / theo dõi / tiếp tục / loại bỏ / ẩn), đề
  xuất của AI và quyết định của chủ sở hữu, cờ rủi ro (monetization, tuân thủ), liên kết tới các lượt khám phá đã phát hiện nó.
- **Lần đánh giá ngách (Niche Evaluation)**: điểm thành phần 6 tiêu chí (giá trị hoặc `UNKNOWN`), Opportunity Score, Confidence
  Score và các yếu tố cấu thành, phiên bản trọng số, thời điểm; nhiều lần đánh giá cho một ngách.
- **Nhóm pain point (Pain Point)**: mô tả, mức độ nghiêm trọng, số bằng chứng, trạng thái xác minh; thuộc một ngách.
- **Buyer Persona**: nhóm khách hàng, bối cảnh, mục tiêu, rào cản, khả năng chi trả; mỗi thuộc tính có trạng thái xác minh.
- **Đối thủ / giải pháp hiện có (Competitor)**: tên/định danh, loại giải pháp, điểm mạnh/yếu có bằng chứng; thuộc một ngách.
- **Phiên bản trọng số (Scoring Weights Version)**: 6 trọng số (tổng 100%), số phiên bản, người tạo, thời điểm.
- **Nguồn (Research Source)** và **Bằng chứng (Research Evidence)**: hạ tầng dùng chung của E0 (URL/định danh chuẩn hóa, loại nguồn,
  hash nội dung, thời điểm thu thập; trích đoạn, trạng thái xác minh, thời điểm xác minh, job thu thập).
- **Báo cáo xếp hạng (Ranking Report)**: ảnh chụp danh sách ngách đã xếp hạng của một lượt hoặc project tại một thời điểm, kèm phiên
  bản trọng số và bộ lọc đã dùng.
- **Chính sách nguồn (Source Policy)**: loại nguồn, bật/tắt, giới hạn tần suất, số lần thử lại, thời gian chờ, yêu cầu tuân thủ.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Chủ sở hữu khởi chạy được một lượt khám phá không chọn lĩnh vực chỉ với tối đa 3 thao tác (chọn thị trường – xác
  nhận cấu hình – chạy) và nhận danh sách ngách xếp hạng khi lượt chạy hoàn tất. *(AC-04)*
- **SC-002**: Trong lượt khám phá không chọn lĩnh vực, các ngách ứng viên thuộc ít nhất 3 lĩnh vực khác nhau (kiểm tra với bộ dữ
  liệu kiểm thử chuẩn).
- **SC-003**: 100% ngách trong báo cáo có đủ 16 trường đầu ra bắt buộc (giá trị hoặc `UNKNOWN`). *(BR-07)*
- **SC-004**: 100% kết luận được hiển thị có ít nhất một bằng chứng có nguồn và thời điểm thu thập, hoặc mang trạng thái `UNKNOWN`;
  0 số liệu search volume/CPC/keyword difficulty/thị trường do hệ thống tự tạo. *(AC-07, AC-09, NFR-04)*
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
- Không triển khai E2–E8 trong feature này.
