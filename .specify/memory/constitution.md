# NichePilot Constitution

NichePilot (tên kỹ thuật: Affiliate Automation OS – AAOS) là hệ thống AI Agent tự host, tự động hóa
quy trình Affiliate Marketing quốc tế: khám phá ngách → sản phẩm → keyword → nội dung → xuất bản →
doanh thu → tối ưu. Constitution này là luật gốc; mọi spec, plan, task và mã nguồn phải tuân thủ.

## Core Principles

### I. Evidence-First – Không bịa dữ liệu (KHÔNG THƯƠNG LƯỢNG)

- Mọi kết luận nghiên cứu (ngách, pain point, sản phẩm, chương trình affiliate, keyword, đối thủ)
  MUST gắn với ít nhất một bằng chứng có nguồn (URL hoặc định danh nguồn), trích đoạn và thời điểm
  thu thập/xác minh.
- Hệ thống MUST NOT tự tạo số liệu thị trường, search volume, CPC, keyword difficulty, tỷ lệ hoa hồng,
  thời hạn cookie, giá, đánh giá hay trải nghiệm sản phẩm.
- Thuộc tính không xác minh được MUST lưu giá trị `UNKNOWN` (không để trống, không suy đoán).
  Thuộc tính suy luận bởi AI MUST được gắn nhãn `INFERRED` và tách biệt khỏi dữ liệu `VERIFIED`.
- Khi nguồn mâu thuẫn, hệ thống MUST lưu tất cả giá trị kèm nguồn và đánh dấu `CONFLICTING`.
- Mock data trong test MUST nằm trong thư mục test/fixture và được gắn nhãn rõ ràng.
- Ngoài test, mock CHỈ được sinh bởi `MockAIProvider` khi chạy ở môi trường `development` hoặc `test`.
  Mọi bản ghi do mock sinh ra MUST mang nhãn nguồn gốc `MOCK` (ví dụ `data_origin = MOCK`), MUST được hiển
  thị là dữ liệu giả lập, MUST bị loại khỏi báo cáo/xếp hạng nghiên cứu theo mặc định, và MUST NOT được
  trình bày như kết quả nghiên cứu thật. Hệ thống MUST từ chối khởi động nếu bật mock ở môi trường
  `production`.
- Một tích hợp provider chỉ được báo cáo là "đã kiểm thử" khi đã gọi API thật của provider đó thành công;
  kết quả với mock chỉ chứng minh logic nội bộ.
- Báo cáo tiến độ phát triển MUST NOT tuyên bố thành công khi chưa kiểm tra thực tế; thiếu API key
  thì ghi rõ "chưa kiểm tra được", không tạo dữ liệu giả.

*Lý do:* Giá trị cốt lõi của sản phẩm là ra quyết định kinh doanh; dữ liệu bịa gây thiệt hại trực tiếp.

### II. Điểm cơ hội và Độ tin cậy tách biệt

- Mọi đối tượng được chấm điểm (niche, product, keyword) MUST có hai điểm độc lập:
  Opportunity Score (mức hấp dẫn) và Confidence Score (mức chắc chắn của dữ liệu).
- Trọng số chấm điểm MUST cấu hình được, có phiên bản, và mỗi lần chấm MUST lưu phiên bản trọng số
  cùng điểm thành phần để tái lập được kết quả.
- Keyword "hot" hoặc search volume cao MUST NOT là điều kiện bắt buộc để chọn ngách.
- Thiếu chương trình affiliate phù hợp MUST được đánh dấu rủi ro monetization.

### III. Niche-First & AI-First

- Luồng nghiệp vụ bắt đầu từ vấn đề thực của khách hàng (pain point) và khả năng chi trả, không bắt
  đầu từ sản phẩm hay keyword.
- AI là động cơ nghiên cứu và lập kế hoạch chính; logic xác định (lọc trùng, tính điểm, kiểm tra
  ngân sách, kiểm tra schema, chính sách) MUST được viết bằng mã nguồn, không giao cho LLM.

### IV. Human-in-the-Loop & Giới hạn hành động bên ngoài (KHÔNG THƯƠNG LƯỢNG)

- Hai chế độ: REVIEW (mặc định) và AUTO. AUTO MUST NOT bỏ qua giới hạn ngân sách, chính sách nền
  tảng, rate limit, quyền truy cập, kiểm tra chất lượng và các bước phê duyệt bắt buộc.
- Hệ thống MUST NOT tự đăng ký tài khoản affiliate, chấp nhận điều khoản, thanh toán, hoặc xuất bản
  nội dung khi chưa có phê duyệt được ghi nhận. Trong MVP (E0–E4) mọi hành động xuất bản/đăng ký bị
  vô hiệu hóa hoàn toàn.
- Mọi hành động có tác động bên ngoài MUST đi qua cơ chế approval request và được ghi audit log.

### V. AI Safety & Kiểm soát Agent

- Mỗi Agent MUST khai báo: input schema, output schema, danh sách tool được phép, timeout, token
  budget, số bước tối đa, số lần gọi API tối đa, retry policy và acceptance criteria.
