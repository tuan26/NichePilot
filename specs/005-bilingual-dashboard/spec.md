# Feature Specification: E4 – Bilingual Dashboard

**Feature Branch**: `feature/e4-bilingual-dashboard` (thư mục spec: `specs/005-bilingual-dashboard`)

**Created**: 2026-11-28

**Status**: Draft

**Input**: Lộ trình chủ sở hữu (2026-11-27): "E4 dashboard" sau E3; master E4-01…E4-18, AC-07, AC-12, AC-18, QA-12, QA-13, UI-08, BR-10.
Ghi chú master §2: khung frontend (đăng nhập, i18n, layout, trạng thái hệ thống) thuộc E0 (FR-060); E0 chỉ cung cấp Agent Jobs, chi phí AI
và Settings qua API – giao diện quản lý các chức năng đó thuộc E4 (E4-12, E4-13, E4-15).

## Clarifications

### Session 2026-11-28 (mặc định kỹ thuật cấu hình được – không có câu hỏi nghiệp vụ mới; chủ sở hữu cho phép tiếp tục "làm hết những thứ có thể làm")

- Q: Trang chủ `/` hiện là trang Trạng thái hệ thống của E0 (đã nghiệm thu, có E2E). Trang Tổng quan đặt ở đâu? → A: `/overview`; menu điều
  hướng có mục "Tổng quan" đứng đầu; `/` giữ nguyên trang Trạng thái hệ thống của E0 (không đổi hành vi E0).
- Q: Xuất báo cáo "CSV/Excel" (Should) dùng định dạng nào? → A: CSV UTF-8 có BOM (Excel mở trực tiếp, giữ tiếng Việt), không thêm
  dependency tạo `.xlsx`. Ô bắt đầu bằng `=`, `+`, `-`, `@`, tab hoặc CR được thêm tiền tố `'` để chống công thức (CSV injection). MOCK chỉ
  xuất khi người dùng đang bật hiển thị MOCK, và dòng MOCK có cột `data_origin`.
- Q: Trang Settings được sửa những gì? → A: Cấu hình KHÔNG bí mật đã có API của E0 (FR-055): ngân sách (ngày/tháng/mặc định mỗi job/ngưỡng
  cảnh báo), múi giờ, giới hạn agent, ngôn ngữ giao diện mặc định, thị trường/ngôn ngữ nội dung/ngôn ngữ nghiên cứu của dự án. Provider,
  model, giá model và Model Task Profile chỉ **hiển thị** (không sửa, không có nút xác minh model, không có nút kiểm tra kết nối provider
  trong E4) – tránh thao tác có thể dẫn tới gọi API có phí. Công tắc gọi API có phí chỉ hiển thị trạng thái (cấu hình qua biến môi trường).
- Q: Trang Product Discovery / Keyword Research toàn cục (E4-10, E4-11) khác gì trang theo ngách đã có ở E2/E3? → A: Trang toàn cục liệt kê
  các ngách đủ điều kiện kèm tóm tắt sản phẩm/keyword (số lượng, sẵn sàng affiliate, cluster tốt nhất) và liên kết sang trang theo ngách đã có;
  không tạo luồng nghiệp vụ mới.
- Q: Trang Agent Jobs làm được gì? → A: Danh sách job (lọc trạng thái/loại job), chi tiết job + các bước, tạm dừng/tiếp tục/hủy/thử lại
  theo API E0; danh sách lịch chạy với bật/tắt và xóa. Không tạo job/lịch mới từ trang này (lượt được tạo từ trang nghiệp vụ E1–E3).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Điều hướng song ngữ và trang Tổng quan (Priority: P1)

Chủ sở hữu đăng nhập, dùng menu điều hướng để tới mọi trang; trang Tổng quan cho thấy nhanh tình trạng nghiên cứu (số ngách theo trạng thái
bằng chứng/quyết định, số sản phẩm và số sẵn sàng affiliate, số keyword/cluster, job đang chạy/lỗi gần đây, chi phí hôm nay/tháng so với ngân
sách, ngách hàng đầu kèm Opportunity + Confidence), bằng tiếng Việt mặc định hoặc tiếng Anh.

**Why this priority**: AC-12 – dashboard song ngữ là tiêu chí MVP; Tổng quan là điểm vào duy nhất cho các kết quả E1–E3.

**Independent Test**: Seed MOCK E1–E3 → mở Tổng quan, bật MOCK → số liệu khớp DB, đổi EN → mọi chuỗi tiếng Anh, tải lại vẫn EN.

**Acceptance Scenarios**:

