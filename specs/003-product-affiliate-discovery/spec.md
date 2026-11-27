# Feature Specification: E2 – Product & Affiliate Discovery

**Feature Branch**: `claude/inspiring-wright-06dzhw` (thư mục spec: `specs/003-product-affiliate-discovery`)

**Created**: 2026-11-27

**Status**: Draft

**Input**: User description: "E2 – Product & Affiliate Discovery. Từ các ngách E1 đã đủ bằng chứng, tìm sản phẩm theo ngách và pain
point, website chính thức, chương trình affiliate; xác minh chương trình; thu thập hoa hồng, cookie, phương thức thanh toán, điều kiện
đăng ký từ Việt Nam, quốc gia được quảng bá, giới hạn quảng cáo; giá và tính năng; khách hàng mục tiêu; loại trùng; chấm điểm
Opportunity/Confidence; lưu nguồn và thời gian xác minh; theo dõi thay đổi điều khoản (Should). Yêu cầu Master E2-01…E2-17, BR-02,
BR-04, BR-08, AC-07, AC-08, AC-09, AC-19. Mọi nguồn qua adapter, chỉ nguồn ALLOWED; kiểm thử bằng adapter/dữ liệu MOCK
(data_origin=MOCK); không tự đăng ký affiliate; không bịa hoa hồng/cookie/giá (UNKNOWN khi không xác minh được); không gọi API có phí;
tái sử dụng hạ tầng E0/E1 (evidence, source registry, PII, gateway, jobs) không đổi hành vi E0/E1."

## Clarifications

### Session 2026-11-27 (quyết định chủ sở hữu cho Q1–Q2 của /speckit-specify)

- Q: Ngách nào được chạy Product Discovery? → A: **C có điều kiện** – mọi ngách đạt ngưỡng bằng chứng E1 (≥ 2 bằng chứng pain point
  hợp lệ từ ≥ 2 nhóm nguồn độc lập, trạng thái `EVIDENCE_SUFFICIENT`) và chưa bị loại bỏ: `PURSUE`, `WATCH` hoặc chưa có quyết định.
  `INSUFFICIENT_EVIDENCE` và `REJECTED` bị từ chối. Chủ sở hữu phải chủ động chọn ngách hoặc tự cấu hình lịch; không chạy hàng loạt tự
  động khi chưa cấu hình; giữ giới hạn ngân sách AI của E0.
- Q: Tiêu chí và trọng số Opportunity Score sản phẩm? → A: **A** – phù hợp pain point & buyer persona 25%, hấp dẫn chương trình affiliate
  25%, khả năng tham gia & quảng bá hợp lệ 20%, uy tín & chất lượng sản phẩm 15%, giá phù hợp khả năng chi trả 15%. Bổ sung: trọng số cấu
  hình được và có version; chỉ chấm bằng dữ liệu có bằng chứng; `UNKNOWN` không gán điểm giả; Opportunity và Confidence tách biệt; hiển
  thị Coverage (%) và thông tin còn thiếu; chưa xác minh chương trình → `AFFILIATE_UNVERIFIED`; chưa xác minh điều kiện tham gia từ Việt
  Nam hoặc quyền quảng bá ở thị trường mục tiêu → không được `READY_TO_PROMOTE`; không đề xuất quảng bá chỉ vì hoa hồng cao; Product Score
  không phải dự báo doanh thu.

### Session 2026-11-27 (b) (/speckit-clarify – đề xuất theo yêu cầu chủ sở hữu và mặc định cấu hình được; không có câu hỏi nghiệp vụ mới)

- Q: Ngưỡng Coverage mặc định cho sản phẩm? → A: **60%**, giống E1 (FR-019a của E1) – cấu hình được, có version cùng bộ trọng số. Thêm điều
  kiện: tiêu chí "phù hợp pain point & buyer persona" phải có dữ liệu, nếu không sản phẩm vào "cần nghiên cứu thêm" dù Coverage ≥ 60%.
  (Chủ sở hữu yêu cầu đề xuất, ưu tiên nhất quán E1.)
- Q: Điểm số và quyết định gắn với sản phẩm hay với cặp (sản phẩm, ngách)? → A: **Cặp (sản phẩm, ngách)**: mức phù hợp pain point/persona,
  thị trường mục tiêu và giá so với khả năng chi trả phụ thuộc ngách. Sản phẩm và chương trình affiliate là bản ghi dùng chung trong
  project (không trùng); đánh giá, xếp hạng, trạng thái sẵn sàng affiliate và quyết định của chủ sở hữu tính theo từng ngách.
- Q: Ngưỡng chấm mức từng tiêu chí (ví dụ hoa hồng bao nhiêu là "hấp dẫn")? → A: Mức rời rạc 0/25/50/75/100 theo bảng quy tắc mặc định
  trong `plan.md` (scoring rubric), **lưu cùng phiên bản trọng số và cấu hình được** – thay đổi không cần sửa mã; báo cáo cho chủ sở hữu
  rà soát.
