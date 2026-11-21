"""DiscoveryService – nghiệp vụ lượt khám phá (US1: T051/T062; data-model `discovery_runs`, `niches`, `page_fetch_log`).

Không import `ai`/`tools` (phân lớp E0). Tạo bản ghi lượt idempotent theo `job_id` – dùng chung cho API và agent
(`ensure_run`), nên lượt theo lịch (Scheduler E0 tạo job bình thường) cũng có bản ghi mà không sửa Scheduler.
"""

from __future__ import annotations

import json
import re
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nichepilot.modules.discovery.evaluation import evaluation_dto
from nichepilot.modules.discovery.sources.policy import UsableSourcePolicy

METRIC_KEYS = (
    "pages_attempted",
    "pages_succeeded",
    "pages_failed",
    "pages_skipped",
    "needs_review_segments",
    "elapsed_active_s",
    "independent_sources",
    "candidates",
    "candidate_domains",
    "evidence_items",
    "evidence_sufficient",
    "insufficient_evidence",
    "insufficient_scoring_data",
    "ai_calls",
)


def empty_metrics() -> dict[str, Any]:
    m: dict[str, Any] = dict.fromkeys(METRIC_KEYS, 0)
    m.update({"skipped_by_reason": {}, "source_status": {}, "cost_real_usd": "0", "cost_mock_usd": "0"})
    return m


def dedup_key(customer_group: str, core_problem: str) -> str:
    def norm(s: str) -> str:
        return " ".join(re.findall(r"[^\W_]+", s.lower()))

    return f"{norm(customer_group)}|{norm(core_problem)}"[:500]


async def create_run_record(
    session: AsyncSession,
    *,
    job_id: uuid.UUID,
    params: dict[str, Any],
    usable: list[UsableSourcePolicy],
    source_mode: str,
) -> uuid.UUID:
    """INSERT … ON CONFLICT (job_id) DO NOTHING – trả id lượt (đã có hoặc vừa tạo)."""
    job = (
        (
            await session.execute(
                text("SELECT project_id, trigger, budget_limit_usd, data_origin FROM agent_jobs WHERE id = :j"),
                {"j": job_id},
            )
        )
        .mappings()
        .one()
    )
    weights = (await session.execute(text("SELECT id FROM scoring_weights_versions WHERE is_active"))).scalar_one()
    origin = "MOCK" if "MOCK" in (source_mode, job["data_origin"]) else "REAL"
    run_id = (
        await session.execute(
            text(
                "INSERT INTO discovery_runs (project_id, job_id, market, research_language, seed_topic, max_candidates,"
                " budget_usd, time_limit_s, page_limit, per_domain_interval_s, trigger, source_policy_ids,"
                " weights_version_id, source_mode, data_origin, metrics, idempotency_key) VALUES (:p, :j, :m, :l, :t,"
                " :mc, :b, :tl, :pl, :pi, :tr, CAST(:sp AS uuid[]), :w, :sm, :o, CAST(:met AS jsonb), :ik)"
                " ON CONFLICT (job_id) DO NOTHING RETURNING id"
            ),
            {
                "p": job["project_id"],
                "j": job_id,
                "m": params["market"],
                "l": params.get("research_language", "en"),
                "t": params.get("seed_topic"),
                "mc": params.get("max_candidates", 20),
                "b": job["budget_limit_usd"],
                "tl": params.get("time_limit_s", 5400),
                "pl": params.get("page_limit", 300),
                "pi": params.get("per_domain_interval_s", 2.0),
                "tr": job["trigger"],
                "sp": [str(u.policy_id) for u in usable],
                "w": weights,
                "sm": source_mode,
                "o": origin,
                "met": json.dumps(empty_metrics()),
                "ik": params.get("idempotency_key"),
            },
        )
    ).scalar_one_or_none()
    if run_id is None:
        run_id = (
            await session.execute(text("SELECT id FROM discovery_runs WHERE job_id = :j"), {"j": job_id})
        ).scalar_one()
    return uuid.UUID(str(run_id))


