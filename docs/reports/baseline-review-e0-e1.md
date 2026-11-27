# Rà soát baseline E0/E1 trước khi coi `main` là baseline ổn định – 2026-11-25

**Phạm vi:** commit `8125501` (nhánh `main` và `claude/inspiring-wright-06dzhw`).
**Trạng thái:** E0/E1 = `IMPLEMENTATION_COMPLETE / PENDING_EXTERNAL_VERIFICATION`. **Không** phải `PRODUCTION_VERIFIED`.
CI PASS **không** đồng nghĩa với nghiệm thu production.

## 1. Trạng thái Git

| Mục | Kết quả |
|---|---|
| Working tree | Sạch (0 thay đổi chưa commit) |
| Commit kiểm thử | `812550122a320cdf276e28385a1a334d20ccad37` – CI #57 `success` |
| Lịch sử | 63 commit tuyến tính từ `0ceac28`; không force-push, không rewrite |
| Nhánh `main` | **Đã tạo** trên GitHub tại `8125501` (push thường, không force) |
| Nhánh `claude/inspiring-wright-06dzhw` | Giữ nguyên, trùng `main` |
| Tag `e1-impl-complete` | Tạo **cục bộ** (annotated) tại `8125501`; **đẩy lên GitHub bị từ chối** (HTTP 403 – chính sách proxy git của phiên chỉ cho đẩy nhánh). Không thử lại |
| Default branch GitHub | Vẫn là `claude/inspiring-wright-06dzhw` – chưa đổi (cần quyền quản trị + xác nhận riêng) |

## 2. Đối chiếu Constitution v1.1.0

| Nguyên tắc | Đánh giá | Căn cứ |
|---|---|---|
| I. Evidence-First (không bịa) | Đạt ở mức tự động | `evidence_rules` (ngưỡng ≥ 2 bằng chứng, ≥ 2 nhóm độc lập), `UNKNOWN` cho tiêu chí thiếu dữ liệu; MOCK tách riêng (`ORIGIN_MISMATCH`) |
| II. Opportunity ≠ Confidence | Đạt | `scoring/opportunity.py`, `scoring/confidence.py` tách biệt; một nơi tạo đánh giá (`evaluation.evaluate_and_store`) |
| III. Niche-First & AI-First | Đạt (logic) – chưa chứng minh với AI thật | Agent `discovery.*` chạy với MockAIProvider |
| IV. Human-in-the-Loop | Đạt | Quyết định ngách do người ghi (PURSUE/WATCH/…); không tự đăng ký/xuất bản (AC-19) |
| V. AI Safety | Đạt ở mức tự động | Schema validation, retry, hủy job, giới hạn bước |
| VI. Cost-Aware | Đạt ở mức tự động | `AI_PAID_CALLS_ENABLED=false` mặc định; chặn khi model/giá chưa xác minh (`TC_FR019_01`, `TC_FR019c_01`); bỏ job có phí khi hết ngân sách (`TC_FR034_01`) |
| VII. OSS-First | Đạt | spaCy chưa duyệt → không dùng production |
| VIII. Module & API-First | Đạt | `lint-imports`: 4 contract kept, 0 broken |
| IX. TDD & truy vết | Đạt | Truy vết `--strict` rc=0 (mục 3) |
| X. Security-by-Design | Đạt ở mức tự động | detect-secrets so với baseline (CI job `secrets`); che secret; băm mật khẩu Argon2/bcrypt (`core/security.py`); audit log; robots.txt/ToS – nguồn chỉ dùng khi `ALLOWED` |
| XI. Self-Hosted | Linux PASS; **Windows NOT_TESTED** | CI `smoke`; RAM nghỉ 324–361 MB (Linux) |
| XII. Song ngữ | Đạt | i18next VI/EN; E2E chuyển EN |
| Quy trình Spec Kit | Đạt | spec/plan/tasks/analyze cho E0 (001) và E1 (002); E1 analyze cuối 0 CRITICAL/HIGH |
| Cổng chất lượng trước merge | Đạt | ruff, mypy, lint-imports, pytest, oxlint, tsc, vitest, Playwright, migration upgrade→downgrade→upgrade (`TC_FR004_01`), không secret |

## 3. Requirement coverage và truy vết (`scripts/traceability_report.py --strict`, rc = 0)

| Feature | FR mức Must | Có test tự động | Thiếu |
|---|---|---|---|
| E0 | 58 | 58 | 0 |
| E1 | 59 | 59 | 0 |

- SC-013 = `LIVE_ONLY` (chỉ có test live, chưa chạy) → **BLOCKED**.
- Cảnh báo tồn tại từ trước: mã test `TC_E1_FR034_*` tham chiếu "FR-034" không có trong spec E1 (spec E0 có FR-034) – không làm hỏng
  strict; đề xuất đổi tên test ở lần sửa sau (không thuộc phạm vi rà soát này).
- Toàn bộ test tự động dùng MockAIProvider/transport giả lập – **không chứng minh tích hợp provider thật**.

### Đối chiếu tiêu chí nghiệm thu MVP (master-requirements §10) thuộc E0/E1