- Q: Nguồn để tìm trang sản phẩm/điều khoản? → A: Như E1: tìm kiếm qua nguồn `ALLOWED` trong source registry; trang kết quả (website chính
  thức, trang điều khoản affiliate) tải qua page fetcher của E1, tuân thủ robots.txt, tốc độ truy cập, chặn CAPTCHA/đăng nhập/paywall. Không
  thêm loại nguồn mới trong E2.
- Q: Cảnh báo thay đổi điều khoản gửi qua đâu? → A: Trong ứng dụng (trang chi tiết chương trình + nhật ký thay đổi); không gửi email/kênh
  ngoài. Lịch kiểm tra mặc định hằng tuần qua scheduler E0, chỉ cho chương trình chủ sở hữu bật theo dõi.

## User Scenarios & Testing *(mandatory)*

Tác nhân duy nhất: **chủ sở hữu** (single-user, single-workspace). "Hệ thống" gồm Product Discovery Agent và Affiliate Verification
Agent chạy như job của E0, dùng hạ tầng bằng chứng, nguồn, che PII, AI Gateway và ngân sách đã có.

### User Story 1 - Tìm sản phẩm tiềm năng cho một ngách (Priority: P1)

Chủ sở hữu chọn một ngách đủ điều kiện từ E1 và chạy **lượt tìm sản phẩm**. Hệ thống tìm các sản phẩm/dịch vụ giải quyết pain point
của ngách (từ nguồn `ALLOWED`), xác định website chính thức của từng sản phẩm, thu thập giá, tính năng chính và khách hàng mục tiêu
kèm bằng chứng; thuộc tính không xác minh được hiển thị `UNKNOWN`.

**Why this priority**: Đây là đầu ra cốt lõi của E2 (AC-08): danh sách sản phẩm gắn với vấn đề thật của ngách. Không có nó, các
bước affiliate và chấm điểm không có đối tượng.

**Independent Test**: Với adapter nguồn giả lập và MockAIProvider, chạy lượt tìm sản phẩm cho một ngách MOCK đủ bằng chứng → có danh
sách sản phẩm gắn pain point, mỗi thuộc tính có bằng chứng hoặc `UNKNOWN`, toàn bộ gắn `MOCK`.

**Acceptance Scenarios**:

1. **Given** ngách đủ điều kiện có pain point, **When** chủ sở hữu chạy lượt tìm sản phẩm, **Then** hệ thống tạo job, trả về danh sách
   sản phẩm, mỗi sản phẩm liên kết ít nhất một pain point của ngách và có bằng chứng cho mối liên hệ đó.
2. **Given** một sản phẩm được tìm thấy, **When** xem chi tiết, **Then** thấy website chính thức (hoặc `UNKNOWN`), giá, tính năng chính,
   khách hàng mục tiêu – mỗi trường có trạng thái `VERIFIED`/`INFERRED`/`CONFLICTING`/`UNKNOWN` và nguồn.
3. **Given** không tìm thấy sản phẩm nào (QA-03), **When** lượt kết thúc, **Then** lượt hoàn tất với kết quả rỗng có lý do và ngách
   được gắn cờ rủi ro monetization – không tạo sản phẩm giả.
4. **Given** ngách `INSUFFICIENT_EVIDENCE` hoặc đã bị chủ sở hữu loại bỏ, **When** chạy lượt tìm sản phẩm, **Then** hệ thống từ chối
   với lý do rõ ràng.

---

### User Story 2 - Tìm và xác minh chương trình affiliate (Priority: P1)

Với mỗi sản phẩm, hệ thống tìm chương trình affiliate (chương trình riêng của nhà sản xuất hoặc qua mạng affiliate), rồi xác minh từ
trang điều khoản chính thức: tỷ lệ hoa hồng, thời hạn cookie, phương thức thanh toán, điều kiện đăng ký từ Việt Nam, quốc gia được
phép quảng bá, giới hạn quảng cáo (ví dụ cấm brand bidding, cấm coupon site). Hệ thống **không** đăng ký tài khoản hay chấp nhận
điều khoản.

**Why this priority**: Không có chương trình affiliate đã xác minh thì sản phẩm không kiếm tiền được; dữ liệu hoa hồng/cookie bịa gây
quyết định sai (Constitution I).

**Independent Test**: Với trang điều khoản giả lập (MOCK) chứa đủ/thiếu/mâu thuẫn thuộc tính → chương trình có thuộc tính `VERIFIED`
khi có trích đoạn từ trang chính thức, `UNKNOWN` khi thiếu, `CONFLICTING` khi hai nguồn khác nhau; không có lời gọi đăng ký nào.

**Acceptance Scenarios**:

1. **Given** sản phẩm có trang affiliate chính thức, **When** xác minh, **Then** mỗi thuộc tính (hoa hồng, cookie, thanh toán, đăng ký
   từ Việt Nam, quốc gia quảng bá, giới hạn quảng cáo) có giá trị kèm trích đoạn, URL và thời điểm xác minh, hoặc `UNKNOWN`.
2. **Given** thông tin chỉ có từ trang tổng hợp bên thứ ba, **When** xác minh, **Then** thuộc tính chỉ được `INFERRED`, không `VERIFIED`.
3. **Given** trang chính thức và trang bên thứ ba ghi tỷ lệ hoa hồng khác nhau (QA-05), **When** xác minh, **Then** thuộc tính là
   `CONFLICTING` và lưu cả hai giá trị kèm nguồn.
