# Feature Specification: E0 — Foundation & AI Infrastructure

**Feature Branch**: `001-foundation-ai-infrastructure` (thư mục spec; nhánh git làm việc hiện tại: `claude/inspiring-wright-06dzhw`)

**Created**: 2026-11-18

**Status**: Draft – chờ Clarify

**Input**: User description: "E0 — Foundation & AI Infrastructure: xây dựng nền tảng kỹ thuật để các AI Agent
và module hoạt động độc lập nhưng phối hợp trong cùng một hệ thống: cấu trúc dự án, API backend, database và
migration, tích hợp Claude API (mặc định) và interface cho OpenAI API (dự phòng), AI Tool Registry, quản lý Agent
Job và trạng thái, chạy thủ công và theo lịch, retry/timeout/error handling, theo dõi token và chi phí, giới hạn
ngân sách ngày/tháng/job, structured logging, audit log, xác thực Dashboard, quản lý cấu hình và API key an toàn,
Docker Compose, unit/integration test, backup/restore, checkpoint/resume." (Nguồn: Master Requirements §3.1,
E0-01…E0-20, AI-01…AI-10)

**Status cập nhật**: Clarified (2026-11-18) – sẵn sàng cho `/speckit-plan`

## Clarifications

### Session 2026-11-18

- Q: Khi chi phí ước tính của lời gọi AI kế tiếp vượt ngân sách, job xử lý thế nào và ngân sách mặc định là bao nhiêu? → A: Job chuyển `PAUSED_BUDGET`, tiếp tục từ checkpoint sau khi chủ sở hữu điều chỉnh ngân sách; mặc định $3/ngày, $30/tháng, $2/job, cấu hình được; hệ thống không tự tăng ngân sách và không tự chuyển model để vượt giới hạn.
- Q: API key được lưu và cập nhật ở đâu? → A: Chỉ trong file `.env` hoặc Docker secrets; không lưu trong database; không hiển thị giá trị trên Dashboard, không ghi log; có chức năng kiểm tra kết nối API; không commit `.env` chứa thông tin nhạy cảm.
- Q: E0 triển khai những trang giao diện nào? → A: Chỉ khung Dashboard song ngữ VI/EN: khởi tạo tài khoản, đăng nhập, trang trạng thái, chuyển ngôn ngữ. Agent Jobs, chi phí AI, Settings chỉ cung cấp qua API trong E0; giao diện đầy đủ ở E4.
- Q: Hàng đợi job và scheduler dùng hạ tầng nào? → A: PostgreSQL làm hàng đợi; đánh giá Procrastinate trước, nếu không phù hợp thì tự triển khai tối giản bằng `SELECT … FOR UPDATE SKIP LOCKED`; không thêm Redis/Valkey trong E0; phải hỗ trợ retry, timeout, checkpoint, idempotency, chống xử lý trùng.
- Q: Môi trường phát triển trên Windows chạy thế nào? → A: Docker Desktop + WSL2, mã nguồn trong filesystem WSL, có hot-reload, tương đồng Linux production; có hướng dẫn cài đặt, khởi động, kiểm tra và xử lý lỗi cho Windows 10/11.
- Q (yêu cầu bổ sung của chủ sở hữu): Chọn model AI và xử lý khi Claude từ chối thế nào? → A: Claude là AI chính, OpenAI dự phòng; model cấu hình theo từng tác vụ, không hard-code model mặc định trong business logic; ưu tiên model hiệu quả chi phí phù hợp từng tác vụ (không bắt buộc Opus); khi Claude từ chối vì lý do chính sách, KHÔNG tự chuyển sang model/provider khác – ghi nhận trạng thái và lý do để kiểm tra.
- Q (yêu cầu bổ sung – phát triển khi chưa có API key): Phát triển và kiểm thử E0 thế nào khi chủ sở hữu chỉ có Claude Pro, chưa có API key? → A: Ba provider sau một interface chung, chọn bằng cấu hình không sửa business logic: `AnthropicAPIProvider` (chính, vận hành), `OpenAIAPIProvider` (dự phòng), `MockAIProvider` (phát triển/kiểm thử khi chưa có key). E0 khởi động và kiểm thử đầy đủ (job queue, retry, checkpoint, logging, budget) bằng MockAIProvider với các kịch bản: thành công, timeout, rate limit, sai schema, lỗi provider, vượt ngân sách. Dữ liệu mock gắn nhãn rõ, không trình bày như nghiên cứu thật; MockAIProvider bị cấm ở production. Không dùng OAuth token, cookie, session hay Claude Code CLI để giả lập API; Claude Pro chỉ dùng để phát triển, phân tích thủ công, thử prompt – không phải provider, không có workflow 24/7 phụ thuộc Claude Pro. Không tự động gọi API có phí khi phát triển; chỉ gọi thật khi chủ sở hữu cho phép; khi có key chỉ cần cấu hình key + chọn provider; ngân sách giữ $3/ngày, $30/tháng, $2/job. Không báo cáo tích hợp Claude API là đã kiểm thử nếu chưa gọi API thật.

### Session 2026-11-18 (phê duyệt plan có điều kiện)

- Q: Điều kiện nào áp dụng cho model AI trước khi gọi API có phí? → A: Model ID, khả năng hỗ trợ và bảng giá phải được xác minh từ nguồn chính thức; chưa xác minh → chặn lời gọi có phí; không hard-code model ID hay giá trong business logic; cấu hình theo loại tác vụ; không tự nâng cấp/chuyển model khi chưa cấu hình.
- Q: Rào chắn MockAIProvider cần chặt đến mức nào? → A: Kiểm tra ở cả tầng cấu hình (khởi động) và runtime; production cấu hình mock → từ chối khởi động; không thể chọn mock động trong production; mọi dữ liệu mock có `data_origin = MOCK`; không xuất hiện trong báo cáo nghiên cứu hay thống kê kinh doanh thực tế; usage/chi phí mock tách hoàn toàn khỏi chi phí thật; test dùng mock không được tính là đã kiểm thử API thật.
- Q: Reservation ngân sách xử lý thế nào khi gọi thất bại hoặc chưa rõ kết quả? → A: Giữ chỗ nguyên tử trong database, an toàn khi nhiều worker; thành công → đối soát theo usage thực tế; thất bại → phân biệt "chắc chắn chưa phát sinh phí" (giải phóng) và "chưa xác định được chi phí" (giữ nguyên phần giữ chỗ, chờ đối soát); không tự động giải phóng toàn bộ khi chưa xác định; có cơ chế xử lý reservation bị treo; không thể vượt giới hạn ngày/tháng/job do race condition.
- Q: Các giá trị mặc định vận hành có cố định không? → A: Tạm chấp thuận (phiên 12 giờ, khóa 15 phút sau 5 lần sai, backup 03:00 giữ 7 bản, CI GitHub Actions, PostgreSQL 17, bảng giá mock riêng không tính là chi phí thật) và tất cả phải thay đổi được bằng cấu hình.

