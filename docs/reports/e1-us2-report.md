# Báo cáo E1 – User Story 2 (T069–T084): Pain point, Buyer Persona, Evidence Management, Evidence Erasure

> Ngày: 2026-11-21 · Nhánh `claude/inspiring-wright-06dzhw` · Commit US2 `4c8db87` và commit sửa CI `e0b3968`.
> Mọi kết quả dưới đây dùng **nguồn giả lập và AI kịch bản (MOCK)**. Báo cáo này không chứng minh nguồn thật, Claude/OpenAI API thật,
> hay chất lượng phân tích của model thật. Không có lời gọi API có phí nào. Không nguồn `UNVERIFIED` nào được bật.

## 1. Số task

| Nhóm | Task | Trạng thái |
|---|---|---|
| Test viết trước | T069–T078 (10) | Hoàn thành |
| Triển khai | T079–T084 (6) | Hoàn thành |
| Bổ sung `task_type` theo phê duyệt | doc + test hồi quy | Hoàn thành |
| **Tổng** | **16/16 task US2** | `[x]` trong `tasks.md` |

Thứ tự TDD: test đơn vị T069 được viết trước và FAIL (thiếu module), sau đó mới viết `evidence_rules.py`. Test vitest T078 cũng FAIL
trước khi có màn hình. Với test tích hợp (T070–T077), phần lớn được viết **cùng lúc** với phần mã agent/API tương ứng, chứ không phải
trước hẳn. Chúng FAIL ở lần chạy đầu với các lỗi thật (mục 4).

## 2. Kết quả kiểm thử (chạy 2026-11-21)

| Bước kiểm tra | Kết quả |
|---|---|
| `ruff check` / `ruff format --check` | PASS / PASS (228 file) |
| `mypy` (strict) | PASS – 97 file nguồn |
| `lint-imports` | 4 contract KEPT, 0 broken |
| `pytest` backend (đầy đủ, Docker + postgres:17-alpine) | **449 passed, 3 skipped, 0 failed**. Kết quả giống hệt khi chạy lại trên một bản clone sạch |
| 3 test skipped | BLOCKED (không phải PASS): gồm SC-013 nguồn thật – chưa có nguồn ALLOWED |
| Frontend `lint` / `typecheck` / `test` | PASS / PASS / **13 passed** (3 file) |
| Truy vết `--strict` | PASS. E0: 58/58 FR Must có test. E1: 39 có test, 20 PENDING (US3–US7), **0 thiếu** |
| Secret scanning (`detect-secrets` so với baseline) | Không có finding mới. Baseline không bị sửa |

Test mới của US2:

- Đơn vị: `test_evidence_rules.py` (9 test).
- Tích hợp:
  - `test_insufficient_evidence.py` (2)
  - `test_evidence_not_profitability.py` (2)
  - `test_extraction.py` (7)
  - `test_pii_end_to_end.py` (3)
  - `test_erasure_restore.py` (2)
  - `test_erasure_during_run.py` (2)
- Hợp đồng: `test_erasure_api.py` (6), `test_niche_detail_api.py` (1).
- Bổ sung: redirect tới trang hồ sơ, lọc URL chứa PII, `task_type` đi qua gateway.
- Frontend: `niche-detail-page.test.ts` (5).

### Các ca kiểm thử chủ sở hữu yêu cầu

| Yêu cầu | Test | Kết quả |
|---|---|---|
| Xóa khi job đang chạy | `TC_E1_FR013e_05`: xóa nguồn đúng lúc agent đang fetch trang kế tiếp. Trích đoạn đã xóa không có trong prompt `extract`/`assess`, không được tính ngưỡng. Bản sao khác tên miền → `ERASED_CONTENT` | PASS |
| Bản sao khác tên miền | `TC_E1_FR013b_03`, `TC_E1_SC003a_01`, `TC_E1_FR013c_01`: bản sao nguyên văn, bản sửa 2–3 từ, bản sao toàn trang → cùng nhóm; 0 cặp bản sao được tính là độc lập | PASS |
| Bằng chứng thiếu trường | `TC_E1_FR013a_01`: thiếu hoặc rỗng URL, trích đoạn, thời điểm thu thập, trạng thái (hoặc trạng thái UNKNOWN) → không tính | PASS |
| PII không nhận diện chắc chắn | `TC_E1_FR012b_03`: "Thanks, Morgan" và câu chứa tên người tự do → `NEEDS_REVIEW`. Không lưu, không có trong prompt, không có trong bất kỳ bảng nào | PASS |
| Lỗi I/O ledger | `TC_E1_FR013e_06`: ghi sổ thất bại (OSError) → 503 `ERASURE_LEDGER_WRITE_FAILED`, DB không thay đổi | PASS |
| Ledger lệch DB | `TC_E1_FR013e_07`: sổ có dòng chưa áp dụng → API 503. Áp dụng sổ → bằng chứng bị xóa, ngách được tính lại | PASS |
| Ghi sổ xong nhưng DB lỗi | `TC_E1_FR013e_08`: rollback, sức khỏe sổ `OUT_OF_SYNC`; lần áp dụng sau hoàn tất việc xóa | PASS |
| Resume job sau khi xóa | `TC_E1_FR013e_09`: job PAUSED sau bước fetch (checkpoint không chứa văn bản) → xóa → resume → không dùng lại bằng chứng đã xóa | PASS |
| Restore backup cũ hơn yêu cầu xóa | `TC_E1_FR013f_09`/`SC016_03`: API 503 cho tới khi áp dụng sổ; sau đó dữ liệu vẫn ERASED, ngách được tính lại, API không trả trích đoạn | PASS (restore được **mô phỏng ở mức DB**, xem mục 6) |

