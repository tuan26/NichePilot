# Data Model – E4 Bilingual Dashboard

**Không có bảng/migration mới.** E4 chỉ đọc bảng E0–E3 và ghi qua API sẵn có (settings, project, budget, jobs, schedules, quyết định E1–E3).

## View chỉ đọc (DTO)

### Overview (`GET /api/v1/dashboard/overview`)
| Trường | Nguồn |
|---|---|
| `niches.total`, `niches.by_evidence_status`, `niches.by_decision` | `niches` (merged_into_id IS NULL, lọc MOCK) |
| `products.total`, `products.ready_to_promote` | `product_niches` ⨝ `products` (chưa gộp) |
| `keywords.total`, `keywords.clusters`, `keywords.long_tail` | `keywords`, `keyword_clusters` |
| `jobs.by_status`, `jobs.failed_7d` | `agent_jobs` (lọc theo `data_origin` khi ẩn MOCK) |
| `top_niches[]` (≤ 5): `niche_id`, `name`, `opportunity_score`, `confidence_score`, `data_origin` | `niches` ⨝ `niche_evaluations` mới nhất |
| `include_mock`, `generated_at` | – |

### NicheResearchRow (`GET /api/v1/dashboard/niches`)
`niche_id`, `name`, `country`, `evidence_status`, `decision_status`, `eligible` (quy tắc E2), `opportunity_score`, `confidence_score`,
`products {has_run, total, ready_to_promote}`, `keywords {has_run, total, clusters, long_tail, best_cluster {cluster_id, name,
opportunity_score, confidence_score} | null}`, `data_origin`.
