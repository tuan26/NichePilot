# Internal Interfaces – E2

## 1. Module `nichepilot.modules.products` (lớp modules)

Được import: `modules.evidence` (EvidenceService), `modules.audit`, `modules.settings`, và **API công khai chỉ đọc** của
`modules.discovery` (`fingerprint`, `risk`, `access.DomainAccessService`, `sources.policy.SourcePolicyService`, model đọc `Niche`,
`PainPoint`, `BuyerPersona`). Model ORM E1 (`Niche`, `PainPoint`, `BuyerPersona`) là interface công khai **chỉ đọc** cho E2 – E2 không bao giờ ghi bảng E1
(kiểm bởi TC_E2_FR034_01). Hợp đồng import-linter mới: `modules.discovery` và module E0 **không** import `modules.products`.

| File | Trách nhiệm |
|---|---|
| `models.py` | ORM bảng data-model §2 |
| `schemas.py` | Pydantic: đầu ra AI (schema bắt buộc, `extra="forbid"`), DTO API, `ProductRunParams`, `ProductRunResult` |
| `eligibility.py` | `check_niche_eligible(session, niche_id) -> None` – raise `NICHE_NOT_ELIGIBLE` (lý do: `INSUFFICIENT_EVIDENCE`, `REJECTED`, `HIDDEN`, `MERGED`) |
| `queries.py` | `build_queries(niche, pain_points, persona, templates)` → truy vấn xác định (R-02) |
| `extraction.py` | `validate_extract(out, allowed_evidence, excerpts)`: kiểm id, kiểm số xuất hiện trong trích đoạn (R-03), danh mục mã; trả bản đã lọc + `rejected_values` |
| `attributes.py` | `verification_for(source_domain, official_domain/operator_domain)`; `resolve(evidence_rows) -> ResolvedAttribute` (R-04) |
| `programs.py` | `program_status(resolved)`, `best_program(programs)`, `terms_snapshot`, `diff_snapshots` |
| `readiness.py` | `readiness(best_program_attrs, country) -> (status, flags)` (rubric §4) |
| `scoring/criteria.py` | 5 hàm mức tiêu chí (rubric §2) |
| `scoring/opportunity.py`, `scoring/confidence.py` | Opportunity/Coverage; Confidence (rubric §3) – không phụ thuộc lẫn nhau |
| `weights.py` | đọc/tạo phiên bản `product_scoring_weights` (tổng 100, 5 khóa) |
| `dedup.py` | `product_dedup_key`, `program_dedup_key`, upsert/gộp (R-08) |
| `evaluation.py` | `evaluate_pair(session, product_niche_id, *, ai_levels=None) -> Evaluation` – **nơi duy nhất** ghi `product_evaluations`; tự lấy mức AI gần nhất khi tính lại; bỏ qua khi trùng đánh giá trước |
| `service.py` | tạo lượt (kiểm ngân sách/nguồn như E1), danh sách, chi tiết, quyết định, tóm tắt ngách, watch, acknowledge |
| `report.py` | báo cáo JSON/Markdown VI/EN (FR-032) |

## 2. Agent và job type (lớp jobs)

| job_type | Agent | paid | Task type AI | Tool cho phép |
|---|---|---|---|---|
| `products.run` | `ProductDiscoveryAgent` (`jobs/agents/product_discovery.py`) | true | `products.extract`, `products.program_extract`, `products.assess` | `source.query`, `page.fetch`, `robots.fetch` |
| `products.terms_check` | `ProgramTermsCheckAgent` (`jobs/agents/program_terms_check.py`) | true | `products.program_extract` | `page.fetch`, `robots.fetch` |
| `products.recompute` | `ProductRecomputeAgent` | false | – | – |

Khai báo AgentDefinition (Constitution V): `products.run` max_steps 160, max_ai_calls 60, timeout_s 5400, token_budget 1 200 000;
`products.terms_check` max_steps 20, max_ai_calls 3, timeout_s 900, token_budget 150 000; `products.recompute` max_steps 50, 0 AI.
`acceptance`: có `run_id`, `outcome ∈ {COMPLETED, PARTIAL_COMPLETED}`, có `stop_reason`.

### Bước `products.run` (checkpoint theo `seq`, state chỉ chứa ID/URL/bộ đếm)

1. **preflight** – cổng ledger; `check_niche_eligible`; `ensure_run` (idempotent theo `job_id`); không có nguồn `ALLOWED` → finalize
   `PARTIAL_COMPLETED / NO_COMPLIANT_SEARCH_SOURCE` (0 lời gọi AI).
