"""Truy vấn chỉ đọc cho dashboard E4 (research R-01…R-03; FR-006…FR-012).

Chỉ SQL đọc trên bảng E0–E3 – module này không ghi DB và không import module nghiệp vụ khác (hợp đồng import-linter).
MOCK bị loại khi
`include_mock = false` (Constitution I). Chi phí KHÔNG tính ở đây: dùng `/api/v1/budget` của E0 (một nguồn duy nhất).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

ELIGIBLE_DECISIONS = ("CANDIDATE", "WATCH", "PURSUE")  # cùng quy tắc E2 (products.eligibility)


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, Decimal | int | float) else None


async def _counts(session: AsyncSession, sql: str, params: dict[str, Any]) -> dict[str, int]:
    return {str(k): int(v) for k, v in (await session.execute(text(sql), params)).all()}


async def overview(session: AsyncSession, *, include_mock: bool) -> dict[str, Any]:
    p = {"m": include_mock}
    by_evidence = await _counts(
        session,
        "SELECT evidence_status, count(*) FROM niches WHERE merged_into_id IS NULL AND (:m OR data_origin = 'REAL')"
        " GROUP BY 1",
        p,
    )
    by_decision = await _counts(
        session,
        "SELECT decision_status, count(*) FROM niches WHERE merged_into_id IS NULL AND (:m OR data_origin = 'REAL')"
        " GROUP BY 1",
        p,
    )
    prod = (
        await session.execute(
            text(
                "SELECT count(DISTINCT pn.product_id),"
                " count(DISTINCT pn.id) FILTER (WHERE pn.readiness_status = 'READY_TO_PROMOTE')"
                " FROM product_niches pn JOIN products pr ON pr.id = pn.product_id AND pr.merged_into_id IS NULL"
                " WHERE (:m OR pn.data_origin = 'REAL')"
            ),
            p,
        )
    ).one()
    kw = (
        await session.execute(
            text(
                "SELECT count(*), count(DISTINCT cluster_id), count(*) FILTER (WHERE length_class = 'LONG_TAIL')"
                " FROM keywords WHERE (:m OR data_origin = 'REAL')"
            ),
            p,
        )
    ).one()
    jobs = await _counts(
        session, "SELECT status, count(*) FROM agent_jobs WHERE (:m OR data_origin = 'REAL') GROUP BY 1", p
    )
    failed_7d = (
        await session.execute(
            text(
                "SELECT count(*) FROM agent_jobs WHERE status = 'FAILED' AND created_at >= now() - interval '7 days'"
                " AND (:m OR data_origin = 'REAL')"
            ),
            p,
        )
    ).scalar_one()
    top = (
        await session.execute(
            text(
                "SELECT n.id, n.name, e.opportunity_score, e.confidence_score, n.data_origin FROM niches n"
                " JOIN niche_evaluations e ON e.id = n.latest_evaluation_id"
                " WHERE n.merged_into_id IS NULL AND (:m OR n.data_origin = 'REAL')"
                " AND n.decision_status NOT IN ('REJECTED', 'HIDDEN') AND e.opportunity_score IS NOT NULL"
                " ORDER BY e.opportunity_score DESC, e.confidence_score DESC, n.name LIMIT 5"
            ),
            p,
        )
    ).all()
    return {
        "niches": {"total": sum(by_evidence.values()), "by_evidence_status": by_evidence, "by_decision": by_decision},
        "products": {"total": int(prod[0]), "ready_to_promote": int(prod[1])},
        "keywords": {"total": int(kw[0]), "clusters": int(kw[1]), "long_tail": int(kw[2])},
        "jobs": {"by_status": jobs, "failed_7d": int(failed_7d)},
        "top_niches": [
            {
                "niche_id": str(r[0]),
                "name": r[1],
                "opportunity_score": _num(r[2]),
                "confidence_score": _num(r[3]),
                "data_origin": r[4],
            }
            for r in top
        ],
        "include_mock": include_mock,
        "generated_at": datetime.now(UTC).isoformat(),
    }


RESEARCH_SQL = """
WITH n AS (
  SELECT n.id, n.name, n.country, n.evidence_status, n.decision_status, n.data_origin, n.created_at,
         e.opportunity_score, e.confidence_score
  FROM niches n LEFT JOIN niche_evaluations e ON e.id = n.latest_evaluation_id
  WHERE n.merged_into_id IS NULL AND (:m OR n.data_origin = 'REAL')
),
p AS (
  SELECT pn.niche_id, count(DISTINCT pn.product_id) AS total,
         count(DISTINCT pn.id) FILTER (WHERE pn.readiness_status = 'READY_TO_PROMOTE') AS ready
  FROM product_niches pn JOIN products pr ON pr.id = pn.product_id AND pr.merged_into_id IS NULL
  WHERE (:m OR pn.data_origin = 'REAL') GROUP BY pn.niche_id
),
pr_runs AS (SELECT DISTINCT niche_id FROM product_runs WHERE (:m OR data_origin = 'REAL')),
k AS (
  SELECT niche_id, count(*) AS total, count(DISTINCT cluster_id) AS clusters,
         count(*) FILTER (WHERE length_class = 'LONG_TAIL') AS long_tail
  FROM keywords WHERE (:m OR data_origin = 'REAL') GROUP BY niche_id
),
kr_runs AS (SELECT DISTINCT niche_id FROM keyword_runs WHERE (:m OR data_origin = 'REAL')),
latest AS (
  SELECT DISTINCT ON (keyword_id) keyword_id, opportunity_score, confidence_score
  FROM keyword_evaluations ORDER BY keyword_id, created_at DESC, id DESC
),
cs AS (
  SELECT c.niche_id, c.id AS cluster_id, coalesce(pk.text, '') AS name,
         round(avg(l.opportunity_score) FILTER (WHERE l.opportunity_score IS NOT NULL), 2) AS opp,
         round(avg(l.confidence_score) FILTER (WHERE l.opportunity_score IS NOT NULL), 2) AS conf
  FROM keyword_clusters c JOIN keywords kw ON kw.cluster_id = c.id
  LEFT JOIN latest l ON l.keyword_id = kw.id LEFT JOIN keywords pk ON pk.id = c.primary_keyword_id
  WHERE (:m OR c.data_origin = 'REAL') AND c.decision_status <> 'REJECTED'
  GROUP BY c.niche_id, c.id, pk.text
),
best AS (
  SELECT DISTINCT ON (niche_id) niche_id, cluster_id, name, opp, conf FROM cs WHERE opp IS NOT NULL
  ORDER BY niche_id, opp DESC, conf DESC, name
)
SELECT n.*, p.total AS p_total, p.ready AS p_ready,
       (pr_runs.niche_id IS NOT NULL OR p.total IS NOT NULL) AS p_run,
       k.total AS k_total, k.clusters AS k_clusters, k.long_tail AS k_long,
       (kr_runs.niche_id IS NOT NULL OR k.total IS NOT NULL) AS k_run,
       best.cluster_id AS b_id, best.name AS b_name, best.opp AS b_opp, best.conf AS b_conf