4. **Given** không tìm thấy chương trình hoặc không truy cập được trang điều khoản (QA-04), **When** lượt kết thúc, **Then** chương trình
   có trạng thái `UNVERIFIED` hoặc sản phẩm có trạng thái "không có chương trình", sản phẩm gắn cờ rủi ro monetization.
5. **Given** bất kỳ trạng thái nào, **When** hệ thống xử lý chương trình, **Then** không có hành động đăng ký, chấp nhận điều khoản hay
   gửi form nào được thực hiện (BR-08, AC-19).

---

### User Story 3 - Chấm điểm và xếp hạng sản phẩm (Priority: P1)

Hệ thống chấm **Opportunity Score** và **Confidence Score** độc lập cho từng sản phẩm của một ngách, loại sản phẩm trùng, và hiển thị
danh sách xếp hạng kèm điểm thành phần, phiên bản trọng số, cờ rủi ro.

**Why this priority**: Chủ sở hữu cần biết sản phẩm nào đáng quảng bá trước (BR-04, Constitution II).

**Independent Test**: Với bộ dữ liệu cố định (MOCK) gồm sản phẩm đủ/thiếu thuộc tính, điểm tính ra xác định, tái lập được từ phiên bản
trọng số; tiêu chí `UNKNOWN` không bị gán điểm giả và làm giảm Confidence.

**Acceptance Scenarios**:

1. **Given** sản phẩm có đủ dữ liệu, **When** chấm điểm, **Then** có Opportunity (0–100) từ các tiêu chí có trọng số và Confidence (0–100)
   tính riêng, lưu điểm thành phần và phiên bản trọng số.
2. **Given** tiêu chí `UNKNOWN`, **When** chấm điểm, **Then** tiêu chí đó không được gán điểm; Opportunity tính trên phần còn lại kèm
   Coverage; Confidence giảm.
3. **Given** hai bản ghi là cùng một sản phẩm (cùng website chính thức, hoặc tên chuẩn hóa trùng cùng nhà sản xuất), **When** lượt kết
   thúc, **Then** chỉ còn một sản phẩm, bằng chứng của cả hai được giữ và truy vết được.
4. **Given** danh sách xếp hạng, **When** xem, **Then** dữ liệu `MOCK` bị ẩn mặc định và chỉ hiện khi bật "hiện dữ liệu giả lập".

---

### User Story 4 - Báo cáo sản phẩm & quyết định của chủ sở hữu (Priority: P2)

Chủ sở hữu xem báo cáo sản phẩm theo ngách (danh sách xếp hạng, chương trình affiliate, nguồn), ghi quyết định cho từng sản phẩm
(chọn / theo dõi / loại bỏ) kèm lý do; ngách nhận lại tóm tắt khả năng kiếm tiền từ E2.

**Why this priority**: Đóng vòng ra quyết định trước khi sang E3 (keyword); cần nhưng không chặn giá trị của US1–US3.

**Independent Test**: Ghi quyết định với lý do → lưu, có audit; báo cáo xuất được VI/EN, loại dữ liệu MOCK mặc định.

**Acceptance Scenarios**:

1. **Given** sản phẩm đã chấm điểm, **When** chủ sở hữu chọn "loại bỏ" với lý do, **Then** quyết định được lưu kèm thời điểm và audit log;
   điểm số không đổi.
2. **Given** ngách đã chạy E2, **When** xem ngách ở E1, **Then** thấy tóm tắt: số sản phẩm, số chương trình `VERIFIED`, cờ rủi ro
   monetization – không thay đổi điểm E1 đã lưu.

---

### User Story 5 - Theo dõi thay đổi điều khoản affiliate (Priority: P3)

Chủ sở hữu bật theo dõi định kỳ cho chương trình affiliate quan tâm; hệ thống kiểm tra lại trang điều khoản chính thức theo lịch, phát
hiện thay đổi thuộc tính (ví dụ hoa hồng giảm, cookie ngắn lại, thêm giới hạn quảng cáo) và ghi lịch sử, cảnh báo chủ sở hữu.

**Why this priority**: E2-16 mức Should; giá trị khi đã có chương trình được chọn.

**Independent Test**: Hai ảnh chụp điều khoản MOCK khác nhau → phiên bản mới, danh sách thay đổi, cảnh báo; nội dung không đổi → không
tạo phiên bản mới.

**Acceptance Scenarios**:

1. **Given** chương trình đang được theo dõi, **When** lần kiểm tra mới thấy hoa hồng đổi, **Then** tạo phiên bản điều khoản mới, lưu giá
   trị cũ/mới, nguồn, thời điểm và hiển thị cảnh báo.
2. **Given** trang điều khoản không truy cập được, **When** kiểm tra theo lịch, **Then** ghi lỗi, giữ phiên bản cũ, không đổi thuộc tính
   sang `UNKNOWN` cho tới khi có dữ liệu mới.

---

### Edge Cases

