"""Dịch vụ E3 cho API (FR-001, FR-003, FR-009, FR-016…FR-028, FR-031; contracts/openapi.yaml).

Chỉ ĐỌC bảng E1/E2. Danh sách/chi tiết tính lại đánh giá xác định khi dữ liệu đã đổi (không AI). Chỉ số keyword luôn
trả kèm nguồn;
không có nguồn → `value = null` (UI hiển thị `UNKNOWN`). Quyết định của chủ sở hữu không đổi điểm và được ghi audit.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nichepilot.core.errors import AppError
from nichepilot.modules.audit.service import record_audit
from nichepilot.modules.keywords import evaluation
from nichepilot.modules.keywords.clustering import cluster_scores
from nichepilot.modules.keywords.generation import display_name
from nichepilot.modules.products.eligibility import check_niche_eligible

ACTIVE_JOB_STATUSES = ("QUEUED", "RUNNING", "PAUSED", "PAUSED_BUDGET", "RETRY_SCHEDULED")
DISCLAIMER_KEY = "keywords.opportunity.disclaimer"


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, Decimal | int | float) else None


async def ensure_can_start(session: AsyncSession, niche_id: uuid.UUID) -> None:
    await check_niche_eligible(session, niche_id)  # cùng quy tắc E2 (FR-001)
    active = (
        await session.execute(
            text(
                "SELECT 1 FROM keyword_runs r JOIN agent_jobs j ON j.id = r.job_id WHERE r.niche_id = :n"
                " AND j.job_type = 'keywords.run' AND j.status = ANY(:s) LIMIT 1"
            ),
            {"n": niche_id, "s": list(ACTIVE_JOB_STATUSES)},
        )
    ).first()
    if active is not None:
        raise AppError("KEYWORD_RUN_ACTIVE")


_RUN_SQL = (
    "SELECT r.id, r.job_id, r.niche_id, j.status, r.outcome, r.stop_reason, r.params, r.metrics, r.data_origin,"
    " r.created_at FROM keyword_runs r JOIN agent_jobs j ON j.id = r.job_id WHERE j.job_type = 'keywords.run'"
)


def _run_dict(r: Any) -> dict[str, Any]:
    return {
        "id": str(r["id"]),
        "job_id": str(r["job_id"]),
        "niche_id": str(r["niche_id"]),
        "status": r["status"],
        "outcome": r["outcome"],
        "stop_reason": r["stop_reason"],
        "params": r["params"],
        "metrics": r["metrics"],
        "data_origin": r["data_origin"],
        "created_at": r["created_at"].isoformat(),
    }


async def list_runs(session: AsyncSession, *, niche_id: uuid.UUID | None, include_mock: bool) -> list[dict[str, Any]]:
    rows = (
        await session.execute(
            text(
                _RUN_SQL + " AND (CAST(:n AS uuid) IS NULL OR r.niche_id = CAST(:n AS uuid))"
                " AND (:m OR r.data_origin = 'REAL') ORDER BY r.created_at DESC LIMIT 200"
            ),
            {"n": niche_id, "m": include_mock},
        )
    ).mappings()
    return [_run_dict(r) for r in rows]


async def get_run(session: AsyncSession, run_id: uuid.UUID) -> dict[str, Any]:
    r = (await session.execute(text(_RUN_SQL + " AND r.id = :i"), {"i": run_id})).mappings().first()
    if r is None:
        raise AppError("KEYWORD_RUN_NOT_FOUND")
    return _run_dict(r)


async def _niche_exists(session: AsyncSession, niche_id: uuid.UUID) -> None:
    if (await session.execute(text("SELECT 1 FROM niches WHERE id = :n"), {"n": niche_id})).first() is None:
        raise AppError("NICHE_NOT_FOUND")


async def refresh_stale(session: AsyncSession, niche_id: uuid.UUID, include_mock: bool) -> None:
    ids = (
        await session.execute(
            text("SELECT id FROM keywords WHERE niche_id = :n AND (:m OR data_origin = 'REAL')"),
            {"n": niche_id, "m": include_mock},
        )
    ).scalars()
    stale = await evaluation.stale_keywords(session, list(ids))
    if stale:
        await evaluation.evaluate_keywords(session, stale)
        clusters = (
            await session.execute(
                text("SELECT DISTINCT cluster_id FROM keywords WHERE id = ANY(:i) AND cluster_id IS NOT NULL"),
                {"i": stale},
            )
        ).scalars()
        await evaluation.refresh_clusters(session, list(clusters))


def _metric(value: Any, source: Any, collected: Any, market: Any) -> dict[str, Any]:
    if value is None or source is None:
        return {"value": None, "source": None, "collected_at": None, "market": None}
    return {
        "value": _num(value),
        "source": source,
        "collected_at": collected.isoformat() if collected else None,
        "market": market,
    }


_KEYWORD_SQL = """
SELECT k.id, k.text, k.language, k.market, k.keyword_type, k.length_class, k.intent, k.intent_status, k.intent_reason,
       k.risk_flags, k.search_volume, k.cpc, k.keyword_difficulty, k.metrics_source, k.metrics_collected_at,
       k.metrics_market, k.data_origin, k.cluster_id,
       ev.id AS eval_id, ev.opportunity_score, ev.confidence_score, ev.coverage, ev.scoring_status, ev.criteria,
       ev.missing, ev.created_at AS computed_at, w.version AS weights_version