1. **Given** đã đăng nhập, **When** mở bất kỳ trang nào, **Then** menu có Tổng quan, Ngách, Sản phẩm, Keyword, Agent Jobs, Chi phí, Cài đặt,
   Nguồn dữ liệu, Trạng thái hệ thống; mục hiện tại được đánh dấu.
2. **Given** dữ liệu MOCK, **When** mở Tổng quan mặc định, **Then** số liệu nghiệp vụ chỉ tính REAL (MOCK ẩn); bật MOCK thì hiện kèm nhãn.
3. **Given** chưa có dữ liệu, **When** mở Tổng quan, **Then** mỗi khối hiển thị trạng thái rỗng có hướng dẫn bước tiếp theo (QA-13).
4. **Given** chuyển EN, **When** tải lại trang, **Then** vẫn tiếng Anh; ngày giờ và số định dạng theo locale.

---

### User Story 2 - Trang Product Discovery và Keyword Research toàn cục (Priority: P1)

Chủ sở hữu xem các ngách đủ điều kiện cùng tóm tắt sản phẩm (số sản phẩm, số sẵn sàng affiliate, rủi ro kiếm tiền) và tóm tắt keyword (số
keyword, cluster, long-tail, cluster tốt nhất) rồi đi tới trang chi tiết theo ngách của E2/E3.

**Why this priority**: E4-10, E4-11 – truy cập kết quả E2/E3 mà không phải đi qua từng ngách.

**Independent Test**: Seed MOCK → trang Sản phẩm/Keyword liệt kê ngách demo với số liệu khớp API E2/E3, liên kết mở đúng trang theo ngách.

**Acceptance Scenarios**:

1. **Given** ngách có sản phẩm/keyword, **When** mở trang, **Then** mỗi dòng có tên ngách, Opportunity/Confidence ngách, tóm tắt E2/E3 và
   liên kết.
2. **Given** ngách chưa chạy E2/E3, **When** xem, **Then** hiển thị "chưa có" kèm liên kết chạy (trang theo ngách), không hiện số 0 như kết quả.

---

### User Story 3 - Trang Agent Jobs (Priority: P1)

Chủ sở hữu xem danh sách job (loại, trạng thái, thời gian, chi phí, nguồn dữ liệu REAL/MOCK), lọc theo trạng thái/loại, mở chi tiết với các
bước, và tạm dừng/tiếp tục/hủy/thử lại; xem và bật/tắt/xóa lịch chạy.

**Why this priority**: E4-12 – E0 chỉ có API (FR-060); thiếu giao diện là thiếu kiểm soát agent.

**Independent Test**: Tạo job qua API → trang hiển thị, hủy từ giao diện → trạng thái CANCELLED; lịch tắt → `enabled=false`.

**Acceptance Scenarios**:

1. **Given** job đang chạy, **When** bấm Hủy và xác nhận, **Then** gọi API E0, trạng thái cập nhật, có thông báo song ngữ.
2. **Given** job lỗi, **When** mở chi tiết, **Then** thấy mã lỗi thân thiện (không stack trace) và các bước.

---

### User Story 4 - Trang Chi phí và Settings (Priority: P2)

Chủ sở hữu xem chi phí AI (hôm nay/tháng, theo provider/model/task type), REAL và MOCK tách riêng, so với ngân sách; sửa cấu hình không bí
mật (ngân sách, múi giờ, giới hạn agent, ngôn ngữ giao diện mặc định, thị trường và ngôn ngữ nội dung/nghiên cứu); xem provider/model/Model Task
Profile ở chế độ chỉ đọc.

**Why this priority**: E4-13, E4-15; cấu hình đã có API E0.

**Independent Test**: Sửa ngân sách ngày → API lưu, audit; giá trị sai (âm, ngày > tháng) → lỗi validate song ngữ; MOCK cost hiển thị riêng.

**Acceptance Scenarios**:

1. **Given** có lượt MOCK, **When** xem Chi phí, **Then** chi phí MOCK không cộng vào chi phí thực.
2. **Given** sửa ngôn ngữ nội dung mặc định, **When** lưu, **Then** ngôn ngữ giao diện không đổi (BR-10, E4-07).

---

### User Story 5 - Xuất báo cáo CSV (Priority: P3, Should)

Chủ sở hữu xuất bảng xếp hạng ngách, danh sách sản phẩm theo ngách và keyword theo ngách ra CSV mở được bằng Excel.

**Why this priority**: E4-16 Should.

**Independent Test**: Xuất từ dữ liệu có ô bắt đầu bằng `=` → ô được vô hiệu hóa công thức; tiếng Việt hiển thị đúng; chỉ số UNKNOWN giữ chữ
`UNKNOWN`.

