# Research – E3 Keyword & Audience Research (Phase 0)

Ngày 2026-11-27. Không có `NEEDS CLARIFICATION`. Tái sử dụng hạ tầng E0/E1/E2; **không** thêm dependency, service, loại nguồn hay API trả phí.

## R-01. Nguồn keyword: nội bộ trước, SERP qua nguồn `ALLOWED`

- **Decision**: Keyword được AI (`keywords.generate`) đề xuất **chỉ từ dữ liệu nội bộ đã có bằng chứng**: pain point, persona, giải pháp hiện tại
  (E1) và sản phẩm E2 (không `REJECTED`). Mỗi keyword phải dẫn `origin` (id pain point / khóa persona / id sản phẩm) – mã kiểm tra origin tồn
  tại thuộc ngách; không có origin hợp lệ → loại. SERP lấy bằng tool `source.query` qua nguồn `ALLOWED` (như E1/E2).
- **Rationale**: FR-005 (keyword xuất phát từ ngách), BR-05/FR-009 (không chỉ số bịa); không cần API keyword trả phí (chủ sở hữu 2026-11-27).
- **Alternatives**: Keyword planner/DataForSEO – cần API key/chi phí, ngoài phạm vi (FR-032 Later).

## R-02. Chỉ số keyword luôn `UNKNOWN` trong E3

- **Decision**: Cột `search_volume`, `cpc`, `keyword_difficulty` NULL; ràng buộc DB: có giá trị ⇒ bắt buộc `metrics_source`, `metrics_collected_at`,
  `metrics_market`. Schema đầu ra AI **không có** trường chỉ số (`extra="forbid"` → AI trả thêm số liệu thì cả đầu ra bị loại).
- **Rationale**: FR-009, SC-002 – không có đường ghi chỉ số không nguồn.

## R-03. Loại và độ dài keyword do mã tính

- **Decision**: Độ dài theo số từ (sau chuẩn hóa): 1–2 `HEAD`, 3 `MID`, ≥ 4 `LONG_TAIL`. Loại do AI đề xuất trong danh mục cố định; `PRODUCT`/
  `COMPARISON` bắt buộc origin sản phẩm. Keyword commercial cho sản phẩm sinh thêm bằng **mẫu xác định** (`best {product} for {segment}`,
  `{product} review`, `{product} alternatives`, `{product} vs {other}`, `{product} pricing`) – đảm bảo SC-003 không phụ thuộc AI.
- **Cờ**: `BRAND_TERM` khi keyword chứa tên sản phẩm có chương trình với `ad_restrictions` gồm `NO_BRAND_BIDDING` (E2);
  `COMPLIANCE_SENSITIVE` theo `discovery.risk`.

## R-04. Chuẩn hóa & gộp trùng

- **Decision**: `normalized` = chữ thường, bỏ dấu, bỏ ký tự không chữ-số, số nhiều đơn giản (bỏ hậu tố `s`/`es` ở từ ≥ 4 ký tự), sắp xếp token
  → `dedup_key`; UNIQUE (`project_id`, `niche_id`, `data_origin`, `dedup_key`). Gộp origin của bản trùng.

## R-05. SERP và trang đối thủ

- **Decision**: Phân tích SERP cho ≤ `serp_keywords` (mặc định 10) keyword có điểm sơ bộ cao nhất (điểm khi chưa có SERP). Mỗi SERP: kết quả
  (vị trí quan sát, URL, tên miền, tiêu đề, loại trang theo heuristic `discovery.scoring.confidence.source_kind` mở rộng: forum, qa, video, review,
  article, product, other). Trang đối thủ (≤ 3/SERP, bỏ forum/Q&A/video) tải bằng `PageCollector` của E2; AI `keywords.analyze` trả **tóm tắt cấu
  trúc** (đề mục ≤ 10, chủ đề phủ, có so sánh/giá/bằng chứng trải nghiệm) kèm `evidence_ids`; trích đoạn lưu theo giới hạn 1000 ký tự của E0.
- **Rationale**: FR-012, FR-013, BR-09.

## R-06. Content gap, kênh, cạnh tranh – mã xác định

- **Gap**: pain point gắn với cluster mà **không** nằm trong `covered_pain_point_ids` của bất kỳ trang đối thủ nào được phân tích → gap (bằng chứng =
  các trang đã xét). Không có trang đối thủ → gap `UNKNOWN`.
- **Kênh**: kết quả SERP loại `forum`/`qa`/`video` → kênh (tên miền/cộng đồng, URL bằng chứng). Không có SERP → `UNKNOWN`.
- **Cạnh tranh quan sát**: tỷ lệ kết quả "yếu" (forum, qa, trang đối thủ không phủ pain point chính) trong SERP – xem rubric §2.

## R-07. Chấm điểm (contracts/scoring-rubric.md)

- 4/5 tiêu chí xác định từ dữ liệu; `fit` do AI đề xuất mức + mã kiểm (origin tồn tại, lý do, ≥ 1 evidence_id hợp lệ – evidence của pain point/
  sản phẩm gốc). Confidence riêng. Cluster = trung bình keyword `SCORED`.

## R-08. Persona cụm & content strategy

- **Decision**: AI `keywords.strategy` cho ≤ 5 cluster ưu tiên: persona cấp cluster (mục tiêu, rào cản, mức hiểu biết, câu hỏi điển hình) mỗi
  thuộc tính có `evidence_ids` (bằng chứng pain point/SERP/trang đối thủ) hoặc `UNKNOWN`; strategy (loại nội dung trong danh mục, góc tiếp cận,
  pain point, sản phẩm, keyword chính/phụ, gap khai thác). Mã loại tuyên bố "đã dùng thử/đã test" không có bằng chứng (BR-11) – lọc theo từ khóa
  cấu hình (`tested`, `we tried`, `hands-on`…) → bỏ câu chứa, ghi `rejected_claims`.

## R-09. Theo dõi SERP (Should)

- **Decision**: Job `keywords.serp_check` (tham số `cluster_id`): chạy lại SERP cho keyword chính, so danh sách URL/loại trang với phiên bản trước,
  tạo phiên bản + `changes`; lỗi → giữ cũ. Như `products.terms_check`.

## R-10. MOCK, demo, E2E

- Fixture `tests/fixtures/keywords/` (SERP + trang đối thủ tự soạn, `.example`), AI kịch bản `tests/fakes/keywords_ai.py`; lệnh
  `python -m nichepilot.jobs.keywords_demo_seed` (từ chối production) tạo cluster `[MOCK DEMO]` cho ngách demo – phục vụ E2E.
