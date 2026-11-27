"""Đánh giá keyword – NƠI DUY NHẤT ghi `keyword_evaluations` (internal-interfaces §1; FR-017…FR-020; scoring-rubric).

Ngữ cảnh chấm điểm được nạp THEO LÔ (vài truy vấn cho cả danh sách): nguồn gốc, bằng chứng ACTIVE của pain point/sản
phẩm/persona gốc,
SERP mới nhất, trang đối thủ. Không gọi AI: mức `fit` lấy lại từ `keywords.ai_levels`. Bỏ qua khi trùng
`evidence_fingerprint` của đánh
giá gần nhất (idempotent). Chỉ ĐỌC bảng E1/E2.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nichepilot.modules.keywords import weights as weights_mod
from nichepilot.modules.keywords.clustering import Member, choose_primary, cluster_scores
from nichepilot.modules.keywords.scoring import criteria as cr
from nichepilot.modules.keywords.scoring.confidence import ConfidenceInputs, compute_confidence
from nichepilot.modules.keywords.scoring.opportunity import compute_opportunity
from nichepilot.modules.keywords.serp import forum_qa_count
from nichepilot.modules.keywords.store import keyword_origins, set_primary


@dataclass
class KeywordContext:
    keyword_id: uuid.UUID
    niche_id: uuid.UUID
    intent: str
    keyword_type: str
    ai_levels: dict[str, Any]
    data_origin: str
    origins: list[dict[str, Any]]
    origin_pain_points: set[str] = field(default_factory=set)
    allowed: set[str] = field(default_factory=set)
    evidence_meta: dict[str, tuple[str | None, datetime | None]] = field(default_factory=dict)
    groups: int = 0
    serp: tuple[str, list[dict[str, Any]], datetime] | None = None
    pages: list[dict[str, Any]] = field(default_factory=list)

    def fingerprint(self, weights_id: uuid.UUID) -> str:
        payload = json.dumps(
            {
                "e": sorted(self.allowed),
                "s": self.serp[0] if self.serp else None,
                "p": sorted(f"{p['id']}:{p['evidence_active']}:{p['updated_at']}" for p in self.pages),
                "w": str(weights_id),
                "ai": self.ai_levels,
                "i": [self.intent, self.keyword_type],
            },
            sort_keys=True,
            default=str,
            ensure_ascii=False,
        )
        return hashlib.sha256(payload.encode()).hexdigest()


@dataclass(frozen=True)
class EvaluationOutcome:
    keyword_id: uuid.UUID
    created: bool
    opportunity: Decimal | None
    confidence: Decimal
    coverage: Decimal
    scoring_status: str


async def load_contexts(session: AsyncSession, keyword_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, KeywordContext]:
    ids = list(dict.fromkeys(keyword_ids))
    if not ids:
        return {}
    rows = (
        await session.execute(
            text(
                "SELECT id, niche_id, intent, keyword_type, ai_levels, data_origin FROM keywords WHERE id = ANY(:ids)"
            ),
            {"ids": ids},
        )
    ).all()
    origins = await keyword_origins(session, ids)
    ctx: dict[uuid.UUID, KeywordContext] = {
        r[0]: KeywordContext(r[0], r[1], r[2], r[3], dict(r[4] or {}), r[5], origins.get(str(r[0]), [])) for r in rows
    }
    # sản phẩm gốc → cặp (sản phẩm, ngách) E2: bằng chứng fit + liên kết pain point ACTIVE
    prod_keys = {
        (c.niche_id, o["product_id"]) for c in ctx.values() for o in c.origins if o["origin_type"] == "PRODUCT"
    }
    prod_ev: dict[tuple[Any, str], set[str]] = {}
    prod_pp: dict[tuple[Any, str], set[str]] = {}
    if prod_keys:
        niches = list({k[0] for k in prod_keys})
        for niche_id, product_id, levels, pp_id, link_eid in (
            await session.execute(
                text(
                    "SELECT pn.niche_id, pn.product_id, pn.ai_levels, l.pain_point_id, l.evidence_id FROM"
                    " product_niches pn"
                    " LEFT JOIN product_pain_point_links l ON l.product_niche_id = pn.id WHERE pn.niche_id = ANY(:n)"
                ),
                {"n": niches},
            )
        ).all():
            key = (niche_id, str(product_id))
            fit = dict((levels or {}).get("fit") or {})
            prod_ev.setdefault(key, set()).update(str(x) for x in fit.get("evidence_ids") or [])
            if link_eid is not None:
                prod_ev[key].add(str(link_eid))
                prod_pp.setdefault(key, set()).add(str(pp_id))
    for c in ctx.values():
        for o in c.origins:
            if o["origin_type"] == "PAIN_POINT":
                c.origin_pain_points.add(str(o["pain_point_id"]))
            elif o["origin_type"] == "PRODUCT":
                c.origin_pain_points |= prod_pp.get((c.niche_id, str(o["product_id"])), set())
    # bằng chứng pain point (E1 niche_evidence_links) + nhóm nguồn độc lập
    all_pp = list({p for c in ctx.values() for p in c.origin_pain_points})
    pp_ev: dict[str, list[tuple[str, str | None]]] = {}
    if all_pp:
        for pp_id, eid, group in (
            await session.execute(
                text(
                    "SELECT l.pain_point_id, l.evidence_id, l.independence_group FROM niche_evidence_links l"
                    " WHERE l.pain_point_id = ANY(:p)"
                ),
                {"p": [uuid.UUID(x) for x in all_pp]},
            )
        ).all():
            pp_ev.setdefault(str(pp_id), []).append((str(eid), group))
    # persona gốc
    persona_ev: dict[Any, dict[str, list[str]]] = {}
    persona_niches = list({c.niche_id for c in ctx.values() if any(o["origin_type"] == "PERSONA" for o in c.origins)})
    if persona_niches:
        for niche_id, attrs in (
            await session.execute(
                text("SELECT niche_id, attributes FROM buyer_personas WHERE niche_id = ANY(:n)"), {"n": persona_niches}
            )
        ).all():
            persona_ev[niche_id] = {
                k: [str(x) for x in (v or {}).get("evidence_ids") or []]
                for k, v in dict(attrs or {}).items()
                if isinstance(v, dict)
            }
    candidate: dict[uuid.UUID, set[str]] = {}
    for kid, c in ctx.items():
        ev: set[str] = set()
        for o in c.origins:
            if o["origin_type"] == "PRODUCT":
                ev |= prod_ev.get((c.niche_id, str(o["product_id"])), set())
            elif o["origin_type"] == "PERSONA":
                ev |= set(persona_ev.get(c.niche_id, {}).get(str(o["persona_attribute"]), []))
        for pp in c.origin_pain_points:
            ev |= {e for e, _ in pp_ev.get(pp, [])}
        candidate[kid] = ev
    all_ev = list({e for s in candidate.values() for e in s})
    meta: dict[str, tuple[str | None, datetime | None]] = {}
    if all_ev:
        for eid, dom, created in (
            await session.execute(
                text(
                    "SELECT e.id, s.registered_domain, e.created_at FROM research_evidence e"
                    " LEFT JOIN research_sources s ON s.id = e.source_id"
                    " WHERE e.id = ANY(:i) AND e.lifecycle_status = 'ACTIVE'"
                ),
                {"i": [uuid.UUID(x) for x in all_ev if _is_uuid(x)]},
            )
        ).all():
            meta[str(eid)] = (dom, created)
    for kid, c in ctx.items():
        c.allowed = {e for e in candidate[kid] if e in meta}
        c.evidence_meta = {e: meta[e] for e in c.allowed}
        c.groups = len({g or e for pp in c.origin_pain_points for e, g in pp_ev.get(pp, []) if e in meta})
    # SERP mới nhất
    for kid, sid, results, collected in (
        await session.execute(
            text(
                "SELECT DISTINCT ON (keyword_id) keyword_id, id, results, collected_at FROM serp_observations"
                " WHERE keyword_id = ANY(:ids) ORDER BY keyword_id, version DESC"
            ),
            {"ids": ids},
        )
    ).all():
        if kid in ctx:
            ctx[kid].serp = (str(sid), list(results or []), collected)
    # trang đối thủ (chỉ trang có bằng chứng ACTIVE được dùng)
    for kid, pid, url, dom, summary, active, created, updated in (
        await session.execute(
            text(
                "SELECT c.keyword_id, c.id, c.url, c.domain, c.summary, (e.lifecycle_status = 'ACTIVE'), e.created_at,"
                " c.updated_at FROM competitor_pages c LEFT JOIN research_evidence e ON e.id = c.evidence_id"
                " WHERE c.keyword_id = ANY(:ids) ORDER BY c.url"
            ),
            {"ids": ids},
        )
    ).all():
        if kid in ctx:
            ctx[kid].pages.append(
                {
                    "id": str(pid),
                    "url": url,
                    "domain": dom,
                    "summary": dict(summary or {}),
                    "evidence_active": bool(active),
                    "created_at": created,
                    "updated_at": updated,
                }
            )
    return ctx


def _is_uuid(x: str) -> bool:
    try:
        uuid.UUID(str(x))
    except ValueError:
        return False
    return True


def score(c: KeywordContext, w: weights_mod.WeightsVersion) -> dict[str, Any]:
    """Tính 5 tiêu chí, Opportunity/Coverage, Confidence – mã thuần trên ngữ cảnh đã nạp."""
    rubric = dict(w.rubric or {})
    results = c.serp[1] if c.serp else None
    pages = [p for p in c.pages if p["evidence_active"]]
    main_pp = c.origin_pain_points
    uncovering = [p["url"] for p in pages if not set(p["summary"].get("covered_pain_point_ids") or []) & main_pp]
    crit = {
        "fit": cr.fit(c.ai_levels.get("fit"), has_valid_origin=bool(c.origins), allowed_evidence=c.allowed),
        "intent_value": cr.intent_value(c.intent, c.keyword_type, rubric),
        "competition": cr.competition(results, uncovering_urls=uncovering, rubric=rubric),
        "content_gap": cr.content_gap(
            main_pp, [p["summary"].get("covered_pain_point_ids") or [] for p in pages] or None, rubric
        ),
        "demand": cr.demand(c.groups, forum_qa_count(results), rubric),
    }
    opp = compute_opportunity(crit, w.weights, w.coverage_min)
    now = datetime.now(UTC)
    dates = [d for _, d in c.evidence_meta.values() if d is not None] + [
        p["created_at"] for p in pages if p["created_at"]
    ]
    if c.serp:
        dates.append(c.serp[2])
    domains = {d for d, _ in c.evidence_meta.values() if d} | {
        str(r.get("domain")) for r in results or [] if r.get("domain")
    }
    observed = sum(1 for k in ("competition", "content_gap", "demand") if crit[k].status == "OBSERVED")
    conf, comp = compute_confidence(
        ConfidenceInputs(
            has_serp=bool(results),
            source_domains=len(domains),
            ages_days=[max(0.0, (now - d).total_seconds() / 86400) for d in dates],
            observed_criteria=observed,
            coverage=float(opp.coverage),
        ),
        w.confidence_params,
    )
    return {"criteria": crit, "opp": opp, "confidence": conf, "components": comp}


async def evaluate_keywords(
    session: AsyncSession, keyword_ids: Sequence[uuid.UUID], *, run_id: uuid.UUID | None = None, without_ai: bool = True
) -> list[EvaluationOutcome]:
    w = await weights_mod.active(session)
    ctxs = await load_contexts(session, keyword_ids)
    latest = await _latest(session, list(ctxs))
    out: list[EvaluationOutcome] = []
    for kid, c in ctxs.items():
        fp = c.fingerprint(w.id)
        last = latest.get(kid)
        if last is not None and last["fp"] == fp:
            out.append(EvaluationOutcome(kid, False, last["o"], last["c"], last["cov"], last["s"]))
            continue
        s = score(c, w)
        opp = s["opp"]
        missing = sorted(opp.missing)
        await session.execute(
            text(
                "INSERT INTO keyword_evaluations (keyword_id, weights_version_id, opportunity_score, confidence_score,"
                " coverage, scoring_status, criteria, confidence_components, missing, evidence_fingerprint,"
                " computed_without_ai, run_id, data_origin) VALUES (:k, :w, :o, :c, :cov, :s, CAST(:cr AS jsonb),"
                " CAST(:cc AS jsonb), :m, :fp, :nai, :run, :org)"
            ),
            {
                "k": kid,
                "w": w.id,
                "o": opp.opportunity,
                "c": s["confidence"],
                "cov": opp.coverage,
                "s": opp.scoring_status,
                "cr": json.dumps({k: v.as_json() for k, v in s["criteria"].items()}, default=str),
                "cc": json.dumps(s["components"], default=str),
                "m": missing,
                "fp": fp,
                "nai": without_ai,
                "run": run_id,
                "org": c.data_origin,
            },
        )
        out.append(EvaluationOutcome(kid, True, opp.opportunity, s["confidence"], opp.coverage, opp.scoring_status))
    return out


async def _latest(session: AsyncSession, ids: list[uuid.UUID]) -> dict[uuid.UUID, dict[str, Any]]:
    if not ids:
        return {}
    rows = (
        await session.execute(
            text(
                "SELECT DISTINCT ON (keyword_id) keyword_id, evidence_fingerprint, opportunity_score, confidence_score,"
                " coverage, scoring_status FROM keyword_evaluations WHERE keyword_id = ANY(:ids)"
                " ORDER BY keyword_id, created_at DESC, id DESC"
            ),
            {"ids": ids},
        )
    ).all()
    return {r[0]: {"fp": r[1], "o": r[2], "c": r[3], "cov": r[4], "s": r[5]} for r in rows}


async def stale_keywords(session: AsyncSession, keyword_ids: Sequence[uuid.UUID]) -> list[uuid.UUID]:
    """Keyword có đánh giá gần nhất không khớp dữ liệu/trọng số hiện tại (tính theo lô – R-06 E2)."""
    if not keyword_ids:
        return []
    w = await weights_mod.active(session)
    ctxs = await load_contexts(session, keyword_ids)
    latest = await _latest(session, list(ctxs))
    return [kid for kid, c in ctxs.items() if latest.get(kid, {}).get("fp") != c.fingerprint(w.id)]


async def refresh_clusters(session: AsyncSession, cluster_ids: Sequence[uuid.UUID]) -> None:
    """Cập nhật keyword chính của cluster từ đánh giá mới nhất (mã xác định)."""
    for cid in cluster_ids:
        members = await cluster_members(session, cid)
        if members:
            await set_primary(session, cid, choose_primary(members))


async def cluster_members(session: AsyncSession, cluster_id: uuid.UUID) -> list[Member]:
    rows = (
        await session.execute(
            text(
                "SELECT k.id, k.text, k.length_class, ev.opportunity_score, ev.confidence_score FROM keywords k"
                " LEFT JOIN LATERAL (SELECT opportunity_score, confidence_score FROM keyword_evaluations e"
                " WHERE e.keyword_id = k.id ORDER BY e.created_at DESC, e.id DESC LIMIT 1) ev ON true"
                " WHERE k.cluster_id = :c ORDER BY k.created_at, k.id"
            ),
            {"c": cluster_id},
        )
    ).all()
    return [Member(str(r[0]), r[1], r[2], r[3], r[4]) for r in rows]


async def cluster_score(session: AsyncSession, cluster_id: uuid.UUID) -> tuple[Decimal | None, Decimal | None, int]:
    return cluster_scores(await cluster_members(session, cluster_id))
