# Data Model: E1 – Autonomous Niche Discovery

**Ngày**: 2026-11-19, cập nhật 2026-11-20 (quyết định A1/I2 của chủ sở hữu) | Liên quan: [spec.md](./spec.md),
[research.md](./research.md), E0 `specs/001-foundation-ai-infrastructure/data-model.md`

Quy ước chung (giữ như E0 – DATA-01, DATA-02, DATA-06): khóa chính UUID, `created_at`/`updated_at` (timestamptz, NOT NULL), khóa ngoại
và unique rõ ràng; mọi bảng nghiệp vụ có `project_id` (FK projects, NOT NULL, project mặc định); bảng chứa kết quả AI/nghiên cứu có
`data_origin` TEXT NOT NULL ∈ {`REAL`, `MOCK`}; mọi thay đổi qua migration (`0009_discovery`, `0010_discovery_seed`). Tên bảng/cột tiếng
Anh. Cột không ghi "NULL được" là NOT NULL.

Cách trích dẫn trong tasks.md: `data-model.md <bảng>.<cột>`.

## 1. Mở rộng bảng E0 (X2 – đã duyệt 2026-11-20)

### `research_sources` – thêm cột

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| `registered_domain` | TEXT, NULL được (nguồn E0 cũ) | eTLD+1 chữ thường, dùng cho tính độc lập (R-06) |
| `simhash` | BIGINT, NULL được (nguồn E0 cũ) | SimHash 64-bit của nội dung chuẩn hóa |
| `lifecycle_status` | TEXT | `ACTIVE` \| `ERASED`, mặc định `ACTIVE` |
| `erased_at` | timestamptz, NULL được | CHECK `(lifecycle_status = 'ERASED') = (erased_at IS NOT NULL)`; khi `ERASED`, `url`/`canonical_url` = `erased:<sha256>` |
| `source_policy_id` | UUID, NULL được (nguồn E0 cũ) | FK `source_policies`; nguồn thu thập bởi E1 bắt buộc có |
| `policy_verified_at` | DATE, NULL được (nguồn E0 cũ) | snapshot `source_policies.verified_at` tại thời điểm thu thập (truy vết căn cứ `ALLOWED`) |

### `research_evidence` – thêm cột

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| `redaction_status` | TEXT, NULL được (bằng chứng E0 cũ) | `REDACTED` \| `NEEDS_REVIEW`; E1 không bao giờ lưu nội dung chưa che (FR-012a) |
| `redaction_counts` | JSONB, NULL được | khóa ⊆ {`EMAIL`, `PHONE`, `USER`, `PERSON`}, giá trị số nguyên ≥ 0; không chứa nội dung |
| `pii_engine` | TEXT, NULL được | tên + phiên bản `PiiEngine` đã che (ví dụ `regex-phone/1`) |
| `lifecycle_status` | TEXT | `ACTIVE` \| `ERASED`, mặc định `ACTIVE`; CHECK `lifecycle_status <> 'ERASED' OR (excerpt IS NULL AND value IS NULL)` |
| `erased_at` | timestamptz, NULL được | CHECK `(lifecycle_status = 'ERASED') = (erased_at IS NOT NULL)` |
| `content_hash` | TEXT, NULL được | SHA-256 (hex 64 ký tự) của trích đoạn đã che; giữ sau khi xóa để không thu thập lại |

Ràng buộc E0 giữ nguyên (VERIFIED ⇒ có nguồn; UNKNOWN ⇒ value NULL; `excerpt` ≤ 1000 ký tự). `EvidenceService.query` lọc mặc định
`lifecycle_status = ACTIVE` (X3).

## 2. Bảng mới của E1