## User Scenarios & Testing *(mandatory)*

Tác nhân chính là **Chủ sở hữu** (người dùng duy nhất trong MVP). E0 không tạo ra kết quả nghiên cứu; nó cung
cấp nền tảng mà E1–E4 dựa vào. Để kiểm chứng nền tảng, E0 có đúng **một loại job tích hợp sẵn: "Job chẩn đoán
AI"** – gửi một yêu cầu nhỏ tới AI provider đang được cấu hình, yêu cầu kết quả có cấu trúc, gọi một tool nội bộ
vô hại, rồi ghi nhận usage và chi phí. Khi chưa có API key, job chạy với **MockAIProvider** (kết quả và chi phí
được gắn nhãn giả lập); khi có key và chủ sở hữu cho phép gọi có phí, cùng job đó chạy với provider thật mà không
sửa mã.

### User Story 1 - Khởi động hệ thống và đăng nhập an toàn (Priority: P1)

Chủ sở hữu tải mã nguồn về máy Windows, sao chép file cấu hình mẫu, điền API key, chạy một lệnh để khởi động
toàn bộ hệ thống, tạo tài khoản quản trị lần đầu, rồi đăng nhập Dashboard và thấy trạng thái sức khỏe các thành
phần (database, AI provider đã cấu hình hay chưa, worker đang chạy hay không).

**Why this priority**: Không có bước này thì không feature nào khác chạy được (AC-01, AC-15).

**Independent Test**: Trên máy sạch có Docker, làm theo hướng dẫn vận hành, khởi động hệ thống, tạo tài khoản,
đăng nhập, xem trang trạng thái – không cần API key AI thật.

**Acceptance Scenarios**:

1. **Given** máy có Docker và file cấu hình hợp lệ, **When** chủ sở hữu chạy lệnh khởi động, **Then** mọi
   thành phần bắt buộc báo "khỏe" trong vòng 5 phút và database ở phiên bản schema mới nhất.
2. **Given** hệ thống chưa có tài khoản, **When** chủ sở hữu mở Dashboard lần đầu, **Then** hệ thống yêu cầu
   tạo tài khoản quản trị (mật khẩu đạt độ mạnh tối thiểu) và không cho truy cập trang nào khác trước đó.
3. **Given** đã có tài khoản, **When** người chưa đăng nhập truy cập bất kỳ trang/API được bảo vệ, **Then**
   bị từ chối và chuyển về trang đăng nhập.
4. **Given** nhập sai mật khẩu 5 lần liên tiếp, **When** thử lần thứ 6, **Then** tài khoản bị khóa tạm 15 phút
   và sự kiện được ghi audit log.
5. **Given** chưa cấu hình API key AI, **When** xem trang trạng thái, **Then** thấy AI provider ở trạng thái
   "chưa cấu hình" (không phải lỗi hệ thống) và hệ thống vẫn hoạt động.
6. **Given** giao diện mặc định tiếng Việt, **When** chủ sở hữu chuyển sang tiếng Anh ở trang đăng nhập/trạng
   thái, **Then** toàn bộ chuỗi hiển thị bằng tiếng Anh và lựa chọn được ghi nhớ ở lần mở sau.

---

### User Story 2 - Gọi AI có kiểm soát, có cấu trúc và có ghi nhận chi phí (Priority: P1)

Chủ sở hữu cấu hình Claude là provider mặc định, chọn model cho từng loại tác vụ, rồi chạy "Job chẩn đoán AI".
Hệ thống gửi yêu cầu, nhận kết quả đúng cấu trúc đã định, gọi tool nội bộ được cấp quyền, và hiển thị số token
vào/ra, chi phí ước tính, thời gian xử lý.

**Why this priority**: Mọi agent E1–E3 phụ thuộc vào lớp AI này (AC-02); cấu trúc và validation là điều kiện của
nguyên tắc Evidence-First.

**Independent Test**: Không cần API key: chọn MockAIProvider, chạy job chẩn đoán với từng kịch bản giả lập và kiểm
tra kết quả, bản ghi usage (nhãn `MOCK`), chi phí giả lập. Có API key + được phép gọi có phí: chạy lại cùng job với
provider thật (kiểm thử tích hợp thủ công, chỉ khi chủ sở hữu cho phép).

**Acceptance Scenarios**:

1. **Given** API key hợp lệ và ngân sách đủ, **When** chạy job chẩn đoán, **Then** job thành công, kết quả qua
   kiểm tra cấu trúc, và có bản ghi usage gồm provider, model, token vào/ra/cache, chi phí ước tính, thời gian.
2. **Given** provider trả kết quả sai cấu trúc, **When** hệ thống nhận kết quả, **Then** không lưu kết quả đó,
   thử lại tối đa N lần (cấu hình, mặc định 2), sau đó đánh dấu bước thất bại với lý do "sai schema".
3. **Given** provider không phản hồi trong thời gian giới hạn, **When** hết timeout, **Then** bước được thử lại
   theo chính sách retry với khoảng chờ tăng dần, rồi thất bại có lý do rõ ràng nếu vẫn lỗi.
4. **Given** API key sai hoặc hết hạn, **When** chạy job, **Then** job thất bại ngay (không retry vô ích) với
   thông báo "API key không hợp lệ" và không lộ giá trị key ở bất kỳ đâu.
5. **Given** agent yêu cầu gọi một tool không có trong danh sách quyền của nó, **When** hệ thống xử lý yêu cầu,
   **Then** tool không được thực thi, lời từ chối được ghi log và trả về cho agent.
6. **Given** chưa cấu hình provider dự phòng, **When** Claude lỗi, **Then** hệ thống KHÔNG tự chuyển sang
   OpenAI. **Given** đã cấu hình dự phòng rõ ràng, **When** Claude lỗi thuộc loại cho phép chuyển, **Then**
   chuyển sang provider dự phòng và ghi rõ việc chuyển đổi.
7. **Given** agent đạt số bước tối đa hoặc số lời gọi AI tối đa của job, **When** muốn tiếp tục, **Then** job
   dừng với lý do "vượt giới hạn bước/lời gọi".
8. **Given** chưa có API key và provider được cấu hình là MockAIProvider, **When** chạy job chẩn đoán với kịch bản
   "thành công", **Then** job thành công, kết quả và usage được gắn nhãn `MOCK`, giao diện/API hiển thị rõ là giả
   lập, và không có lời gọi mạng nào tới provider thật.
9. **Given** MockAIProvider được cấu hình kịch bản timeout / rate limit / sai schema / lỗi provider / refusal /
   kết quả bị cắt / vượt ngân sách, **When** chạy job chẩn đoán, **Then** hệ thống xử lý đúng như với provider thật
   (retry, trạng thái, log, ngân sách) theo kịch bản tương ứng.
10. **Given** công tắc cho phép gọi API có phí đang tắt (mặc định), **When** job cần gọi provider thật, **Then** lời
   gọi bị chặn trước khi gửi với lý do "chưa được phép gọi API có phí" và không phát sinh chi phí.
