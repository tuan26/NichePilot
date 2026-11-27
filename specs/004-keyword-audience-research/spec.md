# Feature Specification: E3 – Keyword & Audience Research

**Feature Branch**: `feature/e3-keyword-audience` (thư mục spec: `specs/004-keyword-audience-research`)

**Created**: 2026-11-27

**Status**: Draft

**Input**: User description: "E3 – Keyword & Audience Research. Keyword xuất phát từ niche, pain point, buyer persona và sản phẩm; không chỉ
keyword hot; ưu tiên long-tail, commercial intent và problem-based keyword; không bịa Search Volume, CPC, Keyword Difficulty – không có
nguồn hợp lệ thì UNKNOWN; không bắt buộc API keyword trả phí trong giai đoạn phát triển; đánh giá cơ hội dựa trên search intent, mức phù
hợp, cạnh tranh quan sát được và bằng chứng; Opportunity và Confidence tách biệt; MOCK không phải dữ liệu nghiên cứu thật. Master E3-01…
E3-15, BR-04, BR-05, BR-09, BR-10, BR-15, AC-10, AC-11, AC-16."

## Clarifications

### Session 2026-11-27 (quyết định chủ sở hữu – Q1 của /speckit-specify)

- Q: Tiêu chí và trọng số Keyword Opportunity Score? → A: **A** – phù hợp pain point/persona/sản phẩm 30%, giá trị theo search intent 20%,
  cơ hội cạnh tranh quan sát được 20%, khoảng trống nội dung 15%, bằng chứng nhu cầu 15%. Yêu cầu kèm: trọng số cấu hình được + version;
  Coverage tối thiểu 60%; Opportunity ⟂ Confidence; `UNKNOWN` không gán điểm giả; không bịa Search Volume/CPC/KD; keyword xuất phát từ ngách,
  pain point, persona, sản phẩm; ưu tiên long-tail và commercial intent phù hợp; **không mặc định keyword ý định mua cao luôn tốt hơn keyword
  giải quyết vấn đề thực tế**.

### Session 2026-11-27 (b) (/speckit-clarify – mặc định kỹ thuật cấu hình được, không có câu hỏi nghiệp vụ mới)

- Q: "Giá trị theo search intent" chấm thế nào để không ưu tiên mặc định ý định mua? → A: Theo mức hữu ích cho nội dung affiliate giải quyết
  vấn đề: `COMMERCIAL_INVESTIGATION` 100; `INFORMATIONAL` gắn pain point (loại `PROBLEM`/`SOLUTION`) 75; `TRANSACTIONAL` 75; `INFORMATIONAL`
  chung chung 25; `NAVIGATIONAL` 0. Problem-based ngang hàng transactional; bảng nằm trong rubric, cấu hình được.
- Q: Lượt có chạy được khi không có nguồn `ALLOWED`? → A: Có: keyword sinh từ dữ liệu nội bộ (ngách, pain point, persona, sản phẩm); bước
  SERP/đối thủ/kênh bị bỏ qua với `NO_COMPLIANT_SEARCH_SOURCE`, các tiêu chí phụ thuộc SERP `UNKNOWN` → Coverage thấp hơn; không dữ liệu thay thế.
- Q: Gom cluster? → A: Xác định: cùng nguồn gốc chính (pain point hoặc sản phẩm) và cùng intent; điểm cluster = trung bình keyword thành viên
  `SCORED`, Confidence cluster = trung bình; cluster không có keyword `SCORED` → "cần nghiên cứu thêm".
- Q: Giới hạn mặc định của lượt? → A: ≤ 60 keyword, phân tích SERP cho ≤ 10 keyword ưu tiên (xếp theo điểm sơ bộ không cần SERP), ≤ 3 trang đối
  thủ/SERP, 60 trang, 30 phút – cấu hình được theo lượt.
- Q: Theo dõi SERP (Should)? → A: Như theo dõi điều khoản E2: chủ sở hữu bật cho cluster + tự tạo lịch E0; cảnh báo trong ứng dụng.

## User Scenarios & Testing *(mandatory)*