RUN_SELECT = (
    "SELECT r.*, j.status AS job_status, j.job_type, w.version AS weights_version, j.cost_accumulated_usd,"
    " COALESCE((SELECT json_agg(json_build_object('source_key', p.source_key, 'verified_at', p.verified_at)"
    " ORDER BY p.source_key) FROM source_policies p WHERE p.id = ANY(r.source_policy_ids)), '[]'::json) AS sources"
    " FROM discovery_runs r JOIN agent_jobs j ON j.id = r.job_id JOIN scoring_weights_versions w"
    " ON w.id = r.weights_version_id"
)


def run_dto(row: Any) -> dict[str, Any]:
    r = dict(row)
    metrics = dict(r["metrics"] or {})
    outcome, stop_reason = r["outcome"], r["stop_reason"]
    if outcome is None and r["job_status"] == "CANCELLED":
        # job E0 bị hủy giữa chừng (runtime E0 không gọi lại agent) – kết quả nghiệp vụ suy ra, không ghi đè state
        # machine E0
        outcome, stop_reason = "PARTIAL_COMPLETED", "CANCELLED"
    return {
        "id": str(r["id"]),
        "job": {"job_id": str(r["job_id"]), "job_type": r["job_type"], "status": r["job_status"]},
        "market": r["market"],
        "research_language": r["research_language"],
        "seed_topic": r["seed_topic"],
        "max_candidates": r["max_candidates"],
        "budget_usd": str(Decimal(r["budget_usd"]).quantize(Decimal("0.000001"))),
        "time_limit_minutes": int(r["time_limit_s"]) // 60,
        "page_limit": r["page_limit"],
        "per_domain_interval_s": float(r["per_domain_interval_s"]),
        "weights_version": r["weights_version"],
        "source_mode": r["source_mode"],
        "trigger": r["trigger"],
        "sources": [{"source_key": s["source_key"], "verified_at": s["verified_at"]} for s in (r["sources"] or [])],
        "outcome": outcome,
        "stop_reason": stop_reason,
        "metrics": metrics,
        "data_origin": r["data_origin"],
        "created_at": r["created_at"].isoformat(),
    }


async def get_run(session: AsyncSession, run_id: uuid.UUID) -> dict[str, Any] | None:
    row = (await session.execute(text(RUN_SELECT + " WHERE r.id = :i"), {"i": run_id})).mappings().first()
    return run_dto(row) if row else None


async def get_run_by_job(session: AsyncSession, job_id: uuid.UUID) -> dict[str, Any] | None:
    row = (await session.execute(text(RUN_SELECT + " WHERE r.job_id = :j"), {"j": job_id})).mappings().first()
    return run_dto(row) if row else None


async def list_runs(session: AsyncSession, *, limit: int, include_mock: bool) -> list[dict[str, Any]]:
    where = "" if include_mock else " WHERE r.data_origin = 'REAL'"
    rows = (
        (await session.execute(text(RUN_SELECT + where + " ORDER BY r.created_at DESC LIMIT :l"), {"l": limit}))
        .mappings()
        .all()
    )
    return [run_dto(r) for r in rows]