11. **Given** môi trường là `production` và cấu hình chọn MockAIProvider, **When** khởi động hệ thống, **Then** hệ
   thống từ chối khởi động với thông báo rõ ràng.

---

### User Story 3 - Giới hạn ngân sách AI (Priority: P1)

Chủ sở hữu đặt ngân sách AI theo ngày, theo tháng và mức trần mặc định cho mỗi job. Hệ thống chặn mọi lời gọi
tốn phí khi vượt bất kỳ giới hạn nào và hiển thị chi tiêu hiện tại so với ngân sách.

**Why this priority**: Chi phí là rủi ro tài chính trực tiếp (AC-03, Constitution VI – không thương lượng).

**Independent Test**: Đặt ngân sách rất nhỏ, chạy job chẩn đoán (hoặc test double với usage xác định) và xác
nhận lời gọi bị chặn trước khi gửi khi ngân sách không đủ.

**Acceptance Scenarios**:

1. **Given** chưa cấu hình ngân sách, **When** chủ sở hữu tạo lịch cho job tốn phí, **Then** hệ thống từ chối
   và yêu cầu cấu hình ngân sách trước.
2. **Given** chi phí ước tính tối đa của lời gọi tiếp theo vượt phần ngân sách còn lại (ngày, tháng hoặc job),
   **When** agent chuẩn bị gọi AI, **Then** lời gọi không được gửi, job chuyển sang trạng thái `PAUSED_BUDGET` kèm lý do (ngân sách nào bị chạm,
   chi phí ước tính, phần còn lại), và hệ thống không tự tăng ngân sách hay tự đổi sang model rẻ hơn.
3. **Given** job đang `PAUSED_BUDGET`, **When** chủ sở hữu tăng ngân sách (hoặc sang ngày/tháng mới có đủ hạn
   mức) và yêu cầu tiếp tục, **Then** job tiếp tục từ checkpoint, không lặp lại bước đã hoàn tất. Job
   `PAUSED_BUDGET` không tự chạy lại khi chưa có yêu cầu tiếp tục của chủ sở hữu.
4. **Given** cài đặt mới, **When** chưa thay đổi cấu hình, **Then** ngân sách mặc định là $3/ngày, $30/tháng,
   $2/job; cả ba giá trị cấu hình được.
5. **Given** hai job chạy đồng thời, **When** cả hai cùng gần chạm ngân sách, **Then** tổng chi tiêu thực tế
   không vượt ngân sách quá chi phí của một lời gọi đang dở dang.
6. **Given** chi tiêu đạt 80% ngân sách ngày hoặc tháng, **When** xem Dashboard, **Then** thấy cảnh báo.
7. **Given** sang ngày/tháng mới (theo múi giờ cấu hình), **When** kiểm tra ngân sách, **Then** hạn mức ngày/
   tháng được tính lại từ đầu.

---

### User Story 4 - Quản lý vòng đời Agent Job (Priority: P2)

Chủ sở hữu khởi chạy job thủ công, theo dõi trạng thái và từng bước, tạm dừng, tiếp tục, hủy, chạy lại job lỗi,
và xem lịch sử job cùng chi phí từng job.

**Why this priority**: Là cơ chế vận hành chung cho mọi agent (E0-08, E0-10, E0-20, AUT-03), cần ngay sau khi
gọi AI hoạt động.

**Independent Test**: Dùng job chẩn đoán và test double cho các kịch bản: chạy, hủy giữa chừng, lỗi rồi chạy
lại, worker khởi động lại giữa chừng.

**Acceptance Scenarios**:

1. **Given** job đã được tạo, **When** worker nhận job, **Then** trạng thái chuyển `QUEUED → RUNNING` và từng
   bước được ghi lại với thời gian bắt đầu/kết thúc, kết quả, lỗi (nếu có).
2. **Given** job đang chạy, **When** chủ sở hữu bấm hủy, **Then** job dừng trước bước/lời gọi ngoài kế tiếp,
   chuyển `CANCELLED`, không tạo thêm chi phí.
3. **Given** job thất bại ở bước 3/5, **When** chủ sở hữu chạy lại, **Then** job tiếp tục từ checkpoint sau bước
   2 đã hoàn tất và không tạo bản ghi trùng.
4. **Given** worker bị dừng đột ngột khi job đang chạy, **When** worker khởi động lại, **Then** job bị bỏ dở được
   phát hiện trong vòng 5 phút và được đưa về trạng thái có thể tiếp tục.
5. **Given** cùng một yêu cầu job (cùng loại, cùng tham số, cùng chu kỳ) được gửi hai lần, **When** hệ thống xử
   lý, **Then** chỉ một job được tạo.
6. **Given** job đang chạy, **When** chủ sở hữu tạm dừng rồi tiếp tục, **Then** job dừng sau bước hiện tại và
   tiếp tục từ bước kế tiếp.

---

### User Story 5 - Chạy job theo lịch (Priority: P2)

Chủ sở hữu tạo lịch chạy định kỳ cho một loại job (ví dụ hằng ngày lúc 02:00), bật/tắt lịch, và xem lần chạy
gần nhất/kế tiếp.

**Why this priority**: E1-19 (nghiên cứu theo lịch) và AC-13 phụ thuộc cơ chế này.

**Independent Test**: Tạo lịch tần suất ngắn cho job chẩn đoán (test double trong test tự động), xác nhận job
được tạo đúng thời điểm, không trùng.

**Acceptance Scenarios**:

1. **Given** lịch đang bật và ngân sách đã cấu hình, **When** đến thời điểm lịch, **Then** đúng một job được tạo
   (dù có nhiều worker hoặc worker khởi động lại).
2. **Given** lịch bị tắt, **When** đến thời điểm, **Then** không job nào được tạo.
3. **Given** hệ thống tắt trong thời điểm lịch, **When** khởi động lại, **Then** lần chạy bị lỡ được xử lý theo
   chính sách đã cấu hình (mặc định: chạy bù tối đa một lần).

---

### User Story 6 - Cấu hình an toàn và audit (Priority: P3)

Chủ sở hữu xem và thay đổi cấu hình hệ thống (provider, model theo tác vụ, ngân sách, thị trường/ngôn ngữ mặc
định, giới hạn agent), thấy API key ở dạng che, kiểm tra kết nối provider, và tra cứu audit log mọi thay đổi.

**Why this priority**: Cần cho vận hành an toàn (E0-14, E0-16) nhưng có thể dùng giá trị mặc định trong giai đoạn
đầu.

**Independent Test**: Thay đổi cấu hình qua API/Dashboard, xác nhận audit log ghi giá trị trước/sau (không có
secret), xác nhận secret không xuất hiện trong response, log và giao diện.

**Acceptance Scenarios**:

1. **Given** API key đã được cấu hình, **When** xem trang cấu hình hoặc gọi API cấu hình, **Then** chỉ thấy dạng
   che (ví dụ 4 ký tự cuối) và trạng thái "đã cấu hình".