## 3. Nội dung đã triển khai

- **`task_type`** (E0, đã được phê duyệt):
  - `AgentDefinition.extra_task_types` và `JobContext.call_ai(task_type=…)`.
  - Không truyền `task_type` → hành vi E0 giữ nguyên.
  - Task type chưa đăng ký → `TASK_TYPE_NOT_ALLOWED`, không gọi gateway.
  - Mọi lời gọi vẫn đi qua `AIGateway`. Test tích hợp xác nhận `ai_usage_logs` có `discovery.extract` và chi phí được đối soát vào job.
  - Hợp đồng đã cập nhật: E0 `internal-interfaces.md` §3, E1 §7.
- **Ngưỡng và nhóm độc lập** (`evidence_rules.py`, thuần, không I/O):
  - Union-find trên các tín hiệu: eTLD+1, SimHash trích đoạn, SimHash toàn nguồn, `content_hash`, tỉ lệ chứa shingle 3 từ.
  - Tham số đọc từ `scoring_weights_versions.evidence_rules`.
- **Extract và assess**:
  - Extract trả pain point (severity + lý do), persona 5 thuộc tính, 6 nhóm findings và đối thủ.
  - Assess trả relevance, quality, copy_suspected cho từng bằng chứng.
  - Một `evidence_id` lạ → loại **toàn bộ** đầu ra.
  - Kết luận không dẫn bằng chứng → `UNKNOWN`. `CONFLICTING` lưu mọi giá trị (cần ≥ 2, nếu không → UNKNOWN).
  - Trường lạ như `search_volume` → đầu ra bị loại.
  - `AI_SCHEMA_INVALID` chỉ loại đầu ra của ứng viên đó; lượt vẫn hoàn tất (SC-008).
- **`evaluate_niche`** (xác định, không gọi AI):
  - Gán `evidence_status`, `monetization_status`, cờ `MONETIZATION_RISK`.
  - Cắt các ID đã xóa khỏi kết luận.
  - Chạy cho mọi ứng viên ở bước finalize, kể cả khi lượt dừng sớm.
- **Xóa bằng chứng**:
  - Trình tự: khóa trạng thái sổ → kiểm tra sổ đồng bộ → ghi sổ (fsync) → **một** transaction gồm xóa nội dung, ghi yêu cầu, audit, cập nhật `applied_seq` và tính lại ngách đồng bộ.
  - Sau đó tạo job `discovery.recompute` (0 lời gọi AI, đã kiểm tra bằng test).
  - `apply_erasure_ledger` cũng tính lại các ngách bị ảnh hưởng.
  - Khi thu thập, kiểm tra nội dung đã xóa **ngay trước khi lưu**, ở cả mức trang và mức trích đoạn.
- **API**: `POST /api/v1/evidence/{id}/erase` (EVIDENCE/SOURCE) và `GET /api/v1/niches/{id}` (16 trường BR-07, thiếu → UNKNOWN). Cả hai qua cổng ledger.
- **Màn hình 3** `/niches/:id`:
  - Hiển thị pain point, persona, findings, đối thủ, bằng chứng + nguồn + ngày xác minh ALLOWED, nhãn MOCK.
  - Cảnh báo "đạt ngưỡng ≠ sinh lợi".
  - Xóa bằng chứng phải nhập lý do và xác nhận.
  - Song ngữ VI/EN.