async def upsert_candidate(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    project_id: uuid.UUID,
    country: str,
    name: str,
    micro_niche: str,
    customer_group: str,
    core_problem: str,
    data_origin: str,
) -> uuid.UUID:
    """Tạo ngách ứng viên hoặc dùng lại ngách trùng `dedup_key` (FR-029: chạy lại không tạo trùng)."""
    key = dedup_key(customer_group, core_problem)
    niche_id = (
        await session.execute(
            text(
                "INSERT INTO niches (project_id, name, micro_niche, country, customer_group, core_problem, dedup_key,"
                " data_origin) VALUES (:p, :n, :mn, :c, :cg, :cp, :k, :o)"
                " ON CONFLICT (project_id, data_origin, dedup_key) WHERE merged_into_id IS NULL DO NOTHING RETURNING id"
            ),
            {
                "p": project_id,
                "n": name[:200],
                "mn": micro_niche[:200],
                "c": country,
                "cg": customer_group[:300],
                "cp": core_problem[:500],
                "k": key,
                "o": data_origin,
            },
        )
    ).scalar_one_or_none()
    if niche_id is None:
        niche_id = (
            await session.execute(
                text(
                    "SELECT id FROM niches WHERE project_id = :p AND data_origin = :o AND dedup_key = :k"
                    " AND merged_into_id IS NULL"
                ),
                {"p": project_id, "o": data_origin, "k": key},
            )
        ).scalar_one()
    await session.execute(
        text(
            "INSERT INTO niche_run_links (niche_id, run_id, role) VALUES (:n, :r, 'DISCOVERED')"
            " ON CONFLICT (niche_id, run_id) DO NOTHING"
        ),
        {"n": niche_id, "r": run_id},
    )
    return uuid.UUID(str(niche_id))


async def log_fetch(
    session: AsyncSession,
    *,
    run_id: uuid.UUID,
    url_hash: str,
    domain: str,
    outcome: str,
    reason: str | None,
    http_status: int | None,
    source_id: uuid.UUID | None,
) -> bool:
    """Ghi page_fetch_log (UNIQUE run_id+url_hash). Trả False nếu URL đã được xử lý trong lượt (tiếp tục sau sự cố)."""
    inserted = (
        await session.execute(
            text(
                "INSERT INTO page_fetch_log (run_id, url_hash, domain, outcome, reason, http_status, source_id)"
                " VALUES (:r, :h, :d, :o, :re, :hs, :s) ON CONFLICT (run_id, url_hash) DO NOTHING RETURNING id"
            ),
            {"r": run_id, "h": url_hash, "d": domain, "o": outcome, "re": reason, "hs": http_status, "s": source_id},
        )
    ).scalar_one_or_none()
    return inserted is not None


async def already_fetched(session: AsyncSession, run_id: uuid.UUID, url_hash: str) -> bool:
    return bool(
        (
            await session.execute(
                text("SELECT 1 FROM page_fetch_log WHERE run_id = :r AND url_hash = :h"), {"r": run_id, "h": url_hash}
            )
        ).scalar_one_or_none()
    )


ERASED_HASHES_SQL = (
    "SELECT content_hash FROM research_evidence WHERE lifecycle_status = 'ERASED' AND content_hash IS NOT NULL"
    " UNION SELECT content_hash FROM research_sources WHERE lifecycle_status = 'ERASED'"
    " UNION SELECT content_hash FROM evidence_erasure_requests WHERE content_hash IS NOT NULL"
)


async def erased_hashes(session: AsyncSession) -> set[str]:
    """content_hash (trích đoạn hoặc cả trang) đã bị xóa theo yêu cầu – không thu thập lại (FR-013e, research R-09)."""
    rows = (await session.execute(text(ERASED_HASHES_SQL))).all()
    return {str(r[0]) for r in rows}


async def erased_among(session: AsyncSession, hashes: list[str]) -> set[str]:
    """Kiểm tra NGAY trước khi lưu (không dùng ảnh chụp đầu lô) – xóa xảy ra giữa lượt vẫn được tôn trọng."""
    wanted = [h for h in hashes if h]
    if not wanted:
        return set()
    rows = (
        await session.execute(
            text(f"SELECT content_hash FROM ({ERASED_HASHES_SQL}) e WHERE content_hash = ANY(:h)"),  # noqa: S608
            {"h": wanted},
        )
    ).all()
    return {str(r[0]) for r in rows}