2. **Given** chủ sở hữu đổi ngân sách tháng, **When** lưu, **Then** audit log ghi ai, khi nào, giá trị cũ, giá trị
   mới.
3. **Given** cấu hình mới không hợp lệ (ví dụ ngân sách âm, model không có trong bảng giá), **When** lưu, **Then**
   bị từ chối với thông báo lỗi bằng ngôn ngữ giao diện hiện tại.
4. **Given** API key chỉ được quản lý trong `.env`/Docker secrets, **When** chủ sở hữu thay key và khởi động lại
   thành phần liên quan theo hướng dẫn, **Then** key mới có hiệu lực mà không cần sửa mã nguồn, và database không
   chứa bất kỳ API key nào.
5. **Given** API key đã cấu hình, **When** chủ sở hữu gọi chức năng kiểm tra kết nối provider, **Then** nhận kết
   quả "kết nối được / key không hợp lệ / không có mạng / chưa cấu hình" mà không phát sinh chi phí đáng kể (dùng
   thao tác không tính phí hoặc chi phí tối thiểu, được ghi nhận) và không lộ giá trị key.

---

### User Story 7 - Quan sát, log và backup (Priority: P3)

Chủ sở hữu (hoặc người vận hành) tra cứu log có cấu trúc theo job, xem chi phí AI theo ngày/tháng/job/model, sao
lưu database theo lịch và khôi phục khi cần.

**Why this priority**: Hỗ trợ vận hành lâu dài (E0-13, E0-19, NFR-09); không chặn E1.

**Independent Test**: Chạy job, lọc log theo mã job; tạo bản backup, khôi phục vào database trống và đối chiếu số
bản ghi.

**Acceptance Scenarios**:

1. **Given** một job đã chạy, **When** lọc log theo mã job, **Then** thấy toàn bộ sự kiện của job đó theo thứ tự
   thời gian, dạng có cấu trúc, không chứa secret.
2. **Given** lịch backup bật, **When** đến giờ, **Then** tạo file backup có dấu thời gian và giữ N bản gần nhất
   (cấu hình, mặc định 7).
3. **Given** một file backup, **When** chạy quy trình khôi phục theo hướng dẫn vào database trống, **Then** dữ
   liệu khớp với thời điểm backup.

---

### Edge Cases

- **QA-01** AI provider timeout → retry có giới hạn với backoff, sau đó bước thất bại có lý do; không treo job.
- **QA-02** Kết quả AI sai schema → không lưu; thử lại tối đa N lần; thất bại có lý do.
- **QA-08** Database mất kết nối tạm thời → API trả lỗi "dịch vụ tạm thời không khả dụng" (không lộ chi tiết kỹ
  thuật); worker thử kết nối lại; job không bị đánh dấu thành công sai; dữ liệu không ghi nửa chừng.
- **QA-09** Job bị hủy khi đang chờ phản hồi AI → kết quả trả về sau khi hủy bị bỏ qua nhưng chi phí thực tế vẫn
  được ghi nhận.
- **QA-10** Chạy lại job → không tạo bản ghi trùng; lịch không tạo job trùng.
- **QA-11** Vượt ngân sách → chặn trước khi gọi (xem User Story 3).
- **QA-14** Không có internet → kiểm tra sức khỏe báo provider "không kết nối được"; job thất bại sau retry với lý
  do "lỗi mạng"; phần còn lại của hệ thống (đăng nhập, xem dữ liệu) vẫn hoạt động.
- **QA-15** API key sai/hết hạn → thất bại ngay, không retry, thông báo rõ.
- AI provider từ chối trả lời vì lý do chính sách (refusal) → bước được đánh dấu `REFUSED` kèm loại lý do và
  giải thích do provider trả về; không coi là thành công; KHÔNG tự chuyển sang model hoặc provider khác; không
  retry tự động; chủ sở hữu xem được trạng thái và lý do để kiểm tra.
- AI dừng vì đạt giới hạn độ dài đầu ra → bước được đánh dấu "kết quả bị cắt", không lưu kết quả thiếu.
- Rate limit (429) từ provider → chờ theo chỉ dẫn của provider rồi thử lại trong giới hạn.
- Timeout sau khi yêu cầu đã gửi đi (không biết provider có xử lý hay không) → reservation chuyển `UNCERTAIN`, phần giữ
  chỗ vẫn tính vào chi tiêu; lần thử lại tạo reservation mới; chủ sở hữu đối soát sau.
- Worker chết giữa lời gọi → reservation treo được phát hiện và chuyển `RELEASED` (chưa gửi) hoặc `UNCERTAIN` (đã gửi).
- Model trong profile chưa được xác minh hoặc giá chưa xác minh → chặn lời gọi có phí (`MODEL_NOT_VERIFIED` /
  `PRICING_NOT_VERIFIED`), không tự chọn model khác.
- Bảng giá thiếu model đang dùng → không cho chạy job tốn phí với model đó (không thể kiểm tra ngân sách).
- Hai worker cùng nhận một job → chỉ một worker thực thi.
- Đồng hồ hệ thống/múi giờ: ngân sách ngày/tháng và lịch dùng múi giờ cấu hình (mặc định `Asia/Ho_Chi_Minh`).
- Nội dung trả về từ tool/web chứa chỉ thị kiểu "bỏ qua hướng dẫn trước đó" → được xử lý như dữ liệu, không làm
  thay đổi quyền hay hành vi của agent.

## Requirements *(mandatory)*

### Functional Requirements

**Nền tảng & dữ liệu**

- **FR-001**: Hệ thống MUST được tổ chức thành phần backend và phần giao diện tách biệt, mỗi module nghiệp vụ có
  ranh giới rõ ràng. *(E0-01)*
- **FR-002**: Hệ thống MUST cung cấp API có tài liệu hợp đồng tự sinh và endpoint kiểm tra sức khỏe trả trạng thái
  từng thành phần (database, worker, AI provider). *(E0-02, NFR-09)*
- **FR-003**: Hệ thống MUST lưu toàn bộ dữ liệu vận hành trong PostgreSQL. *(E0-03, AC-15)*
- **FR-004**: Mọi thay đổi cấu trúc dữ liệu MUST thực hiện qua migration có phiên bản, nâng và hạ được; hệ thống
  tự áp dụng migration khi khởi động có kiểm soát. *(E0-04, DATA-02)*
- **FR-005**: Mọi bảng MUST dùng khóa chính UUID, có `created_at`/`updated_at`, foreign key và unique constraint
  phù hợp. *(DATA-01)*
- **FR-006**: Hệ thống MUST có thực thể `project` mặc định mà mọi dữ liệu nghiệp vụ tương lai thuộc về; MVP chỉ có
  một project, không triển khai multi-tenant. *(DATA-06)*