Tác nhân duy nhất: **chủ sở hữu**. "Hệ thống" gồm Keyword Research Agent và Content Strategy Agent (mức đề xuất) chạy như job E0, dùng hạ
tầng nguồn/bằng chứng/che PII/AI Gateway/ngân sách của E0–E2.

### User Story 1 - Sinh keyword từ ngách, pain point, persona và sản phẩm (Priority: P1)

Chủ sở hữu chọn một ngách đủ điều kiện và chạy **lượt nghiên cứu keyword**. Hệ thống sinh danh sách keyword ứng viên xuất phát từ pain
point, buyer persona, giải pháp hiện tại và sản phẩm E2 của ngách; mỗi keyword có loại (problem-based, solution, product/commercial,
comparison, informational), độ dài (head / mid / long-tail) và liên kết truy vết tới pain point/persona/sản phẩm nguồn.

**Why this priority**: AC-10 – keyword phải xuất phát từ ngách thật, không từ danh sách keyword hot.

**Independent Test**: Ngách MOCK đủ bằng chứng + 2 sản phẩm demo → lượt sinh keyword gắn pain point/sản phẩm, có long-tail và commercial
intent, mọi chỉ số Search Volume/CPC/KD là `UNKNOWN`, toàn bộ gắn `MOCK`.

**Acceptance Scenarios**:

1. **Given** ngách đủ điều kiện có pain point và persona, **When** chạy lượt keyword, **Then** mỗi keyword liên kết ≥ 1 pain point, mục
   tiêu persona hoặc sản phẩm của ngách, kèm lý do; keyword không liên kết được bị loại.
2. **Given** ngách có sản phẩm E2 không bị loại bỏ, **When** chạy lượt, **Then** có keyword commercial (best/review/alternative/vs/pricing)
   cho các sản phẩm đó.
3. **Given** không có nguồn dữ liệu keyword hợp lệ, **When** xem keyword, **Then** Search Volume, CPC, Keyword Difficulty hiển thị `UNKNOWN`
   (không ước lượng, không 0).
4. **Given** ngách không đủ điều kiện (như quy tắc E2), **When** chạy lượt, **Then** bị từ chối với lý do.

---

### User Story 2 - Phân loại intent và phân tích SERP/đối thủ (Priority: P1)

Với từng keyword ưu tiên, hệ thống phân loại search intent và quan sát kết quả tìm kiếm qua nguồn `ALLOWED` (SERP): loại trang đang xếp
hạng, đối thủ, cấu trúc nội dung của trang đối thủ (đề mục, độ sâu, có/không so sánh, có/không bằng chứng trải nghiệm) và content gap.
Chỉ lưu tóm tắt cấu trúc và trích đoạn ngắn (BR-09), không lưu nguyên văn.

**Why this priority**: AC-11 – phân tích intent và đối thủ; cạnh tranh "quan sát được" thay cho Keyword Difficulty khi không có dữ liệu.

**Independent Test**: SERP + trang đối thủ giả lập → intent được phân loại có lý do, quan sát cạnh tranh có bằng chứng (URL, loại trang),
content gap liệt kê chủ đề đối thủ chưa đáp ứng pain point; không lưu nội dung đối thủ quá giới hạn trích dẫn.

**Acceptance Scenarios**:

1. **Given** keyword đã sinh, **When** phân loại intent, **Then** intent ∈ {informational, commercial investigation, transactional,
   navigational} kèm lý do và trạng thái `INFERRED`; tín hiệu từ SERP quan sát được thì kèm URL bằng chứng.
2. **Given** SERP có trang đối thủ, **When** phân tích, **Then** mỗi kết quả lưu URL, loại trang (diễn đàn, bài review, trang sản phẩm,
   video, Q&A…), tên miền, thời điểm thu thập; cấu trúc nội dung là tóm tắt (đề mục, các tiêu chí phủ) – trích đoạn ≤ giới hạn E0.
3. **Given** đối thủ không trả lời một pain point của ngách, **When** phân tích gap, **Then** gap được ghi kèm pain point và bằng chứng.
4. **Given** nguồn tìm kiếm không có hoặc bị chặn, **When** phân tích, **Then** SERP = `UNKNOWN` có lý do; không tạo SERP giả.