FROM keywords k
LEFT JOIN LATERAL (SELECT * FROM keyword_evaluations e WHERE e.keyword_id = k.id ORDER BY e.created_at DESC, e.id DESC
                   LIMIT 1) ev ON true
LEFT JOIN keyword_scoring_weights w ON w.id = ev.weights_version_id
"""


def _evaluation(r: Any) -> dict[str, Any] | None:
    if r["eval_id"] is None:
        return None
    return {
        "opportunity_score": _num(r["opportunity_score"]),
        "confidence_score": _num(r["confidence_score"]),
        "coverage": _num(r["coverage"]),
        "scoring_status": r["scoring_status"],
        "criteria": r["criteria"],
        "missing": list(r["missing"] or []),
        "weights_version": r["weights_version"],
        "computed_at": r["computed_at"].isoformat() if r["computed_at"] else None,
    }


async def _origin_labels(session: AsyncSession, keyword_ids: list[uuid.UUID]) -> dict[str, list[dict[str, Any]]]:
    rows = (
        await session.execute(
            text(
                "SELECT o.keyword_id, o.origin_type, o.pain_point_id, o.product_id, o.persona_attribute, o.reason,"
                " pp.title, p.name FROM keyword_origins o LEFT JOIN pain_points pp ON pp.id = o.pain_point_id"
                " LEFT JOIN products p ON p.id = o.product_id WHERE o.keyword_id = ANY(:i) ORDER BY o.created_at, o.id"
            ),
            {"i": keyword_ids},
        )
    ).all()
    out: dict[str, list[dict[str, Any]]] = {}
    for kid, t, pp, pr, pa, reason, title, name in rows:
        ref = pp or pr
        label = title if t == "PAIN_POINT" else (name if t == "PRODUCT" else f"persona:{pa}")
        out.setdefault(str(kid), []).append(
            {"origin_type": t, "ref_id": str(ref) if ref else pa, "label": label, "reason": reason}
        )
    return out


async def _keywords(session: AsyncSession, where: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    rows = (
        (await session.execute(text(_KEYWORD_SQL + " WHERE " + where + " ORDER BY k.created_at, k.id"), params))
        .mappings()
        .all()
    )
    labels = await _origin_labels(session, [r["id"] for r in rows])
    out = []
    for r in rows:
        out.append(
            {
                "keyword_id": str(r["id"]),
                "cluster_id": str(r["cluster_id"]) if r["cluster_id"] else None,
                "text": r["text"],
                "language": r["language"],
                "market": r["market"],
                "keyword_type": r["keyword_type"],
                "length_class": r["length_class"],
                "intent": r["intent"],
                "intent_status": r["intent_status"],
                "intent_reason": r["intent_reason"],
                "risk_flags": list(r["risk_flags"] or []),
                "origins": labels.get(str(r["id"]), []),
                "metrics": {
                    "search_volume": _metric(
                        r["search_volume"], r["metrics_source"], r["metrics_collected_at"], r["metrics_market"]
                    ),
                    "cpc": _metric(r["cpc"], r["metrics_source"], r["metrics_collected_at"], r["metrics_market"]),
                    "keyword_difficulty": _metric(
                        r["keyword_difficulty"], r["metrics_source"], r["metrics_collected_at"], r["metrics_market"]
                    ),
                },
                "evaluation": _evaluation(r),
                "data_origin": r["data_origin"],
            }
        )
    return out


async def _cluster_rows(session: AsyncSession, where: str, params: dict[str, Any]) -> list[Any]:
    return list(
        (
            await session.execute(
                text(
                    "SELECT c.id, c.niche_id, c.intent, c.decision_status, c.decision_reason, c.watch_enabled,"  # noqa: S608 (where = hằng nội bộ)
                    " c.insights,"
                    " c.data_origin, c.primary_keyword_id, c.last_checked_at, c.last_check_error,"
                    " pk.text AS primary_text, pp.title AS pp_title, p.name AS product_name, c.cluster_key"
                    " FROM keyword_clusters c LEFT JOIN keywords pk ON pk.id = c.primary_keyword_id"
                    " LEFT JOIN pain_points pp ON pp.id = c.pain_point_id LEFT JOIN products p ON p.id = c.product_id"
                    " WHERE " + where
                ),
                params,
            )
        )
        .mappings()
        .all()
    )


async def _cluster_item(session: AsyncSession, c: Any) -> dict[str, Any]:
    members = await evaluation.cluster_members(session, c["id"])
    opp, conf, scored = cluster_scores(members)
    alert = (
        await session.execute(
            text(
                "SELECT 1 FROM serp_observations s WHERE s.keyword_id = :k AND s.version > 1 AND s.acknowledged_at IS"
                " NULL"
                " LIMIT 1"
            ),
            {"k": c["primary_keyword_id"]},
        )
    ).first()
    origin_label = c["pp_title"] or (
        display_name(c["product_name"]) if c["product_name"] else c["cluster_key"].split("|")[0]
    )
    return {
        "cluster_id": str(c["id"]),
        "niche_id": str(c["niche_id"]),
        "name": c["primary_text"] or (members[0].text if members else ""),
        "intent": c["intent"],
        "keyword_count": len(members),
        "long_tail_count": sum(1 for m in members if m.length_class == "LONG_TAIL"),
        "opportunity_score": _num(opp),
        "confidence_score": _num(conf),
        "scored_count": scored,
        "origin_label": origin_label,
        "decision_status": c["decision_status"],
        "serp_alert": alert is not None,
        "data_origin": c["data_origin"],
    }


async def list_clusters(
    session: AsyncSession, niche_id: uuid.UUID, *, list_name: str, intent: str | None, include_mock: bool
) -> list[dict[str, Any]]:
    await _niche_exists(session, niche_id)
    await refresh_stale(session, niche_id, include_mock)
    rows = await _cluster_rows(
        session,
        "c.niche_id = :n AND (:m OR c.data_origin = 'REAL') AND (CAST(:i AS text) IS NULL OR c.intent = CAST(:i AS"
        " text))",
        {"n": niche_id, "m": include_mock, "i": intent},
    )
    items = [await _cluster_item(session, c) for c in rows]
    if list_name == "needs_research":
        items = [i for i in items if i["opportunity_score"] is None and i["decision_status"] != "REJECTED"]
    else:
        items = [i for i in items if i["opportunity_score"] is not None and i["decision_status"] != "REJECTED"]
    items.sort(key=lambda i: (-(i["opportunity_score"] or 0), -(i["confidence_score"] or 0), i["name"]))
    return items


async def cluster_detail(session: AsyncSession, cluster_id: uuid.UUID) -> dict[str, Any]:
    rows = await _cluster_rows(session, "c.id = :c", {"c": cluster_id})
    if not rows:
        raise AppError("KEYWORD_CLUSTER_NOT_FOUND")
    c = rows[0]
    await refresh_stale(session, c["niche_id"], include_mock=True)
    item = await _cluster_item(session, c)
    kws = await _keywords(session, "k.cluster_id = :c", {"c": cluster_id})
    kids = [uuid.UUID(k["keyword_id"]) for k in kws]
    serp = (
        await session.execute(
            text(
                "SELECT keyword_id, version, collected_at, results, changes, acknowledged_at FROM serp_observations"
                " WHERE keyword_id = ANY(:k) ORDER BY keyword_id, version DESC"
            ),
            {"k": kids},
        )
    ).all()
    pages = (
        await session.execute(
            text(
                "SELECT c.keyword_id, c.url, c.domain, c.summary, e.excerpt, e.lifecycle_status FROM competitor_pages c"
                " LEFT JOIN research_evidence e ON e.id = c.evidence_id WHERE c.keyword_id = ANY(:k) ORDER BY c.url"
            ),
            {"k": kids},
        )
    ).all()
    insights = dict(c["insights"] or {})
    unknown = {"status": "UNKNOWN", "items": []}
    return {
        **item,
        "keywords": kws,
        "serp": [
            {
                "keyword_id": str(r[0]),
                "version": r[1],
                "collected_at": r[2].isoformat(),
                "results": r[3],
                "changes": r[4],
                "acknowledged_at": r[5].isoformat() if r[5] else None,
            }
            for r in serp
        ],
        "competitor_pages": [
            {"keyword_id": str(r[0]), "url": r[1], "domain": r[2], "summary": r[3], "excerpt": r[4]}
            for r in pages
            if r[5] == "ACTIVE"
        ],
        "content_gaps": insights.get("content_gaps") or unknown,
        "channels": insights.get("channels") or unknown,
        "persona": insights.get("persona") or {},
        "strategy": insights.get("strategy") or {"status": "UNKNOWN"},
        "decision_reason": c["decision_reason"],
        "watch_enabled": c["watch_enabled"],
        "last_checked_at": c["last_checked_at"].isoformat() if c["last_checked_at"] else None,
        "last_check_error": c["last_check_error"],
        "disclaimer_key": DISCLAIMER_KEY,
    }


async def record_decision(
    session: AsyncSession,
    cluster_id: uuid.UUID,
    *,
    decision: str,
    reason: str,
    actor_id: uuid.UUID,
    request_id: str | None,
) -> None:
    if not reason.strip():
        raise AppError("VALIDATION_ERROR", detail="reason is required")
    row = (
        await session.execute(
            text("SELECT decision_status, decision_reason FROM keyword_clusters WHERE id = :i FOR UPDATE"),
            {"i": cluster_id},
        )
    ).first()
    if row is None:
        raise AppError("KEYWORD_CLUSTER_NOT_FOUND")
    await session.execute(
        text(
            "UPDATE keyword_clusters SET decision_status = :d, decision_reason = :r, decided_by = :u, decided_at ="
            " now(),"
            " updated_at = now() WHERE id = :i"
        ),
        {"d": decision, "r": reason.strip()[:1000], "u": actor_id, "i": cluster_id},
    )
    await record_audit(
        session,
        action="keyword.cluster_decision",
        actor_type="USER",
        actor_id=actor_id,
        entity_type="keyword_cluster",
        entity_id=cluster_id,
        before={"decision_status": row[0], "reason": row[1]},
        after={"decision_status": decision, "reason": reason.strip()[:1000]},
        request_id=request_id,
    )


async def niche_summary(session: AsyncSession, niche_id: uuid.UUID, *, include_mock: bool) -> dict[str, Any]:
    await _niche_exists(session, niche_id)
    r = (
        (
            await session.execute(
                text(
                    "SELECT count(*) AS keywords, count(DISTINCT cluster_id) AS clusters,"
                    " count(*) FILTER (WHERE length_class = 'LONG_TAIL') AS long_tail FROM keywords"
                    " WHERE niche_id = :n AND (:m OR data_origin = 'REAL')"
                ),
                {"n": niche_id, "m": include_mock},
            )
        )
        .mappings()
        .one()
    )
    runs = await list_runs(session, niche_id=niche_id, include_mock=include_mock)
    top = (await list_clusters(session, niche_id, list_name="ranked", intent=None, include_mock=include_mock))[:3]
    return {
        "keyword_count": int(r["keywords"]),
        "cluster_count": int(r["clusters"]),
        "long_tail_count": int(r["long_tail"]),
        "top_clusters": top,
        "last_run": runs[0] if runs else None,
    }


async def set_watch(
    session: AsyncSession, cluster_id: uuid.UUID, *, enabled: bool, actor_id: uuid.UUID, request_id: str | None
) -> None:
    before = (
        await session.execute(
            text("SELECT watch_enabled FROM keyword_clusters WHERE id = :i FOR UPDATE"), {"i": cluster_id}
        )
    ).scalar_one_or_none()
    if before is None:
        raise AppError("KEYWORD_CLUSTER_NOT_FOUND")
    await session.execute(
        text("UPDATE keyword_clusters SET watch_enabled = :e, updated_at = now() WHERE id = :i"),
        {"e": enabled, "i": cluster_id},
    )
    await record_audit(
        session,
        action="keyword.watch_changed",
        actor_type="USER",
        actor_id=actor_id,
        entity_type="keyword_cluster",
        entity_id=cluster_id,
        before={"watch_enabled": before},
        after={"watch_enabled": enabled},
        request_id=request_id,
    )


async def acknowledge(
    session: AsyncSession, cluster_id: uuid.UUID, version: int, *, actor_id: uuid.UUID, request_id: str | None
) -> None:
    sid = (
        await session.execute(
            text(
                "UPDATE serp_observations s SET acknowledged_at = coalesce(s.acknowledged_at, now()),"
                " updated_at = now() FROM keyword_clusters c"
                " WHERE c.id = :c AND s.keyword_id = c.primary_keyword_id AND s.version = :v RETURNING s.id"
            ),
            {"c": cluster_id, "v": version},
        )
    ).scalar_one_or_none()
    if sid is None:
        raise AppError("KEYWORD_CLUSTER_NOT_FOUND")
    await record_audit(
        session,
        action="keyword.serp_acknowledged",
        actor_type="USER",
        actor_id=actor_id,
        entity_type="keyword_cluster",
        entity_id=cluster_id,
        after={"version": version},
        request_id=request_id,
    )