- **FR-007**: Hệ thống MUST cung cấp kho bằng chứng dùng chung (nguồn + bằng chứng: URL/định danh nguồn, trích
  đoạn, thời điểm thu thập, thời điểm xác minh, trạng thái `VERIFIED`/`INFERRED`/`UNKNOWN`/`CONFLICTING`) để
  E1–E3 sử dụng. E0 chỉ cung cấp cấu trúc và dịch vụ lưu/truy vấn, không tạo dữ liệu nghiên cứu. *(DATA-03, BR-02)*

**AI Provider**

- **FR-010**: Hệ thống MUST tích hợp Claude API làm provider mặc định và MUST NOT dùng model chạy local. *(E0-05,
  AI-01)*
- **FR-011**: Hệ thống MUST định nghĩa một interface provider chung với ba triển khai: `AnthropicAPIProvider`
  (chính), `OpenAIAPIProvider` (dự phòng, chỉ dùng khi được cấu hình rõ ràng) và `MockAIProvider` (phát triển/kiểm
  thử); chuyển provider chỉ bằng cấu hình, không sửa business logic. *(E0-06, AI-07, AI-14)*
- **FR-018**: `MockAIProvider` MUST: (a) không gọi mạng; (b) trả kết quả xác định theo kịch bản cấu hình được –
  thành công, timeout, rate limit, sai schema, lỗi provider, lỗi xác thực, refusal, kết quả bị cắt, và usage lớn để
  kích hoạt vượt ngân sách; (c) báo usage và chi phí giả lập theo bảng giá giả lập riêng; (d) gắn nhãn `MOCK` lên
  mọi kết quả, usage log, bước job và dữ liệu sinh ra; (e) chỉ được bật ở môi trường `development`/`test` – hệ thống
  MUST từ chối khởi động nếu bật ở `production`. Chi tiêu giả lập MUST được tính riêng, không cộng vào chi tiêu thật,
  nhưng đi qua cùng cơ chế kiểm tra ngân sách; (f) điều kiện sử dụng mock MUST được kiểm tra ở cả tầng cấu hình (khi
  khởi động) và runtime (mỗi lần AI Gateway chọn provider, mỗi lần cập nhật Model Task Profile, mỗi tham số
  `mock_scenario`); trong production MUST NOT có đường nào chọn mock động (API, tham số job, biến lúc chạy); (g) dữ liệu
  mock MUST NOT xuất hiện trong báo cáo nghiên cứu, xếp hạng hay thống kê kinh doanh/chi phí thực tế (các truy vấn này
  mặc định chỉ lấy `data_origin = REAL`); (h) kết quả test với mock MUST NOT được ghi nhận là đã kiểm thử provider thật.
  *(AI-14, Constitution I)*
- **FR-019**: Hệ thống MUST có công tắc "cho phép gọi API có phí", mặc định TẮT; khi tắt, mọi lời gọi tốn phí tới
  provider thật bị chặn trước khi gửi (job thất bại với mã `PAID_CALLS_DISABLED`). Kiểm tra kết nối không tính phí
  (FR-056) vẫn được phép. Test tự động MUST NOT gọi API có phí. *(AI-15, Constitution VI)*
- **FR-019b**: Provider thật MUST chỉ xác thực bằng API key chính thức được cấu hình cho hệ thống; MUST NOT dùng OAuth
  token, cookie, session của tài khoản người dùng, thông tin đăng nhập Claude Code/CLI hay hồ sơ đăng nhập trên máy để
  gọi API. *(AI-16)*
- **FR-012**: Hệ thống MUST cho phép cấu hình theo từng loại tác vụ: provider, model, mức độ suy luận/effort, giới
  hạn token đầu ra. Business logic MUST NOT hard-code tên model; agent chỉ tham chiếu loại tác vụ và nhận model từ
  cấu hình. Cấu hình mặc định MUST chọn model hiệu quả chi phí phù hợp từng loại tác vụ (không bắt buộc model mạnh
  nhất cho mọi tác vụ). *(AI-02)*
- **FR-013**: Hệ thống MUST hỗ trợ yêu cầu kết quả có cấu trúc và kiểm tra kết quả theo schema trước khi trả cho
  agent; kết quả không hợp lệ MUST NOT được lưu. *(AI-03, NFR-15)*
- **FR-014**: Hệ thống MUST phân loại kết quả/lỗi của provider thành: thành công, sai schema, timeout, rate limit,
  lỗi xác thực, lỗi mạng, lỗi phía provider, từ chối trả lời, kết quả bị cắt; mỗi loại có chính sách retry riêng
  (lỗi xác thực và yêu cầu không hợp lệ: không retry). *(E0-10)*
- **FR-015**: Hệ thống MUST loại bỏ secret (API key, mật khẩu, token) khỏi mọi nội dung gửi tới AI provider và chỉ
  gửi dữ liệu cần thiết cho tác vụ. *(AI-06)*
- **FR-016**: Hệ thống MUST đánh dấu nội dung đến từ tool/web là dữ liệu không tin cậy khi đưa vào ngữ cảnh AI và
  MUST NOT để nội dung đó thay đổi quyền tool hay giới hạn của agent. *(AI-10)*
- **FR-017**: Khi provider từ chối trả lời vì lý do chính sách, hệ thống MUST ghi nhận trạng thái `REFUSED`, loại lý
  do và giải thích (nếu có) vào usage log và bước job, MUST NOT tự chuyển sang model hoặc provider khác, và MUST NOT
  bật tính năng chuyển model tự động phía provider. Provider dự phòng (FR-011) chỉ áp dụng cho lỗi kỹ thuật được
  cấu hình rõ (ví dụ provider không khả dụng), không áp dụng cho refusal. *(AI-07, AI-11)*
- **FR-019c**: Trước mọi lời gọi có phí, hệ thống MUST xác nhận model của tác vụ đã được **xác minh** (model ID tồn tại
  theo nguồn chính thức của provider, hỗ trợ các khả năng tác vụ cần – structured output, tool calling, effort – có
  ghi nguồn và thời điểm xác minh) và bảng giá của model đó đã được xác minh; nếu chưa, lời gọi MUST bị chặn với mã
  `MODEL_NOT_VERIFIED` hoặc `PRICING_NOT_VERIFIED`. Model ID và giá MUST chỉ nằm trong cấu hình/dữ liệu, không trong
  business logic. Hệ thống MUST NOT tự nâng cấp model (không dùng alias kiểu "latest"), MUST NOT tự chuyển model khi
  chưa được cấu hình. *(AI-02, AI-17)*

**Tool Registry & Agent**

- **FR-020**: Hệ thống MUST có Tool Registry, mỗi tool khai báo: tên, mô tả, schema đầu vào, schema đầu ra,
  timeout, có tác động bên ngoài hay không, và giới hạn tần suất. *(E0-07)*
- **FR-021**: Mỗi định nghĩa agent MUST khai báo: schema đầu vào, schema đầu ra, danh sách tool được phép, timeout,
  token budget, số bước tối đa, số lời gọi AI tối đa, chính sách retry, tiêu chí chấp nhận. *(AI-08)*
