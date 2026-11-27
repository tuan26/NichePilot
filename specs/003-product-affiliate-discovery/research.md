# Research – E2 Product & Affiliate Discovery (Phase 0)

Ngày: 2026-11-27. Không có `NEEDS CLARIFICATION` trong Technical Context. Mọi quyết định dưới đây **tái sử dụng** hạ tầng E0/E1, không
thêm dependency, service hay loại nguồn mới.

## R-01. Thu thập trang sản phẩm / điều khoản

- **Decision**: Dùng lại nguyên chuỗi của E1: `SourcePolicyService.usable_for_run()` (chỉ `ALLOWED` ∧ bật) → tool `source.query` → kiểm tra
  `DomainAccessService.permit` (robots.txt + mức trần 1 request/2 s/tên miền) → tool `robots.fetch` khi cần → tool `page.fetch` (trích nội
  dung + che PII **trong handler**) → `EvidenceService.add_source/add_evidence`. Viết `PageCollector` mới trong `jobs/agents/_collector.py`
  (dùng chung cho `products.run` và `products.terms_check`) theo đúng thứ tự kiểm tra của `NicheDiscoveryAgent._fetch`.
- **Rationale**: FR-006/FR-010 yêu cầu cùng tuân thủ như E1; không sửa agent E1 → không đổi hành vi E1 (ràng buộc chủ sở hữu).
- **Alternatives**: (a) Tách `_fetch` của E1 ra helper chung – bị loại: chạm mã E1 đã nghiệm thu, rủi ro hồi quy; có thể gộp ở feature sau
  khi có test hồi quy đầy đủ. (b) Gọi thẳng website sản phẩm không qua nguồn tìm kiếm – bị loại: URL phải xuất phát từ kết quả của nguồn
  `ALLOWED` để có `source_policy_id` truy vết.

## R-02. Truy vấn tìm kiếm – xác định, không dùng AI

- **Decision**: Truy vấn sinh bằng mã từ dữ liệu E1: với tối đa 3 pain point có severity cao nhất: `"<pain point> <segment> tool"`,
  `"best <product kind> for <segment>"`; giai đoạn 2 theo sản phẩm: `"<product> pricing"`, `"<product> affiliate program"`. Mẫu truy vấn
  nằm trong cấu hình phiên bản trọng số (`query_templates`).
- **Rationale**: tiết kiệm lời gọi AI (Constitution VI), kiểm thử xác định.
- **Alternatives**: AI lập truy vấn như `discovery.candidates` – bị loại cho MVP E2 (thêm chi phí, khó test).

## R-03. Trích xuất có kiểm chứng (chống bịa số liệu – FR-009)

- **Decision**: AI (task `products.extract`, `products.program_extract`) chỉ trả **trích xuất có `evidence_ids`**; mã kiểm tra:
  (1) mọi `evidence_id` phải thuộc tập trích đoạn đã đưa vào prompt; một id lạ → loại toàn bộ đầu ra của sản phẩm đó (như E1);
  (2) **giá trị số** (giá, % hoa hồng, số ngày cookie, ngưỡng thanh toán) phải xuất hiện nguyên dạng trong ít nhất một trích đoạn được dẫn
  (so khớp chuẩn hóa: bỏ dấu phẩy nghìn, ký hiệu tiền tệ, khoảng trắng) – không khớp → thuộc tính `UNKNOWN` + ghi `rejected_values`;
  (3) mã quốc gia/mã giới hạn quảng cáo phải thuộc danh mục cho phép.
- **Rationale**: Constitution I – AI không được tạo hoa hồng/cookie/giá. Kiểm tra chuỗi số là cách xác định, rẻ, test được.
- **Alternatives**: Tin AI hoàn toàn – vi phạm Constitution I. Trích bằng regex thuần – không đủ cho văn bản điều khoản đa dạng.

## R-04. Trạng thái xác minh do mã quyết định (FR-008)

- **Decision**: Mỗi bằng chứng thuộc tính được gắn trạng thái theo **tên miền nguồn** (eTLD+1, `registered_domain`):
  - thuộc tính sản phẩm: `VERIFIED` nếu tên miền nguồn = `official_domain` của sản phẩm; ngược lại `INFERRED`;
  - thuộc tính chương trình: `VERIFIED` nếu tên miền nguồn = `operator_domain` (nhà cung cấp hoặc mạng affiliate vận hành chương trình);
    ngược lại `INFERRED`;
  - `official_domain` được chấp nhận khi AI đề xuất và tên miền đó có trong URL kết quả tìm kiếm/trang đã tải (không phải trang review/
    bán lại: danh sách tên miền marketplace/review phổ biến trong cấu hình `non_official_domains`), nếu không → `UNKNOWN`.
  Gộp thuộc tính (`attributes.resolve`): có ≥ 1 `VERIFIED` → lấy giá trị `VERIFIED` (nhiều giá trị `VERIFIED` khác nhau → `CONFLICTING`);
  chỉ `INFERRED` → `INFERRED` (khác nhau → `CONFLICTING`); `VERIFIED` khác `INFERRED` → giá trị `VERIFIED` + cờ `THIRD_PARTY_DISAGREES` và
  trạng thái `CONFLICTING` (QA-05 – lưu mọi giá trị kèm nguồn); không có → `UNKNOWN`.