---

### User Story 3 - Cluster, chấm điểm và xếp hạng keyword (Priority: P1)

Hệ thống gom keyword thành cluster theo chủ đề/intent, chấm **Opportunity Score** và **Confidence Score** độc lập cho keyword và cluster,
hiển thị Coverage và thông tin còn thiếu, xếp hạng; keyword search volume thấp/UNKNOWN không bị loại tự động.

**Why this priority**: E3-07, E3-11, E3-12, BR-04, BR-15.

**Independent Test**: Bộ dữ liệu MOCK cố định → điểm xác định, tái lập từ phiên bản trọng số; tiêu chí UNKNOWN không gán điểm giả.

**Acceptance Scenarios**:

1. **Given** keyword có intent, mức phù hợp và quan sát SERP, **When** chấm điểm, **Then** có Opportunity (0–100) từ tiêu chí có trọng số
   và Confidence tách biệt, lưu phiên bản trọng số và điểm thành phần.
2. **Given** Search Volume `UNKNOWN`, **When** chấm điểm, **Then** keyword vẫn được xếp hạng dựa trên các tiêu chí còn lại; Coverage phản
   ánh phần thiếu; không có tiêu chí nào dùng số liệu bịa.
3. **Given** keyword gần nghĩa, **When** cluster, **Then** mỗi keyword thuộc đúng một cluster, cluster có keyword chính, intent chủ đạo,
   điểm cluster tính từ keyword thành viên.

---

### User Story 4 - Persona cấp keyword, kênh tiếp cận và đề xuất content strategy (Priority: P2)

Chủ sở hữu xem persona cấp cluster (mở rộng persona ngách E1), cộng đồng/kênh nơi khách hàng thảo luận (có bằng chứng) và **đề xuất
content strategy** cho từng cluster ưu tiên (loại nội dung, góc tiếp cận, pain point giải quyết, sản phẩm liên quan, keyword mục tiêu);
ghi quyết định (chọn / theo dõi / loại bỏ) kèm lý do. Đây chỉ là đề xuất – không tạo bài viết (E5).

**Why this priority**: E3-09, E3-10, E3-13; đóng vòng trước E4/E5.

**Independent Test**: Cluster MOCK → strategy có cấu trúc, dẫn keyword/pain point/sản phẩm; quyết định có audit; báo cáo VI/EN loại MOCK.

**Acceptance Scenarios**:

1. **Given** cluster ưu tiên, **When** xem, **Then** có persona cấp cluster (mục tiêu, rào cản, mức hiểu biết) với trạng thái xác minh,
   kênh tiếp cận có bằng chứng, và đề xuất content strategy có liên kết truy vết.
2. **Given** chủ sở hữu loại bỏ cluster với lý do, **When** lưu, **Then** quyết định có audit, điểm không đổi.

---

### User Story 5 - Theo dõi thay đổi SERP (Priority: P3, Should)

Chủ sở hữu bật theo dõi cho cluster quan trọng; hệ thống kiểm tra lại SERP theo lịch, ghi phiên bản và thay đổi (trang mới vào/ra, loại
trang đổi) và cảnh báo trong ứng dụng.

**Why this priority**: E3-15 (Should).

**Independent Test**: Hai SERP MOCK khác nhau → phiên bản mới + danh sách thay đổi; SERP lỗi không xóa dữ liệu cũ.

**Acceptance Scenarios**:

1. **Given** cluster được theo dõi, **When** SERP đổi, **Then** tạo phiên bản mới với thay đổi và cảnh báo.

---

### Edge Cases

- Ngách chưa có sản phẩm E2 → vẫn sinh keyword problem-based/solution từ pain point và persona; keyword commercial cho sản phẩm = 0, có lý do.
- Không có nguồn `ALLOWED` → bước SERP/đối thủ/kênh bị bỏ qua với `NO_COMPLIANT_SEARCH_SOURCE`; keyword vẫn được sinh từ dữ liệu nội bộ
  (ngách, pain point, persona, sản phẩm) và chấm điểm với Coverage thấp hơn; không tạo dữ liệu SERP thay thế.