FROM n LEFT JOIN p ON p.niche_id = n.id LEFT JOIN pr_runs ON pr_runs.niche_id = n.id
LEFT JOIN k ON k.niche_id = n.id LEFT JOIN kr_runs ON kr_runs.niche_id = n.id LEFT JOIN best ON best.niche_id = n.id
ORDER BY n.opportunity_score DESC NULLS LAST, n.confidence_score DESC NULLS LAST, n.name
LIMIT :lim
"""


async def research_niches(session: AsyncSession, *, include_mock: bool, limit: int) -> dict[str, Any]:
    p = {"m": include_mock, "lim": limit}
    total = (
        await session.execute(
            text("SELECT count(*) FROM niches WHERE merged_into_id IS NULL AND (:m OR data_origin = 'REAL')"), p
        )
    ).scalar_one()
    rows = (await session.execute(text(RESEARCH_SQL), p)).mappings().all()
    items = []
    for r in rows:
        eligible = r["evidence_status"] == "EVIDENCE_SUFFICIENT" and r["decision_status"] in ELIGIBLE_DECISIONS
        best = (
            {
                "cluster_id": str(r["b_id"]),
                "name": r["b_name"],
                "opportunity_score": _num(r["b_opp"]),
                "confidence_score": _num(r["b_conf"]),
            }
            if r["b_id"]
            else None
        )
        items.append(
            {
                "niche_id": str(r["id"]),
                "name": r["name"],
                "country": r["country"],
                "evidence_status": r["evidence_status"],
                "decision_status": r["decision_status"],
                "eligible": eligible,
                "opportunity_score": _num(r["opportunity_score"]),
                "confidence_score": _num(r["confidence_score"]),
                "products": {
                    "has_run": bool(r["p_run"]),
                    "total": int(r["p_total"] or 0),
                    "ready_to_promote": int(r["p_ready"] or 0),
                },
                "keywords": {
                    "has_run": bool(r["k_run"]),
                    "total": int(r["k_total"] or 0),
                    "clusters": int(r["k_clusters"] or 0),
                    "long_tail": int(r["k_long"] or 0),
                    "best_cluster": best,
                },
                "data_origin": r["data_origin"],
            }
        )
    return {"items": items, "total": int(total), "limit": limit}
