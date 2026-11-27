"""Dịch vụ E2 cho API (FR-001…FR-004, FR-032…FR-037, FR-040; contracts/openapi.yaml).

Chỉ ĐỌC bảng E1. Danh sách/chi tiết tính lại đánh giá xác định khi tập bằng chứng ACTIVE đã đổi (R-06). Quyết định của
chủ sở hữu
không đổi điểm số và được ghi audit (FR-033, FR-037).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nichepilot.core.errors import AppError
from nichepilot.modules.audit.service import record_audit
from nichepilot.modules.products import evaluation
from nichepilot.modules.products.attributes import PRODUCT_KEYS, PROGRAM_KEYS, ResolvedAttribute, resolve_all
from nichepilot.modules.products.eligibility import check_niche_eligible

ACTIVE_JOB_STATUSES = ("QUEUED", "RUNNING", "PAUSED", "PAUSED_BUDGET", "RETRY_SCHEDULED")
DISCLAIMER_KEY = "products.opportunity.disclaimer"


def _num(v: Any) -> float | None:
    return float(v) if isinstance(v, Decimal | int | float) else None


async def ensure_can_start(session: AsyncSession, niche_id: uuid.UUID) -> None:
    await check_niche_eligible(session, niche_id)
    active = (
        await session.execute(
            text(
                "SELECT 1 FROM product_runs r JOIN agent_jobs j ON j.id = r.job_id WHERE r.niche_id = :n"
                " AND j.job_type = 'products.run' AND j.status = ANY(:s) LIMIT 1"
            ),
            {"n": niche_id, "s": list(ACTIVE_JOB_STATUSES)},
        )
    ).first()
    if active is not None:
        raise AppError("PRODUCT_RUN_ACTIVE")


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


_RUN_SQL = (
    "SELECT r.id, r.job_id, r.niche_id, j.status, r.outcome, r.stop_reason, r.params, r.metrics, r.data_origin,"
    " r.created_at"
    " FROM product_runs r JOIN agent_jobs j ON j.id = r.job_id WHERE j.job_type = 'products.run'"
)


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
        raise AppError("PRODUCT_RUN_NOT_FOUND")
    return _run_dict(r)


async def get_run_by_job(session: AsyncSession, job_id: uuid.UUID) -> dict[str, Any]:
    r = (await session.execute(text(_RUN_SQL + " AND r.job_id = :j"), {"j": job_id})).mappings().first()
    if r is None:
        raise AppError("PRODUCT_RUN_NOT_FOUND")
    return _run_dict(r)


async def refresh_stale(session: AsyncSession, pair_ids: Sequence[uuid.UUID]) -> None:
    """R-06: đánh giá gần nhất không khớp tập bằng chứng ACTIVE hiện tại (vd. bằng chứng vừa bị xóa) → tính lại (không
    AI)."""
    for pid in await evaluation.stale_pairs(session, pair_ids):
        await evaluation.evaluate_pair(session, pid)


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


_LIST_SQL = """
SELECT pn.id AS pair_id, p.id AS product_id, p.name, p.vendor, p.official_domain, p.category, p.data_origin,
       pn.readiness_status, pn.risk_flags, pn.ai_recommendation, pn.ai_recommendation_reason, pn.decision_status,
       pn.decision_reason, pn.persona_match, e.id AS eval_id, e.opportunity_score, e.confidence_score, e.coverage,
       e.scoring_status, e.criteria, e.missing, e.created_at AS computed_at, w.version AS weights_version
FROM product_niches pn
JOIN products p ON p.id = pn.product_id
LEFT JOIN LATERAL (SELECT * FROM product_evaluations x WHERE x.product_niche_id = pn.id
                   ORDER BY x.created_at DESC, x.id DESC LIMIT 1) e ON true