- **Rationale**: BR-02 – `VERIFIED` chỉ từ nguồn trực tiếp; quyết định bằng mã (Constitution III).

## R-05. Lưu thuộc tính bằng kho bằng chứng E0

- **Decision**: Mỗi giá trị thuộc tính là một dòng `research_evidence` (`subject_type` = `product` | `affiliate_program`, `claim_key`
  theo danh mục ở data-model §3, `value` JSONB có cấu trúc, `excerpt` = trích đoạn đã che PII chứa giá trị, `source_id`, trạng thái).
  Không có bảng thuộc tính riêng; trạng thái gộp tính khi đọc/chấm điểm từ bằng chứng `ACTIVE`.
- **Rationale**: DATA-03 (kết luận → evidence → source) có sẵn; xóa bằng chứng (E1 FR-013e, ledger) tự động áp dụng cho E2.
- **Alternatives**: Bảng `product_attributes` riêng – trùng dữ liệu, phải đồng bộ khi xóa bằng chứng.

## R-06. Đánh giá theo cặp (sản phẩm, ngách) và tính lại khi bằng chứng đổi

- **Decision**: `product_evaluations` gắn `product_niche_id`, bất biến, lưu `evidence_fingerprint` (SHA-256 của danh sách id bằng chứng
  ACTIVE đã dùng). Khi đọc danh sách/chi tiết, nếu fingerprint hiện tại khác → tính lại xác định (không AI, `computed_without_ai = true`)
  và ghi đánh giá mới. Đổi trọng số → job `products.recompute` (không AI).
- **Rationale**: xóa bằng chứng ở E1 không cần biết E2 (không sửa mã E1); điểm luôn khớp bằng chứng còn hiệu lực.

## R-07. Chấm điểm (FR-027…FR-029) – xem contracts/scoring-rubric.md

- **Decision**: 3 tiêu chí xác định hoàn toàn từ thuộc tính (hấp dẫn affiliate, khả năng tham gia, uy tín & chất lượng); 2 tiêu chí do AI
  đề xuất mức (phù hợp pain point & persona, giá phù hợp khả năng chi trả) và mã kiểm tra điều kiện dữ liệu (như E1). Ngưỡng rời rạc nằm
  trong `rubric` của phiên bản trọng số – cấu hình được.
- **Rationale**: chủ sở hữu yêu cầu chỉ chấm bằng dữ liệu có bằng chứng; mức "phù hợp" là phán đoán cần AI nhưng phải dẫn bằng chứng.

## R-08. Trùng sản phẩm (FR-015)

- **Decision**: `dedup_key` = `domain:<official_domain>` khi có; ngược lại `name:<vendor chuẩn hóa>|<tên chuẩn hóa>` (chữ thường, bỏ dấu,
  bỏ hậu tố pháp lý "inc", "llc", "ltd", bỏ ký tự không chữ-số). Unique theo `(project_id, data_origin, dedup_key)`. Một sản phẩm có tên
  miền mới khớp sản phẩm cũ theo tên → gộp (`merged_into_id`), giữ bằng chứng của cả hai. Chương trình: `dedup_key` =
  `<operator_domain>|<terms_url chuẩn hóa>`.
- **Alternatives**: so khớp mờ rapidfuzz như E1 – không cần ở MVP vì sản phẩm có định danh mạnh (tên miền).

## R-09. Theo dõi điều khoản (FR-040, Should)

- **Decision**: Job `products.terms_check` (tham số `program_id`) tải lại `terms_url` (qua `PageCollector`, robots/rate), trích lại thuộc tính,
  so sánh snapshot gộp với phiên bản gần nhất; khác → `program_terms_versions` mới + `changes` + cờ cảnh báo chưa xem. Lỗi truy cập → ghi
  `last_check_error`, không đổi thuộc tính. Lịch hằng tuần do chủ sở hữu tạo qua `/schedules` E0 (không tự tạo).

## R-10. MOCK, demo và E2E

- **Decision**: Test dùng `MockWeb` (fixture JSON + HTML tự soạn, tên miền `.example`) và AI giả lập theo kịch bản (`tests/fakes`). Lệnh
  `python -m nichepilot.jobs.products_demo_seed` (từ chối ở production, idempotent) tạo sản phẩm/chương trình `[MOCK DEMO]` cho ngách demo
  E1 qua đúng pipeline lưu/chấm điểm – phục vụ E2E và xem thử giao diện.
- **Rationale**: Constitution I – dữ liệu mock gắn `MOCK`, ẩn mặc định; SC-008 giữ `BLOCKED`.

## R-11. Không có chức năng đăng ký affiliate (FR-025, SC-002)

- **Decision**: Tool đăng ký/đăng nhập/gửi form không tồn tại; agent E2 chỉ được cấp `source.query`, `page.fetch`, `robots.fetch` (chỉ đọc,
  `external_effect = false`). Test SC-002 kiểm tra: mọi request ra ngoài trong test là GET của `page.fetch`/`robots.fetch`/`source.query`;
  `allowed_tools` của agent không chứa tool nào có `external_effect = true`.
