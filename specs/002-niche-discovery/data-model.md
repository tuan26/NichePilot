# Data Model: E1 – Autonomous Niche Discovery

**Ngày**: 2026-11-19 | Liên quan: [spec.md](./spec.md), [research.md](./research.md), E0 `specs/001-foundation-ai-infrastructure/data-model.md`

Quy ước chung (giữ như E0 – DATA-01, DATA-02, DATA-06): khóa chính UUID, `created_at`/`updated_at`, khóa ngoại và unique rõ ràng;
mọi bảng nghiệp vụ có `project_id` (project mặc định); bảng chứa kết quả AI/nghiên cứu có `data_origin ∈ {REAL, MOCK}`; mọi thay đổi
qua migration (dự kiến `0009_discovery`, `0010_discovery_seed`, và `0009` gồm cả phần mở rộng bảng E0 ở §1). Tên bảng/cột tiếng Anh.

## 1. Mở rộng bảng E0 (CẦN CHỦ SỞ HỮU DUYỆT – thay đổi schema của E0)

### `research_sources` (E0 §14) – thêm cột

| Cột | Kiểu | Ràng buộc / Ghi chú |
|---|---|---|
| `registered_domain` | TEXT | eTLD+1 (ví dụ `example.co.uk`); dùng cho tính độc lập (R-06) |
| `simhash` | BIGINT | SimHash 64-bit của nội dung chuẩn hóa; NULL cho nguồn cũ |
| `lifecycle_status` | TEXT | `ACTIVE` \| `ERASED`, mặc định `ACTIVE` |
| `erased_at` | timestamptz | NOT NULL ⇔ `ERASED`; khi `ERASED`, `url`/`canonical_url` thay bằng `erased:<sha256>` |

### `research_evidence` (E0 §14) – thêm cột

| Cột | Kiểu | Ràng buộc / Ghi chú |
|---|---|---|
| `redaction_status` | TEXT | `REDACTED` \| `NEEDS_REVIEW` (E1 không bao giờ lưu nội dung chưa che – FR-012a) |
| `redaction_counts` | JSONB | số thay thế theo loại `{"EMAIL":1,"PHONE":0,"USER":2,"PERSON":1}`; không chứa nội dung |
| `lifecycle_status` | TEXT | `ACTIVE` \| `ERASED`; CHECK `ERASED ⇒ excerpt IS NULL AND value IS NULL` |
| `erased_at` | timestamptz | NOT NULL ⇔ `ERASED` |
| `content_hash` | TEXT | SHA-256 trích đoạn đã che, giữ sau khi xóa để không thu thập lại |

Các ràng buộc E0 giữ nguyên (VERIFIED ⇒ có nguồn; UNKNOWN ⇒ value NULL; excerpt ≤ 1000 ký tự). `EvidenceService.query` của E0 bổ
sung lọc mặc định `lifecycle_status = ACTIVE` (mở rộng interface, không đổi hành vi hiện có cho dữ liệu cũ).

## 2. Bảng mới của E1

### `scoring_weights_versions`

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| id | UUID | PK |
| version | INT | UNIQUE, ≥ 1 |
| weights | JSONB | 6 khóa: `problem_severity`, `monetization`, `market_gap`, `reachability`, `competition_opportunity`, `demand_stability`; mỗi giá trị 0–100 (đơn vị %), tổng = 100 (kiểm tra ở service + CHECK) |
| coverage_threshold | NUMERIC(5,2) | mặc định 60, 0 < x ≤ 100 |
| evidence_rules | JSONB | `{"min_items":2,"min_independent_groups":2,"min_relevance":0.6,"min_quality":0.5,"simhash_max_distance":3}` |
| confidence_params | JSONB | trọng số N/Q/D/F/K/V, `freshness_days` 730, `insufficient_cap` 30, `formula_version` 1 |
| dedup_params | JSONB | `{"duplicate":0.85,"possible":0.60,"w_problem":0.6,"w_customer":0.4}` |
| is_active | BOOLEAN | đúng một phiên bản active (partial unique index) |
| created_by | UUID | FK users, NULL cho seed |
| created_at | timestamptz | |