- **FR-022**: Hệ thống MUST chỉ thực thi tool có trong danh sách quyền của agent; yêu cầu gọi tool ngoài danh sách
  MUST bị từ chối và ghi log. *(AI-04, NFR-14)*
- **FR-023**: Trong MVP, tool có tác động bên ngoài (đăng ký, xuất bản, gửi dữ liệu ra ngoài ngoài việc đọc thông
  tin công khai) MUST bị vô hiệu hóa; cơ chế yêu cầu phê duyệt được dành chỗ trong thiết kế nhưng chưa triển khai
  luồng phê duyệt. *(BR-08, AUT-01, AC-19)*
- **FR-024**: Vòng lặp agent MUST dừng khi đạt số bước tối đa, số lời gọi AI tối đa, timeout của job, hoặc ngân
  sách; không có vòng lặp vô hạn. *(AI-05)*
- **FR-025**: Mọi agent MUST dùng chung AI provider, Tool Registry và Job Runtime. *(AI-09)*
- **FR-026**: E0 MUST cung cấp đúng một loại job tích hợp sẵn – "Job chẩn đoán AI" – để kiểm chứng end-to-end:
  một yêu cầu AI có cấu trúc + một lời gọi tool nội bộ không tác động bên ngoài. *(AC-02)*

**Job Runtime & Scheduler**

- **FR-030**: Hệ thống MUST quản lý vòng đời job với các trạng thái tối thiểu: `QUEUED`, `RUNNING`, `PAUSED`,
  `PAUSED_BUDGET`, `RETRY_SCHEDULED`, `SUCCEEDED`, `FAILED`,
  `CANCELLED`; chỉ cho phép các chuyển trạng thái hợp lệ. *(E0-08)*
- **FR-031**: Hệ thống MUST ghi lại từng bước của job (thời gian, đầu vào tóm tắt, kết quả, lỗi, chi phí) và từng
  lần thực thi tool. *(E0-08)*
- **FR-032**: Chủ sở hữu MUST có thể: tạo job thủ công, xem danh sách/chi tiết/lịch sử, tạm dừng, tiếp tục, hủy,
  chạy lại job lỗi. *(E0-09, AUT-03)*
- **FR-033**: Hệ thống MUST hỗ trợ lịch chạy định kỳ (biểu thức kiểu cron, múi giờ cấu hình), bật/tắt, xem lần chạy
  trước/kế tiếp, chính sách xử lý lần chạy bị lỡ. *(E0-09)*
- **FR-034**: Hệ thống MUST NOT tạo hoặc chạy job tốn phí theo lịch khi chưa cấu hình ngân sách. *(AUT-04)*
- **FR-035**: Hệ thống MUST áp dụng retry với số lần tối đa và khoảng chờ tăng dần, timeout cho mỗi lời gọi ngoài
  và cho toàn job. *(E0-10, NFR-03)*
- **FR-036**: Hệ thống MUST lưu checkpoint sau mỗi bước hoàn tất và tiếp tục job từ checkpoint sau khi lỗi, tạm
  dừng hoặc worker khởi động lại. *(E0-20)*
- **FR-037**: Hệ thống MUST đảm bảo idempotency: cùng khóa job không tạo job trùng; chạy lại không tạo dữ liệu
  trùng; một job chỉ được một worker thực thi tại một thời điểm. *(AUT-05, QA-10)*
- **FR-038**: Số job chạy đồng thời MUST cấu hình được, mặc định 1. *(NFR-01, Constitution XI)*

**Chi phí & ngân sách**

- **FR-040**: Hệ thống MUST ghi nhận cho mỗi lời gọi AI: provider, model, loại tác vụ, job/bước liên quan, token
  vào, token ra, token cache (đọc/ghi), chi phí ước tính theo bảng giá có phiên bản, thời gian xử lý, kết quả.
  *(E0-11)*
- **FR-041**: Bảng giá model MUST cấu hình được và có phiên bản; chi phí của mỗi lời gọi lưu kèm phiên bản bảng giá
  đã dùng. *(Constitution VI)*
- **FR-042**: Hệ thống MUST cho phép cấu hình ngân sách theo ngày, theo tháng và trần mặc định theo job (có thể
  ghi đè cho từng job trong giới hạn ngày/tháng); giá trị mặc định $3/ngày, $30/tháng, $2/job. *(E0-12)*
- **FR-043**: Trước mỗi lời gọi tốn phí, hệ thống MUST giữ chỗ (reservation) chi phí ước tính tối đa so với phần còn
  lại của cả ba ngân sách (ngày, tháng, job) và MUST NOT gửi lời gọi nếu không đủ. Việc kiểm tra và giữ chỗ MUST là một
  thao tác nguyên tử trong database, an toàn khi nhiều worker/job chạy đồng thời, sao cho tổng (chi tiêu thực + giữ
  chỗ đang mở + giữ chỗ chưa xác định) không bao giờ vượt bất kỳ giới hạn nào do race condition. *(E0-12, NFR-06)*
- **FR-044**: Hệ thống MUST cung cấp tổng hợp chi phí theo ngày, tháng, job, model và cảnh báo khi đạt 80% ngân sách
  ngày/tháng (ngưỡng cấu hình được); tổng hợp mặc định chỉ gồm chi phí thật (`REAL`), chi phí giả lập chỉ hiển thị khi
  yêu cầu rõ và luôn tách riêng. *(E0-11, E4-15)*
- **FR-047**: Sau mỗi lời gọi, reservation MUST được xử lý theo kết quả: (a) có usage thực tế → đối soát theo chi phí
  thực tế (`SETTLED`), ghi nhận chênh lệch; (b) chắc chắn chưa phát sinh phí (lời gọi chưa rời hệ thống, hoặc nhận được
  phản hồi lỗi mà chính sách tính phí đã xác minh của provider xác định là không tính phí) → giải phóng (`RELEASED`) kèm
  lý do; (c) chưa xác định được chi phí (timeout sau khi đã gửi, mất kết nối giữa chừng, worker chết sau khi gửi, phản
  hồi không đọc được usage, hoặc phản hồi lỗi khi chính sách tính phí chưa được xác minh) → chuyển `UNCERTAIN`, **giữ
  nguyên toàn bộ phần đã giữ chỗ** trong chi tiêu cho tới khi được đối soát; hệ thống MUST NOT tự động giải phóng
  reservation `UNCERTAIN`. Chủ sở hữu MUST có thể đối soát reservation `UNCERTAIN` bằng chi phí thực tế (ví dụ lấy từ
  trang quản lý của provider) hoặc xác nhận không tính phí; mỗi lần đối soát được ghi audit log. *(E0-12, AI-18)*
- **FR-048**: Hệ thống MUST phát hiện reservation bị treo (`ACTIVE` quá hạn, ví dụ do worker chết): nếu lời gọi chắc
  chắn chưa được gửi → `RELEASED`; nếu đã gửi hoặc không chắc → `UNCERTAIN`. Tổng reservation `UNCERTAIN` MUST hiển thị
  trong trạng thái ngân sách kèm cảnh báo. *(E0-12, AI-18)*