**Acceptance Scenarios**:

1. **Given** bảng có dữ liệu, **When** bấm Xuất CSV, **Then** tải tệp UTF-8 BOM với tiêu đề cột theo ngôn ngữ giao diện.

### Edge Cases

- API lỗi/ngắt mạng → thông báo thân thiện + nút thử lại; không lộ chi tiết kỹ thuật (FR-061 E0).
- Erasure ledger chưa áp dụng → các khối dữ liệu nghiên cứu hiển thị lỗi 503 thân thiện, khối hệ thống/chi phí vẫn dùng được.
- Danh sách rất dài (≥ 500 ngách/job) → phân trang hoặc giới hạn + thông báo "hiển thị N mới nhất".
- Phiên hết hạn → chuyển về đăng nhập.
- Chuỗi dịch thiếu → test thất bại (không hiển thị khóa thô).

## Requirements *(mandatory)*

### Functional Requirements

**Song ngữ & điều hướng**

- **FR-001**: Mọi trang E4 MUST hiển thị bằng tiếng Việt và tiếng Anh, mặc định tiếng Việt, có nút chuyển VI/EN và ghi nhớ lựa chọn (dùng hạ
  tầng E0). *(E4-01…E4-04, AC-12, QA-12)*
- **FR-002**: Menu, form, thông báo, lỗi và trạng thái rỗng MUST được dịch; không có chuỗi hard-code trong JSX (kiểm tra tự động). *(E4-05,
  UI-08)*
- **FR-003**: Ngày giờ, số, tiền tệ và phần trăm MUST định dạng theo locale giao diện. *(E4-06)*
- **FR-004**: Ngôn ngữ giao diện MUST độc lập với ngôn ngữ nội dung/nghiên cứu: đổi một cái không đổi cái kia. *(E4-07, BR-10)*
- **FR-005**: Mọi trang sau đăng nhập MUST có menu điều hướng tới Tổng quan, Ngách, Sản phẩm, Keyword, Agent Jobs, Chi phí, Cài đặt, Nguồn dữ
  liệu, Trạng thái hệ thống; trang hiện tại được đánh dấu (`aria-current`).

**Tổng quan**

- **FR-006**: Hệ thống MUST cung cấp trang Tổng quan và API tổng hợp chỉ đọc: số ngách theo trạng thái bằng chứng và quyết định, số sản phẩm,
  số sẵn sàng affiliate, số keyword, cluster, job theo trạng thái (đang chạy/chờ/lỗi 7 ngày), chi phí hôm nay/tháng REAL và MOCK tách riêng
  so với ngân sách, tối đa 5 ngách hàng đầu kèm Opportunity và Confidence. *(E4-08, E4-14, E4-15)*
- **FR-007**: Số liệu nghiệp vụ trên Tổng quan MUST loại MOCK mặc định và chỉ gồm MOCK khi người dùng bật; giá trị MOCK có nhãn. *(Constitution I)*
- **FR-008**: Mỗi khối MUST có trạng thái đang tải, lỗi (có thử lại) và rỗng có hướng dẫn. *(QA-13)*

**Trang nghiệp vụ**

- **FR-009**: Trang Niche Discovery MUST truy cập được từ menu (dùng trang xếp hạng/chi tiết E1). *(E4-09)*
- **FR-010**: Trang Product Discovery toàn cục MUST liệt kê ngách đủ điều kiện (theo quy tắc E2) kèm tóm tắt E2 và liên kết tới trang sản phẩm
  theo ngách; ngách chưa chạy E2 hiển thị "chưa có", không hiển thị 0 như kết quả. *(E4-10)*
- **FR-011**: Trang Keyword Research toàn cục MUST liệt kê ngách đủ điều kiện kèm tóm tắt E3 (số keyword, cluster, long-tail, cluster có
  Opportunity cao nhất) và liên kết tới trang keyword theo ngách. *(E4-11)*
- **FR-012**: Mọi điểm hiển thị trên dashboard MUST đi kèm Confidence (hoặc `UNKNOWN`) và đường tới bằng chứng/nguồn ở trang chi tiết; không
  hiển thị Opportunity đơn độc. *(E4-14, AC-07)*

**Agent Jobs**

- **FR-013**: Trang Agent Jobs MUST liệt kê job (loại, trạng thái, tạo lúc, cập nhật, chi phí, `data_origin`) có lọc trạng thái/loại và giới
  hạn số dòng; chi tiết job hiển thị tham số không bí mật, kết quả/mã lỗi thân thiện và các bước. *(E4-12)*