## 4. Lỗi phát hiện và cách xử lý

| # | Lỗi | Phát hiện bởi | Xử lý |
|---|---|---|---|
| 1 | **CI GitHub đỏ từ Phase 2** (run 39, 40, 41): fixture `pii_labeled.jsonl` bị `.gitignore` (`*.jsonl`) bỏ qua nên không được commit. Ở máy local test vẫn PASS. Báo cáo US1 trước đây **không** nêu kết quả CI – đó là thiếu sót | Kiểm tra CI theo yêu cầu báo cáo | Thêm ngoại lệ `!backend/tests/fixtures/**/*.jsonl`, commit fixture (PII giả). Đã kiểm tra lại bằng bản clone sạch: 449 passed |
| 2 | **Rò rỉ PII**: URL hồ sơ cá nhân (`/user/<handle>`) nằm trong output của `source.query`, được lưu vào `tool_executions` dù agent đã lọc phía sau | `TC_E1_FR012a_07` (quét mọi bảng DB) | Tool `source.query` bỏ các hit có URL hồ sơ hoặc URL chứa PII (đếm `skipped_pii_urls`). `page.fetch` từ chối redirect tới trang hồ sơ (`PII_UNSAFE`, `final_url = null`). Thêm 2 test |
| 3 | SimHash ≤ 3 **bỏ sót** bản sao sửa 2–3 từ (Hamming = 5) | `TC_E1_FR013b_03` | Thêm tín hiệu tỉ lệ chứa shingle 3 từ ≥ 0,5 (chỉ gộp thêm nhóm, chặt hơn). Ghi bổ sung vào `scoring-rubric.md` §1 |
| 4 | Hậu tố ngoài PSL (`.example`) làm `community.forum.example` thành một "tên miền khác" | `TC_E1_FR013b_02` | `registered_domain` lấy 2 nhãn cuối khi hậu tố không có trong PSL (bỏ qua địa chỉ IP) |
| 5 | Kiểm tra `ERASED_CONTENT` so hash cả trang với hash trích đoạn (không bao giờ khớp) và dùng ảnh chụp đầu lô (xóa giữa lô không được tôn trọng) | `TC_E1_FR013e_05` | `erased_among()` truy vấn ngay trước khi lưu, ở cả hai mức; bỏ trích đoạn đã xóa; nguồn đã xóa cũng được tính |
| 6 | Đầu ra sai schema làm hỏng cả job (`AI_SCHEMA_INVALID`) | `TC_E1_SC004_01` | Chỉ loại đầu ra của ứng viên đó và tăng `ai_outputs_rejected`; các lỗi khác (ngân sách, provider) vẫn theo cơ chế E0 |
| 7 | Tạo job tính lại lỗi 500: `params` chứa UUID không tuần tự hóa được JSON | `TC_E1_FR013e_02` | `RecomputeParams.niche_ids` là chuỗi |
| 8 | Lỗi DB sau khi ghi sổ: cache sức khỏe sổ (60 s) vẫn báo OK | Phân tích khi viết `TC_E1_FR013e_08` | `DiscoveryServices.erase` luôn xóa cache sức khỏe sổ, kể cả khi lỗi |
| 9 | Truy vết không nhận TC thứ hai trong tên test ghép (`…FR010_01_FR011_01`) → FR-011 thiếu | `traceability --strict` | Đổi tên thành `…_TC_E1_FR011_01` (5 test) |
| 10 | Docker daemon trong môi trường dừng giữa chừng → 196 ERROR khi kết nối testcontainers | pytest | Khởi động lại dockerd và chạy lại (lỗi môi trường, không phải lỗi mã) |

## 5. Truy vết yêu cầu (US2)

| Yêu cầu | Test |
|---|---|
| FR-007, FR-008, FR-009, FR-010, FR-011, FR-013, FR-014 | `test_extraction.py` |
| FR-012a, FR-012b, FR-012c, SC-016 | `test_pii_end_to_end.py`, `test_page_fetch_tool.py`, `test_source_query_tool.py` |
| FR-013a, FR-013b, FR-015, SC-003a | `test_evidence_rules.py`, `test_insufficient_evidence.py` |
| FR-013c | `test_insufficient_evidence.py` |
| FR-013d | `test_evidence_not_profitability.py` – **một phần**: phần bảng xếp hạng và danh sách affiliate thuộc US3, chưa kiểm thử |
| FR-013e | `test_erasure_api.py`, `test_erasure_during_run.py` |
| FR-013f | `test_erasure_restore.py`, `test_erasure_api.py` (ledger lệch/lỗi), cùng các test US1 sẵn có |
| FR-023, SC-003 | `test_niche_detail_api.py`. Opportunity/Confidence = UNKNOWN cho tới US3 |
| FR-026 (màn hình 3), SC-004, SC-008 | `niche-detail-page.test.ts`, `test_extraction.py` |
| FR-028 (`task_type`) | `test_runtime_task_type.py`, `test_discovery_run_flow.py::…FR028_05` |