- Agent CHỈ gọi được tool đã đăng ký trong Tool Registry và nằm trong danh sách quyền của Agent đó.
- Mọi output của LLM MUST được validate theo schema trước khi lưu; output sai schema MUST được thử
  lại có giới hạn rồi đánh dấu lỗi, MUST NOT lưu dữ liệu không hợp lệ.
- Vòng lặp agent MUST có điểm dừng cứng; không có vòng lặp vô hạn.
- Không chuyển provider AI (Claude → OpenAI) nếu chưa được cấu hình rõ ràng. Provider được chọn bằng cấu
  hình qua một interface chung; business logic MUST NOT phụ thuộc provider cụ thể.
- AI provider của hệ thống CHỈ là API chính thức có API key (Anthropic API, OpenAI API) hoặc
  `MockAIProvider` (dev/test). MUST NOT dùng OAuth token, cookie, session của tài khoản người dùng hoặc
  Claude Code CLI để giả lập API backend; workflow tự động MUST NOT phụ thuộc tài khoản thuê bao cá nhân
  (Claude Pro…). Claude Code chỉ là công cụ phát triển.
- Không gửi dữ liệu nhạy cảm (API key, mật khẩu, thông tin cá nhân không cần thiết) tới LLM.
- Nội dung thu thập từ web là dữ liệu không tin cậy: MUST NOT được thực thi như chỉ thị
  (phòng chống prompt injection).

### VI. Cost-Aware (KHÔNG THƯƠNG LƯỢNG)

- Mọi lời gọi AI MUST ghi nhận provider, model, token vào/ra/cache, chi phí ước tính và job liên quan.
- Ngân sách theo ngày, tháng và theo job MUST được kiểm tra TRƯỚC mỗi lời gọi tốn phí; vượt ngân sách
  MUST dừng/tạm dừng job, không chỉ cảnh báo.
- Job tốn phí MUST NOT chạy theo lịch khi chưa cấu hình ngân sách.
- Lời gọi API có phí MUST bị chặn theo mặc định (công tắc cho phép gọi có phí tắt); chỉ bật khi chủ sở hữu
  cho phép rõ ràng. Quá trình phát triển và test tự động MUST NOT tự động gọi API có phí.
- Bảng giá model MUST cấu hình được (không hard-code rải rác trong mã).

### VII. OSS-First & Đánh giá công nghệ

- Ưu tiên phần mềm mã nguồn mở thực sự (giấy phép OSI). Công cụ source-available, AGPL hoặc có hạn chế
  thương mại MUST được ghi rõ trong Technology Evaluation trước khi đưa vào.
- Mỗi công nghệ mới MUST được đánh giá: giấy phép, tình trạng bảo trì, khả năng tích hợp (API/CLI),
  tài nguyên, khả năng thương mại hóa, rủi ro bảo mật, khả năng thay thế.
- Công cụ nặng (crawler, browser, video, OCR) CHỈ được kích hoạt khi feature cần đến.

### VIII. Kiến trúc Module & API-First

- Hệ thống là modular monolith: mỗi module (E0–E8) có ranh giới rõ, giao tiếp qua service interface
  và API có hợp đồng (OpenAPI); không truy cập trực tiếp bảng dữ liệu của module khác ngoài interface
  đã công bố.
- Provider bên ngoài (LLM, search, crawl, TTS, publishing) MUST đứng sau một adapter interface để có
  thể thay thế.
- Mọi chức năng Dashboard MUST đi qua API backend; không có logic nghiệp vụ chỉ tồn tại ở frontend.

### IX. Test-Driven & Truy vết yêu cầu (KHÔNG THƯƠNG LƯỢNG)

- Mỗi requirement có ID MUST truy vết được tới ít nhất một test (unit, integration, API, E2E hoặc
  acceptance). Mỗi task MUST tham chiếu requirement ID.
- Test cho logic nghiệp vụ được viết trước hoặc cùng lúc với mã; PR không có test cho thay đổi hành vi
  bị từ chối.
- Test tự động MUST NOT gọi API trả phí thật; test "live" với API thật được tách riêng, chạy thủ công
  có chủ đích và có giới hạn chi phí.
- Các tình huống lỗi bắt buộc (timeout, sai schema, rate limit, mất kết nối DB, hủy job, chạy lại
  không trùng, vượt ngân sách, sai API key, mất internet) MUST có test.

### X. Security-by-Design

- Secrets (API key, mật khẩu, token) MUST NOT nằm trong mã nguồn, git, log hoặc response API; khi
  hiển thị MUST được che (masked).
- Dashboard MUST yêu cầu xác thực; mật khẩu băm bằng thuật toán hiện đại (Argon2id/bcrypt).
- Mọi hành động quản trị và thay đổi cấu hình MUST được ghi audit log (ai, khi nào, cái gì, trước/sau
  – không chứa secret).
- Truy cập web MUST tôn trọng robots.txt, ToS, rate limit; không vượt paywall, CAPTCHA hay đăng nhập
  trái phép.

### XI. Self-Hosted & Tiết kiệm tài nguyên

