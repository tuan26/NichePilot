# Data Model – E2 Product & Affiliate Discovery

Migration: `0011_products` (bảng), `0012_products_seed` (trọng số v1, Model Task Profile cho task type E2). Mọi bảng có `id` UUID,
`created_at`, `updated_at` (E0 `UUIDPkMixin` + `TimestampMixin`), FK và ràng buộc CHECK; `data_origin ∈ {REAL, MOCK}`. Không sửa bảng E0/E1.

## 1. Bảng dùng lại (không đổi cấu trúc)

| Bảng | Dùng cho E2 |
|---|---|
| `niches`, `pain_points`, `buyer_personas` (E1) | Đầu vào; chỉ đọc. Ngách đủ điều kiện: `evidence_status = 'EVIDENCE_SUFFICIENT'` ∧ `decision_status ∈ {CANDIDATE, WATCH, PURSUE}` ∧ `merged_into_id IS NULL` (CANDIDATE = chưa có quyết định; `REJECTED`, `HIDDEN` bị từ chối) |
| `research_sources`, `research_evidence` (E0/E1) | Trang đã tải và **mọi giá trị thuộc tính** (R-05) |
| `source_policies`, `domain_access_state`, `erasure_ledger_state` (E1) | Tuân thủ nguồn, robots/tốc độ, cổng xóa bằng chứng |
| `agent_jobs`, `job_steps`, `tool_calls`, `ai_usage_logs`, `audit_logs`, `job_schedules` (E0) | Job, chi phí, audit, lịch |

## 2. Bảng mới

### `product_runs` – lượt tìm sản phẩm (FR-002, FR-003, FR-038)

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| project_id | UUID FK projects | |
| job_id | UUID FK agent_jobs | UNIQUE (idempotent theo job) |
| niche_id | UUID FK niches | |
| params | JSONB | `max_products` (1–20, mặc định 10), `page_limit` (mặc định 60), `time_limit_s` (mặc định 1800), `per_domain_interval_s` (mặc định 2) |
| outcome | TEXT NULL | `COMPLETED`, `PARTIAL_COMPLETED`, `FAILED` |
| stop_reason | TEXT NULL | vd. `NO_COMPLIANT_SEARCH_SOURCE`, `NO_PRODUCTS_FOUND`, `PAGE_LIMIT_REACHED`, `TIME_LIMIT_REACHED`, `PRODUCTS_EXHAUSTED` |
| metrics | JSONB | `ai_calls`, `cost_real_usd`, `cost_mock_usd`, `pages_attempted/succeeded/failed/skipped`, `skipped_by_reason`, `products_found`, `programs_by_status`, `needs_review_segments`, `elapsed_active_s`, `rejected_values` |
| data_origin | TEXT | REAL/MOCK |

### `products` – sản phẩm dùng chung trong project (FR-011…FR-016)

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| project_id | UUID FK | |
| name | TEXT | 1–200 ký tự |
| normalized_name | TEXT | |
| vendor | TEXT NULL | |
| official_domain | TEXT NULL | chữ thường, eTLD+1; NULL = `UNKNOWN` |
| official_url | TEXT NULL | |
| dedup_key | TEXT | UNIQUE (`project_id`, `data_origin`, `dedup_key`) – R-08 |
| category | TEXT NULL | `PHYSICAL`, `SOFTWARE`, `DIGITAL`, `UNKNOWN` |
| risk_flags | TEXT[] | ⊆ {`COMPLIANCE_SENSITIVE`} |
| merged_into_id | UUID NULL FK products | ≠ id |
| data_origin | TEXT | |

### `product_niches` – cặp (sản phẩm, ngách) (FR-026, FR-029a, FR-033)

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| product_id | UUID FK products | UNIQUE (`product_id`, `niche_id`) |
| niche_id | UUID FK niches | |
| first_run_id | UUID FK product_runs | |
| readiness_status | TEXT | `READY_TO_PROMOTE`, `ELIGIBILITY_UNVERIFIED`, `NOT_ELIGIBLE`, `AFFILIATE_UNVERIFIED`, `NO_PROGRAM`, `PROGRAM_CLOSED` (mặc định `NO_PROGRAM`) |
| risk_flags | TEXT[] | ⊆ {`MONETIZATION_RISK`, `MARKET_NOT_ALLOWED`, `MARKET_UNKNOWN`, `COMPLIANCE_SENSITIVE`} |
| persona_match | TEXT | `MATCH`, `PARTIAL`, `NO_MATCH`, `UNKNOWN` |
| ai_recommendation | TEXT | `SELECT`, `REJECT`, `UNKNOWN` |
| ai_recommendation_reason | TEXT NULL | |
| decision_status | TEXT | `CANDIDATE`, `SELECTED`, `WATCH`, `REJECTED` |
| decision_reason | TEXT NULL | bắt buộc khi ≠ CANDIDATE |
| decided_by / decided_at | UUID FK users / TIMESTAMPTZ NULL | |
| data_origin | TEXT | |

### `product_pain_point_links` (FR-011)

`product_niche_id` FK, `pain_point_id` FK pain_points, `evidence_id` FK research_evidence, `verification_status` (`VERIFIED`/`INFERRED`);
UNIQUE (`product_niche_id`, `pain_point_id`, `evidence_id`).

### `affiliate_programs` (FR-017…FR-024)