## 6. Thay đổi chạm vào E0

| Thay đổi | Phê duyệt | Ảnh hưởng |
|---|---|---|
| `jobs/runtime.py`: `extra_task_types` và tham số `task_type` của `call_ai` | Có (2026-11-20) | Mặc định không đổi; regression test cho cả hai trường hợp; toàn bộ suite E0 PASS |
| `core/errors.py`: thêm `TASK_TYPE_NOT_ALLOWED`, `ERASURE_LEDGER_WRITE_FAILED` | Bổ sung mã lỗi (không đổi mã cũ) | `error-codes.json` có 59 mã, đủ i18n VI/EN |
| `specs/001…/contracts/internal-interfaces.md` §3 | Theo yêu cầu cập nhật hợp đồng | Chỉ tài liệu |
| `.gitignore` (ngoại lệ fixture `.jsonl`) | Sửa lỗi CI | Không ảnh hưởng runtime |

Không sửa Job Runtime (ngoài phần trên), Scheduler, AIGateway, BudgetService hay Tool Registry. Job `discovery.recompute` đặt
`max_ai_calls = 1` vì ràng buộc `agent_jobs` của E0 yêu cầu ≥ 1; agent này không bao giờ gọi AI (đã có test kiểm tra).

## 7. BLOCKED / NOT_TESTED / hạn chế còn lại

- **SC-013 – BLOCKED** (không đổi): chưa có nguồn `ALLOWED`; mọi nguồn seed vẫn `UNVERIFIED` và tắt.
- **API thật (Claude/OpenAI) – NOT_TESTED**. Mọi phân tích dùng `ScriptedDiscoveryAI` (MOCK).
- **Restore bằng `pg_dump/pg_restore` thật cho US2 – NOT_TESTED**: test mô phỏng restore ở mức DB (ghi lại các cột như trong backup và đặt sổ BLOCKED như `restore.sh`). Lần chạy `make restore` thật gần nhất là smoke ở US1, trước khi có tính lại ngách.
- **PII engine**: chỉ kiểm thử tiếng Anh trên bộ mẫu tự soạn. Ngôn ngữ khác → `NEEDS_REVIEW` (theo thiết kế). spaCy vẫn chưa được phê duyệt cho production (I2).
- **FR-013d**: phần "có trong bảng cơ hội nhưng không có trong danh sách affiliate" chờ xếp hạng ở US3.
- `published_at` của bằng chứng hiện là `null` (bảng `research_sources` chưa có cột này). Sẽ bổ sung khi chấm độ mới F ở US3 nếu chủ sở hữu đồng ý.
- E2E Playwright cho màn hình 3 chưa viết (SC-014 thuộc giai đoạn hoàn thiện).
- Windows/WSL2 – NOT_TESTED.

## 8. GitHub CI

| Run | Commit | Kết quả |
|---|---|---|
| [#39](https://github.com/tuan26/NichePilot/actions/runs/44685931533) Phase 2, [#40](https://github.com/tuan26/NichePilot/actions/runs/44687959281) US1 | `fdbfee7`, `0324ae6` | **failure** – thiếu fixture `pii_labeled.jsonl` (lỗi #1). Báo cáo trước đây không nêu điều này |
| [#41](https://github.com/tuan26/NichePilot/actions/runs/44885889776) | `4c8db87` (US2) | **failure** – cùng nguyên nhân (446 passed, 2 failed) |
| [#42](https://github.com/tuan26/NichePilot/actions/runs/44886152857) | `e0b3968` (sửa fixture) | backend, frontend, secrets, traceability, smoke: success; **e2e: failure** – job e2e không sinh `SEARXNG_SECRET` (hồi quy từ US1, trước đây bị che vì e2e bị skip khi backend đỏ) |
| [#43](https://github.com/tuan26/NichePilot/actions/runs/44886659917) | `a448a8b` | **success** – cả 6 job xanh: backend, frontend, secrets, traceability, smoke, e2e |

Commit chỉ chứa báo cáo sau run #43 sẽ chạy CI lại; mã nguồn không đổi.