### `scoring_weights_versions`

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| `version` | INT | UNIQUE, ≥ 1, tăng dần |
| `weights` | JSONB | đúng 6 khóa `problem_severity`, `monetization`, `market_gap`, `reachability`, `competition_opportunity`, `demand_stability`; mỗi giá trị số 0–100; tổng = 100 (service + CHECK) |
| `coverage_threshold` | NUMERIC(5,2) | 0 < x ≤ 100, mặc định 60 |
| `evidence_rules` | JSONB | khóa `min_items` (int ≥ 1, mặc định 2), `min_independent_groups` (int ≥ 1, mặc định 2), `min_relevance` (0–1, 0,6), `min_quality` (0–1, 0,5), `simhash_max_distance` (0–64, 3) |
| `confidence_params` | JSONB | trọng số `N,Q,D,F,K,V` (mỗi 0–1, tổng = 1; mặc định 0,25/0,20/0,15/0,15/0,15/0,10), `freshness_days` (int > 0, 730), `insufficient_cap` (0–100, 30), `formula_version` (int ≥ 1, 1) |
| `dedup_params` | JSONB | `duplicate` (0–1, 0,85), `possible` (0–1, 0,60, < duplicate), `w_problem` + `w_customer` = 1 (0,6/0,4) |
| `is_active` | BOOLEAN | đúng một bản ghi `true` (partial unique index) |
| `created_by` | UUID, NULL được (seed) | FK users |

Seed v1 = BR-03. Phiên bản mới có audit `scoring.weights_version_created`; không sửa phiên bản cũ.

### `source_policies` (FR-006c…FR-006g, research R-13)

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| `source_key` | TEXT | UNIQUE, `^[a-z0-9_:.-]{2,64}$` |
| `display_name` | TEXT | 1–120 ký tự |
| `adapter_type` | TEXT | `searxng_engine` \| `http_json_api` \| `open_dataset` \| `licensed_data` |
| `config` | JSONB | validate theo schema của `adapter_type` (internal-interfaces §1); gồm chính sách truy cập riêng `rate_limit_per_minute` (int ≥ 1), `max_retries` (0–5), `timeout_s` (1–60); **không chứa credential** – khóa bị cấm liệt kê ở internal-interfaces §1.1; xác thực chỉ qua `auth_env_var` (`^[A-Z][A-Z0-9_]{2,63}$`, tên biến môi trường) |
| `tos_url` | TEXT | URL `https://`, 1–2000 ký tự |
| `verified_at` | DATE, NULL được | không ở tương lai |
| `verified_by` | UUID, NULL được | FK users |
| `verification_note` | TEXT, NULL được | 10–2000 ký tự (trích đoạn + vị trí) |
| `allowed_access_methods` | TEXT[] | phần tử ⊆ {`SEARXNG_ENGINE`, `OFFICIAL_API`, `DATASET_DOWNLOAD`}, mặc định rỗng |
| `permitted_use_scope` | TEXT, NULL được | 10–1000 ký tự |
| `known_limits` | TEXT, NULL được | ≤ 1000 ký tự |
| `compliance_status` | TEXT | `ALLOWED` \| `UNVERIFIED` \| `PROHIBITED`, mặc định `UNVERIFIED` |
| `enabled` | BOOLEAN | mặc định false; CHECK `NOT enabled OR compliance_status = 'ALLOWED'` |
| `updated_by` | UUID, NULL được (seed) | FK users |

CHECK `compliance_status <> 'ALLOWED' OR (verified_at IS NOT NULL AND verified_by IS NOT NULL AND verification_note IS NOT NULL AND
cardinality(allowed_access_methods) > 0 AND permitted_use_scope IS NOT NULL)`. CHECK `compliance_status <> 'PROHIBITED' OR (verified_at IS
NOT NULL AND verification_note IS NOT NULL)`. Đổi `compliance_status` khỏi `ALLOWED` → `enabled` đặt `false` trong cùng transaction.
Không có đường mã nào đặt `ALLOWED` hay `enabled = true` ngoài API của chủ sở hữu (audit `source.updated` trước/sau). Seed: nguồn S1–S11
([source-verification.md](./source-verification.md)), `UNVERIFIED`, `enabled = false`.

