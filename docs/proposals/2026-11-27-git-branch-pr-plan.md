# Phương án tách PR theo feature (CHỜ CHỦ SỞ HỮU DUYỆT) – 2026-11-27

## 1. Trạng thái thực tế (kiểm tra 2026-11-27)

| Ref | Commit | Ghi chú |
|---|---|---|
| `main` (default, có ruleset `protect-main`) | `8125501` | = tag `e1-impl-complete` |
| `claude/inspiring-wright-06dzhw` | `d05b1ba` (+ commit đề xuất này) | Hơn `main` 9 commit tới `d05b1ba` |
| PR #1 (`claude/inspiring-wright-06dzhw` → `main`) | head = nhánh làm việc | Ban đầu chỉ `a1f0fbf` (báo cáo rà soát baseline); nay chứa cả E2 |

Commit trên nhánh làm việc (cũ → mới): `a1f0fbf` rà soát baseline · `bf849b6` spec E2 + đề xuất quy trình · `3c2e90a` Constitution 1.2.0 +
clarify E2 · `cd01c4b` plan · `709a13a` tasks · `c3c1be9`, `79dd309`, `162b5da`, `d05b1ba` implement + báo cáo E2.

Lịch sử tuyến tính, không có commit merge. Không cần (và không) viết lại lịch sử.

## 2. Phương án đề xuất – PR xếp chồng (không mất commit, không force-push)

| Bước | Hành động | Base | Head |
|---|---|---|---|
| 1 | Tạo nhánh `docs/baseline-review` tại `a1f0fbf` | – | – |
| 2 | Tạo nhánh `feature/e2-product-affiliate` tại commit cuối của E2 (sau đề xuất này) | – | – |
| 3 | PR A "Rà soát baseline E0/E1" | `main` | `docs/baseline-review` (1 commit) |
| 4 | PR B "E2 – Product & Affiliate Discovery" (gồm Constitution 1.2.0) | `docs/baseline-review` | `feature/e2-product-affiliate` |
| 5 | Đóng PR #1 **không merge** (nội dung đã nằm trọn trong PR A + B), ghi chú liên kết | – | – |
| 6 | Merge (chủ sở hữu, qua ruleset): PR A → `main`; GitHub tự đổi base PR B sang `main` khi nhánh base bị xóa sau merge, hoặc đổi tay | | |

Mỗi PR chỉ hiển thị diff của feature mình. Commit giữ nguyên SHA (nhánh mới chỉ là con trỏ tới commit có sẵn).

Phương án thay thế (đơn giản hơn): giữ PR #1, đổi tiêu đề/mô tả thành "Baseline + E2" và review một lần. Nhược điểm: diff lớn, khó review.

## 3. Từ E3 trở đi

- Nhánh `feature/e3-keyword-audience` tạo từ commit cuối của E2 (E3 phụ thuộc mã E2 – không thể tạo từ `main` hiện tại).
- PR C (khi E3 xong): `feature/e3-keyword-audience` → `feature/e2-product-affiliate` (xếp chồng), đổi base sang `main` sau khi PR B merge.
- Nhánh `claude/inspiring-wright-06dzhw` dừng nhận commit feature mới sau E2.

## 4. Cần chủ sở hữu duyệt

Bước 1–5 (tạo nhánh, mở PR A/B, đóng PR #1 không merge). Claude không merge, không force-push, không đổi ruleset. Riêng nhánh E3 (§3)
được tạo ngay theo yêu cầu "từ E3 trở đi mỗi feature một nhánh riêng", base = commit cuối của E2.
