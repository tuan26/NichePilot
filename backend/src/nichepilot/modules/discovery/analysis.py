"""Lưu kết quả phân tích ngách + đánh giá ngưỡng bằng chứng (US2: T080, T081; data-model `pain_points`,
`buyer_personas`,
`competitors`, `niche_findings`, `niche_evidence_links`, `niches.evidence_status`).

Nguyên tắc:
- Đầu ra AI chỉ được lưu sau `validate_extract`: mọi `evidence_ids` phải thuộc tập bằng chứng ĐÃ cung cấp – một ID lạ
  → loại
  TOÀN BỘ đầu ra (chống bịa nguồn). Trạng thái xác minh chuẩn hóa theo BR-02/FR-014.
- `evaluate_niche` là logic xác định (không AI): đọc lại bằng chứng hiện tại (bằng chứng đã xóa không được tính), cắt
  ID đã xóa
  khỏi kết luận (kết luận mất hết bằng chứng → `UNKNOWN`), gán nhóm độc lập + `counted_for_threshold`,
  `evidence_status`,
  `monetization_status` (đạt ngưỡng bằng chứng ≠ sinh lợi – FR-013d).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nichepilot.modules.discovery.evidence_rules import EvidenceItem, EvidenceRules, ThresholdResult, evaluate_threshold
from nichepilot.modules.discovery.schemas import ExtractOutput, FindingOut

PERSONA_ATTRS = ("segment", "context", "goals", "obstacles", "ability_to_pay")
FINDING_FIELDS = ("CURRENT_SOLUTIONS", "MARKET_GAPS", "POTENTIAL_PRODUCTS", "MONETIZATION", "CHANNELS", "RISKS")


class ExtractRejected(ValueError):
    """Đầu ra AI tham chiếu bằng chứng không được cung cấp (hoặc không hợp lệ) – không lưu gì."""


@dataclass(frozen=True)
class NormFinding:
    value: Any
    status: str
    evidence_ids: list[str]

    def as_json(self) -> dict[str, Any]:
        return {"value": self.value, "status": self.status, "evidence_ids": self.evidence_ids}


UNKNOWN = NormFinding(None, "UNKNOWN", [])


def _norm(text_: str) -> str:
    return " ".join(text_.lower().split())[:200]


def normalize_finding(f: FindingOut | None) -> NormFinding:
    """FR-013/FR-014/SC-004: mọi kết luận phải dẫn ≥ 1 bằng chứng, nếu không → UNKNOWN (không giá trị); UNKNOWN không
    giá trị;
    CONFLICTING lưu MỌI giá trị kèm nguồn (≥ 2 giá trị, nếu không → UNKNOWN – không tự chọn một giá trị)."""
    if f is None or f.status == "UNKNOWN":
        return UNKNOWN
    if f.status == "CONFLICTING":
        if len(f.conflicting_values) < 2:
            return UNKNOWN
        ids = sorted({i for cv in f.conflicting_values for i in cv.evidence_ids})
        values = [{"value": cv.value, "evidence_ids": cv.evidence_ids} for cv in f.conflicting_values]
        return NormFinding(values, "CONFLICTING", ids)
    if f.value is None or (isinstance(f.value, str | list | dict) and not f.value) or not f.evidence_ids:
        return UNKNOWN
    return NormFinding(f.value, f.status, list(dict.fromkeys(f.evidence_ids)))


def referenced_ids(out: ExtractOutput) -> set[str]:
    ids: set[str] = set()
    for pp in out.pain_points:
        ids.update(pp.evidence_ids)
    for c in out.competitors:
        ids.update(c.evidence_ids)
    groups: list[Any] = []
    if out.persona:
        groups += [getattr(out.persona, a) for a in PERSONA_ATTRS]
    if out.findings:
        groups += [getattr(out.findings, f) for f in FINDING_FIELDS]
    for f in groups:
        if f is not None:
            ids.update(f.evidence_ids)
            for cv in f.conflicting_values:
                ids.update(cv.evidence_ids)
    return ids


def validate_extract(out: ExtractOutput, allowed_ids: set[str]) -> None:
    unknown = referenced_ids(out) - allowed_ids
    if unknown:
        raise ExtractRejected(f"{len(unknown)} evidence_id không thuộc tập đã cung cấp")


async def save_extraction(
    session: AsyncSession, *, niche_id: uuid.UUID, out: ExtractOutput, data_origin: str
) -> dict[str, int]:
    """Lưu (idempotent theo UNIQUE) pain point, persona, findings, đối thủ và liên kết bằng chứng. Gọi SAU
    `validate_extract`."""
    n_pp = 0
    for pp in out.pain_points:
        ids = list(dict.fromkeys(pp.evidence_ids))
        if pp.status == "UNKNOWN" or not ids:  # kết luận không dẫn bằng chứng → không lưu (FR-013, SC-004)
            continue
        status = pp.status
        pp_id = (
            await session.execute(
                text(
                    "INSERT INTO pain_points (niche_id, title, normalized_title, description, severity,"
                    " severity_reason,"
                    " evidence_count, verification_status, data_origin) VALUES (:n, :t, :nt, :d, :sv, :sr, :c, :st, :o)"
                    " ON CONFLICT (niche_id, normalized_title) DO UPDATE SET description = EXCLUDED.description,"
                    " severity = EXCLUDED.severity, severity_reason = EXCLUDED.severity_reason,"
                    " verification_status = EXCLUDED.verification_status, updated_at = now() RETURNING id"
                ),
                {
                    "n": niche_id,
                    "t": pp.title[:200],
                    "nt": _norm(pp.title),
                    "d": pp.description,
                    "sv": pp.severity,
                    "sr": pp.severity_reason,
                    "c": len(ids),
                    "st": status,
                    "o": data_origin,
                },
            )
        ).scalar_one()
        n_pp += 1
        for eid in ids:
            await _link(session, niche_id, eid, "PAIN_POINT", data_origin, pain_point_id=pp_id)
    if out.persona is not None:
        attrs = {a: normalize_finding(getattr(out.persona, a)) for a in PERSONA_ATTRS}
        await session.execute(
            text(
                "INSERT INTO buyer_personas (niche_id, attributes, data_origin) VALUES (:n, CAST(:a AS jsonb), :o)"
                " ON CONFLICT (niche_id) DO UPDATE SET attributes = EXCLUDED.attributes, updated_at = now()"
            ),
            {"n": niche_id, "a": json.dumps({k: v.as_json() for k, v in attrs.items()}), "o": data_origin},
        )
        for f in attrs.values():
            for eid in f.evidence_ids:
                await _link(session, niche_id, eid, "PERSONA", data_origin)
    if out.findings is not None:
        purpose = {"MONETIZATION": "MONETIZATION", "CHANNELS": "CHANNEL"}
        for field_ in FINDING_FIELDS:
            f = normalize_finding(getattr(out.findings, field_))
            await _upsert_finding(session, niche_id, field_, f, data_origin)
            for eid in f.evidence_ids:
                await _link(session, niche_id, eid, purpose.get(field_, "SOLUTION"), data_origin)
    for c in out.competitors:
        await session.execute(
            text(
                "INSERT INTO competitors (niche_id, name, normalized_name, kind, url, strengths, weaknesses,"
                " data_origin)"
                " VALUES (:n, :nm, :nn, :k, :u, CAST(:s AS jsonb), CAST(:w AS jsonb), :o)"
                " ON CONFLICT (niche_id, normalized_name) DO UPDATE SET kind = EXCLUDED.kind, url = EXCLUDED.url,"
                " strengths = EXCLUDED.strengths, weaknesses = EXCLUDED.weaknesses, updated_at = now()"
            ),
            {
                "n": niche_id,
                "nm": c.name[:200],
                "nn": _norm(c.name),
                "k": c.kind,
                "u": c.url,
                "s": json.dumps(c.strengths),
                "w": json.dumps(c.weaknesses),
                "o": data_origin,
            },
        )
        for eid in c.evidence_ids:
            await _link(session, niche_id, eid, "COMPETITOR", data_origin)
    return {"pain_points": n_pp, "competitors": len(out.competitors)}


async def _upsert_finding(
    session: AsyncSession, niche_id: uuid.UUID, field_: str, f: NormFinding, data_origin: str
) -> None:
    await session.execute(
        text(
            "INSERT INTO niche_findings (niche_id, field, value, verification_status, evidence_ids, data_origin)"
            " VALUES (:n, :f, CAST(:v AS jsonb), :st, CAST(:ids AS uuid[]), :o) ON CONFLICT (niche_id, field) DO UPDATE"
            " SET value = EXCLUDED.value, verification_status = EXCLUDED.verification_status,"
            " evidence_ids = EXCLUDED.evidence_ids, updated_at = now()"
        ),
        {
            "n": niche_id,
            "f": field_,
            "v": None if f.value is None else json.dumps(f.value),
            "st": f.status,
            "ids": f.evidence_ids,
            "o": data_origin,
        },
    )


async def _link(
    session: AsyncSession,
    niche_id: uuid.UUID,
    evidence_id: str,
    purpose: str,
    data_origin: str,
    *,
    pain_point_id: uuid.UUID | None = None,
) -> None:
    """Một liên kết / (ngách, bằng chứng); PAIN_POINT được ghi trước nên ưu tiên. Nhóm độc lập gán ở
    `evaluate_niche`."""
    await session.execute(
        text(
            "INSERT INTO niche_evidence_links (niche_id, evidence_id, purpose, pain_point_id, independence_group,"
            " data_origin) VALUES (:n, :e, :p, :pp, 'pending', :o) ON CONFLICT (niche_id, evidence_id) DO NOTHING"
        ),
        {"n": niche_id, "e": evidence_id, "p": purpose, "pp": pain_point_id, "o": data_origin},
    )


async def save_assessment(session: AsyncSession, *, niche_id: uuid.UUID, assessments: list[Any]) -> int:
    """Ghi relevance/quality/copy_suspected (nhận định AI – INFERRED) vào liên kết đã có. Không tạo liên kết mới."""
    n = 0
    for a in assessments:
        res = await session.execute(
            text(
                "UPDATE niche_evidence_links SET relevance = :r, quality = :q, copy_suspected = :c,"
                " assessment_reason = :why, updated_at = now() WHERE niche_id = :n AND evidence_id = CAST(:e AS uuid)"
            ),
            {
                "r": a.relevance,
                "q": a.quality,
                "c": a.copy_suspected,
                "why": a.reason[:500],
                "n": niche_id,
                "e": a.evidence_id,
            },
        )
        n += int(getattr(res, "rowcount", 0) or 0)
    return n


async def active_rules(session: AsyncSession) -> EvidenceRules:
    data = (
        await session.execute(text("SELECT evidence_rules FROM scoring_weights_versions WHERE is_active"))
    ).scalar_one()
    return EvidenceRules.from_json(data)


async def evaluate_niche(
    session: AsyncSession, niche_id: uuid.UUID, *, rules: EvidenceRules | None = None
) -> ThresholdResult:
    """Đánh giá lại ngưỡng bằng chứng của MỘT ngách từ dữ liệu hiện tại (idempotent, không AI – FR-013b/c/d/e)."""
    rules = rules or await active_rules(session)
    niche = (
        await session.execute(
            text("SELECT data_origin, risk_flags FROM niches WHERE id = :n FOR UPDATE"), {"n": niche_id}
        )
    ).one()
    rows = (
        (
            await session.execute(
                text(
                    "SELECT l.evidence_id, l.purpose, l.relevance, l.quality, l.copy_suspected, e.excerpt,"
                    " e.created_at AS collected_at, e.verification_status, e.redaction_status, e.lifecycle_status,"
                    " e.data_origin, e.content_hash, s.url, s.registered_domain, s.simhash"
                    " FROM niche_evidence_links l JOIN research_evidence e ON e.id = l.evidence_id"
                    " LEFT JOIN research_sources s ON s.id = e.source_id WHERE l.niche_id = :n"
                ),
                {"n": niche_id},
            )
        )
        .mappings()
        .all()
    )
    items = [
        EvidenceItem(
            evidence_id=str(r["evidence_id"]),
            source_url=r["url"] if r["lifecycle_status"] == "ACTIVE" else None,
            excerpt=r["excerpt"],
            collected_at=r["collected_at"],
            verification_status=r["verification_status"],
            redaction_status=r["redaction_status"],
            lifecycle_status=r["lifecycle_status"],
            purpose=r["purpose"],
            relevance=float(r["relevance"]) if r["relevance"] is not None else None,
            quality=float(r["quality"]) if r["quality"] is not None else None,
            copy_suspected=bool(r["copy_suspected"]),
            data_origin=r["data_origin"],
            registered_domain=r["registered_domain"],
            source_simhash=r["simhash"],
            content_hash=r["content_hash"],
        )
        for r in rows
    ]
    result = evaluate_threshold(items, origin=niche.data_origin, rules=rules)
    for it in items:
        await session.execute(
            text(
                "UPDATE niche_evidence_links SET independence_group = :g, counted_for_threshold = :c, updated_at ="
                " now()"
                " WHERE niche_id = :n AND evidence_id = CAST(:e AS uuid)"
            ),
            {
                "g": result.groups.get(it.evidence_id, "erased"),
                "c": it.evidence_id in result.counted_ids,
                "n": niche_id,
                "e": it.evidence_id,
            },
        )
    erased = {it.evidence_id for it in items if it.lifecycle_status != "ACTIVE"}
    await _prune_erased(session, niche_id, erased)
    monetization = await _monetization_status(session, niche_id)
    flags = [f for f in (niche.risk_flags or []) if f != "MONETIZATION_RISK"]
    if monetization != "SIGNALS_FOUND":
        flags.append("MONETIZATION_RISK")  # FR-010: không tìm thấy chương trình phù hợp → cờ rủi ro
    await session.execute(
        text(
            "UPDATE niches SET evidence_status = :s, monetization_status = :m, risk_flags = CAST(:f AS text[]),"
            " updated_at = now() WHERE id = :n"
        ),
        {"s": result.status, "m": monetization, "f": sorted(set(flags)), "n": niche_id},
    )
    return result


async def _prune_erased(session: AsyncSession, niche_id: uuid.UUID, erased: set[str]) -> None:
    """Bằng chứng đã xóa không còn hỗ trợ kết luận nào; kết luận không còn bằng chứng (đã từng có) → UNKNOWN
    (SC-004)."""
    await session.execute(
        text(
            "UPDATE pain_points p SET evidence_count = sub.c, verification_status = CASE WHEN sub.c = 0 AND"
            " sub.total > 0"
            " THEN 'UNKNOWN' ELSE p.verification_status END, updated_at = now() FROM (SELECT pp.id,"
            " count(l.id) FILTER (WHERE e.lifecycle_status = 'ACTIVE') AS c, count(l.id) AS total FROM pain_points pp"
            " LEFT JOIN niche_evidence_links l ON l.pain_point_id = pp.id LEFT JOIN research_evidence e"
            " ON e.id = l.evidence_id WHERE pp.niche_id = :n GROUP BY pp.id) sub WHERE p.id = sub.id"
        ),
        {"n": niche_id},
    )
    if not erased:
        return
    rows = (
        await session.execute(
            text("SELECT field, value, verification_status, evidence_ids FROM niche_findings WHERE niche_id = :n"),
            {"n": niche_id},
        )
    ).all()
    for field_, value, status, ids in rows:
        kept = [str(i) for i in ids if str(i) not in erased]
        if len(kept) == len(ids):
            continue
        if not kept:
            nf = UNKNOWN
        elif status == "CONFLICTING":
            vals = [
                {**v, "evidence_ids": [i for i in v["evidence_ids"] if i not in erased]}
                for v in value
                if any(i not in erased for i in v["evidence_ids"])
            ]
            nf = (
                NormFinding(vals, "CONFLICTING", kept)
                if len(vals) >= 2
                else NormFinding(vals[0]["value"], "VERIFIED", vals[0]["evidence_ids"])
            )
        else:
            nf = NormFinding(value, status, kept)
        await session.execute(
            text(
                "UPDATE niche_findings SET value = CAST(:v AS jsonb), verification_status = :st,"
                " evidence_ids = CAST(:ids AS uuid[]), updated_at = now() WHERE niche_id = :n AND field = :f"
            ),
            {
                "v": None if nf.value is None else json.dumps(nf.value),
                "st": nf.status,
                "ids": nf.evidence_ids,
                "n": niche_id,
                "f": field_,
            },
        )
    persona = (
        await session.execute(text("SELECT attributes FROM buyer_personas WHERE niche_id = :n"), {"n": niche_id})
    ).scalar_one_or_none()
    if persona:
        changed = False
        for attr, f in persona.items():
            ids = list(f.get("evidence_ids") or [])
            kept = [i for i in ids if i not in erased]
            if len(kept) != len(ids):
                changed = True
                persona[attr] = UNKNOWN.as_json() if not kept else {**f, "evidence_ids": kept}
        if changed:
            await session.execute(
                text(
                    "UPDATE buyer_personas SET attributes = CAST(:a AS jsonb), updated_at = now() WHERE niche_id = :n"
                ),
                {"a": json.dumps(persona), "n": niche_id},
            )


async def _monetization_status(session: AsyncSession, niche_id: uuid.UUID) -> str:
    row = (
        await session.execute(
            text(
                "SELECT verification_status, cardinality(evidence_ids) FROM niche_findings"
                " WHERE niche_id = :n AND field = 'MONETIZATION'"
            ),
            {"n": niche_id},
        )
    ).first()
    if row and row[0] in ("VERIFIED", "INFERRED") and int(row[1]) > 0:
        return "SIGNALS_FOUND"
    return "MONETIZATION_UNVERIFIED"


async def affected_niches(session: AsyncSession, evidence_ids: list[uuid.UUID]) -> list[uuid.UUID]:
    """Ngách có liên kết hoặc là chủ thể của các bằng chứng này (để tính lại sau khi xóa)."""
    if not evidence_ids:
        return []
    rows = (
        await session.execute(
            text(
                "SELECT niche_id FROM niche_evidence_links WHERE evidence_id = ANY(:e) UNION SELECT e.subject_id"
                " FROM research_evidence e JOIN niches n ON n.id = e.subject_id WHERE e.id = ANY(:e)"
                " AND e.subject_type = 'niche'"
            ),
            {"e": evidence_ids},
        )
    ).all()
    return sorted({uuid.UUID(str(r[0])) for r in rows}, key=str)