LEFT JOIN product_scoring_weights w ON w.id = e.weights_version_id
WHERE pn.niche_id = :n AND p.merged_into_id IS NULL AND (:m OR pn.data_origin = 'REAL')
"""


def _item(r: Any) -> dict[str, Any]:
    return {
        "product_id": str(r["product_id"]),
        "name": r["name"],
        "vendor": r["vendor"],
        "official_domain": r["official_domain"],
        "category": r["category"],
        "readiness_status": r["readiness_status"],
        "risk_flags": list(r["risk_flags"] or []),
        "evaluation": _evaluation(r),
        "ai_recommendation": r["ai_recommendation"],
        "ai_recommendation_reason": r["ai_recommendation_reason"],
        "decision_status": r["decision_status"],
        "decision_reason": r["decision_reason"],
        "persona_match": r["persona_match"],
        "data_origin": r["data_origin"],
    }


async def _niche_exists(session: AsyncSession, niche_id: uuid.UUID) -> None:
    if (await session.execute(text("SELECT 1 FROM niches WHERE id = :n"), {"n": niche_id})).first() is None:
        raise AppError("NICHE_NOT_FOUND")


async def list_products(
    session: AsyncSession, niche_id: uuid.UUID, *, list_name: str, include_mock: bool
) -> list[dict[str, Any]]:
    await _niche_exists(session, niche_id)
    pair_ids = (
        (
            await session.execute(
                text("SELECT id FROM product_niches WHERE niche_id = :n AND (:m OR data_origin = 'REAL')"),
                {"n": niche_id, "m": include_mock},
            )
        )
        .scalars()
        .all()
    )
    await refresh_stale(session, list(pair_ids))
    rows = (await session.execute(text(_LIST_SQL), {"n": niche_id, "m": include_mock})).mappings().all()
    items = [_item(r) for r in rows]
    if list_name == "needs_research":
        sel = [i for i in items if (i["evaluation"] or {}).get("scoring_status") != "SCORED"]
        return sorted(sel, key=lambda i: -((i["evaluation"] or {}).get("confidence_score") or 0))
    sel = [
        i
        for i in items
        if (i["evaluation"] or {}).get("scoring_status") == "SCORED" and i["decision_status"] != "REJECTED"
    ]
    return sorted(
        sel,
        key=lambda i: (-(i["evaluation"]["opportunity_score"] or 0), -(i["evaluation"]["confidence_score"] or 0)),
    )


def _attr_json(a: ResolvedAttribute) -> dict[str, Any]:
    return {
        "key": a.key,
        "status": a.status,
        "value": a.value,
        "flags": list(a.flags),
        "values": [
            {
                "value": v.value,
                "status": v.status,
                "evidence_id": v.evidence_id,
                "source_url": v.source_url,
                "excerpt": v.excerpt,
                "collected_at": v.collected_at.isoformat() if v.collected_at else None,
                "verified_at": v.verified_at.isoformat() if v.verified_at else None,
            }
            for v in a.values
        ],
    }


async def program_detail(session: AsyncSession, program_id: uuid.UUID) -> dict[str, Any]:
    r = (
        (
            await session.execute(
                text(
                    "SELECT id, name, operator_type, operator_name, operator_domain, terms_url, verification_status,"
                    " watch_enabled, last_checked_at, last_check_error, data_origin FROM affiliate_programs WHERE id ="
                    " :i"
                ),
                {"i": program_id},
            )
        )
        .mappings()
        .first()
    )
    if r is None:
        raise AppError("PROGRAM_NOT_FOUND")
    attrs = resolve_all(PROGRAM_KEYS, await evaluation.load_attr_evidence(session, "affiliate_program", program_id))
    versions = (
        await session.execute(
            text(
                "SELECT version, checked_at, changes, acknowledged_at FROM program_terms_versions WHERE program_id = :i"
                " ORDER BY version DESC"
            ),
            {"i": program_id},
        )
    ).mappings()
    return {
        "program_id": str(r["id"]),
        "name": r["name"],
        "operator_type": r["operator_type"],
        "operator_name": r["operator_name"],
        "operator_domain": r["operator_domain"],
        "terms_url": r["terms_url"],
        "verification_status": r["verification_status"],
        "attributes": [_attr_json(attrs[k]) for k in PROGRAM_KEYS],
        "watch_enabled": r["watch_enabled"],
        "last_checked_at": r["last_checked_at"].isoformat() if r["last_checked_at"] else None,
        "last_check_error": r["last_check_error"],
        "terms_versions": [
            {
                "version": v["version"],
                "checked_at": v["checked_at"].isoformat(),
                "changes": v["changes"],
                "acknowledged_at": v["acknowledged_at"].isoformat() if v["acknowledged_at"] else None,
            }
            for v in versions
        ],
        "data_origin": r["data_origin"],
    }


async def product_detail(session: AsyncSession, product_id: uuid.UUID, niche_id: uuid.UUID) -> dict[str, Any]:
    pair = (
        await session.execute(
            text("SELECT id FROM product_niches WHERE product_id = :p AND niche_id = :n"),
            {"p": product_id, "n": niche_id},
        )
    ).scalar_one_or_none()
    if pair is None:
        raise AppError("PRODUCT_NOT_FOUND")
    await refresh_stale(session, [pair])
    row = (
        (await session.execute(text(_LIST_SQL + " AND pn.id = :pn"), {"n": niche_id, "m": True, "pn": pair}))
        .mappings()
        .one()
    )
    item = _item(row)
    attrs = resolve_all(PRODUCT_KEYS, await evaluation.load_attr_evidence(session, "product", product_id))
    links = (
        await session.execute(
            text(
                "SELECT pp.id, pp.title, l.evidence_id, l.verification_status, e.excerpt, s.url FROM"
                " product_pain_point_links l"
                " JOIN pain_points pp ON pp.id = l.pain_point_id JOIN research_evidence e ON e.id = l.evidence_id"
                " LEFT JOIN research_sources s ON s.id = e.source_id WHERE l.product_niche_id = :pn"
                " AND e.lifecycle_status = 'ACTIVE' ORDER BY pp.title"
            ),
            {"pn": pair},
        )
    ).all()
    pains: dict[str, dict[str, Any]] = {}
    for pid, title, eid, status, excerpt, url in links:
        pains.setdefault(str(pid), {"pain_point_id": str(pid), "title": title, "evidence": []})["evidence"].append(
            {"evidence_id": str(eid), "status": status, "excerpt": excerpt, "source_url": url}
        )
    prog_ids = (
        await session.execute(text("SELECT program_id FROM product_programs WHERE product_id = :p"), {"p": product_id})
    ).scalars()
    return {
        **item,
        "attributes": [_attr_json(attrs[k]) for k in PRODUCT_KEYS],
        "pain_points": list(pains.values()),
        "programs": [await program_detail(session, pid) for pid in prog_ids],
        "disclaimer_key": DISCLAIMER_KEY,
    }


async def record_decision(
    session: AsyncSession,
    product_id: uuid.UUID,
    niche_id: uuid.UUID,
    *,
    decision: str,
    reason: str,
    actor_id: uuid.UUID,
    request_id: str | None,
) -> None:
    if not reason.strip():
        raise AppError("VALIDATION_ERROR", errors=[{"field": "reason", "code": "required"}])
    row = (
        await session.execute(
            text(
                "SELECT id, decision_status, decision_reason FROM product_niches WHERE product_id = :p AND niche_id ="
                " :n"
                " FOR UPDATE"
            ),
            {"p": product_id, "n": niche_id},
        )
    ).first()
    if row is None:
        raise AppError("PRODUCT_NOT_FOUND")
    await session.execute(
        text(
            "UPDATE product_niches SET decision_status = :d, decision_reason = :r, decided_by = :u, decided_at = now(),"
            " updated_at = now() WHERE id = :i"
        ),
        {"d": decision, "r": reason.strip()[:1000], "u": actor_id, "i": row[0]},
    )
    await record_audit(
        session,
        action="product.decision",
        actor_type="USER",
        actor_id=actor_id,
        entity_type="product_niche",
        entity_id=row[0],
        before={"decision_status": row[1], "reason": row[2]},
        after={"decision_status": decision, "reason": reason.strip()[:1000]},
        request_id=request_id,
    )


async def niche_summary(session: AsyncSession, niche_id: uuid.UUID, *, include_mock: bool) -> dict[str, Any]:
    await _niche_exists(session, niche_id)
    r = (
        (
            await session.execute(
                text(
                    "SELECT count(DISTINCT pn.product_id) AS products,"
                    " count(DISTINCT ap.id) FILTER (WHERE ap.verification_status = 'VERIFIED') AS programs_verified,"
                    " count(DISTINCT pn.id) FILTER (WHERE pn.readiness_status = 'READY_TO_PROMOTE') AS ready"
                    " FROM product_niches pn JOIN products p ON p.id = pn.product_id AND p.merged_into_id IS NULL"
                    " LEFT JOIN product_programs pp ON pp.product_id = pn.product_id"
                    " LEFT JOIN affiliate_programs ap ON ap.id = pp.program_id"
                    " WHERE pn.niche_id = :n AND (:m OR pn.data_origin = 'REAL')"
                ),
                {"n": niche_id, "m": include_mock},
            )
        )
        .mappings()
        .one()
    )
    last = (
        await session.execute(
            text(
                "SELECT r.id FROM product_runs r JOIN agent_jobs j ON j.id = r.job_id WHERE r.niche_id = :n"
                " AND j.job_type = 'products.run' AND (:m OR r.data_origin = 'REAL') ORDER BY r.created_at DESC LIMIT 1"
            ),
            {"n": niche_id, "m": include_mock},
        )
    ).scalar_one_or_none()
    products = int(r["products"])
    return {
        "products": products,
        "programs_verified": int(r["programs_verified"]),
        "ready_to_promote": int(r["ready"]),
        "monetization_risk": (products > 0 and int(r["ready"]) == 0) or (products == 0 and last is not None),
        "last_run_id": str(last) if last else None,
    }


async def set_watch(
    session: AsyncSession, program_id: uuid.UUID, *, enabled: bool, actor_id: uuid.UUID, request_id: str | None
) -> None:
    before = (
        await session.execute(
            text("SELECT watch_enabled FROM affiliate_programs WHERE id = :i FOR UPDATE"), {"i": program_id}
        )
    ).scalar_one_or_none()
    if before is None:
        raise AppError("PROGRAM_NOT_FOUND")
    await session.execute(
        text("UPDATE affiliate_programs SET watch_enabled = :e, updated_at = now() WHERE id = :i"),
        {"e": enabled, "i": program_id},
    )
    await record_audit(
        session,
        action="program.watch_changed",
        actor_type="USER",
        actor_id=actor_id,
        entity_type="affiliate_program",
        entity_id=program_id,
        before={"watch_enabled": before},
        after={"watch_enabled": enabled},
        request_id=request_id,
    )


async def acknowledge(
    session: AsyncSession, program_id: uuid.UUID, version: int, *, actor_id: uuid.UUID, request_id: str | None
) -> None:
    vid = (
        await session.execute(
            text(
                "UPDATE program_terms_versions SET acknowledged_at = coalesce(acknowledged_at, now()), updated_at ="
                " now()"
                " WHERE program_id = :p AND version = :v RETURNING id"
            ),
            {"p": program_id, "v": version},
        )
    ).scalar_one_or_none()
    if vid is None:
        raise AppError("PROGRAM_NOT_FOUND")
    await record_audit(
        session,
        action="program.terms_acknowledged",
        actor_type="USER",
        actor_id=actor_id,
        entity_type="affiliate_program",
        entity_id=program_id,
        after={"version": version},
        request_id=request_id,
    )
