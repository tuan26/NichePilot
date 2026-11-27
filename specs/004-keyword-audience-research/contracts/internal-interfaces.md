# Internal Interfaces – E3

## 1. Module `nichepilot.modules.keywords` (lớp modules)

Import được: `modules.evidence`, `modules.audit`, `modules.settings`, API công khai chỉ đọc của `modules.discovery` (model `Niche`,
`PainPoint`, `BuyerPersona`, `risk`, `fingerprint`, `sources.policy.SourcePolicyService`) và của `modules.products` (model `Product`,
`ProductNiche`, `ProductPainPointLink`, `eligibility.check_niche_eligible`, `attributes.resolve`). E3 **không ghi** bảng E1/E2 (TC_E3_FR002_02).
Hợp đồng import-linter mới: `modules.discovery`, `modules.products` và module E0 **không** import `modules.keywords`.

| File | Trách nhiệm |
|---|---|
| `models.py` | ORM bảng data-model §2 |
| `schemas.py` | Đầu ra AI (`extra="forbid"`, không trường chỉ số), DTO API, `KeywordRunParams` |
| `normalize.py` | `normalize(text)`, `dedup_key(text)`, `length_class(text)` (R-03, R-04) |
| `generation.py` | `inputs_for_niche(session, niche_id)` → pain point/persona/sản phẩm hợp lệ; `validate_generated(out, inputs)` kiểm origin + danh mục; `commercial_templates(products, templates)` (R-03) |
| `serp.py` | `page_type(url, title)`; `diff_results(old, new)` (R-05, R-09) |
| `analysis.py` | `validate_page_summary(out, pain_point_ids, evidence_ids)`; `content_gaps(pain_point_ids, pages)`; `channels(results)` (R-06) |
| `clustering.py` | `cluster_key(keyword, origins)`, gán cluster + keyword chính (Clarification (b)) |
| `scoring/criteria.py` | 5 hàm mức tiêu chí (rubric §2) |
| `scoring/opportunity.py`, `scoring/confidence.py` | rubric §3 – độc lập |
| `weights.py` | đọc/tạo phiên bản `keyword_scoring_weights` |
| `evaluation.py` | `evaluate_keyword(session, keyword_id, *, ai_levels=None)` – nơi duy nhất ghi `keyword_evaluations`; `stale_keywords(...)` (batch); `cluster_scores(...)` |
| `strategy.py` | `validate_strategy(out, allowed_evidence, templates)` – lọc tuyên bố trải nghiệm (R-08) |
| `store.py` | upsert keyword/origin/cluster/SERP/competitor page (idempotent) |
| `service.py` | tạo lượt, danh sách, chi tiết, quyết định, tóm tắt, watch, acknowledge |
| `report.py` | báo cáo JSON/Markdown VI/EN (FR-026) |

## 2. Agent và job type (lớp jobs)

| job_type | Agent | paid | Task type AI | Tool cho phép |
|---|---|---|---|---|
| `keywords.run` | `KeywordResearchAgent` (`jobs/agents/keyword_research.py`) | true | `keywords.generate`, `keywords.analyze`, `keywords.strategy` | `source.query`, `page.fetch`, `robots.fetch` |
| `keywords.serp_check` | `SerpCheckAgent` (`jobs/agents/serp_check.py`) | false (không AI) | – | `source.query` |
| `keywords.recompute` | `KeywordRecomputeAgent` | false | – | – |

AgentDefinition: `keywords.run` max_steps 200, max_ai_calls 40, timeout_s 5400, token_budget 1 000 000; `keywords.serp_check` max_steps 10,
max_ai_calls 1, token_budget 1, timeout_s 600; `keywords.recompute` max_steps 50, max_ai_calls 1, token_budget 1 (ràng buộc E0 ≥ 1 – không gọi
AI). `acceptance`: có `run_id`, `outcome ∈ {COMPLETED, PARTIAL_COMPLETED}`, có `stop_reason`.