- Ngách có nhiều pain point nhưng nguồn `ALLOWED` không có trang sản phẩm phù hợp → kết quả rỗng có lý do, cờ rủi ro monetization.
- Không có nguồn `ALLOWED` nào đang bật → lượt bị từ chối ngay với mã lỗi rõ ràng (như E1 FR-006e); không dùng nguồn `UNVERIFIED`.
- Trang sản phẩm/điều khoản bị robots.txt chặn, CAPTCHA, yêu cầu đăng nhập hoặc nằm sau paywall → bỏ qua có ghi lý do, không vượt.
- Tỷ lệ hoa hồng dạng khoảng ("lên tới 30%"), theo bậc, theo danh mục, phí cố định → lưu nguyên dạng có cấu trúc (kiểu, giá trị/khoảng,
  đơn vị, điều kiện); không quy đổi thành một con số khi nguồn không nêu.
- Giá theo nhiều gói, theo vùng, khuyến mãi tạm thời → lưu theo gói với tiền tệ, chu kỳ, thời điểm thu thập; khuyến mãi gắn nhãn tạm thời.
- Chương trình qua mạng affiliate yêu cầu đăng nhập để xem điều khoản → thuộc tính sau đăng nhập là `UNKNOWN`, ghi lý do "cần tài khoản"
  (không đăng nhập thay chủ sở hữu).
- Sản phẩm thuộc lĩnh vực nhạy cảm/hạn chế (y tế, tài chính, cờ bạc, chất kích thích…) → gắn cờ rủi ro tuân thủ, không tự loại.
- Nội dung trang chứa chỉ thị nhắm tới AI (prompt injection) → coi là dữ liệu, không thực thi.
- Trang chứa thông tin cá nhân (email, số điện thoại của nhân viên/khách hàng) → che PII trước khi lưu/gửi AI như E1.
- Chạy lại lượt, tiếp tục sau sự cố hay chạy theo lịch → không tạo sản phẩm, chương trình, nguồn, bằng chứng trùng.
- Ngân sách AI cạn giữa lượt → dừng/tạm dừng theo E0, giữ dữ liệu đã lưu, tiếp tục được khi có ngân sách.
- Chương trình đóng/ngừng nhận affiliate mới → trạng thái `CLOSED` có bằng chứng, sản phẩm gắn cờ rủi ro monetization.
- Thuộc tính "đăng ký từ Việt Nam" không được nêu rõ → `UNKNOWN`, không suy ra "được phép".

## Requirements *(mandatory)*

### Functional Requirements

**Đầu vào và lượt tìm sản phẩm**

- **FR-001**: Chủ sở hữu MUST chạy được lượt tìm sản phẩm cho một ngách đủ điều kiện: ngách `EVIDENCE_SUFFICIENT` theo ngưỡng E1 (≥ 2
  bằng chứng pain point hợp lệ từ ≥ 2 nhóm nguồn độc lập) có quyết định `PURSUE`, `WATCH` hoặc chưa có quyết định. Ngách
  `INSUFFICIENT_EVIDENCE` hoặc `REJECTED` MUST bị từ chối với lý do. Lượt chỉ bắt đầu khi chủ sở hữu chủ động chọn ngách hoặc tự cấu hình
  lịch cho ngách đó; hệ thống MUST NOT tự chạy Product Discovery hàng loạt khi chưa được cấu hình. *(E2-01; Clarification Q1)*
- **FR-002**: Mỗi lượt MUST có cấu hình rõ ràng (ngách, thị trường lấy từ ngách, số sản phẩm tối đa – mặc định 10, giới hạn thời gian/số
  trang, nguồn sử dụng) và được lưu cùng kết quả để tái lập.
- **FR-003**: Lượt tìm sản phẩm MUST chạy như job của E0: trạng thái, tạm dừng/tiếp tục/hủy, checkpoint sau mỗi bước, tiếp tục từ bước
  cuối hoàn thành sau sự cố. *(AUT-03, NFR-03)*
- **FR-004**: Lượt tốn phí MUST bị từ chối khi ngân sách chưa cấu hình hoặc bằng 0; mọi lời gọi AI MUST đi qua AI Gateway và cơ chế giữ
  chỗ ngân sách của E0; vượt ngân sách MUST dừng/tạm dừng, không chỉ cảnh báo. *(AUT-04, NFR-06)*
- **FR-005**: Chạy lại, chạy theo lịch hoặc tiếp tục sau sự cố MUST NOT tạo sản phẩm, chương trình, nguồn hay bằng chứng trùng. *(AUT-05,
  QA-10)*

**Nguồn dữ liệu và bằng chứng**

- **FR-006**: Mọi dữ liệu bên ngoài MUST được lấy qua adapter nguồn đã có của E1 (source registry); CHỈ nguồn `ALLOWED` đang bật được
  dùng; không có nguồn khả dụng → lượt bị từ chối với mã lỗi rõ ràng. Hệ thống MUST NOT vượt CAPTCHA, đăng nhập, paywall hay giới hạn
  tần suất; tôn trọng robots.txt, ToS và tốc độ truy cập của E1. *(BR-01, NFR-11)*