Seed v1 = BR-03 (25/20/20/15/10/10). Tạo phiên bản mới có audit `scoring.weights_version_created`; không sửa phiên bản cũ.

### `search_source_policies` (FR-006c…FR-006f)

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| id | UUID | PK |
| engine_key | TEXT | UNIQUE (tên engine SearXNG hoặc `api:<tên>`) |
| display_name | TEXT | |
| integration_method | TEXT | `SEARXNG_ENGINE` \| `OFFICIAL_API` |
| tos_url | TEXT | NOT NULL |
| verified_at | DATE | NULL khi `UNVERIFIED` chưa đọc được |
| verification_note | TEXT | trích đoạn/kết luận ngắn, người xác minh |
| compliance_status | TEXT | `ALLOWED` \| `UNVERIFIED` \| `PROHIBITED` |
| known_limits | TEXT | giới hạn truy vấn đã biết |
| enabled | BOOLEAN | CHECK `NOT (enabled AND compliance_status = 'PROHIBITED')` |
| warning_acknowledged_at | timestamptz | NOT NULL khi bật nguồn `UNVERIFIED` (FR-006d) |
| updated_by | UUID | FK users |

Seed: các nguồn ở research R-01, tất cả `UNVERIFIED`, `enabled = false`.

### `discovery_runs`

| Cột | Kiểu | Ràng buộc / Ghi chú |
|---|---|---|
| id | UUID | PK |
| project_id | UUID | FK projects |
| job_id | UUID | FK agent_jobs, UNIQUE |
| market | TEXT | `^[A-Z]{2}$` |
| research_language | TEXT | |
| seed_topic | TEXT | NULL = không chọn lĩnh vực |
| max_candidates | INT | 1–50, mặc định 20 |
| budget_usd | NUMERIC(14,6) | > 0, mặc định 2, ≤ hạn mức ngày (kiểm tra lúc tạo) |
| time_limit_s | INT | mặc định 5400 |
| page_limit | INT | mặc định 300 |
| per_domain_interval_s | NUMERIC | mặc định 2, ≥ 1 (mức trần) |
| weights_version_id | UUID | FK scoring_weights_versions (chốt lúc bắt đầu) |
| source_mode | TEXT | `REAL` \| `MOCK` (adapter nguồn) |
| outcome | TEXT | NULL khi chưa kết thúc; `COMPLETED` \| `PARTIAL_COMPLETED` |
| stop_reason | TEXT | `ALL_CANDIDATES_SUFFICIENT`, `CANDIDATES_EXHAUSTED`, `TIME_LIMIT_REACHED`, `PAGE_LIMIT_REACHED`, `NO_COMPLIANT_SEARCH_SOURCE`, `SOURCES_UNAVAILABLE`, `CANCELLED` |
| metrics | JSONB | FR-032: pages_attempted/succeeded/failed/skipped (+ theo lý do), elapsed_active_s, independent_sources, candidates, sufficient, insufficient, insufficient_scoring, ai_calls, cost_real_usd, cost_mock_usd |
| data_origin | TEXT | `MOCK` nếu nguồn hoặc AI là mock |
| idempotency_key | TEXT | UNIQUE (cùng cơ chế job E0) |

### `niches`