### `discovery_runs`

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| `job_id` | UUID | FK agent_jobs, UNIQUE (tạo idempotent – kể cả lượt theo lịch, FR-029/FR-033) |
| `market` | TEXT | `^[A-Z]{2}$` |
| `research_language` | TEXT | BCP-47 ngắn `^[a-z]{2}(-[A-Z]{2})?$` |
| `seed_topic` | TEXT, NULL được | ≤ 200 ký tự; NULL = không chọn lĩnh vực |
| `max_candidates` | INT | 1–50, mặc định 20 |
| `budget_usd` | NUMERIC(14,6) | > 0, mặc định 2; ≤ hạn mức ngày còn lại (kiểm tra lúc tạo) |
| `time_limit_s` | INT | 300–14400, mặc định 5400 |
| `page_limit` | INT | 10–2000, mặc định 300 |
| `per_domain_interval_s` | NUMERIC(6,2) | ≥ 1, mặc định 2 (mức trần) |
| `trigger` | TEXT | `MANUAL` \| `SCHEDULE` \| `RETRY` – sao chép từ `agent_jobs.trigger` của E0 (`JOB_TRIGGERS`) |
| `source_policy_ids` | UUID[] | nguồn `ALLOWED` ∧ `enabled` được chốt lúc bắt đầu lượt; rỗng ⇒ `stop_reason = NO_COMPLIANT_SEARCH_SOURCE` |
| `weights_version_id` | UUID | FK scoring_weights_versions (chốt lúc bắt đầu) |
| `source_mode` | TEXT | `REAL` \| `MOCK` |
| `outcome` | TEXT, NULL được | NULL khi chưa kết thúc; `COMPLETED` \| `PARTIAL_COMPLETED` |
| `stop_reason` | TEXT, NULL được | `ALL_CANDIDATES_SUFFICIENT` \| `CANDIDATES_EXHAUSTED` \| `TIME_LIMIT_REACHED` \| `PAGE_LIMIT_REACHED` \| `NO_COMPLIANT_SEARCH_SOURCE` \| `SOURCES_UNAVAILABLE` \| `CANCELLED` |
| `metrics` | JSONB | khóa FR-032: `pages_attempted`, `pages_succeeded`, `pages_failed`, `pages_skipped`, `skipped_by_reason`, `needs_review_segments`, `elapsed_active_s`, `independent_sources`, `candidates`, `evidence_sufficient`, `insufficient_evidence`, `insufficient_scoring_data`, `ai_calls`, `cost_real_usd`, `cost_mock_usd` (số ≥ 0) |
| `idempotency_key` | TEXT, NULL được | UNIQUE khi khác NULL, ≤ 128 ký tự |

### `niches`

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| `name` | TEXT | 1–200 ký tự |
| `micro_niche` | TEXT | 1–200 ký tự |
| `country` | TEXT | `^[A-Z]{2}$` |
| `customer_group` | TEXT | 1–300 ký tự, dạng chuẩn hóa (INFERRED) |
| `core_problem` | TEXT | 1–500 ký tự, dạng chuẩn hóa (INFERRED) |
| `dedup_key` | TEXT | chuẩn hóa; UNIQUE (`project_id`, `data_origin`, `dedup_key`) WHERE `merged_into_id IS NULL` |
| `evidence_status` | TEXT | `EVIDENCE_SUFFICIENT` \| `INSUFFICIENT_EVIDENCE` |
| `decision_status` | TEXT | `CANDIDATE` \| `WATCH` \| `PURSUE` \| `REJECTED` \| `HIDDEN`, mặc định `CANDIDATE` |
| `ai_recommendation` | TEXT | `PURSUE` \| `REJECT` \| `UNKNOWN` |
| `ai_recommendation_reason` | TEXT, NULL được | ≤ 2000 ký tự |
| `owner_decision_reason` | TEXT, NULL được | ≤ 2000 ký tự |
| `decided_by` | UUID, NULL được | FK users; NOT NULL khi `decision_status <> 'CANDIDATE'` |
| `monetization_status` | TEXT | `SIGNALS_FOUND` \| `MONETIZATION_UNVERIFIED` \| `NO_AFFILIATE_FOUND` |
| `risk_flags` | TEXT[] | phần tử ⊆ {`MONETIZATION_RISK`, `COMPLIANCE_SENSITIVE`, `LOW_EVIDENCE_FRESHNESS`} |
| `merged_into_id` | UUID, NULL được | FK niches, ≠ id |
| `latest_evaluation_id` | UUID, NULL được | FK niche_evaluations |