### Bước `keywords.run` (checkpoint theo `seq`; state chỉ ID/URL/bộ đếm)

1. **preflight** – cổng ledger; `check_niche_eligible` (E2); `ensure_run` idempotent theo `job_id`.
2. **generate** – `inputs_for_niche`; AI `keywords.generate` (≤ 2 lời gọi, mỗi lần ≤ 30 keyword) → `validate_generated`; cộng keyword mẫu
   commercial (không AI) → upsert keyword + origin (≤ `max_keywords`, ưu tiên LONG_TAIL khi cắt).
3. **pre_score** – `evaluate_keyword` (chưa SERP) → chọn ≤ `serp_keywords` keyword điểm cao nhất.
4. **serp** – không có nguồn `ALLOWED` usable → ghi `stop_reason = NO_COMPLIANT_SEARCH_SOURCE` và nhảy 7 (không lỗi). Ngược lại `source.query`
   cho từng keyword → `serp_observations` (phiên bản 1 hoặc mới khi đổi) → URL đối thủ (≤ `competitor_pages`) vào hàng đợi.
5. **fetch** – `PageCollector` (E2), subject `keyword_run`.
6. **analyze** – AI `keywords.analyze` (≤ 4 trang/prompt, `<untrusted_content>`) → `validate_page_summary` → `competitor_pages`.
7. **cluster_evaluate** (không AI) – gán cluster, `evaluate_keyword` cho mọi keyword, content gap + kênh vào `insights`.
8. **strategy** – AI `keywords.strategy` cho ≤ 5 cluster có Opportunity cao nhất → `validate_strategy` → `insights.persona/strategy`.
9. **finalize** – outcome, stop_reason, metrics (FR-030).

Giới hạn thời gian/trang → nhảy 7–9 với dữ liệu có. Hết ngân sách → `PAUSED_BUDGET` (E0).

## 3. Schema đầu ra AI (rút gọn – `schemas.py` là chuẩn)

- `KeywordsGenerateOutput`: `keywords[]` { `text`, `keyword_type`, `intent`, `intent_reason`, `origins[]` {`origin_type`, `pain_point_id?`,
  `product_id?`, `persona_attribute?`, `reason`}, `fit` {`level`, `reason`, `evidence_ids`} } – không có volume/CPC/KD.
- `KeywordsAnalyzeOutput`: `pages[]` { `url`, `headings[]` (≤ 10), `topics[]`, `has_comparison`, `has_pricing`, `has_experience_evidence`,
  `covered_pain_point_ids[]`, `evidence_ids[]` }.
- `KeywordsStrategyOutput`: `clusters[]` { `cluster_id`, `persona` {`goals`, `barriers`, `knowledge_level`, `typical_questions` – mỗi mục
  {`value`, `evidence_ids`} hoặc null}, `strategy` {`content_type` ∈ {GUIDE, COMPARISON, REVIEW, LIST, FAQ}, `angle`, `pain_point_ids`,
  `product_ids`, `primary_keyword_id`, `secondary_keyword_ids`, `gap_refs`} }.

## 4. Mã lỗi mới

`KEYWORD_RUN_ACTIVE`, `KEYWORD_RUN_NOT_FOUND`, `KEYWORD_CLUSTER_NOT_FOUND`, `KEYWORD_WEIGHTS_INVALID`. Dùng lại: `NICHE_NOT_FOUND`,
`NICHE_NOT_ELIGIBLE` (E2), `BUDGET_NOT_CONFIGURED`, `ERASURE_LEDGER_NOT_APPLIED`, `VALIDATION_ERROR`.

## 5. Lệnh dev/test

`python -m nichepilot.jobs.keywords_demo_seed` – từ chối khi `APP_ENV=production` (thoát 2); idempotent; cần ngách demo E1 + sản phẩm demo E2
→ tạo keyword/cluster `[MOCK DEMO]` qua `store` + `evaluation` (không AI, không mạng).