| Cột | Kiểu | Ràng buộc |
|---|---|---|
| project_id | UUID FK | |
| name | TEXT | |
| operator_type | TEXT | `VENDOR`, `NETWORK`, `UNKNOWN` |
| operator_name | TEXT NULL | |
| operator_domain | TEXT NULL | eTLD+1, chữ thường |
| terms_url | TEXT NULL | |
| dedup_key | TEXT | UNIQUE (`project_id`, `data_origin`, `dedup_key`) |
| verification_status | TEXT | `VERIFIED`, `PARTIAL`, `UNVERIFIED`, `CLOSED` (tính bằng mã, FR-018) |
| watch_enabled | BOOL | mặc định false (FR-040) |
| last_checked_at | TIMESTAMPTZ NULL | |
| last_check_error | TEXT NULL | |
| data_origin | TEXT | |

### `product_programs`

`product_id` FK, `program_id` FK; UNIQUE (`product_id`, `program_id`).

### `program_terms_versions` (FR-040)

`program_id` FK, `version` INT (UNIQUE với program_id), `snapshot` JSONB (thuộc tính gộp: giá trị + trạng thái + evidence_ids),
`changes` JSONB (danh sách `{claim_key, old, new}`), `checked_at`, `job_id` FK NULL, `acknowledged_at` NULL, `data_origin`.

### `product_scoring_weights` (FR-027, FR-028)

`version` INT UNIQUE, `weights` JSONB (5 tiêu chí, tổng 100), `rubric` JSONB (ngưỡng mức – scoring-rubric §2), `coverage_min` NUMERIC
(mặc định 60), `confidence_params` JSONB, `query_templates` JSONB, `non_official_domains` TEXT[], `is_active` BOOL (đúng 1 dòng
active – partial unique index), `created_by` UUID NULL.

### `product_evaluations` – bất biến (FR-027…FR-029, FR-029a)

| Cột | Kiểu | Ghi chú |
|---|---|---|
| product_niche_id | UUID FK | |
| weights_version_id | UUID FK product_scoring_weights | |
| opportunity_score | NUMERIC(5,2) NULL | NULL khi `INSUFFICIENT_SCORING_DATA` |
| confidence_score | NUMERIC(5,2) | |
| coverage | NUMERIC(5,2) | 0–100 |
| scoring_status | TEXT | `SCORED`, `INSUFFICIENT_SCORING_DATA` |
| criteria | JSONB | mỗi tiêu chí: `level` (0/25/50/75/100/null), `status`, `reason`, `evidence_ids`, `inputs` |
| confidence_components | JSONB | |
| missing | TEXT[] | khóa thuộc tính/tiêu chí còn `UNKNOWN` |
| evidence_fingerprint | TEXT | SHA-256 danh sách id bằng chứng ACTIVE đã dùng (R-06) |
| computed_without_ai | BOOL | |
| run_id | UUID FK product_runs NULL | |
| data_origin | TEXT | |

## 3. Danh mục `claim_key` (giá trị trong `research_evidence.value`)

| subject_type | claim_key | value (JSON) |
|---|---|---|
| `product_run` | `page_excerpt` | NULL (chỉ trích đoạn) |
| `product` | `official_website` | `{"url": str}` |
| `product` | `price` | `{"plan": str, "amount": number, "currency": "USD", "period": "one_time\|month\|year\|other", "promo": bool}` |
| `product` | `feature` | `{"text": str}` |
| `product` | `target_customer` | `{"text": str}` |
| `product` | `third_party_mention` | `{"sentiment": "positive\|neutral\|negative"}` (luôn `INFERRED`) |
| `affiliate_program` | `commission` | `{"kind": "percent\|fixed\|tiered\|per_category\|recurring", "value": number?, "min": number?, "max": number?, "up_to": bool, "currency": str?, "recurring_months": int?, "conditions": str?}` |
| `affiliate_program` | `cookie_days` | `{"days": int}` hoặc `{"session": true}` |
| `affiliate_program` | `payment` | `{"methods": [str], "min_payout": number?, "currency": str?, "schedule": str?}` |
| `affiliate_program` | `vn_eligibility` | `{"status": "ALLOWED\|NOT_ALLOWED"}` (im lặng → không có bằng chứng → `UNKNOWN`) |
| `affiliate_program` | `promotion_regions` | `{"global": bool, "include": [ISO2], "exclude": [ISO2]}` |
| `affiliate_program` | `ad_restrictions` | `{"codes": [NO_BRAND_BIDDING\|NO_COUPON_SITES\|NO_PPC\|NO_EMAIL\|NO_SOCIAL_ADS\|OTHER], "other": str?}` |
| `affiliate_program` | `program_status` | `{"status": "OPEN\|CLOSED"}` |

Trạng thái gộp (`VERIFIED`/`INFERRED`/`CONFLICTING`/`UNKNOWN`) tính khi đọc bằng `attributes.resolve` (research R-04) từ bằng chứng `ACTIVE`.

## 4. Trạng thái và chuyển đổi

- **Chương trình** (FR-018, tính lại mỗi lần lưu thuộc tính): `program_status` CLOSED có bằng chứng → `CLOSED`; trang điều khoản đã đọc
  (≥ 1 bằng chứng từ `operator_domain`) và `commission` hoặc `cookie_days` `VERIFIED` → `VERIFIED`; có ≥ 1 thuộc tính `VERIFIED`/`INFERRED`
  → `PARTIAL`; còn lại `UNVERIFIED`.
- **Sẵn sàng affiliate** của cặp (FR-026): xem scoring-rubric §4.
- **Quyết định**: `CANDIDATE → SELECTED | WATCH | REJECTED` và giữa các trạng thái đó; lý do bắt buộc; audit `product.decision`.
- **Lượt**: theo state machine job của E0; `product_runs.outcome` ghi khi finalize.

## 5. Audit (FR-037)

`product.run_created`, `product.decision`, `product.weights_created`, `program.watch_changed`, `program.terms_acknowledged`.