- AI đề xuất keyword có số liệu (vd. "10K searches") → số liệu bị bỏ, chỉ giữ chuỗi keyword.
- Keyword trùng/gần trùng (khác hoa/thường, số ít/nhiều, thứ tự từ) → gộp về một keyword.
- Keyword chứa thương hiệu đối thủ → gắn cờ (rủi ro brand bidding theo điều khoản E2), không tự loại.
- Lĩnh vực nhạy cảm (y tế, tài chính…) → cờ rủi ro tuân thủ như E1/E2.
- Trang đối thủ bị robots chặn/đăng nhập/paywall → bỏ qua có lý do.
- Nội dung đối thủ chứa PII hoặc chỉ thị nhắm tới AI → che PII; coi là dữ liệu, không thực thi.
- Chạy lại/tiếp tục sau sự cố → không tạo keyword, cluster, SERP, bằng chứng trùng.
- Ngân sách AI cạn → dừng/tạm dừng theo E0.

## Requirements *(mandatory)*

### Functional Requirements

**Đầu vào và lượt nghiên cứu**

- **FR-001**: Chủ sở hữu MUST chạy được lượt nghiên cứu keyword cho một ngách đủ điều kiện theo cùng quy tắc E2 (Clarification Q1 E2:
  `EVIDENCE_SUFFICIENT`, chưa bị loại bỏ, chủ sở hữu chủ động chọn hoặc tự cấu hình lịch); ngách không đủ điều kiện MUST bị từ chối có lý do;
  hệ thống MUST NOT tự chạy hàng loạt. *(E3-01)*
- **FR-002**: Đầu vào của lượt MUST gồm pain point, buyer persona, giải pháp hiện tại (E1) và sản phẩm E2 của ngách chưa bị loại bỏ (nếu có);
  cấu hình lượt (số keyword tối đa, số keyword phân tích SERP, giới hạn trang/thời gian) MUST được lưu để tái lập.
- **FR-003**: Lượt MUST chạy như job E0 (trạng thái, tạm dừng/tiếp tục/hủy, checkpoint, tiếp tục sau sự cố); mọi lời gọi AI qua AI Gateway
  và giữ chỗ ngân sách E0; vượt ngân sách dừng/tạm dừng; lượt tốn phí bị từ chối khi chưa cấu hình ngân sách; một lượt hoạt động/ngách.
- **FR-004**: Chạy lại, chạy theo lịch, tiếp tục sau sự cố MUST NOT tạo keyword, cluster, quan sát SERP hay bằng chứng trùng. *(AUT-05)*

**Sinh keyword**

- **FR-005**: Hệ thống MUST sinh keyword từ pain point, persona và sản phẩm; mỗi keyword MUST liên kết ≥ 1 nguồn gốc (pain point, thuộc tính
  persona, sản phẩm) kèm lý do; keyword không liên kết được MUST bị loại. *(E3-01, AC-10)*
- **FR-006**: Mỗi keyword MUST có loại (`PROBLEM`, `SOLUTION`, `PRODUCT`, `COMPARISON`, `INFORMATIONAL`) và độ dài (`HEAD` 1–2 từ, `MID` 3,
  `LONG_TAIL` ≥ 4 từ – tính bằng mã); lượt MUST ưu tiên long-tail và problem-based/commercial: mặc định ≥ 50% keyword là long-tail. *(E3-02)*
- **FR-007**: Hệ thống MUST sinh keyword commercial-intent cho sản phẩm E2 (best/review/alternative/vs/pricing/discount theo mẫu cấu hình được)
  và gắn cờ keyword chứa thương hiệu khi chương trình affiliate có giới hạn `NO_BRAND_BIDDING`. *(E3-03)*