### `niche_run_links`

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| `niche_id`, `run_id` | UUID | FK; UNIQUE(niche_id, run_id) |
| `role` | TEXT | `DISCOVERED` \| `REEVALUATED` |

### `niche_similarity`

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| `niche_a_id`, `niche_b_id` | UUID | FK niches; CHECK `niche_a_id < niche_b_id`; UNIQUE cặp |
| `score` | NUMERIC(4,3) | 0–1 |
| `status` | TEXT | `POSSIBLE` \| `CONFIRMED_DUPLICATE` \| `NOT_DUPLICATE`, mặc định `POSSIBLE` |
| `resolved_by` | UUID, NULL được | FK users; NOT NULL khi `status <> 'POSSIBLE'` |

### `niche_evaluations` (bất biến)

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| `niche_id` | UUID | FK niches |
| `run_id` | UUID, NULL được | FK discovery_runs (NULL khi tính lại không gắn lượt) |
| `weights_version_id` | UUID | FK scoring_weights_versions |
| `criteria` | JSONB | đúng 6 khóa như `weights`; mỗi khóa `{score ∈ {0,25,50,75,100} \| null, status ∈ {VERIFIED, INFERRED, UNKNOWN, CONFLICTING}, reason, evidence_ids[]}`; `score = null` ⇔ status ∈ {UNKNOWN, CONFLICTING} |
| `coverage` | NUMERIC(5,2) | 0–100 |
| `scoring_status` | TEXT | `SCORED` \| `INSUFFICIENT_SCORING_DATA` |
| `opportunity_score` | NUMERIC(5,2), NULL được | 0–100; CHECK `(opportunity_score IS NULL) = (scoring_status = 'INSUFFICIENT_SCORING_DATA')` |
| `confidence_score` | NUMERIC(5,2) | 0–100 |
| `confidence_components` | JSONB | khóa `N,Q,D,F,K,V` (0–1) + tham số đã dùng |
| `evidence_status` | TEXT | `EVIDENCE_SUFFICIENT` \| `INSUFFICIENT_EVIDENCE` (tại thời điểm chấm) |
| `independent_groups` | INT | ≥ 0 |
| `computed_without_ai` | BOOLEAN | |

UPDATE/DELETE bị chặn bằng trigger (bất biến).

### `niche_findings` – trường BR-07 dạng văn bản

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| `niche_id` | UUID | FK; UNIQUE(niche_id, field) |
| `field` | TEXT | `CURRENT_SOLUTIONS` \| `MARKET_GAPS` \| `POTENTIAL_PRODUCTS` \| `MONETIZATION` \| `CHANNELS` \| `RISKS` |
| `value` | JSONB, NULL được | NULL ⇔ `verification_status = 'UNKNOWN'` |
| `verification_status` | TEXT | `VERIFIED` \| `INFERRED` \| `UNKNOWN` \| `CONFLICTING` |
| `evidence_ids` | UUID[] | `VERIFIED` ⇒ ≥ 1 phần tử |