| AC | Trạng thái |
|---|---|
| AC-01 Khởi động trên Windows | **NOT_TESTED** (Linux PASS) |
| AC-02 Claude API hoạt động | **NOT_TESTED** (chưa được phép gọi có phí) |
| AC-03 Giới hạn chi phí AI | PASS (tự động) |
| AC-04 AI tự tìm ngách | PASS với MockAIProvider + nguồn giả lập; **chưa với AI/nguồn thật** |
| AC-05 Pain point + persona | PASS (tự động, MOCK) |
| AC-06 Opportunity + Confidence | PASS (tự động) |
| AC-07 Nguồn bằng chứng | PASS (tự động); nguồn thật BLOCKED |
| AC-09 UNKNOWN cho thông tin chưa xác minh | PASS (tự động) |
| AC-12 VI/EN (khung) | PASS (E2E) |
| AC-13 Chạy thủ công và theo lịch | PASS (tự động) |
| AC-14 Logging + retry | PASS (tự động) |
| AC-15 PostgreSQL | PASS |
| AC-16 Báo cáo nghiên cứu | PASS (tự động); chưa có báo cáo từ dữ liệu thật |
| AC-17 Automated tests | PASS – backend 513 passed / 6 skipped (1 BLOCKED), frontend 24 passed |
| AC-18 E2E thực tế | Một phần – E2E E0 + E1 (MOCK) PASS; luồng đầy đủ thuộc E4 |
| AC-19 Không tự đăng ký/xuất bản | PASS (không có chức năng) |
| AC-20 Hướng dẫn vận hành | PASS (tài liệu `docs/operations`, quickstart) |

## 4. Rà soát an toàn

| Chủ đề | Cơ chế | Test đại diện |
|---|---|---|
| MockAIProvider | Production từ chối khởi động/thực thi khi cấu hình mock; dữ liệu gắn `MOCK` | `TC_FR012_11`, `TC_FR018f_04`, `TC_E1_FR016_01`, `TC_E1_FR012a_09`, `TC_E1_FR026_06` (lệnh seed demo từ chối production) |
| API có phí | `AI_PAID_CALLS_ENABLED=false`; chặn trước khi gửi; chặn khi model/giá `UNVERIFIED` | `TC_FR019_01`, `TC_FR019c_01` |
| Budget | Đặt chỗ ngân sách trước khi gọi; scheduler bỏ job có phí khi hết ngân sách | `TC_FR034_01` + 34 file test liên quan budget |
| PII | Che trước khi lưu DB/log/checkpoint/gửi AI; `NEEDS_REVIEW` không gửi AI; engine chưa duyệt bị từ chối ở production; regex không coi là đủ (tên người → `NEEDS_REVIEW`) | `TC_E1_FR012a_03`, `TC_E1_FR012a_04`, `TC_E1_FR012a_09` |
| Source Compliance | Chỉ nguồn `ALLOWED` được bật; robots.txt; backoff `Retry-After`/maxlag; không có nguồn thật nào `ALLOWED` | 26 file test liên quan `UNVERIFIED`/không được phép; 4 file robots |
| Secrets | Không credential trong repo; detect-secrets so với baseline đã rà soát; không tự thêm baseline | CI job `secrets` |
| Xóa dữ liệu | Erasure ledger đọc trạng thái DB mỗi request | `TC_E1_FR013f_14` |

## 5. Chưa được kiểm thử thực tế (NOT_TESTED / BLOCKED)

- Windows 10/11 (WSL2): **NOT_TESTED**.
- Claude/OpenAI API thật: **NOT_TESTED** (Q6 – chưa bật).
- Nguồn dữ liệu thật: **BLOCKED** – không nguồn nào `ALLOWED`; SC-013 **BLOCKED**; quickstart §3 BLOCKED.
- Wikipedia (S1), HN, Stack Exchange, GitHub: `UNVERIFIED` (điều khoản chưa đọc được – dịch vụ môi trường từ chối mở mạng).
- `docker compose kill worker` và dừng PostgreSQL trên stack thật: NOT_TESTED (đã có integration test).
- Image `browser-fetcher`: chưa build; fetcher tắt (Q8).
- spaCy (PII production): chưa duyệt (Q7); từ khóa lĩnh vực nhạy cảm chỉ tiếng Anh.
- E2E màn hình chi tiết/quyết định: **đã kiểm** bằng dữ liệu MOCK (CI #56) – không phải dữ liệu thật.

## 6. Kết luận

`8125501` đủ điều kiện làm **baseline mã nguồn** (mọi cổng chất lượng tự động đạt, truy vết đầy đủ, không vi phạm constitution phát hiện
được). **Không** đủ điều kiện nghiệm thu production: còn các mục ở §5.

## 7. Đề xuất branch protection cho `main` (chủ sở hữu tự cấu hình trong GitHub → Settings → Branches/Rulesets)

1. Bắt buộc pull request trước khi merge; ≥ 1 review phê duyệt (chủ sở hữu); dismiss review cũ khi có commit mới.
2. Bắt buộc status checks đạt và nhánh cập nhật: các job CI `backend`, `frontend`, `secrets`, `smoke`, `traceability`, `e2e` (theo
   `.github/workflows/ci.yml`).
3. Chặn force-push và xóa nhánh `main`.
4. Lịch sử tuyến tính (squash hoặc rebase merge).
5. Bảo vệ tag `e1-impl-complete` (tag ruleset: cấm cập nhật/xóa) sau khi tag được đẩy lên.
6. Đổi default branch sang `main` – cần xác nhận riêng của chủ sở hữu.
