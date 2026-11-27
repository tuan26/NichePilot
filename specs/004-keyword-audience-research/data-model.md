# Data Model – E3 Keyword & Audience Research

Migration `0013_keywords` (bảng), `0014_keywords_seed` (trọng số v1, Model Task Profile). Quy ước E0: `id` UUID, `created_at`/`updated_at`,
FK, CHECK, `data_origin ∈ {REAL, MOCK}`. Không sửa bảng E0/E1/E2.

## 1. Bảng dùng lại (chỉ đọc trừ `research_*`)

`niches`, `pain_points`, `buyer_personas` (E1); `products`, `product_niches`, `affiliate_programs`, `product_programs` (E2); `research_sources`,
`research_evidence` (bằng chứng trang SERP/đối thủ, subject `keyword_run`); `source_policies`, `domain_access_state`; `agent_jobs`, `audit_logs`.

## 2. Bảng mới

### `keyword_runs`
`project_id` FK, `job_id` FK agent_jobs UNIQUE, `niche_id` FK, `params` JSONB (`max_keywords` 5–200 mặc định 60, `serp_keywords` 0–30 mặc định 10,
`competitor_pages` 0–5 mặc định 3, `page_limit` 5–200 mặc định 60, `time_limit_s` 60–5400 mặc định 1800), `outcome` NULL | `COMPLETED` |
`PARTIAL_COMPLETED` | `FAILED`, `stop_reason`, `metrics` JSONB, `data_origin`.

### `keywords`
| Cột | Ràng buộc |
|---|---|
| project_id, niche_id | FK |
| text | 2–150 ký tự |
| normalized, dedup_key | UNIQUE (`project_id`, `niche_id`, `data_origin`, `dedup_key`) |
| language | `^[a-z]{2}$` |
| market | `^[A-Z]{2}$` |
| keyword_type | `PROBLEM`, `SOLUTION`, `PRODUCT`, `COMPARISON`, `INFORMATIONAL` |
| length_class | `HEAD`, `MID`, `LONG_TAIL` |
| intent | `INFORMATIONAL`, `COMMERCIAL_INVESTIGATION`, `TRANSACTIONAL`, `NAVIGATIONAL` |
| intent_status | `INFERRED`, `VERIFIED` (có tín hiệu SERP + bằng chứng) |
| intent_reason | TEXT |
| search_volume, cpc, keyword_difficulty | NULL = `UNKNOWN`; CHECK: khác NULL ⇒ `metrics_source`, `metrics_collected_at`, `metrics_market` khác NULL |
| metrics_source, metrics_collected_at, metrics_market | NULL |
| risk_flags | ⊆ {`BRAND_TERM`, `COMPLIANCE_SENSITIVE`} |
| cluster_id | FK keyword_clusters NULL |
| ai_levels | JSONB (mức `fit` hợp lệ gần nhất – tính lại không AI) |
| first_run_id | FK keyword_runs |
| data_origin | |

### `keyword_origins`
`keyword_id` FK, `origin_type` `PAIN_POINT` | `PERSONA` | `PRODUCT`, `pain_point_id` FK NULL, `product_id` FK NULL, `persona_attribute` TEXT NULL
(một trong ba khớp `origin_type` – CHECK), `reason` TEXT; UNIQUE (`keyword_id`, `origin_type`, `pain_point_id`, `product_id`, `persona_attribute`).

### `keyword_clusters`
`project_id`, `niche_id` FK; `cluster_key` (UNIQUE với niche_id, data_origin) = `<origin>|<intent>`; `primary_keyword_id` FK NULL; `intent`;
`pain_point_id` FK NULL; `product_id` FK NULL; `insights` JSONB (`content_gaps`, `channels`, `persona`, `strategy`, `rejected_claims` – mỗi mục có trạng thái + evidence_ids);
`decision_status` `CANDIDATE`/`SELECTED`/`WATCH`/`REJECTED`; `decision_reason` (bắt buộc khi ≠ CANDIDATE); `decided_by`, `decided_at`;
`watch_enabled` BOOL; `data_origin`.

### `serp_observations`
`keyword_id` FK, `version` INT ≥ 1 (UNIQUE với keyword_id), `results` JSONB (mảng `{position, url, domain, title, page_type}`), `source_policy_id`
FK NULL, `collected_at`, `changes` JSONB, `acknowledged_at` NULL, `job_id` FK NULL, `data_origin`.

### `competitor_pages`
`keyword_id` FK, `url`, `domain`, `evidence_id` FK research_evidence (trích đoạn ≤ 1000 ký tự), `summary` JSONB (`headings` ≤ 10, `topics`,
`has_comparison`, `has_pricing`, `has_experience_evidence`, `covered_pain_point_ids`), `data_origin`; UNIQUE (`keyword_id`, `url`).

### `keyword_scoring_weights`
`version` UNIQUE, `weights` (5 khóa tổng 100), `rubric` JSONB, `coverage_min` (mặc định 60), `confidence_params`, `templates` JSONB (mẫu keyword
commercial, từ khóa tuyên bố trải nghiệm), `is_active` (đúng 1).

### `keyword_evaluations` (bất biến – trigger)
`keyword_id` FK, `weights_version_id` FK, `opportunity_score` NULL/0–100, `confidence_score` 0–100, `coverage` 0–100, `scoring_status` `SCORED` |
`INSUFFICIENT_SCORING_DATA` (SCORED ⇔ opportunity khác NULL), `criteria` JSONB, `confidence_components` JSONB, `missing` TEXT[],
`evidence_fingerprint`, `computed_without_ai`, `run_id` NULL, `data_origin`.

## 3. Trạng thái

- Quyết định cluster: `CANDIDATE → SELECTED | WATCH | REJECTED`, lý do bắt buộc, audit `keyword.cluster_decision`.
- SERP: phiên bản tăng dần; phiên bản mới chỉ khi kết quả đổi (`changes` ≠ ∅) hoặc lần đầu.

## 4. Audit

`keyword.run_created`, `keyword.cluster_decision`, `keyword.weights_created`, `keyword.watch_changed`, `keyword.serp_acknowledged`.