### `pain_points`

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| `niche_id` | UUID | FK; UNIQUE(niche_id, normalized_title) |
| `title` | TEXT | 1–200 ký tự |
| `normalized_title` | TEXT | chữ thường, bỏ dấu câu |
| `severity` | SMALLINT, NULL được | 1–5; NULL khi UNKNOWN |
| `evidence_count` | INT | ≥ 0 |
| `verification_status` | TEXT | `VERIFIED` \| `INFERRED` \| `UNKNOWN` \| `CONFLICTING` |

### `buyer_personas` – một bản ghi mỗi ngách

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| `niche_id` | UUID | FK, UNIQUE |
| `attributes` | JSONB | đúng 5 khóa `segment`, `context`, `goals`, `obstacles`, `ability_to_pay`; mỗi khóa `{value \| null, status ∈ {VERIFIED, INFERRED, UNKNOWN, CONFLICTING}, evidence_ids[]}` |

### `competitors`

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| `niche_id` | UUID | FK; UNIQUE(niche_id, normalized_name) |
| `name` | TEXT | 1–200 ký tự |
| `kind` | TEXT | `PRODUCT` \| `SERVICE` \| `MANUAL_WORKAROUND` |
| `url` | TEXT, NULL được | URL http(s) |
| `strengths`, `weaknesses` | JSONB | mảng `{text, status, evidence_ids[]}` |

### `niche_evidence_links`

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| `niche_id`, `evidence_id` | UUID | FK; UNIQUE cặp |
| `purpose` | TEXT | `PAIN_POINT` \| `PERSONA` \| `SOLUTION` \| `COMPETITOR` \| `MONETIZATION` \| `CHANNEL` |
| `pain_point_id` | UUID, NULL được | FK pain_points; NOT NULL ⇔ `purpose = 'PAIN_POINT'` |
| `relevance` | NUMERIC(3,2), NULL được | 0–1 (AI, INFERRED) |
| `quality` | NUMERIC(3,2), NULL được | 0–1 (AI, INFERRED) |
| `copy_suspected` | BOOLEAN | mặc định false |
| `independence_group` | TEXT | mã tính (registered_domain + cụm SimHash) |
| `counted_for_threshold` | BOOLEAN | mã tính |

### `domain_access_state`

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| `domain` | TEXT | PK, chữ thường |
| `last_request_at` | timestamptz, NULL được | |
| `min_interval_s` | NUMERIC(8,2) | ≥ 1 |
| `robots_status` | TEXT | `OK` \| `NOT_FOUND` \| `UNREACHABLE` \| `PENDING` |
| `robots_fetched_at` | timestamptz, NULL được | cache 24 h |
| `robots_rules` | TEXT, NULL được | nội dung robots.txt cần cho luật (≤ 64 KB), chỉ khi `robots_status = OK` |
| `crawl_delay_s` | NUMERIC(8,2), NULL được | ≥ 0 |
| `blocked_until` | timestamptz, NULL được | |
| `block_reason` | TEXT, NULL được | `RATE_LIMITED` \| `ACCESS_RESTRICTED` \| `ROBOTS_UNREACHABLE` |

### `page_fetch_log`

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| `run_id` | UUID | FK discovery_runs |
| `url_hash` | TEXT | SHA-256 hex; UNIQUE(run_id, url_hash) |
| `domain` | TEXT | chữ thường |
| `outcome` | TEXT | `SUCCESS` \| `FAILED` \| `SKIPPED` |
| `reason` | TEXT, NULL được | `ROBOTS_DISALLOWED` \| `RATE_LIMITED` \| `ACCESS_RESTRICTED` \| `HTTP_ERROR` \| `TIMEOUT` \| `NETWORK_ERROR` \| `NON_HTML` \| `TOO_LARGE` \| `PII_UNSAFE` \| `PAGE_LIMIT` \| `TIME_LIMIT` \| `ERASED_CONTENT`; NOT NULL khi `outcome <> 'SUCCESS'` |
| `http_status` | SMALLINT, NULL được | 100–599 |
| `source_id` | UUID, NULL được | FK research_sources; NOT NULL ⇔ `outcome = 'SUCCESS'` |