- **FR-045**: Khi vượt ngân sách, job MUST chuyển `PAUSED_BUDGET`, chỉ tiếp tục (từ checkpoint) khi chủ sở hữu yêu
  cầu và ngân sách đủ; hệ thống MUST NOT tự tăng ngân sách hoặc tự đổi model/provider để tránh giới hạn. *(E0-12)*

**Logging, audit, bảo mật, cấu hình**

- **FR-050**: Hệ thống MUST ghi log có cấu trúc (máy đọc được) với mã tương quan (request, job, bước) và MUST tự
  động che secret trong log. *(E0-13, NFR-05)*
- **FR-051**: Hệ thống MUST ghi audit log cho: đăng nhập thành công/thất bại, khóa tài khoản, tạo tài khoản, thay
  đổi cấu hình/ngân sách/lịch, tạo/hủy/tạm dừng/tiếp tục/chạy lại job; mỗi bản ghi có tác nhân, thời điểm, hành
  động, đối tượng, giá trị trước/sau (không chứa secret); audit log không sửa/xóa được qua giao diện. *(E0-14)*
- **FR-052**: Dashboard và API MUST yêu cầu xác thực, trừ trang đăng nhập/khởi tạo lần đầu và endpoint sức khỏe tối
  giản; mô hình người dùng là một chủ sở hữu duy nhất. *(E0-15)*
- **FR-053**: Mật khẩu MUST được băm bằng thuật toán băm mật khẩu hiện đại; phiên đăng nhập hết hạn sau thời gian
  không hoạt động cấu hình được (mặc định 12 giờ); chống đoán mật khẩu bằng khóa tạm (mặc định 15 phút sau 5 lần sai,
  cả hai giá trị cấu hình được). *(E0-15, Constitution X)*
- **FR-054**: Secret MUST NOT xuất hiện trong mã nguồn, git, log, response API hoặc giao diện (chỉ hiển thị dạng
  che). API key MUST chỉ được cung cấp qua file môi trường (`.env`) hoặc Docker secrets, MUST NOT lưu trong
  database; file `.env` thật MUST bị loại khỏi git (chỉ commit `.env.example`). *(E0-16, NFR-05)*
- **FR-056**: Hệ thống MUST cung cấp chức năng kiểm tra kết nối cho từng provider đã cấu hình, trả về trạng thái
  (kết nối được / key không hợp lệ / không có mạng / chưa cấu hình) mà không lộ giá trị key; mỗi lần kiểm tra được
  ghi audit log. *(E0-16)*
- **FR-055**: Hệ thống MUST cho phép xem và cập nhật cấu hình không bí mật: provider/model theo tác vụ, ngân sách,
  giới hạn agent, múi giờ, thị trường mặc định (Mỹ), ngôn ngữ nội dung mặc định (tiếng Anh), ngôn ngữ nghiên cứu
  (theo thị trường), ngôn ngữ giao diện mặc định (tiếng Việt); các cấu hình ngôn ngữ độc lập nhau; cấu hình được
  validate trước khi lưu. *(E0-16, BR-10)*

**Giao diện trong phạm vi E0**

- **FR-060**: E0 MUST cung cấp khung giao diện song ngữ: trang khởi tạo tài khoản, đăng nhập, trạng thái hệ thống,
  bộ chuyển VI/EN (mặc định tiếng Việt, ghi nhớ lựa chọn) và hạ tầng dịch thuật dùng cho E4. Agent Jobs, chi phí
  AI và cấu hình (Settings) chỉ được cung cấp qua API trong E0; E0 MUST NOT xây giao diện quản lý cho các chức năng
  này (thuộc E4-12, E4-13, E4-15). *(E0-01, E4-01…E4-05)*
- **FR-061**: Mọi thông báo lỗi trả về giao diện MUST thân thiện, theo ngôn ngữ giao diện, không lộ chi tiết kỹ
  thuật (stack trace, câu lệnh, secret). *(UI-02, E4-05)*

**Triển khai, kiểm thử, backup**

- **FR-070**: Toàn bộ hệ thống MUST khởi động bằng một lệnh Docker Compose trên Windows 10/11 (Docker Desktop/WSL2)
  và Linux, với giới hạn tài nguyên cho từng thành phần và thành phần tùy chọn tách theo profile. *(E0-17, NFR-10)*
- **FR-071**: Hệ thống MUST có file cấu hình mẫu với giá trị mặc định an toàn và hướng dẫn vận hành tiếng Việt
  (cài đặt, cấu hình, khởi động, nâng cấp, backup/restore, xử lý sự cố), gồm hướng dẫn riêng cho Windows 10/11 với
  Docker Desktop + WSL2 (mã nguồn đặt trong filesystem WSL). *(AC-20, NFR-13)*
- **FR-074**: Môi trường phát triển MUST hỗ trợ hot-reload cho backend và frontend khi chạy trong Docker và giữ
  tương đồng với cấu hình production Linux. *(E0-17)*
- **FR-072**: Hệ thống MUST có unit test và integration test chạy tự động không cần API key thật và không phát sinh
  chi phí; test với provider thật được tách riêng, chạy thủ công, có trần chi phí. *(E0-18, Constitution IX)*
- **FR-073**: Hệ thống SHOULD hỗ trợ backup database theo lịch (mặc định 03:00, giữ 7 bản – cấu hình được) và quy trình
  khôi phục có tài liệu và có kiểm thử. *(E0-19)*

### Key Entities *(include if feature involves data)*

- **User**: chủ sở hữu duy nhất; tên đăng nhập, mật khẩu đã băm, ngôn ngữ giao diện ưa thích, trạng thái khóa, lần
  đăng nhập cuối.
- **Project**: phạm vi dữ liệu nghiệp vụ; một project mặc định trong MVP; thị trường, ngôn ngữ nội dung, ngôn ngữ
  nghiên cứu mặc định.
- **Setting**: cặp khóa–giá trị có kiểu và phiên bản cho cấu hình không bí mật (model theo tác vụ, ngân sách, giới
  hạn agent, múi giờ, ngôn ngữ).
- **Model Pricing**: bảng giá theo provider/model có phiên bản và ngày hiệu lực (giá token vào, ra, cache).
- **Agent Job**: một lần chạy agent; loại job, tham số, khóa idempotency, trạng thái, nguồn kích hoạt (thủ công/
  lịch), ngân sách job, chi phí tích lũy, checkpoint, thời gian, lỗi cuối.
- **Job Step**: một bước trong job; thứ tự, loại bước, trạng thái, số lần thử, kết quả tóm tắt, lỗi, chi phí.
- **Tool Execution**: một lần gọi tool; tool, job/bước, đầu vào/đầu ra (đã che secret), trạng thái, thời gian, bị từ
  chối do quyền hay không.
- **AI Usage Log**: một lời gọi AI; provider, model, loại tác vụ, token vào/ra/cache, chi phí, phiên bản bảng giá,
  kết quả phân loại, thời gian.
