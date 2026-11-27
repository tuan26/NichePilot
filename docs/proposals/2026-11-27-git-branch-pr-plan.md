# Phương án tách PR theo feature – bản 2 (CHỜ CHỦ SỞ HỮU DUYỆT) – 2026-11-27

Chủ sở hữu đồng ý **nguyên tắc** (2026-11-27). Chưa thực hiện thao tác nào trên PR. Không force-push, không rewrite, không merge, không đóng
PR #1 trước khi PR thay thế đã tạo và bao phủ đủ commit.

## 1. Trạng thái thực tế (kiểm tra lại 2026-11-27, `git ls-remote` + `git log`)

| Ref | Commit | Ghi chú |
|---|---|---|
| `main` (default, ruleset `protect-main`) | `8125501` | = tag `e1-impl-complete` |
| `claude/inspiring-wright-06dzhw` = head PR #1 (base `main`) | `e019c8c` + commit tài liệu này | Lịch sử tuyến tính, không merge commit |
| `feature/e3-keyword-audience` | tách từ `e019c8c` | Chỉ chứa commit E3 phía trên E2 |

Commit trên PR #1 (cũ → mới): `a1f0fbf` rà soát baseline · `bf849b6` spec E2 + đề xuất quy trình · `3c2e90a` Constitution 1.2.0 + clarify
E2 · `cd01c4b` plan · `709a13a` tasks · `c3c1be9`, `79dd309`, `162b5da`, `d05b1ba` implement/báo cáo E2 · `e019c8c` đề xuất rubric v2 + PR
plan · (commit tài liệu bản 2 này).

## 2. Phương án khuyến nghị – giữ PR #1, thêm 1 PR, không đóng PR nào

| PR | Base | Head | Commit được review | Hành động |
|---|---|---|---|---|
| **PR A (mới)** "Rà soát baseline E0/E1" | `main` (`8125501`) | `docs/baseline-review` = nhánh mới trỏ **đúng** `a1f0fbf` | `a1f0fbf` (1 commit) | Tạo nhánh + mở PR |
| **PR #1 (giữ nguyên số)** đổi tên "E2 – Product & Affiliate Discovery" | đổi base `main` → `docs/baseline-review` | `claude/inspiring-wright-06dzhw` (không đổi) | `bf849b6` … commit tài liệu bản 2 (E2 + Constitution 1.2.0) | Đổi base + tiêu đề/mô tả |
| **PR C (khi E3 xong)** "E3 – Keyword & Audience Research" | `claude/inspiring-wright-06dzhw` | `feature/e3-keyword-audience` | chỉ commit E3 | Mở khi E3 `TECHNICAL_VERIFIED` |

Kiểm chứng bao phủ: `PR A ∪ PR #1 = toàn bộ 12 commit` của nhánh làm việc so với `main`; không commit nào bị bỏ hay lặp. Ưu điểm: không
cần đóng PR #1, không tạo lại PR, SHA giữ nguyên.

Thứ tự merge (chủ sở hữu thực hiện): PR A → `main`; sau đó đổi base PR #1 về `main` (GitHub cũng tự đổi nếu xóa nhánh `docs/baseline-review`
sau merge) → merge PR #1; tương tự PR C.

## 3. Phương án dự phòng (nếu muốn PR E2 mới)

PR B mới `feature/e2-product-affiliate` (trỏ cùng commit với nhánh làm việc) → base `docs/baseline-review`; **chỉ đóng PR #1 không merge sau
khi** PR A và PR B đã tạo và tổng commit = 12. Nhiều thao tác hơn, không có lợi ích thêm.

## 4. Thao tác Claude sẽ làm khi được duyệt

1. `git push origin a1f0fbf:refs/heads/docs/baseline-review` (tạo nhánh, không đổi commit nào).
2. Mở PR A (base `main`, head `docs/baseline-review`).
3. Đổi base PR #1 sang `docs/baseline-review`, cập nhật tiêu đề/mô tả; kiểm tra diff PR #1 chỉ còn commit E2.
Không merge, không force-push, không xóa nhánh, không đổi ruleset.
