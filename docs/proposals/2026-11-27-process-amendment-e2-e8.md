# Đề xuất sửa đổi quy trình cho E2–E8 (ĐÃ DUYỆT 2026-11-27 – áp dụng Constitution 1.2.0) – 2026-11-27

Bối cảnh: chủ sở hữu yêu cầu (2026-11-27) phát triển tuần tự E2 → E3 → E4 → E5 → E6 → E7 → E8 theo Spec Kit, dùng MOCK khi chưa có
API thật, và cho phép Claude tự tiếp tục các bước kỹ thuật khi đủ điều kiện. Tài liệu này rà soát Constitution v1.1.0 và Master
Requirements, chỉ ra điểm cần sửa. **Chưa áp dụng** – Governance yêu cầu chủ sở hữu duyệt bằng văn bản.

## 1. Kết quả rà soát

| Quy định hiện hành | Nguồn | Ảnh hưởng | Cần sửa? |
|---|---|---|---|
| Thứ tự E0 → E1 → E2 → E3 → E4 | Constitution – Quy trình | E2–E4 đúng thứ tự | Không |
| "Không bắt đầu feature tiếp theo khi feature trước chưa qua Test & Verify" | Master §11 | E1 = `IMPLEMENTATION_COMPLETE / PENDING_EXTERNAL_VERIFICATION`, đã được chủ sở hữu nghiệm thu (D1, 2026-11-22). Tiền lệ: E1 bắt đầu khi E0 ở cùng trạng thái | Không cho E2 (theo tiền lệ); nên **làm rõ** (A1) |
| "Không chuyển sang E5–E8 khi chưa được yêu cầu" | Constitution – Quy trình; CLAUDE.md | Đã được yêu cầu bằng văn bản 2026-11-27 | Không – ghi nhận yêu cầu |
| GĐ1 hoàn thành khi "Đạt AC-01…AC-20" rồi mới tới GĐ2 (E5, E6), GĐ3 (E7, E8) | Master §11 | AC-01 (Windows) và AC-02 (Claude API thật) đang `NOT_TESTED` → theo nghĩa chặt, chưa được bắt đầu E5 | **Có** (A2) |
| E5–E8 "ngoài phạm vi MVP" | Master §12 | Mô tả phạm vi MVP, không cấm giai đoạn sau | Không |
| "Trong MVP (E0–E4) mọi hành động xuất bản/đăng ký bị vô hiệu hóa hoàn toàn" | Constitution IV | Chưa nói rõ trạng thái xuất bản khi phát triển E7 bằng mock/sandbox | **Nên làm rõ** (A3) |
| "Yêu cầu chưa rõ phải hỏi xác nhận trước khi triển khai" | Constitution – Quy trình | Khớp cơ chế tự tiếp tục của chủ sở hữu | Không – ghi vào CLAUDE.md (A4) |

## 2. Các sửa đổi đề xuất (Constitution 1.1.0 → 1.2.0, MINOR)

**A1 – Hai mức kiểm chứng (Constitution – Quy trình; Master §11).** Thêm định nghĩa:
- *Technical Verify*: toàn bộ quality gate tự động đạt, truy vết yêu cầu → test 100% (FR mức Must), `/speckit-analyze` 0 CRITICAL/HIGH,
  E2E phù hợp đạt. Đủ để chuyển sang feature tiếp theo.
- *External Verify*: kiểm chứng với API/nguồn thật, Windows, production. Hạng mục chưa làm được ghi `PENDING_EXTERNAL_VERIFICATION`,
  không chặn feature sau ở mức kỹ thuật, nhưng chặn trạng thái `PRODUCTION_VERIFIED` và chặn vận hành thật.

**A2 – Điều kiện bắt đầu GĐ2/GĐ3 (Master §11).** Cho phép implement kỹ thuật E5–E8 sau khi E4 đạt Technical Verify, trước khi MVP đạt
AC-01/AC-02 ở mức External Verify; E5–E8 dùng MockAIProvider, adapter mock/sandbox và dữ liệu test gắn `MOCK`.

**A3 – Xuất bản trong giai đoạn phát triển (Constitution IV).** Thêm: adapter xuất bản (E7) chỉ chạy với mock/sandbox; công tắc xuất bản
thật tắt mặc định, chỉ bật khi chủ sở hữu cho phép và vẫn qua approval request + audit log. E8 chỉ nhận dữ liệu test gắn `MOCK`,
không hiển thị/tính như doanh thu thật.

**A4 – Cơ chế tự tiếp tục (CLAUDE.md, không đổi Constitution).** Ghi điều kiện chủ sở hữu đặt ngày 2026-11-27: Claude tự chạy các bước kỹ
thuật khi yêu cầu rõ, không đổi kiến trúc quan trọng, không có CRITICAL/HIGH tồn đọng, quality gate đạt, không cần API key/quyền truy cập
bên ngoài, không phát sinh chi phí, không có hành động bên ngoài có hậu quả; ngược lại dừng và hỏi.

## 3. Tác động và kế hoạch chuyển đổi

- Không thay đổi mã, kiến trúc hay hành vi E0/E1.
- Sau khi duyệt: cập nhật `.specify/memory/constitution.md` (1.2.0, Sync Impact Report), Master §11, CLAUDE.md.
- E2 (và E3, E4) **không phụ thuộc** đề xuất này – bắt đầu theo quy định hiện hành. A2/A3 cần được duyệt **trước khi bắt đầu E5**.