| Cột | Kiểu | Ràng buộc / Ghi chú |
|---|---|---|
| id | UUID | PK |
| project_id | UUID | FK |
| name, micro_niche | TEXT | |
| country | TEXT | `^[A-Z]{2}$` |
| customer_group, core_problem | TEXT | dạng chuẩn hóa (INFERRED) dùng cho dedup |
| dedup_key | TEXT | chuỗi chuẩn hóa; index |
| evidence_status | TEXT | `EVIDENCE_SUFFICIENT` \| `INSUFFICIENT_EVIDENCE` |
| decision_status | TEXT | `CANDIDATE` \| `WATCH` \| `PURSUE` \| `REJECTED` \| `HIDDEN` |
| ai_recommendation | TEXT | `PURSUE` \| `REJECT` \| `UNKNOWN` + `ai_recommendation_reason` |
| owner_decision_reason, decided_by, decided_at | | audit `niche.decision_recorded` |
| monetization_status | TEXT | `SIGNALS_FOUND` \| `MONETIZATION_UNVERIFIED` \| `NO_AFFILIATE_FOUND` (cờ rủi ro BR-06) |
| risk_flags | TEXT[] | `MONETIZATION_RISK`, `COMPLIANCE_SENSITIVE`, … |
| merged_into_id | UUID | FK niches (trùng chắc chắn) |
| latest_evaluation_id | UUID | FK niche_evaluations |
| data_origin | TEXT | |

UNIQUE (`project_id`, `data_origin`, `dedup_key`) cho ngách chưa gộp – bảo đảm chạy lại không tạo trùng (FR-029).

### `niche_run_links` – (`niche_id`, `run_id`, `role` = `DISCOVERED`\|`REEVALUATED`) UNIQUE(niche_id, run_id)

### `niche_similarity` – cặp có thể tương đồng

(`niche_a_id` < `niche_b_id`, `score`, `status` = `POSSIBLE`\|`CONFIRMED_DUPLICATE`\|`NOT_DUPLICATE`, `resolved_by`, `resolved_at`)
UNIQUE(niche_a_id, niche_b_id).

### `niche_evaluations` (bất biến – mỗi lần chấm một bản ghi)

| Cột | Kiểu | Ghi chú |
|---|---|---|
| id, niche_id, run_id | UUID | run_id NULL khi chấm lại thủ công |
| weights_version_id | UUID | FK |
| criteria | JSONB | 6 khóa → `{score: 0–100 \| null, status: VERIFIED\|INFERRED\|UNKNOWN\|CONFLICTING, reason, evidence_ids[]}` |
| coverage | NUMERIC(5,2) | Σ trọng số gốc tiêu chí hợp lệ |
| scoring_status | TEXT | `SCORED` \| `INSUFFICIENT_SCORING_DATA` |
| opportunity_score | NUMERIC(5,2) | NULL ⇔ `INSUFFICIENT_SCORING_DATA` (CHECK) |
| confidence_score | NUMERIC(5,2) | 0–100 |
| confidence_components | JSONB | N, Q, D, F, K, V + tham số |
| evidence_status | TEXT | trạng thái ngưỡng tại thời điểm chấm |
| independent_groups | INT | |
| computed_without_ai | BOOLEAN | true khi chấm lại theo phiên bản trọng số mới / sau xóa |
| data_origin | TEXT | |

### `niche_findings` – các trường BR-07 dạng văn bản

(`niche_id`, `field` ∈ {`CURRENT_SOLUTIONS`, `MARKET_GAPS`, `POTENTIAL_PRODUCTS`, `MONETIZATION`, `CHANNELS`, `RISKS`}, `value`
JSONB NULL khi UNKNOWN, `verification_status`, `evidence_ids` UUID[], `data_origin`) UNIQUE(niche_id, field).

### `pain_points`

(`id`, `niche_id`, `title`, `description`, `severity` 1–5, `severity_reason`, `evidence_count`, `verification_status`, `data_origin`)
UNIQUE(niche_id, normalized_title).

### `buyer_personas` – một bản ghi mỗi ngách

`attributes` JSONB: `segment`, `context`, `goals`, `obstacles`, `ability_to_pay` → mỗi khóa `{value|null, status, evidence_ids[]}`.

### `competitors`

(`id`, `niche_id`, `name`, `kind` = `PRODUCT`\|`SERVICE`\|`MANUAL_WORKAROUND`, `url`, `strengths`/`weaknesses` JSONB có status,
`data_origin`) UNIQUE(niche_id, normalized_name).

### `niche_evidence_links` – bằng chứng được dùng cho ngách