2. **search_products** – truy vấn R-02 qua mọi nguồn usable → hàng đợi URL.
3. **fetch** – `PageCollector` (lô 5): robots → rate → `page.fetch` → lưu nguồn + trích đoạn `subject_type = product_run`.
4. **extract_products** – AI `products.extract` (≤ 12 trích đoạn/prompt, bọc `<untrusted_content>`) → `validate_extract` → upsert sản phẩm,
   cặp, liên kết pain point, thuộc tính; tối đa `max_products`. 0 sản phẩm hợp lệ → finalize `COMPLETED / NO_PRODUCTS_FOUND` + cờ ngách.
5. **search_details** (theo sản phẩm) – truy vấn "pricing", "affiliate program" → hàng đợi; **fetch** lại.
6. **extract_programs** (theo sản phẩm) – AI `products.program_extract` → thuộc tính sản phẩm bổ sung + chương trình + thuộc tính chương
   trình; trạng thái xác minh theo tên miền (R-04).
7. **assess** (theo cặp) – AI `products.assess`: `fit`, `price_fit` (mức + lý do + evidence_ids), `persona_match`, `third_party_mentions`,
   khuyến nghị.
8. **evaluate** (không AI) – dedup/gộp, `program_status`, `readiness`, `evaluate_pair`, khuyến nghị theo rubric §5.
9. **finalize** – outcome, stop_reason, metrics.

Giới hạn thời gian/trang → nhảy tới 8–9 với dữ liệu đã có. Hết ngân sách → `PAUSED_BUDGET` của E0.

## 3. `PageCollector` (`jobs/agents/_collector.py`)

```python
class PageCollector:
    async def collect(self, ctx, state, *, run_project_id, run_origin, subject_type, subject_id, batch=5) -> CollectStats
```
Thứ tự kiểm tra giống `NicheDiscoveryAgent._fetch` (E1): giới hạn trang/thời gian → đã tải trong lượt → `DomainAccessService.permit`
(+ `robots.fetch`) → chờ/hoãn theo tên miền → `page.fetch` → bỏ nội dung đã xóa (`erased_among`) → `EvidenceService.add_source` +
`add_evidence` (`VERIFIED`, `REDACTED`, ≤ 1000 ký tự, chống trùng theo `content_hash`). Bỏ URL hồ sơ cá nhân (`PROFILE_URL_RE`).

## 4. Schema đầu ra AI (rút gọn – `schemas.py` là chuẩn)

- `ProductsExtractOutput`: `products[]` { `name`, `vendor?`, `official_url?`, `category`, `pain_point_links[]` {`pain_point_id`,
  `evidence_ids`}, `prices[]` {`plan`, `amount`, `currency`, `period`, `promo`, `evidence_ids`}, `features[]` {`text`, `evidence_ids`},
  `target_customer?` {`text`, `evidence_ids`} }.
- `ProgramExtractOutput`: `product_attributes` (như trên), `programs[]` { `name`, `operator_type`, `operator_name?`, `terms_url?`,
  `commission?`, `cookie?`, `payment?`, `vn_eligibility?`, `promotion_regions?`, `ad_restrictions?`, `program_status?` – mỗi mục có
  `evidence_ids` }.
- `AssessOutput`: `fit` {level, reason, evidence_ids}, `price_fit` {…}, `persona_match`, `third_party_mentions[]` {evidence_id,
  sentiment}, `recommendation` {SELECT|REJECT|UNKNOWN, reason}.

## 5. Mã lỗi mới

`NICHE_NOT_ELIGIBLE`, `PRODUCT_RUN_ACTIVE`, `PRODUCT_RUN_NOT_FOUND`, `PRODUCT_NOT_FOUND`, `PROGRAM_NOT_FOUND`, `PRODUCT_WEIGHTS_INVALID`
(thêm vào `core/errors.py` + bản dịch VI/EN của frontend). Dùng lại: `NICHE_NOT_FOUND`, `NO_COMPLIANT_SEARCH_SOURCE`,
`BUDGET_NOT_CONFIGURED`, `ERASURE_LEDGER_NOT_APPLIED`, `VALIDATION_ERROR`.

## 6. Lệnh dev/test

`python -m nichepilot.jobs.products_demo_seed` – từ chối khi `APP_ENV=production` (thoát mã 2); idempotent; cần ngách demo E1
(`discovery_demo_seed`) – tạo 2 sản phẩm + 2 chương trình `[MOCK DEMO]` (một `READY_TO_PROMOTE`, một `ELIGIBILITY_UNVERIFIED`) qua
`EvidenceService` + `evaluation.evaluate_pair`.