- **FR-008**: Keyword trùng/gần trùng MUST được gộp (chuẩn hóa hoa/thường, dấu, số ít/nhiều, thứ tự từ) trong ngách và giữa các lượt.
- **FR-009**: Search Volume, CPC và Keyword Difficulty MUST là `UNKNOWN` khi không có nguồn dữ liệu keyword hợp lệ; hệ thống MUST NOT ước
  lượng, suy luận hay lấy số từ đầu ra AI cho các chỉ số này; khi có nguồn hợp lệ trong tương lai, giá trị MUST có nguồn, thời điểm và phạm vi
  (quốc gia/ngôn ngữ). Không có nguồn keyword trả phí nào được tích hợp trong E3. *(BR-05)*
- **FR-010**: Search Volume thấp hoặc `UNKNOWN` MUST NOT tự động loại keyword hay chặn keyword khỏi xếp hạng cao. *(BR-15)*

**Intent, SERP, đối thủ, gap**

- **FR-011**: Mỗi keyword được phân tích MUST có intent ∈ {`INFORMATIONAL`, `COMMERCIAL_INVESTIGATION`, `TRANSACTIONAL`, `NAVIGATIONAL`} kèm
  lý do và trạng thái (`INFERRED` từ ngữ nghĩa; tín hiệu SERP quan sát được kèm bằng chứng). *(E3-04, AC-11)*
- **FR-012**: Quan sát SERP MUST lấy qua nguồn `ALLOWED` của E1 (chỉ nguồn đang bật, tuân thủ robots/tốc độ/che PII), lưu cho mỗi kết quả:
  vị trí quan sát, URL, tên miền, loại trang, tiêu đề, thời điểm thu thập, nguồn; không có nguồn → SERP `UNKNOWN` có lý do. *(E3-05)*
- **FR-013**: Phân tích đối thủ MUST tải trang xếp hạng qua page fetcher của E1 và lưu **tóm tắt cấu trúc** (đề mục chính, các chủ đề/tiêu chí
  được phủ, có so sánh/bảng giá/bằng chứng trải nghiệm hay không) kèm trích đoạn ngắn ≤ giới hạn E0; MUST NOT lưu hay tái xuất bản nguyên văn
  quá mức trích dẫn. *(E3-06, BR-09)*
- **FR-014**: Content gap MUST được xác định bằng đối chiếu pain point/persona của ngách với chủ đề đối thủ đã phủ; mỗi gap ghi pain point,
  keyword liên quan và bằng chứng (trang đối thủ được xét). *(E3-08)*
- **FR-015**: Cạnh tranh cấp keyword MUST được đánh giá từ quan sát SERP (loại trang, độ phủ của đối thủ với pain point, tỷ lệ diễn đàn/Q&A/
  trang mỏng trong kết quả) bằng quy tắc xác định; không quan sát được → `UNKNOWN`. Keyword Difficulty của bên thứ ba MUST NOT được bịa. *(E3-11)*

**Cluster, chấm điểm, xếp hạng**

- **FR-016**: Keyword MUST được gom cluster theo chủ đề và intent; mỗi keyword thuộc đúng một cluster; cluster có keyword chính, intent chủ
  đạo, pain point và sản phẩm liên quan. *(E3-07)*
- **FR-017**: Mỗi keyword và cluster MUST có Opportunity Score (0–100) là tổng có trọng số của các tiêu chí keyword. Bộ tiêu chí và trọng số
  mặc định: phù hợp pain point/persona/sản phẩm 30%, giá trị theo search intent 20%, cơ hội cạnh tranh quan sát được 20%, khoảng trống
  nội dung 15%, bằng chứng nhu cầu 15%. Mỗi tiêu chí chấm bằng quy tắc xác định từ dữ liệu có bằng chứng (riêng mức phù hợp do AI đề xuất có
  bằng chứng, mã kiểm tra). Giá trị intent MUST NOT mặc định ưu tiên ý định mua hơn keyword giải quyết vấn đề thực tế. Trọng số cấu hình được,
  tổng 100%, có phiên bản; lưu điểm thành phần. *(E3-12, Constitution II; Clarification Q1)*
- **FR-018**: Tiêu chí `UNKNOWN` MUST NOT được gán điểm giả; Opportunity tính trên tiêu chí có dữ liệu kèm Coverage và danh sách thiếu; Coverage
  dưới ngưỡng (mặc định 60%, như E1/E2) → "cần nghiên cứu thêm".
