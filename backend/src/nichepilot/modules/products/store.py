"""Lưu dữ liệu E2 trong một transaction do caller quản lý (data-model §2–3; FR-005, FR-007, FR-015, FR-017).

Mọi thao tác idempotent: chạy lại/tiếp tục sau sự cố không tạo bản ghi trùng (SC-003). Giá trị thuộc tính là một dòng
`research_evidence` dẫn tới cùng nguồn (`source_id`) và trích đoạn ĐÃ CHE PII của bằng chứng trang
(`product_run/page_excerpt`).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nichepilot.modules.products.dedup import normalize_name, product_dedup_key, program_dedup_key


@dataclass(frozen=True)
class PageExcerpt:
    """Bằng chứng trang đã lưu (subject `product_run`) – nguồn để dẫn cho thuộc tính."""

    evidence_id: str
    source_id: str
    excerpt: str
    url: str
    registered_domain: str | None
    redaction_counts: dict[str, int]
    pii_engine: str | None
    data_origin: str


async def ensure_run(
    session: AsyncSession, *, job_id: uuid.UUID, niche_id: uuid.UUID, params: dict[str, Any], origin: str
) -> uuid.UUID:
    project_id = (
        await session.execute(text("SELECT project_id FROM agent_jobs WHERE id = :j"), {"j": job_id})
    ).scalar_one()
    rid = (
        await session.execute(
            text(
                "INSERT INTO product_runs (project_id, job_id, niche_id, params, metrics, data_origin)"
                " VALUES (:p, :j, :n, CAST(:pa AS jsonb), '{}'::jsonb, :o) ON CONFLICT (job_id) DO NOTHING RETURNING id"
            ),
            {"p": project_id, "j": job_id, "n": niche_id, "pa": json.dumps(params), "o": origin},
        )
    ).scalar_one_or_none()
    if rid is not None:
        return uuid.UUID(str(rid))
    return uuid.UUID(
        str((await session.execute(text("SELECT id FROM product_runs WHERE job_id = :j"), {"j": job_id})).scalar_one())
    )


async def upsert_product(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    origin: str,
    name: str,
    vendor: str | None,
    official_domain: str | None,
    official_url: str | None,
    category: str,
    risk_flags: list[str],
) -> uuid.UUID:
    """R-08: khóa theo tên miền chính thức, nếu không có thì theo tên. Sản phẩm cũ khớp tên được nâng cấp lên khóa tên
    miền;
    nếu cả hai đã tồn tại → bản theo tên được gộp vào bản theo tên miền (`merged_into_id`), giữ bằng chứng."""
    name_key = product_dedup_key(name, vendor, None)
    key = product_dedup_key(name, vendor, official_domain)
    params = {"p": project_id, "o": origin}
    by_key = (
        await session.execute(
            text("SELECT id FROM products WHERE project_id = :p AND data_origin = :o AND dedup_key = :k"),
            {**params, "k": key},
        )
    ).scalar_one_or_none()
    by_name = None
    if official_domain:
        by_name = (
            await session.execute(
                text(
                    "SELECT id FROM products WHERE project_id = :p AND data_origin = :o AND dedup_key = :k"
                    " AND merged_into_id IS NULL"
                ),
                {**params, "k": name_key},
            )
        ).scalar_one_or_none()
    if by_key is None and not official_domain:
        # chưa biết tên miền: sản phẩm cùng tên chuẩn hóa (và cùng nhà cung cấp nếu có) đã được nâng lên khóa
        # tên miền → dùng lại
        by_key = (
            await session.execute(
                text(
                    "SELECT id FROM products WHERE project_id = :p AND data_origin = :o AND normalized_name = :nn"
                    " AND merged_into_id IS NULL AND (CAST(:v AS text) IS NULL OR vendor IS NULL OR lower(vendor) ="
                    " lower(:v))"
                    " ORDER BY created_at LIMIT 1"
                ),
                {**params, "nn": normalize_name(name), "v": vendor},
            )
        ).scalar_one_or_none()
    if by_key is None and by_name is not None:
        await session.execute(
            text(
                "UPDATE products SET dedup_key = :k, official_domain = :d, official_url = coalesce(official_url, :u),"
                " updated_at = now() WHERE id = :i"
            ),
            {"k": key, "d": official_domain, "u": official_url, "i": by_name},
        )
        return uuid.UUID(str(by_name))
    if by_key is not None:
        if by_name is not None and by_name != by_key:
            await session.execute(
                text("UPDATE products SET merged_into_id = :t, updated_at = now() WHERE id = :i"),
                {"t": by_key, "i": by_name},
            )
        await session.execute(
            text(
                "UPDATE products SET vendor = coalesce(vendor, :v), official_url = coalesce(official_url, :u),"
                " risk_flags = (SELECT array(SELECT DISTINCT unnest(risk_flags || CAST(:f AS text[])))),"
                " category = CASE WHEN category = 'UNKNOWN' THEN :c ELSE category END, updated_at = now() WHERE id = :i"
            ),
            {"v": vendor, "u": official_url, "f": risk_flags, "c": category, "i": by_key},
        )
        return uuid.UUID(str(by_key))
    pid = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO products (id, project_id, name, normalized_name, vendor, official_domain, official_url,"
            " dedup_key,"
            " category, risk_flags, data_origin) VALUES (:id, :p, :n, :nn, :v, :d, :u, :k, :c, :f, :o)"
        ),
        {
            "id": pid,
            **params,
            "n": name[:200],
            "nn": normalize_name(name),
            "v": vendor,
            "d": official_domain,
            "u": official_url,
            "k": key,
            "c": category,
            "f": risk_flags,
        },
    )
    return pid


async def ensure_pair(
    session: AsyncSession, *, product_id: uuid.UUID, niche_id: uuid.UUID, run_id: uuid.UUID | None, origin: str
) -> uuid.UUID:
    pn = (
        await session.execute(
            text(
                "INSERT INTO product_niches (product_id, niche_id, first_run_id, data_origin) VALUES (:p, :n, :r, :o)"
                " ON CONFLICT (product_id, niche_id) DO NOTHING RETURNING id"
            ),
            {"p": product_id, "n": niche_id, "r": run_id, "o": origin},
        )
    ).scalar_one_or_none()
    if pn is not None:
        return uuid.UUID(str(pn))
    return uuid.UUID(
        str(
            (
                await session.execute(
                    text("SELECT id FROM product_niches WHERE product_id = :p AND niche_id = :n"),
                    {"p": product_id, "n": niche_id},
                )
            ).scalar_one()
        )
    )


async def add_pain_link(
    session: AsyncSession, *, pair_id: uuid.UUID, pain_point_id: uuid.UUID, evidence_id: uuid.UUID, status: str
) -> None:
    await session.execute(
        text(
            "INSERT INTO product_pain_point_links (product_niche_id, pain_point_id, evidence_id, verification_status)"
            " VALUES (:pn, :pp, :e, :s) ON CONFLICT DO NOTHING"
        ),
        {"pn": pair_id, "pp": pain_point_id, "e": evidence_id, "s": status},
    )


async def upsert_program(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    origin: str,
    name: str,
    operator_type: str,
    operator_name: str | None,
    operator_domain: str | None,
    terms_url: str | None,
) -> uuid.UUID:
    key = program_dedup_key(name, operator_domain, terms_url)
    pid = (
        await session.execute(
            text(
                "INSERT INTO affiliate_programs (project_id, name, operator_type, operator_name, operator_domain,"
                " terms_url,"
                " dedup_key, data_origin) VALUES (:p, :n, :t, :on, :od, :u, :k, :o)"
                " ON CONFLICT (project_id, data_origin, dedup_key) DO UPDATE SET updated_at = now() RETURNING id"
            ),
            {
                "p": project_id,
                "n": name[:200],
                "t": operator_type,
                "on": operator_name,
                "od": operator_domain,
                "u": terms_url,
                "k": key,
                "o": origin,
            },
        )
    ).scalar_one()
    return uuid.UUID(str(pid))


async def link_product_program(session: AsyncSession, product_id: uuid.UUID, program_id: uuid.UUID) -> None:
    await session.execute(
        text("INSERT INTO product_programs (product_id, program_id) VALUES (:a, :b) ON CONFLICT DO NOTHING"),
        {"a": product_id, "b": program_id},
    )


def _attr_hash(subject_id: uuid.UUID, claim_key: str, value: Any, source_id: str) -> str:
    raw = json.dumps([str(subject_id), claim_key, value, source_id], sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


async def add_attribute(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    subject_type: str,
    subject_id: uuid.UUID,
    claim_key: str,
    value: dict[str, Any],
    page: PageExcerpt,
    status: str,
    job_id: uuid.UUID | None,
) -> uuid.UUID | None:
    """Một giá trị thuộc tính = một bằng chứng dẫn tới trích đoạn trang (đã che PII). Trùng (cùng chủ thể, khóa, giá
    trị, nguồn)
    → bỏ qua (idempotent). Nội dung đã bị xóa (trích đoạn không còn ACTIVE) → không lưu."""
    active = (
        await session.execute(
            text("SELECT 1 FROM research_evidence WHERE id = :e AND lifecycle_status = 'ACTIVE'"),
            {"e": page.evidence_id},
        )
    ).first()
    if active is None:
        return None
    h = _attr_hash(subject_id, claim_key, value, page.source_id)
    dup = (
        await session.execute(
            text("SELECT id FROM research_evidence WHERE subject_id = :s AND claim_key = :k AND content_hash = :h"),
            {"s": subject_id, "k": claim_key, "h": h},
        )
    ).scalar_one_or_none()
    if dup is not None:
        return uuid.UUID(str(dup))
    eid = uuid.uuid4()
    await session.execute(
        text(
            "INSERT INTO research_evidence (id, project_id, source_id, subject_type, subject_id, claim_key, value,"
            " excerpt,"
            " verification_status, verified_at, collected_by_job_id, data_origin, redaction_status, redaction_counts,"
            " pii_engine, content_hash) VALUES (:id, :p, :src, :st, :sid, :k, CAST(:v AS jsonb), :ex, :vs,"
            " CASE WHEN :vs = 'VERIFIED' THEN now() END, :j, :o, 'REDACTED', CAST(:rc AS jsonb), :pe, :h)"
        ),
        {
            "id": eid,
            "p": project_id,
            "src": page.source_id,
            "st": subject_type,
            "sid": subject_id,
            "k": claim_key,
            "v": json.dumps(value),
            "ex": page.excerpt[:1000],
            "vs": status,
            "j": job_id,
            "o": page.data_origin,
            "rc": json.dumps(page.redaction_counts or {}),
            "pe": page.pii_engine,
            "h": h,
        },
    )
    return eid


async def page_excerpts(
    session: AsyncSession, run_id: uuid.UUID, evidence_ids: list[str] | None = None
) -> list[PageExcerpt]:
    """Trích đoạn trang ACTIVE + REDACTED của lượt (đọc lại ngay trước khi dùng – xóa giữa chừng được tôn trọng)."""
    rows = (
        await session.execute(
            text(
                "SELECT e.id, e.source_id, e.excerpt, s.url, s.registered_domain, e.redaction_counts, e.pii_engine,"
                " e.data_origin FROM research_evidence e JOIN research_sources s ON s.id = e.source_id"
                " WHERE e.subject_type = 'product_run' AND e.subject_id = :r AND e.lifecycle_status = 'ACTIVE'"
                " AND e.redaction_status = 'REDACTED' AND e.excerpt IS NOT NULL ORDER BY e.created_at, e.id"
            ),
            {"r": run_id},
        )
    ).all()
    out = [PageExcerpt(str(r[0]), str(r[1]), r[2], r[3], r[4], dict(r[5] or {}), r[6], r[7]) for r in rows]
    if evidence_ids is not None:
        wanted = set(evidence_ids)
        out = [p for p in out if p.evidence_id in wanted]
    return out
