"""Đánh giá cặp (sản phẩm, ngách) – NƠI DUY NHẤT ghi `product_evaluations` (internal-interfaces §1; FR-026…FR-029a;
R-06).

Đọc bằng chứng ACTIVE → gộp thuộc tính → trạng thái chương trình → readiness → 5 tiêu chí → Opportunity/Coverage →
Confidence → khuyến
nghị theo rubric §5. Bỏ qua khi kết quả trùng đánh giá gần nhất (cùng `evidence_fingerprint`). Không gọi AI: mức AI
(`fit`, `price_fit`,
mention) được truyền vào hoặc lấy lại từ `product_niches.ai_levels`. Chỉ ĐỌC bảng E1.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nichepilot.modules.products import weights as weights_mod
from nichepilot.modules.products.attributes import (
    PRODUCT_KEYS,
    PROGRAM_KEYS,
    REQUIRED_PRODUCT,
    REQUIRED_PROGRAM,
    AttrEvidence,
    ResolvedAttribute,
    resolve_all,
)
from nichepilot.modules.products.programs import ProgramView, best_program, program_status
from nichepilot.modules.products.readiness import readiness
from nichepilot.modules.products.scoring import criteria as cr
from nichepilot.modules.products.scoring.confidence import ConfidenceInputs, compute_confidence
from nichepilot.modules.products.scoring.opportunity import compute_opportunity

EMPTY = ResolvedAttribute("none", "UNKNOWN", None)


def final_recommendation(
    ai_decision: str | None, *, readiness: str, fit_valid: bool, scoring_status: str
) -> tuple[str, str | None]:
    """scoring-rubric §5 / FR-028a: SELECT chỉ được giữ khi READY_TO_PROMOTE ∧ fit hợp lệ ∧ SCORED – hoa hồng cao
    không đủ."""
    if ai_decision == "REJECT":
        return "REJECT", None
    if ai_decision != "SELECT":
        return "UNKNOWN", None
    if readiness != "READY_TO_PROMOTE":
        return "UNKNOWN", "NOT_READY_TO_PROMOTE"
    if not fit_valid:
        return "UNKNOWN", "FIT_UNKNOWN"
    if scoring_status != "SCORED":
        return "UNKNOWN", "INSUFFICIENT_SCORING_DATA"
    return "SELECT", None


@dataclass(frozen=True)
class EvaluationOutcome:
    evaluation_id: uuid.UUID
    created: bool
    opportunity: Decimal | None
    confidence: Decimal
    coverage: Decimal
    scoring_status: str
    readiness: str


async def load_attr_evidence(session: AsyncSession, subject_type: str, subject_id: uuid.UUID) -> list[AttrEvidence]:
    rows = (
        await session.execute(
            text(
                "SELECT e.id, e.claim_key, e.value, e.verification_status, s.url, s.registered_domain, e.excerpt,"
                " e.created_at, e.verified_at FROM research_evidence e"
                " LEFT JOIN research_sources s ON s.id = e.source_id"
                " WHERE e.subject_type = :t AND e.subject_id = :i AND e.lifecycle_status = 'ACTIVE'"
                " AND e.value IS NOT NULL"
                " ORDER BY e.created_at, e.id"
            ),
            {"t": subject_type, "i": subject_id},
        )
    ).all()
    return [
        AttrEvidence(str(r[0]), r[1], dict(r[2]), r[3], r[4], r[5], r[6], r[7], r[8])
        for r in rows
        if isinstance(r[2], dict)
    ]


async def program_views(
    session: AsyncSession, product_id: uuid.UUID, *, cheapest: float | None, rubric: Mapping[str, Any]
) -> tuple[list[ProgramView], list[AttrEvidence]]:
    progs = (
        await session.execute(
            text(
                "SELECT p.id, p.name, p.operator_domain, p.verification_status FROM affiliate_programs p"
                " JOIN product_programs pp ON pp.program_id = p.id WHERE pp.product_id = :p ORDER BY p.created_at, p.id"
            ),
            {"p": product_id},
        )
    ).all()
    views: list[ProgramView] = []
    used: list[AttrEvidence] = []
    for pid, name, op_domain, stored_status in progs:
        ev = await load_attr_evidence(session, "affiliate_program", pid)
        used += ev
        attrs = resolve_all(PROGRAM_KEYS, ev)
        has_op = bool(op_domain) and any(e.registered_domain == op_domain for e in ev)
        status = program_status(attrs, has_operator_source=has_op)
        if status != stored_status:  # trạng thái chương trình luôn tính lại bằng mã từ bằng chứng ACTIVE (FR-018)
            await session.execute(
                text("UPDATE affiliate_programs SET verification_status = :s, updated_at = now() WHERE id = :i"),
                {"s": status, "i": pid},
            )
        level = cr.affiliate(attrs["commission"], attrs["cookie_days"], cheapest=cheapest, rubric=rubric).level
        views.append(ProgramView(str(pid), name, status, attrs, level))
    return views, used


def _fingerprint(ids: Sequence[str], weights_id: uuid.UUID, ai_levels: Mapping[str, Any]) -> str:
    payload = json.dumps(
        {"e": sorted(set(ids)), "w": str(weights_id), "ai": ai_levels}, sort_keys=True, default=str, ensure_ascii=False
    )
    return hashlib.sha256(payload.encode()).hexdigest()


async def current_fingerprint(session: AsyncSession, product_niche_id: uuid.UUID) -> str | None:
    """Fingerprint của tập bằng chứng ACTIVE hiện tại – so với đánh giá gần nhất để biết cần tính lại không (R-06)."""
    pair = (
        await session.execute(
            text("SELECT product_id, ai_levels FROM product_niches WHERE id = :i"), {"i": product_niche_id}
        )
    ).first()
    if pair is None:
        return None
    w = await weights_mod.active(session)
    ids = await _active_ids(session, product_niche_id, pair[0])
    return _fingerprint(ids, w.id, dict(pair[1] or {}))


async def _active_ids(session: AsyncSession, product_niche_id: uuid.UUID, product_id: uuid.UUID) -> list[str]:
    rows = (
        await session.execute(
            text(
                "SELECT e.id FROM research_evidence e WHERE e.lifecycle_status = 'ACTIVE' AND ("
                " (e.subject_type = 'product' AND e.subject_id = :p)"
                " OR (e.subject_type = 'affiliate_program' AND e.subject_id IN"
                "     (SELECT program_id FROM product_programs WHERE product_id = :p))"
                " OR e.id IN (SELECT evidence_id FROM product_pain_point_links WHERE product_niche_id = :pn))"
            ),
            {"p": product_id, "pn": product_niche_id},
        )
    ).scalars()
    return [str(x) for x in rows]


async def evaluate_pair(
    session: AsyncSession,
    product_niche_id: uuid.UUID,
    *,
    ai_levels: Mapping[str, Any] | None = None,
    ai_decision: tuple[str, str] | None = None,
    run_id: uuid.UUID | None = None,
) -> EvaluationOutcome:
    pair = (
        await session.execute(
            text(
                "SELECT pn.product_id, pn.niche_id, pn.persona_match, pn.ai_levels, pn.ai_recommendation,"
                " pn.ai_recommendation_reason, pn.data_origin, n.country, p.official_domain, p.risk_flags"
                " FROM product_niches pn JOIN niches n ON n.id = pn.niche_id JOIN products p ON p.id = pn.product_id"
                " WHERE pn.id = :i FOR UPDATE OF pn"
            ),
            {"i": product_niche_id},
        )
    ).one()
    (
        product_id,
        niche_id,
        persona_match,
        stored_levels,
        stored_rec,
        stored_reason,
        origin,
        country,
        official_domain,
        p_flags,
    ) = pair
    levels: dict[str, Any] = dict(ai_levels) if ai_levels is not None else dict(stored_levels or {})
    if ai_levels is not None:
        persona_match = str(levels.get("persona_match") or persona_match)
    w = await weights_mod.active(session)
    rubric = dict(w.rubric or {})

    product_ev = await load_attr_evidence(session, "product", product_id)
    pattrs = resolve_all(PRODUCT_KEYS, product_ev)
    cheapest = cr.cheapest_price(pattrs["price"])
    views, prog_ev = await program_views(session, product_id, cheapest=cheapest, rubric=rubric)
    best = best_program([v for v in views if v.status in ("VERIFIED", "PARTIAL")]) or best_program(views)
    battrs: Mapping[str, ResolvedAttribute] = best.attrs if best else {}
    status, flags = readiness(views, country)

    links = (
        (
            await session.execute(
                text(
                    "SELECT l.evidence_id FROM product_pain_point_links l"
                    " JOIN research_evidence e ON e.id = l.evidence_id"
                    " WHERE l.product_niche_id = :i AND e.lifecycle_status = 'ACTIVE'"
                ),
                {"i": product_niche_id},
            )
        )
        .scalars()
        .all()
    )
    link_ids = [str(x) for x in links]
    persona = (
        await session.execute(text("SELECT attributes FROM buyer_personas WHERE niche_id = :n"), {"n": niche_id})
    ).scalar_one_or_none()
    atp = (persona or {}).get("ability_to_pay") or {}
    ability_known = (
        isinstance(atp, dict) and atp.get("status") not in (None, "UNKNOWN") and atp.get("value") not in (None, "")
    )

    used = [*product_ev, *prog_ev]
    active_ids = {e.evidence_id for e in used} | set(link_ids)
    mentions = [
        (e.registered_domain or "", str(e.value.get("sentiment")))
        for e in product_ev
        if e.claim_key == "third_party_mention"
    ]
    criteria = {
        "fit": cr.fit(
            levels.get("fit"),
            has_pain_links=bool(link_ids),
            persona_match=persona_match,
            active_ids=active_ids,
            rubric=rubric,
        ),
        "affiliate": cr.affiliate(
            battrs.get("commission", EMPTY), battrs.get("cookie_days", EMPTY), cheapest=cheapest, rubric=rubric
        ),
        "eligibility": cr.eligibility(
            battrs.get("vn_eligibility", EMPTY),
            battrs.get("promotion_regions", EMPTY),
            battrs.get("ad_restrictions", EMPTY),
            country=country,
            rubric=rubric,
        ),
        "quality": cr.quality(
            pattrs["official_website"], pattrs["feature"], mentions, official_domain=official_domain, rubric=rubric
        ),
        "price_fit": cr.price_fit(
            levels.get("price_fit"),
            price_has_data=pattrs["price"].has_data,
            ability_to_pay_known=ability_known,
            active_ids=active_ids,
        ),
    }
    opp = compute_opportunity(criteria, w.weights, w.coverage_min)

    required = {**{k: pattrs[k] for k in REQUIRED_PRODUCT}, **{k: battrs.get(k, EMPTY) for k in REQUIRED_PROGRAM}}
    now = datetime.now(UTC)
    ages = [max(0.0, (now - e.collected_at).total_seconds() / 86400) for e in used if e.collected_at is not None]
    conf, comp = compute_confidence(
        ConfidenceInputs(
            required_total=len(required),
            required_verified=sum(1 for a in required.values() if a.verified),
            source_domains=len({e.registered_domain for e in used if e.registered_domain}),
            ages_days=ages,
            conflicting=sum(1 for a in required.values() if a.status == "CONFLICTING"),
            with_data_or_conflicting=sum(1 for a in required.values() if a.status != "UNKNOWN"),
            coverage=float(opp.coverage),
        ),
        w.confidence_params,
    )
    missing = sorted(
        [k for k, a in required.items() if a.status == "UNKNOWN"] + [k for k, c in criteria.items() if c.level is None]
    )

    decision, decision_reason = ai_decision if ai_decision is not None else (stored_rec, stored_reason)
    rec, code = final_recommendation(
        decision, readiness=status, fit_valid=criteria["fit"].level is not None, scoring_status=opp.scoring_status
    )
    rec_reason = decision_reason if code is None else code
    pair_flags = sorted({*flags, *(["COMPLIANCE_SENSITIVE"] if "COMPLIANCE_SENSITIVE" in (p_flags or []) else [])})
    await session.execute(
        text(
            "UPDATE product_niches SET readiness_status = :r, risk_flags = :f, persona_match = :pm,"
            " ai_levels = CAST(:lv AS jsonb), ai_recommendation = :rec, ai_recommendation_reason = :rr,"
            " updated_at = now()"
            " WHERE id = :i"
        ),
        {
            "r": status,
            "f": pair_flags,
            "pm": persona_match,
            "lv": json.dumps(levels, default=str),
            "rec": rec,
            "rr": rec_reason,
            "i": product_niche_id,
        },
    )

    fingerprint = _fingerprint([*active_ids], w.id, levels)
    last = (
        await session.execute(
            text(
                "SELECT id, evidence_fingerprint, opportunity_score, confidence_score, coverage, scoring_status"
                " FROM product_evaluations WHERE product_niche_id = :i ORDER BY created_at DESC, id DESC LIMIT 1"
            ),
            {"i": product_niche_id},
        )
    ).first()
    if last is not None and last[1] == fingerprint:
        return EvaluationOutcome(last[0], False, last[2], last[3], last[4], last[5], status)
    eval_id = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO product_evaluations (id, product_niche_id, weights_version_id, opportunity_score,"
            " confidence_score,"
            " coverage, scoring_status, criteria, confidence_components, missing, evidence_fingerprint,"
            " computed_without_ai, run_id, data_origin) VALUES (:id, :pn, :w, :o, :c, :cov, :s, CAST(:cr AS jsonb),"
            " CAST(:cc AS jsonb), :m, :fp, :nai, :run, :org)"
        ),
        {
            "id": eval_id,
            "pn": product_niche_id,
            "w": w.id,
            "o": opp.opportunity,
            "c": conf,
            "cov": opp.coverage,
            "s": opp.scoring_status,
            "cr": json.dumps({k: c.as_json() for k, c in criteria.items()}, default=str),
            "cc": json.dumps(comp, default=str),
            "m": missing,
            "fp": fingerprint,
            "nai": ai_levels is None,
            "run": run_id,
            "org": origin,
        },
    )
    return EvaluationOutcome(eval_id, True, opp.opportunity, conf, opp.coverage, opp.scoring_status, status)


async def stale_pairs(session: AsyncSession, pair_ids: Sequence[uuid.UUID]) -> list[uuid.UUID]:
    """Các cặp có đánh giá gần nhất KHÔNG khớp tập bằng chứng ACTIVE/trọng số/mức AI hiện tại (R-06) – tính theo lô
    (vài truy
    vấn cho cả danh sách, không theo từng cặp)."""
    if not pair_ids:
        return []
    ids = list(pair_ids)
    w = await weights_mod.active(session)
    pairs = (
        await session.execute(
            text("SELECT id, product_id, ai_levels FROM product_niches WHERE id = ANY(:ids)"), {"ids": ids}
        )
    ).all()
    products = list({r[1] for r in pairs})
    ev: dict[Any, set[str]] = {}
    for prod, eid in (
        await session.execute(
            text(
                "SELECT subject_id, id FROM research_evidence WHERE subject_type = 'product' AND subject_id = ANY(:p)"
                " AND lifecycle_status = 'ACTIVE' AND value IS NOT NULL"
            ),
            {"p": products},
        )
    ).all():
        ev.setdefault(prod, set()).add(str(eid))
    for prod, eid in (
        await session.execute(
            text(
                "SELECT pp.product_id, e.id FROM product_programs pp JOIN research_evidence e"
                " ON e.subject_type = 'affiliate_program' AND e.subject_id = pp.program_id"
                " AND e.lifecycle_status = 'ACTIVE' AND e.value IS NOT NULL WHERE pp.product_id = ANY(:p)"
            ),
            {"p": products},
        )
    ).all():
        ev.setdefault(prod, set()).add(str(eid))
    links: dict[Any, set[str]] = {}
    for pair, eid in (
        await session.execute(
            text(
                "SELECT l.product_niche_id, l.evidence_id FROM product_pain_point_links l JOIN research_evidence e"
                " ON e.id = l.evidence_id AND e.lifecycle_status = 'ACTIVE' WHERE l.product_niche_id = ANY(:ids)"
            ),
            {"ids": ids},
        )
    ).all():
        links.setdefault(pair, set()).add(str(eid))
    latest: dict[Any, Any] = dict(
        (
            await session.execute(
                text(
                    "SELECT DISTINCT ON (product_niche_id) product_niche_id, evidence_fingerprint FROM"
                    " product_evaluations"
                    " WHERE product_niche_id = ANY(:ids) ORDER BY product_niche_id, created_at DESC, id DESC"
                ),
                {"ids": ids},
            )
        ).all()
    )
    out: list[uuid.UUID] = []
    for pair, prod, levels in pairs:
        fp = _fingerprint([*ev.get(prod, set()), *links.get(pair, set())], w.id, dict(levels or {}))
        if latest.get(pair) != fp:
            out.append(pair)
    return out