- **FR-007**: Mọi kết luận (sản phẩm phù hợp pain point, website chính thức, giá, tính năng, khách hàng mục tiêu, chương trình affiliate
  và từng thuộc tính của chương trình) MUST gắn bằng chứng có URL nguồn, trích đoạn đã che PII, thời điểm thu thập và thời điểm xác minh,
  dùng chung hạ tầng bằng chứng của E0/E1. *(E2-15, DATA-03, AC-07)*
- **FR-008**: Trạng thái xác minh MUST theo BR-02: `VERIFIED` chỉ khi có trích đoạn từ nguồn trực tiếp (website chính thức của sản phẩm
  hoặc trang điều khoản chính thức của chương trình/mạng affiliate); dữ liệu từ nguồn bên thứ ba hoặc do AI suy luận là `INFERRED`;
  nguồn mâu thuẫn là `CONFLICTING` kèm mọi giá trị và nguồn; không xác minh được là `UNKNOWN`. *(BR-02, AC-09)*
- **FR-009**: Hệ thống MUST NOT tự tạo tỷ lệ hoa hồng, thời hạn cookie, giá, đánh giá, tính năng hay số liệu bán hàng; AI chỉ được trích
  xuất từ nội dung đã thu thập và mỗi giá trị trích xuất MUST trỏ về bằng chứng chứa nó, nếu không MUST bị loại thành `UNKNOWN`.
  *(Constitution I, NFR-04)*
- **FR-010**: Nội dung thu thập MUST qua bước che PII của E1 trước khi lưu và trước khi gửi AI; nội dung `NEEDS_REVIEW` MUST NOT được gửi
  AI; nội dung web MUST được coi là dữ liệu không tin cậy, không thực thi như chỉ thị. *(Constitution V)*

**Sản phẩm**

- **FR-011**: Hệ thống MUST tìm sản phẩm/dịch vụ giải quyết pain point của ngách; mỗi sản phẩm MUST liên kết ≥ 1 pain point của ngách
  kèm bằng chứng cho mối liên hệ. *(E2-01, AC-08)*
- **FR-012**: Hệ thống MUST xác định website chính thức của sản phẩm (tên miền của nhà sản xuất/nhà cung cấp, không phải trang bán lại hay
  trang review); không xác định được → `UNKNOWN`. *(E2-02)*
- **FR-013**: Hệ thống MUST thu thập giá (theo gói: số tiền, tiền tệ, chu kỳ, thời điểm thu thập, nhãn khuyến mãi tạm thời) và tính năng
  chính của sản phẩm, mỗi mục có bằng chứng hoặc `UNKNOWN`. *(E2-11)*
- **FR-014**: Hệ thống MUST xác định khách hàng mục tiêu của sản phẩm và mức khớp với buyer persona của ngách (E1), kèm bằng chứng; suy
  luận của AI gắn `INFERRED`. *(E2-12)*
- **FR-015**: Hệ thống MUST phát hiện sản phẩm trùng trong cùng ngách và giữa các lượt (cùng tên miền website chính thức đã chuẩn hóa,
  hoặc tên sản phẩm chuẩn hóa trùng cùng nhà cung cấp) và gộp về một sản phẩm, giữ toàn bộ bằng chứng và lịch sử truy vết. *(E2-13)*
- **FR-016**: Sản phẩm thuộc lĩnh vực nhạy cảm/hạn chế MUST được gắn cờ rủi ro tuân thủ; hệ thống không tự loại.

**Chương trình affiliate**

- **FR-017**: Hệ thống MUST tìm chương trình affiliate cho mỗi sản phẩm (chương trình riêng của nhà cung cấp hoặc qua mạng affiliate),
  lưu tên chương trình, đơn vị vận hành (nhà cung cấp hoặc mạng affiliate), URL trang chương trình/điều khoản. *(E2-03)*
- **FR-018**: Mỗi chương trình MUST có trạng thái xác minh tổng: `VERIFIED` (trang điều khoản chính thức đã đọc được và ≥ 1 thuộc tính cốt
  lõi – hoa hồng hoặc cookie – `VERIFIED`), `PARTIAL`, `UNVERIFIED`, `CLOSED` (có bằng chứng ngừng nhận affiliate). *(E2-04)*
- **FR-019**: Tỷ lệ hoa hồng MUST lưu dạng có cấu trúc: kiểu (phần trăm / cố định / theo bậc / theo danh mục / định kỳ), giá trị hoặc khoảng,
  tiền tệ (nếu cố định), thời hạn hoa hồng định kỳ, điều kiện – kèm bằng chứng hoặc `UNKNOWN`. *(E2-05)*
- **FR-020**: Thời hạn cookie MUST lưu số ngày (hoặc "phiên", "không nêu") kèm bằng chứng, hoặc `UNKNOWN`. *(E2-06)*
- **FR-021**: Phương thức thanh toán MUST lưu danh sách phương thức, ngưỡng thanh toán tối thiểu, chu kỳ thanh toán (nếu nêu) kèm bằng chứng,
  hoặc `UNKNOWN`. *(E2-07)*