- **FR-019**: Confidence Score MUST tính riêng, không dùng Opportunity làm đầu vào, phản ánh độ phủ quan sát SERP, số nguồn độc lập, độ mới, tỷ
  lệ dữ liệu quan sát so với suy luận. *(BR-04)*
- **FR-020**: Chấm điểm, gộp trùng, phân loại độ dài và đánh giá cạnh tranh MUST là mã xác định; AI chỉ đề xuất keyword/intent/tóm tắt có
  bằng chứng. *(Constitution III)*
- **FR-021**: Opportunity Score MUST NOT được trình bày như dự báo traffic hay doanh thu.

**Persona, kênh, content strategy, quyết định**

- **FR-022**: Hệ thống MUST tạo persona cấp cluster (mục tiêu, rào cản, mức hiểu biết, câu hỏi điển hình) mở rộng từ persona ngách E1, mỗi
  thuộc tính có trạng thái xác minh và bằng chứng hoặc `UNKNOWN`. *(E3-09)*
- **FR-023**: Hệ thống MUST liệt kê cộng đồng/kênh nơi khách hàng thảo luận (diễn đàn, subreddit, nhóm, kênh video…) kèm bằng chứng từ nguồn
  `ALLOWED`; không có bằng chứng → `UNKNOWN`. Hệ thống MUST NOT đăng bài hay tham gia cộng đồng. *(E3-10)*
- **FR-024**: Hệ thống MUST đề xuất content strategy cho cluster: loại nội dung (hướng dẫn, so sánh, review, danh sách, FAQ), góc tiếp cận,
  pain point giải quyết, sản phẩm liên quan, keyword chính/phụ, content gap khai thác; chỉ là đề xuất, MUST NOT sinh bài viết (E5) và MUST NOT
  đề xuất tuyên bố trải nghiệm sản phẩm không có bằng chứng. *(E3-13, BR-11)*
- **FR-025**: Chủ sở hữu MUST ghi quyết định cho cluster (chọn / theo dõi / loại bỏ) kèm lý do bắt buộc; quyết định có audit, không đổi điểm.
- **FR-026**: Hệ thống MUST tạo báo cáo keyword theo ngách (cluster xếp hạng, keyword, intent, SERP, gap, strategy, nguồn) JSON/Markdown VI/EN;
  MOCK bị loại mặc định. *(AC-16)*

**Chung**

- **FR-027**: Mọi dữ liệu do nguồn/AI giả lập sinh ra MUST mang `data_origin = MOCK`, ẩn mặc định, có nhãn; chế độ giả lập bị từ chối ở
  production. *(Constitution I)*
- **FR-028**: E3 MUST cung cấp API cho mọi chức năng và 2 màn hình tối thiểu song ngữ: danh sách cluster/keyword theo ngách (xếp hạng, lọc MOCK,
  chỉ số UNKNOWN hiển thị rõ) và chi tiết cluster (keyword, intent, SERP, đối thủ, gap, persona, kênh, strategy, quyết định). *(BR-10)*
- **FR-029**: Mỗi agent E3 MUST khai báo schema vào/ra, tool, timeout, token budget, số bước, retry; output AI validate theo schema; nội dung
  web là dữ liệu không tin cậy; PII che trước khi lưu/gửi AI. *(Constitution V)*
- **FR-030**: Mỗi lượt MUST ghi số liệu: lời gọi AI, chi phí REAL/MOCK, trang thu thập (thành công/thất bại + lý do), số keyword theo loại/độ dài,
  số cluster, số keyword có quan sát SERP, lý do dừng. Thay đổi cấu hình và quyết định MUST có audit.
- **FR-031** *(Should)*: Theo dõi thay đổi SERP cho cluster được bật: kiểm tra lại theo lịch E0, phiên bản + thay đổi + cảnh báo trong ứng dụng;
  lỗi truy cập không xóa dữ liệu cũ. *(E3-15)*
