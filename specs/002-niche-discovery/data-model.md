# Data Model: E1 – Autonomous Niche Discovery

**Ngày**: 2026-11-19, cập nhật 2026-11-20 | Liên quan: [spec.md](./spec.md), [research.md](./research.md), E0 `specs/001-foundation-ai-infrastructure/data-model.md`

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
| `source_policy_id` | UUID | FK `source_policies`, NULL cho nguồn E0/không qua adapter E1 |
| `source_compliance` | TEXT | trạng thái của nguồn **tại thời điểm thu thập**: `ALLOWED` \| `UNVERIFIED` (FR-006d, SC-017) |

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

### `source_policies` (FR-006c…FR-006g, research R-13)

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| id | UUID | PK |
| source_key | TEXT | UNIQUE, `^[a-z0-9_:.-]{2,64}$` |
| display_name | TEXT | |
| adapter_type | TEXT | `searxng_engine` \| `http_json_api` \| `open_dataset` \| `licensed_data` |
| config | JSONB | cấu hình adapter **không chứa secret** (validate theo schema của `adapter_type`); xác thực chỉ qua `auth_env_var` = tên biến môi trường |
| tos_url | TEXT | NOT NULL |
| verified_at | DATE | |
| verified_by | UUID | FK users |
| verification_note | TEXT | căn cứ (trích đoạn ≤ 1000 ký tự + vị trí) |
| allowed_access_methods | TEXT[] | ⊆ {`SEARXNG_ENGINE`, `OFFICIAL_API`, `DATASET_DOWNLOAD`} |
| permitted_use_scope | TEXT | phạm vi sử dụng được phép |
| known_limits | TEXT | |
| compliance_status | TEXT | `ALLOWED` \| `UNVERIFIED` \| `PROHIBITED`, mặc định `UNVERIFIED` |
| enabled | BOOLEAN | mặc định false; CHECK `NOT (enabled AND compliance_status = 'PROHIBITED')` |
| warning_acknowledged_at | timestamptz | CHECK `NOT (enabled AND compliance_status = 'UNVERIFIED' AND warning_acknowledged_at IS NULL)` |
| updated_by, updated_at | | audit `source.created` / `source.updated` (trước/sau) |

CHECK `compliance_status <> 'ALLOWED' OR (verified_at IS NOT NULL AND verification_note IS NOT NULL AND cardinality(allowed_access_methods) > 0
AND permitted_use_scope IS NOT NULL)`. Không có cột/route nào cho phép hệ thống tự đổi `compliance_status` hay `enabled` (chỉ API của
chủ sở hữu). Seed (`0010_discovery_seed`): các nguồn S1–S11 của [source-verification.md](./source-verification.md), tất cả `UNVERIFIED`,
`enabled = false`.

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
| trigger | TEXT | `MANUAL` \| `SCHEDULED` |
| include_unverified_sources | BOOLEAN | mặc định false; CHECK `NOT (include_unverified_sources AND trigger = 'SCHEDULED')` (FR-006d) |
| source_policy_ids | UUID[] | nguồn được chốt lúc bắt đầu lượt |
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
`ledger_seq` UNIQUE) – không có nội dung. Sổ chuẩn nằm ngoài DB (volume `erasure-ledger`, research R-09).

### `erasure_ledger_state` (một dòng – X4)

(`id` = 1 CHECK, `ledger_id` UUID, `applied_seq` BIGINT, `applied_hash` TEXT, `status` = `OK`\|`BLOCKED`, `checked_at`, `last_error`
TEXT không chứa nội dung). `status = BLOCKED` hoặc lệch với đuôi sổ → API trả 503 `ERASURE_LEDGER_NOT_APPLIED` cho dữ liệu E1, worker
không nhận job E1.

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
5. Lượt `SCHEDULED` chỉ dùng nguồn `ALLOWED`; bằng chứng từ nguồn `UNVERIFIED` giữ `source_compliance = UNVERIFIED` và được hiển thị rõ.
6. `MOCK` nếu bất kỳ đầu vào AI hoặc nguồn nào của bản ghi là mock; dữ liệu `MOCK` không vào báo cáo/xếp hạng mặc định.