- **FR-022**: Điều kiện đăng ký từ Việt Nam MUST là một trong: `ALLOWED` (nguồn nêu rõ chấp nhận/không loại trừ Việt Nam trong danh sách
  quốc gia), `NOT_ALLOWED` (nguồn nêu rõ loại trừ), `UNKNOWN` (không nêu) – kèm bằng chứng; MUST NOT suy ra `ALLOWED` khi nguồn im lặng.
  *(E2-08)*
- **FR-023**: Quốc gia/khu vực được phép quảng bá MUST lưu danh sách (hoặc "toàn cầu" khi nguồn nêu rõ) kèm bằng chứng; hệ thống MUST so với
  thị trường mục tiêu của ngách và gắn cờ khi thị trường không được phép hoặc `UNKNOWN`. *(E2-09)*
- **FR-024**: Giới hạn quảng cáo MUST lưu danh sách có mã chuẩn (ví dụ `NO_BRAND_BIDDING`, `NO_COUPON_SITES`, `NO_PPC`, `NO_EMAIL`,
  `NO_SOCIAL_ADS`, `OTHER` kèm mô tả) kèm bằng chứng; không tìm thấy → `UNKNOWN` (không phải "không có giới hạn"). *(E2-10)*
- **FR-025**: Hệ thống MUST NOT tự đăng ký tài khoản affiliate, gửi form, chấp nhận điều khoản, đăng nhập vào mạng affiliate hay thanh toán;
  mọi chức năng như vậy không tồn tại trong E2. *(BR-08, AC-19, Constitution IV)*
- **FR-026**: Mỗi sản phẩm MUST có trạng thái sẵn sàng affiliate, tính bằng mã xác định từ chương trình tốt nhất của nó:
  - `READY_TO_PROMOTE`: có chương trình `VERIFIED`/`PARTIAL` với điều kiện đăng ký từ Việt Nam `ALLOWED` **và** thị trường mục tiêu của
    ngách nằm trong phạm vi quảng bá đã xác minh (`VERIFIED`) – cả hai có bằng chứng;
  - `ELIGIBILITY_UNVERIFIED`: có chương trình `VERIFIED`/`PARTIAL` nhưng điều kiện từ Việt Nam hoặc quyền quảng bá ở thị trường mục tiêu
    là `UNKNOWN`/`INFERRED`/`CONFLICTING`;
  - `NOT_ELIGIBLE`: nguồn nêu rõ loại trừ Việt Nam (`NOT_ALLOWED`) hoặc loại trừ thị trường mục tiêu;
  - `AFFILIATE_UNVERIFIED`: tìm thấy chương trình nhưng chưa xác minh được (`UNVERIFIED`);
  - `NO_PROGRAM` / `PROGRAM_CLOSED`: không tìm thấy chương trình / chương trình đã đóng (có bằng chứng).
  Mọi trạng thái khác `READY_TO_PROMOTE` MUST mang cờ rủi ro monetization; ngách có toàn bộ sản phẩm mang cờ này MUST gắn cờ rủi ro
  monetization cấp ngách. `READY_TO_PROMOTE` chỉ là điều kiện tham gia, không phải khuyến nghị quảng bá. *(BR-06, Constitution II;
  Clarification Q2)*

**Chấm điểm**

- **FR-027**: Mỗi sản phẩm MUST có Opportunity Score (0–100) là tổng có trọng số của 5 tiêu chí, trọng số mặc định: phù hợp pain point &
  buyer persona 25%, hấp dẫn chương trình affiliate 25%, khả năng tham gia & quảng bá hợp lệ 20%, uy tín & chất lượng sản phẩm 15%, giá phù
  hợp khả năng chi trả 15%. Mỗi tiêu chí MUST được chấm từ dữ liệu có bằng chứng theo quy tắc xác định (mức điểm rời rạc, không do AI chấm
  trực tiếp). Trọng số MUST cấu hình được, tổng 100%, có phiên bản; mỗi lần chấm MUST lưu phiên bản trọng số và điểm thành phần.
  *(E2-14, Constitution II; Clarification Q2)*
- **FR-028**: Tiêu chí `UNKNOWN` MUST NOT được gán điểm giả; Opportunity tính lại trên các tiêu chí có dữ liệu kèm **Coverage** (tổng trọng
  số gốc của tiêu chí có dữ liệu, 0–100%) và danh sách thông tin còn thiếu, cả hai hiển thị cùng điểm. Coverage dưới ngưỡng → sản phẩm ở
  danh sách "cần nghiên cứu thêm" với `INSUFFICIENT_SCORING_DATA`; ngưỡng mặc định **60%** (cấu hình được, có version), và tiêu chí phù hợp
  pain point & buyer persona MUST có dữ liệu. *(Clarification 2026-11-27 (b))*
- **FR-028a**: Hệ thống MUST NOT đề xuất quảng bá (khuyến nghị "chọn") một sản phẩm chỉ dựa trên hoa hồng: khuyến nghị "chọn" chỉ hợp lệ khi
  sản phẩm `READY_TO_PROMOTE`, tiêu chí phù hợp pain point có dữ liệu và Coverage đạt ngưỡng; lý do khuyến nghị MUST dẫn bằng chứng về mức
  phù hợp pain point. *(Clarification Q2)*