- **AI Model (catalog)**: model ID theo provider, trạng thái xác minh, nguồn và thời điểm xác minh, khả năng hỗ trợ
  (structured output, tool calling, effort), giới hạn ngữ cảnh/đầu ra.
- **Model Task Profile**: ánh xạ loại tác vụ → provider, model, effort, giới hạn token, số lần retry schema.
- **Budget Reservation**: phần ngân sách được giữ chỗ cho lời gọi đang thực hiện; được quyết toán theo chi phí thực.
- **Job Schedule**: lịch định kỳ; loại job, tham số, biểu thức lịch, múi giờ, bật/tắt, lần chạy trước/kế tiếp,
  chính sách chạy bù.
- **Audit Log**: bản ghi bất biến về hành động quản trị; tác nhân, hành động, đối tượng, trước/sau, thời điểm.
- **Research Source / Research Evidence**: hạ tầng bằng chứng dùng chung (FR-007); nguồn (URL/định danh, loại
  nguồn, thời điểm thu thập) và bằng chứng (trích đoạn, trạng thái xác minh, thời điểm xác minh, liên kết tới đối
  tượng được chứng minh).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Người dùng làm theo hướng dẫn vận hành có thể khởi động hệ thống và đăng nhập trên máy Windows
  (4 core, 15 GB RAM, không GPU) trong vòng 30 phút kể từ khi có mã nguồn, với một lệnh khởi động. *(AC-01)*
- **SC-002**: Ở trạng thái nghỉ, toàn bộ thành phần bắt buộc của E0 dùng tổng cộng không quá 3 GB RAM. *(NFR-01)*
- **SC-003**: Job chẩn đoán AI với provider thật hoàn tất thành công và hiển thị token và chi phí; chi phí ghi nhận
  lệch không quá 1% so với tính toán thủ công từ usage và bảng giá. *(AC-02, E0-11)* – **Chỉ kiểm chứng được khi chủ
  sở hữu cung cấp API key và cho phép gọi có phí; trước đó tiêu chí này ghi trạng thái "chưa kiểm chứng", không được
  báo cáo là đạt.**
- **SC-003b**: Không cần API key, toàn bộ luồng E0 (khởi động, job, retry, checkpoint, lịch, ngân sách, logging, audit)
  chạy và kiểm thử được bằng MockAIProvider; 100% kịch bản giả lập ở FR-018 có test tự động pass; 0 lời gọi mạng tới
  provider thật trong toàn bộ test tự động.
- **SC-004**: Trong 100% kịch bản kiểm thử vượt ngân sách (ngày, tháng, job, và đồng thời với ít nhất 2 tiến trình
  worker × 10 lời gọi tranh chấp), không có lời gọi tốn phí nào được gửi khi ngân sách còn lại không đủ cho chi phí ước
  tính tối đa, và tổng chi tiêu + giữ chỗ không vượt giới hạn. *(AC-03)*
- **SC-004b**: 100% kịch bản lỗi sau khi gửi (timeout, mất kết nối, worker chết) để lại reservation `UNCERTAIN` không bị
  giải phóng tự động; 100% kịch bản lỗi trước khi gửi giải phóng reservation. *(FR-047, FR-048)*
- **SC-005**: 100% kết quả AI sai schema trong kiểm thử bị từ chối và không được lưu. *(AI-03)*
- **SC-006**: Job bị gián đoạn (worker dừng đột ngột) tiếp tục được từ checkpoint, không mất bước đã hoàn tất và
  không tạo bản ghi trùng, trong 100% kịch bản kiểm thử. *(E0-20, QA-10)*
- **SC-007**: Lịch chạy tạo đúng một job cho mỗi thời điểm lịch trong 100% kịch bản kiểm thử, kể cả khi khởi động
  lại. *(E0-09)*
- **SC-008**: 0 secret xuất hiện trong log, response API, giao diện hoặc lịch sử git (kiểm tra tự động bằng quét
  secret và test). *(NFR-05)*
- **SC-009**: Mọi tình huống bắt buộc QA-01, 02, 08, 09, 10, 11, 14, 15 có test tự động và đều pass. *(AC-14, AC-17)*
- **SC-010**: 100% chuỗi giao diện trong phạm vi E0 có bản dịch tiếng Việt và tiếng Anh (kiểm tra tự động); chuyển
  ngôn ngữ có hiệu lực ngay, không cần tải lại toàn bộ ứng dụng. *(AC-12 – phần khung)*
- **SC-011**: 100% yêu cầu E0 mức Must truy vết được tới ít nhất một test case. *(Constitution IX)*
- **SC-012**: Khôi phục từ bản backup vào database trống cho số lượng bản ghi khớp 100% với thời điểm backup.
  *(E0-19)*

## Assumptions

- MVP có đúng một người dùng (chủ sở hữu) với toàn quyền; không có phân quyền nhiều vai trò.
- E0 không chứa logic nghiên cứu thị trường; Job chẩn đoán AI là loại job duy nhất, chỉ để kiểm chứng nền tảng.
  Agent nghiên cứu thực tế thuộc E1–E3.
- Chủ sở hữu hiện dùng Claude Pro qua Claude Code để phát triển và chưa có API key; Claude Pro không phải provider của
  hệ thống. Adapter Anthropic và OpenAI được kiểm thử ở mức HTTP giả lập (không gọi mạng) trong E0; kiểm thử với API
  thật chỉ thực hiện khi chủ sở hữu cung cấp key và cho phép rõ ràng.
- Tìm kiếm web (SearXNG), crawl, browser automation không thuộc E0; được đưa vào ở E1 qua Tool Registry.
- Luồng phê duyệt (approval request) chưa triển khai trong E0 vì MVP không có hành động bên ngoài; chỉ đảm bảo thiết
  kế không chặn việc bổ sung sau.
- Múi giờ mặc định cho ngân sách và lịch: `Asia/Ho_Chi_Minh`; tiền tệ ngân sách: USD (theo đơn vị giá của provider).
- Bảng giá model ban đầu được nhập từ giá công bố của provider tại thời điểm triển khai và chủ sở hữu có thể cập nhật.
- Model được gán theo loại tác vụ trong cấu hình; bộ mặc định ưu tiên hiệu quả chi phí (model nhỏ cho tác vụ đơn giản,
  model mạnh hơn cho phân tích phức tạp) và chủ sở hữu thay đổi được; hệ thống không tự đổi model lúc chạy.
- Truy cập Dashboard chủ yếu từ máy cục bộ hoặc mạng nội bộ; công khai ra internet cần reverse proxy có HTTPS (ngoài
  phạm vi E0, có ghi trong hướng dẫn).
- Thời gian giữ log và audit log: mặc định 90 ngày cho log ứng dụng, không tự xóa audit log trong MVP.
- Môi trường phát triển chính: Windows 10/11 + Docker Desktop (WSL2); hệ thống phải chạy được trên Linux không sửa mã.