async def save_metrics(session: AsyncSession, run_id: uuid.UUID, metrics: dict[str, Any]) -> None:
    await session.execute(
        text("UPDATE discovery_runs SET metrics = CAST(:m AS jsonb), updated_at = now() WHERE id = :r"),
        {"m": json.dumps(metrics), "r": run_id},
    )


async def finish_run(
    session: AsyncSession, run_id: uuid.UUID, *, outcome: str, stop_reason: str, metrics: dict[str, Any]
) -> None:
    await session.execute(
        text(
            "UPDATE discovery_runs SET outcome = :o, stop_reason = :s, metrics = CAST(:m AS jsonb), updated_at = now()"
            " WHERE id = :r"
        ),
        {"o": outcome, "s": stop_reason, "m": json.dumps(metrics), "r": run_id},
    )


# ---------------------------------------------------------------------------------------------------------------------
# Chi tiết ngách – màn hình 3 (T083; openapi NicheDetail; FR-023 – 16 trường BR-07, thiếu → UNKNOWN)
# ---------------------------------------------------------------------------------------------------------------------
PERSONA_ATTRS = ("segment", "context", "goals", "obstacles", "ability_to_pay")
FINDING_FIELDS = ("CURRENT_SOLUTIONS", "MARKET_GAPS", "POTENTIAL_PRODUCTS", "MONETIZATION", "CHANNELS", "RISKS")
UNKNOWN_FINDING: dict[str, Any] = {"value": None, "status": "UNKNOWN", "evidence_ids": []}
DISCLAIMER_KEY = "discovery.disclaimer.evidence_not_profitability"


def _iso(v: Any) -> str | None:
    return v.isoformat() if v is not None else None