- **FR-029**: Confidence Score MUST tính riêng, không dùng Opportunity làm đầu vào, phản ánh số lượng, độ đa dạng nguồn, độ mới, tỷ lệ
  thuộc tính `VERIFIED` so với `INFERRED`/`CONFLICTING`/`UNKNOWN`. *(BR-04)*
- **FR-029a**: Đánh giá, xếp hạng, trạng thái sẵn sàng affiliate (FR-026) và quyết định (FR-033) MUST gắn với cặp (sản phẩm, ngách); sản phẩm
  và chương trình affiliate là bản ghi dùng chung trong project. *(Clarification 2026-11-27 (b))*
- **FR-030**: Logic chấm điểm, gộp trùng, đối chiếu thị trường và cờ rủi ro MUST là mã xác định, không giao cho AI; AI chỉ trích xuất có
  bằng chứng. *(Constitution III)*
- **FR-031**: Opportunity Score MUST NOT được trình bày như dự báo doanh thu; giao diện và báo cáo ghi rõ đây là điểm ưu tiên nghiên cứu.

**Báo cáo, quyết định, API và giao diện**

- **FR-032**: Hệ thống MUST tạo báo cáo sản phẩm theo ngách: danh sách xếp hạng (đủ dữ liệu) và danh sách "cần nghiên cứu thêm", mỗi
  sản phẩm có chương trình affiliate, điểm, cờ rủi ro, nguồn; xuất được VI/EN.
- **FR-033**: AI MUST chỉ đề xuất "chọn/loại bỏ" kèm lý do; chủ sở hữu ghi quyết định (chọn / theo dõi / loại bỏ) kèm lý do bắt buộc; quyết
  định không thay đổi điểm số và được ghi audit log.
- **FR-034**: Ngách E1 MUST hiển thị tóm tắt E2 (số sản phẩm, số chương trình `VERIFIED`, cờ rủi ro monetization) mà không thay đổi điểm hay
  đánh giá E1 đã lưu.
- **FR-035**: Mọi dữ liệu do nguồn giả lập hoặc MockAIProvider sinh ra MUST mang `data_origin = MOCK`, bị ẩn khỏi xếp hạng/báo cáo mặc định,
  hiển thị nhãn giả lập; chế độ giả lập MUST bị từ chối ở production. *(Constitution I)*
- **FR-036**: E2 MUST cung cấp API cho mọi chức năng và **2 màn hình tối thiểu song ngữ** (mặc định tiếng Việt): danh sách sản phẩm theo ngách
  (xếp hạng, lọc MOCK) và chi tiết sản phẩm (thuộc tính kèm trạng thái/nguồn, chương trình affiliate, quyết định). Mọi chuỗi qua i18n.
  *(Constitution VIII, XII)*
- **FR-037**: Thay đổi cấu hình E2 (trọng số, nguồn, theo dõi điều khoản) và quyết định của chủ sở hữu MUST được ghi audit log không chứa
  secret.
- **FR-038**: Mỗi lượt MUST ghi nhận: số lời gọi AI, chi phí (tách REAL/MOCK), số trang thu thập (thành công/thất bại kèm lý do), số sản phẩm,
  số chương trình theo trạng thái xác minh, thời gian chạy, lý do dừng. *(Constitution VI, NFR-09)*
- **FR-039**: Mỗi agent của E2 (Product Discovery, Affiliate Verification) MUST khai báo input/output schema, tool được phép, timeout, token
  budget, số bước tối đa, retry policy; output AI MUST được validate theo schema, sai schema thử lại có giới hạn rồi đánh dấu lỗi.
  *(Constitution V, NFR-14, NFR-15)*

**Theo dõi điều khoản (Should) và tích hợp mạng affiliate (Later)**

- **FR-040** *(Should)*: Chủ sở hữu SHOULD bật/tắt theo dõi điều khoản cho từng chương trình; hệ thống kiểm tra lại theo lịch của E0 (mặc định
  hằng tuần), lưu phiên bản điều khoản khi thuộc tính thay đổi (giá trị cũ/mới, nguồn, thời điểm) và cảnh báo trong ứng dụng (không gửi
  kênh ngoài); lỗi truy cập không xóa giá trị cũ. *(E2-16)*
- **FR-041** *(Later)*: Tích hợp API của mạng affiliate (E2-17) nằm ngoài phạm vi triển khai E2; thiết kế MUST để mạng affiliate có thể được
  thêm như một loại adapter nguồn mà không sửa nghiệp vụ. *(E2-17, NFR-07)*

### Key Entities *(include if feature involves data)*

- **Product Discovery Run (lượt tìm sản phẩm)**: một job E0 cho một ngách; cấu hình, trạng thái, số liệu FR-038, `data_origin`.
- **Product (sản phẩm)**: thuộc một project và gắn ≥ 1 ngách; tên, nhà cung cấp, website chính thức, khóa chống trùng, cờ rủi ro (monetization,
  tuân thủ), quyết định của chủ sở hữu, `data_origin`.