- **FR-032** *(Later)*: Tích hợp Google Search Console và nguồn chỉ số keyword (volume/CPC) nằm ngoài phạm vi triển khai E3 (cần quyền truy
  cập/API key do chủ sở hữu cấp); thiết kế MUST cho phép thêm như adapter nguồn chỉ số mà không sửa nghiệp vụ, giá trị luôn kèm nguồn. *(E3-14)*

### Key Entities

- **Keyword Research Run**: job E0 cho một ngách; cấu hình, số liệu, `data_origin`.
- **Keyword**: chuỗi chuẩn hóa, ngôn ngữ, thị trường, loại, độ dài, intent (+ lý do, trạng thái), chỉ số (volume/CPC/KD – mặc định `UNKNOWN`,
  nếu có thì kèm nguồn), cờ rủi ro, liên kết nguồn gốc (pain point / persona / sản phẩm), cluster.
- **Keyword Cluster**: keyword chính, intent chủ đạo, persona cấp cluster, kênh, content strategy, quyết định, theo dõi SERP.
- **SERP Observation**: keyword, nguồn, thời điểm, danh sách kết quả (vị trí, URL, tên miền, loại trang, tiêu đề), phiên bản.
- **Competitor Page Summary**: URL, cấu trúc tóm tắt, chủ đề phủ, trích đoạn ngắn có bằng chứng.
- **Content Gap**: pain point, keyword, trang đối thủ được xét, bằng chứng.
- **Keyword Evaluation / Cluster Evaluation**: Opportunity, Confidence, Coverage, điểm thành phần, phiên bản trọng số.
- Dùng lại: Niche, Pain Point, Buyer Persona (E1); Product, Affiliate Program (E2); Research Source/Evidence, Agent Job, Audit (E0).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% keyword trong báo cáo truy vết được về ≥ 1 pain point, persona hoặc sản phẩm của ngách.
- **SC-002**: 0 giá trị Search Volume/CPC/KD không có nguồn; khi không có nguồn chỉ số, 100% hiển thị `UNKNOWN` (kiểm tra tự động).
- **SC-003**: Với dữ liệu MOCK chuẩn, ≥ 50% keyword là long-tail và có keyword commercial cho mọi sản phẩm E2 chưa bị loại.
- **SC-004**: Chạy lại lượt 2 lần → 0 keyword/cluster/SERP/bằng chứng trùng; điểm tái lập 100% từ dữ liệu + phiên bản trọng số.
- **SC-005**: Lượt MOCK (≤ 60 keyword, ≤ 10 SERP) hoàn tất ≤ 10 phút trên cấu hình tham chiếu.
- **SC-006**: Chủ sở hữu xem được cluster xếp hạng và chi tiết cluster bằng VI và EN; 100% chuỗi mới có bản dịch.
- **SC-007**: 0 nội dung đối thủ được lưu vượt giới hạn trích đoạn; 0 bản ghi MOCK trong báo cáo mặc định.
- **SC-008**: Với nguồn `ALLOWED` thật + AI thật, ≥ 70% keyword ưu tiên có quan sát SERP và intent có tín hiệu quan sát. *(Chỉ đo được khi có nguồn
  thật – hiện `BLOCKED`, không PASS bằng MOCK.)*

## Assumptions

- Thị trường/ngôn ngữ nghiên cứu lấy từ ngách (mặc định Mỹ / tiếng Anh); ngôn ngữ giao diện độc lập (BR-10).
- Không có nguồn chỉ số keyword hợp lệ trong E3 → mọi Search Volume/CPC/KD là `UNKNOWN` (chủ sở hữu 2026-11-27: không bắt buộc API trả phí).
- SERP chỉ qua nguồn `ALLOWED` của source registry E1 (hiện chưa có nguồn nào → lượt thật chỉ sinh keyword nội bộ, SC-008 `BLOCKED`).
- Sản phẩm đầu vào: sản phẩm E2 của ngách có quyết định ≠ `REJECTED`.
- Content strategy chỉ là đề xuất; tạo nội dung thuộc E5.
- Ngân sách AI theo hạn mức E0 ($2/job, $3/ngày, $30/tháng) cho tới khi chủ sở hữu đổi.