- Toàn hệ thống MUST khởi động được bằng Docker Compose trên Windows 10/11 (Docker Desktop/WSL2),
  CPU 4 core, RAM 15 GB, không GPU; và chuyển được sang Linux server không sửa mã.
- MUST NOT dùng LLM chạy local. Số worker đồng thời MUST cấu hình được và mặc định thấp.
- Container MUST có giới hạn tài nguyên; dịch vụ tùy chọn dùng Compose profiles để bật khi cần.

### XII. Song ngữ & Ngôn ngữ

- Tài liệu yêu cầu, spec, plan, tasks, checklist, user story, acceptance criteria, test case viết bằng
  tiếng Việt. Mã nguồn, tên biến, hàm, class, endpoint, bảng database dùng tiếng Anh. Giữ nguyên thuật
  ngữ kỹ thuật (API, Agent, Niche, Keyword, SEO…).
- Dashboard MUST hỗ trợ đầy đủ tiếng Việt (mặc định) và tiếng Anh; mọi chuỗi giao diện đi qua hệ thống
  i18n, không hard-code.
- Ngôn ngữ giao diện, ngôn ngữ nghiên cứu và ngôn ngữ nội dung là ba cấu hình độc lập
  (mặc định: VI / theo thị trường / EN).

## Ràng buộc Kỹ thuật, Bảo mật & Chi phí

- Stack nền tảng đã định hướng: Python + FastAPI, PostgreSQL, SQLAlchemy, Alembic, Pydantic; React +
  TypeScript, Tailwind CSS, shadcn/ui, i18next; Docker Compose; pytest, Playwright. Thay đổi stack
  nền tảng cần sửa đổi constitution.
- AI provider: Claude API mặc định; OpenAI API dự phòng khi được cấu hình. Model chọn theo tác vụ qua
  cấu hình.
- Database: khóa chính UUID, foreign key, unique constraint, timestamps (`created_at`, `updated_at`),
  mọi thay đổi schema qua migration. Chỉ tạo bảng cần cho feature đang triển khai.
- Chuỗi truy vết dữ liệu MUST được bảo toàn: niche → product → keyword → content → publication →
  revenue, và mọi kết luận → evidence → source.
- Phân biệt nghiêm ngặt: affiliate click ≠ sale; pending commission ≠ doanh thu đã nhận.
- Không tạo review giả, không sao chép nội dung đối thủ, không tạo hình ảnh/video giả mạo trải nghiệm
  sản phẩm, luôn có affiliate disclosure (áp dụng từ E5 trở đi).
- MVP là single-user, single-workspace. Multi-tenant/SaaS chỉ triển khai khi được yêu cầu (Giai đoạn 5),
  nhưng thiết kế không được chặn đường mở rộng (ví dụ: có `project_id` để phân vùng dữ liệu).

## Quy trình Phát triển & Cổng Chất lượng

- Quy trình Spec Kit bắt buộc cho mỗi feature: Constitution → Specify → Clarify → Plan → Tasks →
  Analyze → Implement → Test & Verify. Mỗi feature có `spec.md`, `plan.md`, `tasks.md` riêng.
- Không triển khai chức năng chưa được đặc tả; không tự mở rộng phạm vi; yêu cầu chưa rõ phải hỏi xác
  nhận trước khi triển khai, ưu tiên câu hỏi ảnh hưởng kiến trúc, dữ liệu, nghiệp vụ.
- Thứ tự triển khai: E0 → E1 → E2 → E3 → E4. Không chuyển sang E5–E8 khi chưa được yêu cầu.
- Cổng chất lượng trước khi merge: lint + type check sạch, toàn bộ test tự động pass, migration chạy
  được từ đầu và rollback được, không có secret trong diff, tài liệu cập nhật.
- Sau mỗi bước, báo cáo bằng tiếng Việt: việc đã làm, file đã tạo/sửa, quyết định kỹ thuật, vấn đề phát
  hiện, kết quả kiểm thử (ghi rõ nếu chưa chạy), điểm cần xác nhận, bước tiếp theo.

## Governance

- Constitution có hiệu lực cao nhất so với mọi tài liệu và thói quen khác. Khi spec/plan mâu thuẫn với
  constitution, constitution thắng và tài liệu kia phải sửa.
- Sửa đổi constitution: đề xuất bằng văn bản (lý do, tác động, kế hoạch chuyển đổi), được chủ sở hữu dự
  án phê duyệt, cập nhật phiên bản theo SemVer: MAJOR (xóa/định nghĩa lại nguyên tắc), MINOR (thêm
  nguyên tắc/mở rộng đáng kể), PATCH (làm rõ câu chữ).
- Mọi `plan.md` MUST có mục Constitution Check đối chiếu các nguyên tắc I–XII; vi phạm phải được ghi
  trong Complexity Tracking kèm lý do và phương án đơn giản hơn đã bị loại.
- `/speckit-analyze` MUST được chạy trước khi implement mỗi feature; phát hiện mức CRITICAL chặn
  việc triển khai.
- Hướng dẫn phát triển runtime cho AI coding agent nằm trong `CLAUDE.md`.

**Version**: 1.1.0 | **Ratified**: 2026-11-18 | **Last Amended**: 2026-11-18