async def niche_detail(session: AsyncSession, niche_id: uuid.UUID) -> dict[str, Any] | None:
    n = (await session.execute(text("SELECT * FROM niches WHERE id = :n"), {"n": niche_id})).mappings().first()
    if n is None:
        return None
    pps = (
        (
            await session.execute(
                text(
                    "SELECT id, title, description, severity, severity_reason, evidence_count, verification_status"
                    " FROM pain_points WHERE niche_id = :n ORDER BY severity DESC NULLS LAST, title"
                ),
                {"n": niche_id},
            )
        )
        .mappings()
        .all()
    )
    persona_row = (
        await session.execute(text("SELECT attributes FROM buyer_personas WHERE niche_id = :n"), {"n": niche_id})
    ).scalar_one_or_none() or {}
    findings_rows = (
        await session.execute(
            text("SELECT field, value, verification_status, evidence_ids FROM niche_findings WHERE niche_id = :n"),
            {"n": niche_id},
        )
    ).all()
    findings = {f: dict(UNKNOWN_FINDING) for f in FINDING_FIELDS}
    for field_, value, status, ids in findings_rows:
        findings[field_] = {"value": value, "status": status, "evidence_ids": [str(i) for i in ids]}
    comps = (
        (
            await session.execute(
                text(
                    "SELECT name, kind, url, strengths, weaknesses FROM competitors WHERE niche_id = :n ORDER BY name"
                ),
                {"n": niche_id},
            )
        )
        .mappings()
        .all()
    )
    # chỉ bằng chứng ACTIVE (đã xóa → không trả, kể cả trích đoạn – FR-013e); excerpt đã che PII khi thu thập
    evidence = (
        (
            await session.execute(
                text(
                    "SELECT e.id, e.excerpt, e.created_at, e.verification_status, e.redaction_status, e.data_origin,"
                    " s.url, s.registered_domain, s.policy_verified_at, l.purpose, l.relevance, l.quality,"
                    " l.independence_group, COALESCE(l.counted_for_threshold, false) AS counted"
                    " FROM research_evidence e JOIN research_sources s ON s.id = e.source_id"
                    " LEFT JOIN niche_evidence_links l ON l.evidence_id = e.id AND l.niche_id = :n"
                    " WHERE e.subject_type = 'niche' AND e.subject_id = :n AND e.lifecycle_status = 'ACTIVE'"
                    " AND s.lifecycle_status = 'ACTIVE' AND e.excerpt IS NOT NULL ORDER BY e.created_at"
                ),
                {"n": niche_id},
            )
        )
        .mappings()
        .all()
    )
    run_ids = (
        (
            await session.execute(
                text("SELECT run_id FROM niche_run_links WHERE niche_id = :n ORDER BY created_at"), {"n": niche_id}
            )
        )
        .scalars()
        .all()
    )
    latest = (
        (
            await session.execute(
                text(
                    "SELECT e.*, w.version AS weights_version FROM niche_evaluations e JOIN scoring_weights_versions w"
                    " ON w.id = e.weights_version_id WHERE e.id = :e"
                ),
                {"e": n["latest_evaluation_id"]},
            )
        )
        .mappings()
        .first()
        if n["latest_evaluation_id"]
        else None
    )
    latest_dto = evaluation_dto(latest) if latest else None
    persona = {a: persona_row.get(a) or dict(UNKNOWN_FINDING) for a in PERSONA_ATTRS}
    summary: dict[str, int] = {}
    for f in [*findings.values(), *persona.values()]:
        summary[f["status"]] = summary.get(f["status"], 0) + 1
    return {
        "id": str(n["id"]),
        "name": n["name"],
        "micro_niche": n["micro_niche"],
        "country": n["country"],
        "customer_group": n["customer_group"],
        "core_problem": n["core_problem"],
        "opportunity_score": latest_dto["opportunity_score"] if latest_dto else None,  # None → UNKNOWN trên giao diện
        "confidence_score": latest_dto["confidence_score"] if latest_dto else None,
        "coverage": latest_dto["coverage"] if latest_dto else None,
        "scoring_status": latest_dto["scoring_status"] if latest_dto else None,
        "evidence_status": n["evidence_status"],
        "verification_summary": summary,
        "monetization_status": n["monetization_status"],
        "risk_flags": list(n["risk_flags"] or []),
        "ai_recommendation": n["ai_recommendation"],
        "ai_recommendation_reason": n["ai_recommendation_reason"] or "",
        "owner_decision_reason": n["owner_decision_reason"],
        "decision_status": n["decision_status"],
        "has_possible_duplicate": False,
        "data_origin": n["data_origin"],
        "disclaimer_key": DISCLAIMER_KEY,
        "pain_points": [
            {
                "id": str(p["id"]),
                "title": p["title"],
                "description": p["description"] or "",
                "severity": p["severity"],
                "severity_reason": p["severity_reason"],
                "evidence_count": p["evidence_count"],
                "status": p["verification_status"],
            }
            for p in pps
        ],
        "persona": persona,
        "findings": findings,
        "competitors": [
            {
                "name": c["name"],
                "kind": c["kind"],
                "url": c["url"],
                "strengths": c["strengths"],
                "weaknesses": c["weaknesses"],
            }
            for c in comps
        ],
        "evidence": [
            {
                "id": str(e["id"]),
                "source_url": e["url"],
                "source_domain": e["registered_domain"],
                "excerpt": e["excerpt"],
                "collected_at": _iso(e["created_at"]),
                "published_at": None,
                "verification_status": e["verification_status"],
                "redaction_status": e["redaction_status"],
                "purpose": e["purpose"],
                "relevance": float(e["relevance"]) if e["relevance"] is not None else None,
                "quality": float(e["quality"]) if e["quality"] is not None else None,
                "independence_group": e["independence_group"] or "unlinked",
                "counted_for_threshold": bool(e["counted"]),
                "policy_verified_at": _iso(e["policy_verified_at"]),
                "data_origin": e["data_origin"],
            }
            for e in evidence
        ],
        "latest_evaluation": latest_dto,
        "opportunity_disclaimer_key": "discovery.opportunity.disclaimer",
        "run_ids": [str(r) for r in run_ids],
    }
