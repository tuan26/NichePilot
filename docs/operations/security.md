# Quét secret (detect-secrets) và baseline có kiểm soát

**Quyết định chủ sở hữu (N1, 2026-11-18)**: tạo `.secrets.baseline` có kiểm soát; không tắt job `secrets`, không bỏ qua file/thư
mục chỉ để CI PASS.

## Cách kiểm tra

```bash
cd backend && uv run python scripts/check_secrets.py
```

- Dùng detect-secrets **1.5.0** (dev dependency backend), cùng plugin/bộ lọc ghi trong `.secrets.baseline`.
- Quét các file được git theo dõi. Loại trừ duy nhất: `package-lock.json`, `uv.lock` (hash toàn vẹn gói – giữ như cấu hình CI
  trước đây) và chính `.secrets.baseline` (chỉ chứa `hashed_secret`).
- So khớp theo (file, loại, `hashed_secret`), không theo số dòng. **Mọi finding chưa có trong baseline → exit 1** (CI thất bại).
- Mọi mục trong baseline phải có `"is_secret": false` (đã rà soát); có mục chưa rà soát → exit 1.
- Test `backend/tests/unit/test_secrets_baseline.py` (chạy trong job `backend`): baseline chỉ chứa file đã rà soát; repository
  không có finding mới; **canary** – sinh khóa dạng AWS + chuỗi entropy cao lúc chạy (không commit) → phải bị phát hiện.

## Kết quả rà soát baseline ban đầu (2026-11-18, commit gốc `79a89ae`)

Quét: 42 finding / 16 file. Phân loại: **42 Confirmed false positive**, 0 Potential secret, 0 Confirmed secret.
Lịch sử git (`git log -p --all`) chỉ có 2 chuỗi dạng key: `sk-ant-api03-SUPERSECRETVALUE…`, `sk-ant-api03-THIS-IS-A-TEST-ONLY-KEY…`
– đều là giá trị giả trong test, không phải key thật.

| Nhóm | File | Số | Loại detect-secrets | Lý do là dương tính giả (cách xác minh) |
|---|---|---|---|---|
| Hash toàn vẹn Spec Kit | `.specify/integrations/claude.manifest.json`, `speckit.manifest.json`, `.specify/memory/.constitution-template.json` | 22 | Hex High Entropy String | SHA-256 của file template/skill; đã tính lại SHA-256 từng file tham chiếu – 22/22 khớp |
| Mật khẩu chỉ dùng trong test | `backend/tests/api_helpers.py`, `contract/test_auth_session.py`, `contract/test_auth_setup.py`, `integration/test_auth_lockout.py`, `integration/test_no_secret_leak.py`, `frontend/tests/e2e/us1-auth-i18n.spec.ts` | 6 | Secret Keyword | Mật khẩu giả cho tài khoản tạo trong DB test/E2E (`correct-horse-battery`, `wrong-password-x`, `short`, `e2e-only-password-123`) |
| Key giả để kiểm tra che giấu secret | `backend/tests/integration/test_job_logs.py`, `unit/core/test_logging.py`, `unit/core/test_config.py` | 4 | Base64 High Entropy / Secret Keyword | Chuỗi tự đặt (`sk-ant-joblogs-…`, `sk-ant-api03-SUPERSECRETVALUE…`, `from-dotenv`) để test redaction; không đúng định dạng/độ dài key thật; không bao giờ gửi tới provider (test chặn mạng) |
| Nhãn giao diện | `frontend/src/i18n/locales/en.json`, `vi.json` | 8 | Secret Keyword | Khóa i18n `password`, `passwordHint`… và chuỗi hiển thị ("Mật khẩu") |
| Placeholder cấu hình | `deploy/env/.env.example`, `specs/.../contracts/configuration.md` | 2 | Basic Auth Credentials | `change-me-local-only`, `user:pass` – giá trị mẫu bắt buộc đổi; file `.env` thật không được commit |

## Cập nhật baseline (chỉ cho dương tính giả đã rà soát)

1. Chạy `uv run python scripts/check_secrets.py` – đọc từng finding mới.
2. Phân loại: **Confirmed secret** → gỡ khỏi mã nguồn, thu hồi/xoay key ngay, KHÔNG đưa vào baseline. **Potential secret** →
   điều tra trước. **Confirmed false positive** → ghi lý do + cách xác minh vào bảng trên.
3. Chỉ khi là dương tính giả: từ gốc repo chạy
   `backend/.venv/bin/python -m detect_secrets scan --baseline .secrets.baseline --exclude-files '(package-lock\.json|uv\.lock|\.secrets\.baseline)$'`,
   đặt `"is_secret": false` cho đúng mục đã rà soát, cập nhật danh sách `REVIEWED_FILES` trong
   `backend/tests/unit/test_secrets_baseline.py` nếu là file mới.
4. Commit baseline + tài liệu trong cùng commit, mô tả rõ lý do. Người review kiểm tra diff baseline.