Chỉ lưu hash URL + tên miền (URL đầy đủ nằm ở `research_sources` khi thành công).

### `evidence_erasure_requests`

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| `target_type` | TEXT | `EVIDENCE` \| `SOURCE` |
| `target_id` | UUID | |
| `content_hash` | TEXT, NULL được | SHA-256 hex |
| `reason` | TEXT | 3–500 ký tự, không chứa trích đoạn |
| `requested_by` | UUID | FK users |
| `applied_at` | timestamptz, NULL được | |
| `ledger_seq` | BIGINT | UNIQUE, ≥ 1 |

### `erasure_ledger_state` (một dòng – X4)

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| `id` | SMALLINT | PK, CHECK `id = 1` |
| `ledger_id` | UUID, NULL được | NULL chỉ trước lần khởi tạo sổ đầu tiên |
| `applied_seq` | BIGINT | ≥ 0 |
| `applied_hash` | TEXT, NULL được | SHA-256 hex của dòng sổ cuối đã áp dụng |
| `status` | TEXT | `OK` \| `BLOCKED` |
| `last_error` | TEXT, NULL được | ≤ 500 ký tự, không chứa nội dung bằng chứng |

`status = BLOCKED` hoặc lệch đuôi sổ → API E1 trả 503 `ERASURE_LEDGER_NOT_APPLIED`, agent E1 dừng ở bước đầu (không đổi Job Runtime E0).

## 3. Trạng thái

- `niches.evidence_status`: `INSUFFICIENT_EVIDENCE` ⇄ `EVIDENCE_SUFFICIENT` (chỉ qua đánh giá/tính lại; xóa bằng chứng có thể đưa về
  `INSUFFICIENT_EVIDENCE`).
- `niches.decision_status`: `CANDIDATE` → `WATCH` \| `PURSUE` \| `REJECTED` \| `HIDDEN` (chủ sở hữu, audit; quay lại `CANDIDATE` được).
- `source_policies.compliance_status`: `UNVERIFIED` → `ALLOWED` \| `PROHIBITED` (chỉ chủ sở hữu, đủ căn cứ); `ALLOWED` → `UNVERIFIED` \|
  `PROHIBITED` (tắt nguồn ngay).
- `discovery_runs.outcome`: NULL → `COMPLETED` \| `PARTIAL_COMPLETED` khi job E0 `SUCCEEDED`; job `FAILED`/`CANCELLED` → outcome NULL,
  `stop_reason` ghi lý do. State machine job E0 không đổi.

## 4. Quy tắc dữ liệu tổng hợp

1. Chỉ trích đoạn đã che PII được ghi; `NEEDS_REVIEW` không tính vào ngưỡng/điểm và không gửi AI.
2. Bằng chứng `ERASED` không được dùng ở bất kỳ phân tích nào; mọi truy vấn mặc định lọc `ACTIVE`; agent không giữ trích đoạn qua các bước.
3. Chỉ nguồn `ALLOWED` ∧ `enabled` được dùng trong mọi lượt (thủ công hay theo lịch). `UNVERIFIED`, `PROHIBITED` không bao giờ được dùng.
4. Bảng xếp hạng cơ hội: `evidence_status = EVIDENCE_SUFFICIENT` ∧ `scoring_status = SCORED` ∧ `data_origin = REAL` (mặc định); danh sách
   ưu tiên affiliate: thêm `monetization_status = SIGNALS_FOUND` ∧ không cờ `MONETIZATION_RISK`.
5. Mọi đánh giá lưu đủ dữ liệu để tính lại bằng tay.
6. `MOCK` nếu bất kỳ đầu vào AI hoặc nguồn nào của bản ghi là mock; `MOCK` không vào báo cáo/xếp hạng mặc định.