- **FR-014**: Trang Agent Jobs MUST cho phép tạm dừng/tiếp tục/hủy/thử lại theo trạng thái hợp lệ của API E0, có xác nhận cho hủy; nút không hợp
  lệ bị ẩn/khóa. *(E4-12)*
- **FR-015**: Trang Agent Jobs MUST liệt kê lịch chạy (loại job, biểu thức lịch, bật/tắt, lần chạy tiếp theo) và cho bật/tắt/xóa (xóa có xác
  nhận). *(E4-12)*

**Chi phí & Settings**

- **FR-016**: Trang Chi phí MUST hiển thị chi phí hôm nay/tháng so với ngân sách, theo provider/model/task type; REAL và MOCK tách riêng, MOCK
  không cộng vào chi phí thực. *(E4-15, Constitution VI)*
- **FR-017**: Trang Settings MUST cho xem/sửa cấu hình không bí mật có API E0 (ngân sách, múi giờ, giới hạn agent, ngôn ngữ giao diện mặc
  định, thị trường, ngôn ngữ nội dung, ngôn ngữ nghiên cứu); lỗi validate từ API hiển thị theo trường, song ngữ. *(E4-13, FR-055 E0)*
- **FR-018**: Trang Settings MUST hiển thị provider (đã cấu hình hay chưa, gợi ý khóa đã che), model, giá và Model Task Profile ở chế độ chỉ
  đọc; MUST NOT có thao tác xác minh model, sửa giá, kiểm tra kết nối hay bật gọi API có phí. *(Constitution VI, X)*
- **FR-019**: Secret MUST NOT xuất hiện ở bất kỳ trang/response E4 nào. *(FR-054 E0)*

**Xuất báo cáo**

- **FR-020** *(Should)*: Bảng xếp hạng ngách, sản phẩm theo ngách và keyword theo ngách MUST xuất được CSV UTF-8 BOM, tiêu đề theo ngôn ngữ giao
  diện, vô hiệu hóa công thức ở ô nguy hiểm, giữ `UNKNOWN`, chỉ gồm MOCK khi đang bật. *(E4-16)*
- **FR-021** *(Later)*: Content Calendar (E4-17) và Revenue Dashboard (E4-18) nằm ngoài phạm vi E4 (phụ thuộc E7, E8).

**Chất lượng**

- **FR-022**: Luồng end-to-end (đăng nhập → Tổng quan → ngách → sản phẩm → keyword → Agent Jobs → Chi phí → Cài đặt → đổi ngôn ngữ) MUST có
  test E2E tự động với dữ liệu MOCK. *(AC-18 phần tự động; QA-12)*
- **FR-023**: Dashboard E4 MUST NOT gọi API có phí, bật nguồn, hay thực hiện hành động bên ngoài; mọi thao tác ghi đi qua API E0–E3 có audit.

### Key Entities

- **Overview** (chỉ đọc, tổng hợp): bộ đếm ngách/sản phẩm/keyword/job, chi phí REAL/MOCK, ngách hàng đầu.
- **NicheResearchRow** (chỉ đọc): ngách + điểm E1 + tóm tắt E2 + tóm tắt E3.
- Không có bảng mới.

## Success Criteria *(mandatory)*

- **SC-001**: 100% chuỗi giao diện E4 có bản dịch VI và EN (test tự động); 0 chuỗi hard-code trong JSX.
- **SC-002**: Số liệu Tổng quan khớp 100% với truy vấn trực tiếp DB trên dữ liệu kiểm thử (REAL/MOCK tách đúng).
- **SC-003**: Tổng quan và các trang danh sách tải (API p95) < 500 ms với 500 ngách, 500 job trên cấu hình tham chiếu.
- **SC-004**: Mọi trang có trạng thái rỗng/lỗi có hướng dẫn (test render).
- **SC-005**: Luồng E2E FR-022 PASS trong CI.
- **SC-006**: CSV xuất ra mở được bằng Excel (UTF-8 BOM), 0 ô bắt đầu bằng ký tự công thức chưa được vô hiệu hóa.

## Assumptions

- Dùng API E0–E3 hiện có; thêm 2 endpoint chỉ đọc (`/api/v1/dashboard/overview`, `/api/v1/dashboard/niches`). Không bảng mới, không dependency mới.
- Một chủ sở hữu, không phân quyền nhiều người dùng (MVP).
- Kiểm thử bằng dữ liệu MOCK; AC-18 "thực tế" với nguồn/AI thật vẫn `EXTERNAL_VERIFICATION_PENDING`.
