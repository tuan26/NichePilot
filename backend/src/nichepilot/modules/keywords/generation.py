"""Đầu vào và kiểm tra keyword (research R-01, R-03; FR-002, FR-005…FR-007, FR-009).

Keyword chỉ được sinh từ dữ liệu nội bộ có bằng chứng của ngách: pain point (E1), thuộc tính persona (E1) và sản phẩm
E2 chưa bị loại.
Mỗi keyword phải dẫn ≥ 1 nguồn gốc hợp lệ thuộc ngách; không có → bị loại. Keyword commercial cho sản phẩm được sinh
thêm bằng MẪU
xác định (không AI). Chỉ ĐỌC bảng E1/E2.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nichepilot.modules.discovery.risk import compliance_sensitive
from nichepilot.modules.keywords.normalize import dedup_key, length_class, normalize
from nichepilot.modules.keywords.schemas import PERSONA_ATTRIBUTES, KeywordsGenerateOutput

_TAG_PREFIX = re.compile(r"^(\[[^\]]*\]\s*)+")


def display_name(name: str) -> str:
    """Bỏ tiền tố nhãn kiểu `[MOCK DEMO]` khỏi tên dùng trong keyword (nhãn MOCK vẫn nằm ở `data_origin`)."""
    return _TAG_PREFIX.sub("", name).strip() or name


@dataclass(frozen=True)
class PainPointInput:
    id: str
    title: str
    evidence_ids: frozenset[str]
    evidence_groups: int


@dataclass(frozen=True)
class PersonaInput:
    attribute: str
    value: str
    evidence_ids: frozenset[str]


@dataclass(frozen=True)
class ProductInput:
    id: str
    name: str
    fit_level: int | None
    fit_reason: str
    evidence_ids: frozenset[str]
    pain_point_ids: frozenset[str]
    brand_restricted: bool
    compliance_sensitive: bool


@dataclass(frozen=True)
class GenerationInputs:
    niche_id: str
    micro_niche: str
    segment: str
    country: str
    niche_compliance_sensitive: bool
    pain_points: dict[str, PainPointInput]
    persona: dict[str, PersonaInput]
    products: dict[str, ProductInput]


@dataclass
class CandidateKeyword:
    text: str
    keyword_type: str
    intent: str
    intent_reason: str
    origins: list[dict[str, Any]]
    fit: dict[str, Any] | None
    risk_flags: list[str] = field(default_factory=list)

    @property
    def dedup_key(self) -> str:
        return dedup_key(self.text)

    @property
    def length_class(self) -> str:
        return length_class(self.text)


@dataclass
class GenerationValidation:
    kept: list[CandidateKeyword] = field(default_factory=list)
    rejected: int = 0
    reasons: dict[str, int] = field(default_factory=dict)

    def reject(self, reason: str) -> None:
        self.rejected += 1
        self.reasons[reason] = self.reasons.get(reason, 0) + 1


def allowed_evidence(origins: Iterable[Mapping[str, Any]], inputs: GenerationInputs) -> set[str]:
    """Bằng chứng được phép dẫn cho mức `fit`: bằng chứng ACTIVE của chính các nguồn gốc keyword."""
    out: set[str] = set()
    for o in origins:
        if o["origin_type"] == "PAIN_POINT" and o.get("pain_point_id") in inputs.pain_points:
            out |= inputs.pain_points[o["pain_point_id"]].evidence_ids
        elif o["origin_type"] == "PRODUCT" and o.get("product_id") in inputs.products:
            out |= inputs.products[o["product_id"]].evidence_ids
        elif o["origin_type"] == "PERSONA" and o.get("persona_attribute") in inputs.persona:
            out |= inputs.persona[o["persona_attribute"]].evidence_ids
    return out


def risk_flags(text_value: str, origins: Iterable[Mapping[str, Any]], inputs: GenerationInputs) -> list[str]:
    flags: set[str] = set()
    norm = f" {normalize(text_value)} "
    for p in inputs.products.values():
        if p.brand_restricted and f" {normalize(display_name(p.name))} " in norm:
            flags.add("BRAND_TERM")  # chương trình cấm đấu thầu từ khóa thương hiệu (E2 `ad_restrictions`)
    product_ids = {o.get("product_id") for o in origins if o["origin_type"] == "PRODUCT"}
    if (
        inputs.niche_compliance_sensitive
        or compliance_sensitive(text_value)
        or any(inputs.products[p].compliance_sensitive for p in product_ids if p in inputs.products)
    ):
        flags.add("COMPLIANCE_SENSITIVE")
    return sorted(flags)


def _valid_origin(o: Mapping[str, Any], inputs: GenerationInputs) -> bool:
    kind = o["origin_type"]
    if kind == "PAIN_POINT":
        return (
            o.get("pain_point_id") in inputs.pain_points and not o.get("product_id") and not o.get("persona_attribute")
        )
    if kind == "PRODUCT":
        return o.get("product_id") in inputs.products and not o.get("pain_point_id") and not o.get("persona_attribute")
    return (
        o.get("persona_attribute") in inputs.persona
        and o.get("persona_attribute") in PERSONA_ATTRIBUTES
        and not o.get("pain_point_id")
        and not o.get("product_id")
    )


def validate_generated(out: KeywordsGenerateOutput, inputs: GenerationInputs) -> GenerationValidation:
    """Giữ keyword có ≥ 1 nguồn gốc hợp lệ thuộc ngách (FR-005); `PRODUCT`/`COMPARISON` bắt buộc nguồn gốc sản phẩm
    (R-03)."""
    v = GenerationValidation()
    for kw in out.keywords:
        if not normalize(kw.text):
            v.reject("empty_text")
            continue
        origins = [o.model_dump() for o in kw.origins]
        if not all(_valid_origin(o, inputs) for o in origins):
            v.reject("invalid_origin")  # origin lạ / thuộc ngách khác → loại cả keyword (không đoán origin đúng)
            continue
        if kw.keyword_type in ("PRODUCT", "COMPARISON") and not any(o["origin_type"] == "PRODUCT" for o in origins):
            v.reject("product_type_without_product")
            continue
        v.kept.append(
            CandidateKeyword(
                text=" ".join(kw.text.split()),
                keyword_type=kw.keyword_type,
                intent=kw.intent,
                intent_reason=kw.intent_reason,
                origins=origins,
                fit=kw.fit.model_dump() if kw.fit.level is not None else None,
                risk_flags=risk_flags(kw.text, origins, inputs),
            )
        )
    return v


def commercial_keywords(inputs: GenerationInputs, templates: Iterable[str]) -> list[CandidateKeyword]:
    """Keyword commercial theo mẫu cho MỌI sản phẩm chưa bị loại (FR-007, SC-003) – không AI.

    Mức `fit` lấy từ mức `fit` đã kiểm của cặp (sản phẩm, ngách) ở E2 kèm chính bằng chứng đó (không tạo mức mới).
    """
    out: list[CandidateKeyword] = []
    products = sorted(inputs.products.values(), key=lambda p: display_name(p.name).lower())
    for i, prod in enumerate(products):
        name = display_name(prod.name)
        other = display_name(products[(i + 1) % len(products)].name) if len(products) > 1 else None
        for tpl in templates:
            if "{other}" in tpl and other is None:
                continue
            kw = tpl.replace("{product}", name).replace("{segment}", display_name(inputs.segment))
            if other is not None:
                kw = kw.replace("{other}", other)
            kw = " ".join(kw.split())
            if not normalize(kw) or len(kw) > 150:
                continue
            comparison = "{other}" in tpl or " vs " in f" {tpl} "
            origins: list[dict[str, Any]] = [
                {
                    "origin_type": "PRODUCT",
                    "product_id": prod.id,
                    "pain_point_id": None,
                    "persona_attribute": None,
                    "reason": "commercial_template",
                }
            ]
            fit = (
                {
                    "level": prod.fit_level,
                    "reason": prod.fit_reason or "e2_product_fit",
                    "evidence_ids": sorted(prod.evidence_ids),
                }
                if prod.fit_level is not None and prod.evidence_ids
                else None
            )
            out.append(
                CandidateKeyword(
                    text=kw,
                    keyword_type="COMPARISON" if comparison else "PRODUCT",
                    intent="TRANSACTIONAL" if "pricing" in tpl else "COMMERCIAL_INVESTIGATION",
                    intent_reason="template:" + tpl,
                    origins=origins,
                    fit=fit,
                    risk_flags=risk_flags(kw, origins, inputs),
                )
            )
    return out


def _persona_inputs(attributes: Mapping[str, Any]) -> dict[str, PersonaInput]:
    out: dict[str, PersonaInput] = {}
    for key in PERSONA_ATTRIBUTES:
        attr = attributes.get(key)
        if not isinstance(attr, dict) or attr.get("status") in (None, "UNKNOWN"):
            continue
        value = attr.get("value")
        if isinstance(value, list):
            value = ", ".join(str(x) for x in value)
        ids = frozenset(str(x) for x in attr.get("evidence_ids") or [])
        if value in (None, "") or not ids:
            continue
        out[key] = PersonaInput(key, str(value), ids)
    return out


async def load_inputs(session: AsyncSession, niche_id: uuid.UUID) -> GenerationInputs:
    """Đọc đầu vào keyword của ngách (FR-002) – chỉ bằng chứng ACTIVE; sản phẩm `REJECTED`/đã gộp bị bỏ."""
    niche = (
        await session.execute(
            text("SELECT id, micro_niche, customer_group, country, risk_flags FROM niches WHERE id = :n"),
            {"n": niche_id},
        )
    ).one()
    pain: dict[str, PainPointInput] = {}
    for pid, title, ids, groups in (
        await session.execute(
            text(
                "SELECT p.id, p.title, coalesce(array_agg(e.id::text) FILTER (WHERE e.id IS NOT NULL), '{}'),"
                " count(DISTINCT l.independence_group) FILTER (WHERE e.id IS NOT NULL)"
                " FROM pain_points p LEFT JOIN niche_evidence_links l ON l.pain_point_id = p.id"
                " LEFT JOIN research_evidence e ON e.id = l.evidence_id AND e.lifecycle_status = 'ACTIVE'"
                " WHERE p.niche_id = :n GROUP BY p.id, p.title, p.created_at ORDER BY p.created_at, p.id"
            ),
            {"n": niche_id},
        )
    ).all():
        if ids:
            pain[str(pid)] = PainPointInput(str(pid), title, frozenset(ids), int(groups or 0))
    persona_row = (
        await session.execute(text("SELECT attributes FROM buyer_personas WHERE niche_id = :n"), {"n": niche_id})
    ).scalar_one_or_none()
    persona = _persona_inputs(dict(persona_row or {}))
    active = await _active_set(session, persona)
    persona = {
        k: PersonaInput(k, p.value, p.evidence_ids & active) for k, p in persona.items() if p.evidence_ids & active
    }

    products: dict[str, ProductInput] = {}
    rows = (
        await session.execute(
            text(
                "SELECT p.id, p.name, pn.ai_levels, pn.id, p.risk_flags FROM product_niches pn"
                " JOIN products p ON p.id = pn.product_id WHERE pn.niche_id = :n AND pn.decision_status <> 'REJECTED'"
                " AND p.merged_into_id IS NULL ORDER BY p.name, p.id"
            ),
            {"n": niche_id},
        )
    ).all()
    for prod_id, name, levels, pair_id, flags in rows:
        fit = dict((levels or {}).get("fit") or {})
        fit_ids = {str(x) for x in fit.get("evidence_ids") or []}
        link_rows = (
            await session.execute(
                text(
                    "SELECT l.pain_point_id, l.evidence_id FROM product_pain_point_links l"
                    " JOIN research_evidence e ON e.id = l.evidence_id AND e.lifecycle_status = 'ACTIVE'"
                    " WHERE l.product_niche_id = :pn"
                ),
                {"pn": pair_id},
            )
        ).all()
        fit_active = fit_ids & await _active_ids(session, fit_ids)
        restricted = (
            await session.execute(
                text(
                    "SELECT 1 FROM research_evidence e JOIN product_programs pp ON pp.program_id = e.subject_id"
                    " WHERE pp.product_id = :p AND e.subject_type = 'affiliate_program' AND e.claim_key ="
                    " 'ad_restrictions'"
                    " AND e.lifecycle_status = 'ACTIVE' AND e.value -> 'codes' ? 'NO_BRAND_BIDDING' LIMIT 1"
                ),
                {"p": prod_id},
            )
        ).first()
        level = fit.get("level") if fit_active else None
        products[str(prod_id)] = ProductInput(
            id=str(prod_id),
            name=name,
            fit_level=int(level) if isinstance(level, int) else None,
            fit_reason=str(fit.get("reason") or ""),
            evidence_ids=frozenset(fit_active | {str(r[1]) for r in link_rows}),
            pain_point_ids=frozenset(str(r[0]) for r in link_rows),
            brand_restricted=restricted is not None,
            compliance_sensitive="COMPLIANCE_SENSITIVE" in (flags or []),
        )
    segment = persona["segment"].value if "segment" in persona else niche.customer_group
    return GenerationInputs(
        niche_id=str(niche.id),
        micro_niche=niche.micro_niche,
        segment=segment,
        country=niche.country,
        niche_compliance_sensitive="COMPLIANCE_SENSITIVE" in (niche.risk_flags or []),
        pain_points=pain,
        persona=persona,
        products=products,
    )


async def _active_ids(session: AsyncSession, ids: Iterable[str]) -> set[str]:
    wanted = [uuid.UUID(x) for x in ids if _is_uuid(x)]
    if not wanted:
        return set()
    rows = await session.execute(
        text("SELECT id FROM research_evidence WHERE id = ANY(:i) AND lifecycle_status = 'ACTIVE'"), {"i": wanted}
    )
    return {str(x) for x in rows.scalars()}


async def _active_set(session: AsyncSession, persona: Mapping[str, PersonaInput]) -> set[str]:
    ids: set[str] = set()
    for p in persona.values():
        ids |= p.evidence_ids
    return await _active_ids(session, ids)


def _is_uuid(x: str) -> bool:
    try:
        uuid.UUID(str(x))
    except ValueError:
        return False
    return True