- **Product Attribute (thuộc tính sản phẩm)**: giá theo gói, tính năng, khách hàng mục tiêu, mức khớp persona – mỗi giá trị có trạng thái xác
  minh và bằng chứng.
- **Product–Pain Point Link**: liên kết sản phẩm với pain point của ngách kèm bằng chứng.
- **Affiliate Program (chương trình affiliate)**: tên, đơn vị vận hành (nhà cung cấp/mạng), URL điều khoản, trạng thái xác minh tổng, các thuộc
  tính có cấu trúc (hoa hồng, cookie, thanh toán, đăng ký từ Việt Nam, quốc gia quảng bá, giới hạn quảng cáo) mỗi thuộc tính có trạng thái và
  bằng chứng; liên kết với một hoặc nhiều sản phẩm.
- **Program Terms Version (phiên bản điều khoản)**: ảnh chụp thuộc tính tại một thời điểm, các thay đổi so với phiên bản trước (Should).
- **Product Evaluation (lần chấm điểm)**: theo cặp (sản phẩm, ngách); Opportunity, Confidence, Coverage, điểm thành phần, phiên bản trọng số, thời điểm.
- **Product Scoring Weights (bộ trọng số)**: phiên bản, trọng số các tiêu chí, người/thời điểm tạo.
- Dùng lại: Niche, Pain Point, Buyer Persona (E1); Research Source, Research Evidence (E0/E1); Agent Job, AI Usage, Audit Log (E0).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% sản phẩm và chương trình trong báo cáo có mọi thuộc tính bắt buộc ở trạng thái có bằng chứng (`VERIFIED`/`INFERRED`/
  `CONFLICTING`) hoặc `UNKNOWN`; 0 giá trị hoa hồng, cookie, giá không truy về được bằng chứng (kiểm tra tự động).
- **SC-002**: 0 hành động đăng ký affiliate, chấp nhận điều khoản, đăng nhập hay gửi form được thực hiện trong mọi lượt (kiểm tra tự động trên
  toàn bộ lời gọi ra ngoài của test).
- **SC-003**: Chạy lại cùng lượt 2 lần cho kết quả 0 bản ghi sản phẩm/chương trình/bằng chứng trùng.
- **SC-004**: Điểm số tái lập 100%: chấm lại từ dữ liệu và phiên bản trọng số đã lưu cho cùng kết quả.
- **SC-005**: Với dữ liệu MOCK chuẩn, một lượt tìm sản phẩm cho một ngách (≤ 10 sản phẩm) hoàn tất trong ≤ 5 phút trên cấu hình tham chiếu
  (4 core, 15 GB RAM).
- **SC-006**: Chủ sở hữu xem được danh sách sản phẩm xếp hạng và chi tiết một sản phẩm (thuộc tính, chương trình, nguồn) bằng VI và EN; 100%
  chuỗi giao diện mới có bản dịch hai ngôn ngữ.
- **SC-007**: 0 bản ghi `MOCK` xuất hiện trong báo cáo/xếp hạng mặc định; production từ chối khởi động khi cấu hình nguồn/AI giả lập.
- **SC-008**: Với nguồn thật `ALLOWED` và AI thật, ≥ 70% sản phẩm của ngách đủ điều kiện có website chính thức `VERIFIED` và ≥ 50% có ít nhất
  một chương trình affiliate `VERIFIED`/`PARTIAL`. *(Chỉ đo được khi có nguồn `ALLOWED` và được phép gọi AI thật – hiện `BLOCKED`, không đánh
  dấu PASS bằng dữ liệu MOCK.)*

## Assumptions

- E1 đã cung cấp ngách, pain point, buyer persona, hạ tầng bằng chứng, source registry, che PII, gộp nguồn trùng và các agent job; E2 dùng
  lại qua interface đã công bố, không sửa hành vi E0/E1.
- Thị trường mục tiêu của lượt E2 lấy từ ngách (mặc định Mỹ); ngôn ngữ nghiên cứu theo thị trường.
- Đối tượng gồm sản phẩm vật lý, phần mềm/SaaS và sản phẩm số; dịch vụ cá nhân (thuê người) không nằm trong phạm vi.
- Mạng affiliate (Amazon Associates, Impact, CJ, ShareASale/Awin, PartnerStack…) chỉ được đọc qua trang công khai khi là nguồn `ALLOWED`;
  API mạng affiliate là E2-17 (Later) và cần khóa API – ngoài phạm vi.
- Bảng `affiliate_applications` và `affiliate_links` (Master DATA) chưa tạo trong E2 vì E2 không có chức năng đăng ký hay link (BR-08);
  sẽ tạo khi có feature cần.
- Ngưỡng Coverage 60% và cách tính Confidence dùng lại khung của E1 (cùng hướng, tham số riêng cho sản phẩm).
- Kiểm thử tự động dùng MockAIProvider và adapter nguồn giả lập; không gọi API có phí; SC-008 chỉ kiểm chứng khi có nguồn `ALLOWED` và AI thật.
- Ngân sách AI mặc định cho lượt E2 dùng hạn mức job/ngày/tháng của E0 ($2/job, $3/ngày, $30/tháng như E1) cho tới khi chủ sở hữu đổi.