| Cột | Ghi chú |
|---|---|
| niche_id, evidence_id | UNIQUE cặp |
| purpose | `PAIN_POINT` \| `PERSONA` \| `SOLUTION` \| `COMPETITOR` \| `MONETIZATION` \| `CHANNEL` |
| pain_point_id | NULL nếu không phải pain point |
| relevance, quality | 0–1, do AI đánh giá (INFERRED) + `assessment_reason` |
| copy_suspected | BOOLEAN (AI) |
| independence_group | TEXT (mã tính: registered_domain + cụm SimHash) |
| counted_for_threshold | BOOLEAN (mã tính) |

### `domain_access_state` – trạng thái truy cập theo tên miền (FR-030a)

(`domain` PK, `last_request_at`, `min_interval_s`, `robots_fetched_at`, `robots_status` = `OK`\|`NOT_FOUND`\|`UNREACHABLE`,
`crawl_delay_s`, `blocked_until`, `block_reason`). Không lưu nội dung robots.txt ngoài các luật cần thiết.

### `page_fetch_log` – nhật ký truy cập trang (FR-032, Q6 quy tắc dữ liệu)

(`id`, `run_id`, `url_hash`, `domain`, `attempted_at`, `outcome` = `SUCCESS`\|`FAILED`\|`SKIPPED`, `reason`
(`ROBOTS_DISALLOWED`, `RATE_LIMITED`, `ACCESS_RESTRICTED`, `HTTP_ERROR`, `TIMEOUT`, `PII_UNSAFE`, `PAGE_LIMIT`…), `http_status`,
`source_id`) UNIQUE(run_id, url_hash) → tiếp tục/chạy lại không thu thập lại trang đã có. Chỉ lưu hash URL + tên miền (URL đầy
đủ nằm ở `research_sources` khi thành công).

### `evidence_erasure_requests` (FR-013e, FR-013f)

(`id`, `target_type` = `EVIDENCE`\|`SOURCE`, `target_id`, `content_hash`, `reason`, `requested_by`, `requested_at`, `applied_at`,
`ledger_seq`) – không có nội dung. Đồng bộ với sổ ngoài DB (volume `erasure-ledger`, research R-09).

## 3. Trạng thái

- `niches.evidence_status`: `INSUFFICIENT_EVIDENCE` ⇄ `EVIDENCE_SUFFICIENT` (chỉ đổi qua lần đánh giá/tính lại; xóa bằng chứng có thể
  đưa về `INSUFFICIENT_EVIDENCE`).
- `niches.decision_status`: `CANDIDATE` → `WATCH` \| `PURSUE` \| `REJECTED` \| `HIDDEN` (chủ sở hữu; mọi chuyển có audit; quay lại
  `CANDIDATE` được phép).
- `discovery_runs.outcome`: NULL → `COMPLETED` \| `PARTIAL_COMPLETED` khi job E0 kết thúc `SUCCEEDED`; job `FAILED`/`CANCELLED` →
  outcome NULL, `stop_reason` ghi lý do. Vòng đời job theo state machine E0, không thay đổi.

## 4. Quy tắc dữ liệu tổng hợp

1. Chỉ trích đoạn đã che PII được ghi; `NEEDS_REVIEW` không tính vào ngưỡng/điểm.
2. Bằng chứng `ERASED` không được dùng ở bất kỳ phân tích nào; mọi truy vấn mặc định lọc `ACTIVE`.
3. Bảng xếp hạng cơ hội: `evidence_status = EVIDENCE_SUFFICIENT` ∧ `scoring_status = SCORED` ∧ `data_origin = REAL` (mặc định);
   danh sách ưu tiên affiliate: thêm `monetization_status = SIGNALS_FOUND` ∧ không cờ `MONETIZATION_RISK`.
4. Mọi đánh giá lưu đủ dữ liệu để tính lại bằng tay (trọng số, Coverage, điểm thành phần, tham số Confidence).
5. `MOCK` nếu bất kỳ đầu vào AI hoặc nguồn nào của bản ghi là mock; dữ liệu `MOCK` không vào báo cáo/xếp hạng mặc định.
