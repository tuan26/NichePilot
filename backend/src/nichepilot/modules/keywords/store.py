"""Lưu dữ liệu E3 trong transaction do caller quản lý (data-model §2; FR-004, FR-008, FR-012, FR-013, FR-016).

Mọi thao tác idempotent: chạy lại/tiếp tục sau sự cố không tạo keyword/cluster/SERP/trang đối thủ trùng (SC-004).
Không có hàm nào ghi
Search Volume/CPC/KD (FR-009).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nichepilot.modules.keywords.clustering import cluster_key, primary_origin
from nichepilot.modules.keywords.generation import CandidateKeyword
from nichepilot.modules.keywords.normalize import normalize
from nichepilot.modules.keywords.serp import diff_results


@dataclass(frozen=True)
class PageExcerpt:
    evidence_id: str
    source_id: str
    excerpt: str
    url: str
    registered_domain: str | None
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
                "INSERT INTO keyword_runs (project_id, job_id, niche_id, params, metrics, data_origin)"
                " VALUES (:p, :j, :n, CAST(:pa AS jsonb), '{}'::jsonb, :o) ON CONFLICT (job_id) DO NOTHING RETURNING id"
            ),
            {"p": project_id, "j": job_id, "n": niche_id, "pa": json.dumps(params), "o": origin},
        )
    ).scalar_one_or_none()
    if rid is not None:
        return uuid.UUID(str(rid))
    got = (await session.execute(text("SELECT id FROM keyword_runs WHERE job_id = :j"), {"j": job_id})).scalar_one()
    return uuid.UUID(str(got))


async def upsert_keyword(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    niche_id: uuid.UUID,
    kw: CandidateKeyword,
    market: str,
    origin: str,
    run_id: uuid.UUID | None,
) -> tuple[uuid.UUID, bool]:
    """Thêm keyword hoặc gộp vào bản trùng (cùng `dedup_key`); gộp nguồn gốc và cờ rủi ro. Trả (id, mới tạo?)."""
    ai_levels = {"fit": kw.fit} if kw.fit else {}
    row = (
        await session.execute(
            text(
                "INSERT INTO keywords (project_id, niche_id, text, normalized, dedup_key, language, market,"
                " keyword_type,"
                " length_class, intent, intent_reason, risk_flags, ai_levels, first_run_id, data_origin)"
                " VALUES (:p, :n, :t, :norm, :k, 'en', :m, :kt, :lc, :i, :ir, :rf, CAST(:lv AS jsonb), :run, :o)"
                " ON CONFLICT (project_id, niche_id, data_origin, dedup_key) DO NOTHING RETURNING id"
            ),
            {
                "p": project_id,
                "n": niche_id,
                "t": kw.text,
                "norm": normalize(kw.text),
                "k": kw.dedup_key,
                "m": market if len(market) == 2 and market.isalpha() and market.isupper() else "US",
                "kt": kw.keyword_type,
                "lc": kw.length_class,
                "i": kw.intent,
                "ir": kw.intent_reason or None,
                "rf": kw.risk_flags,
                "lv": json.dumps(ai_levels, default=str),
                "run": run_id,
                "o": origin,
            },
        )
    ).scalar_one_or_none()
    created = row is not None
    if row is None:
        row = (
            await session.execute(
                text(
                    "SELECT id FROM keywords WHERE project_id = :p AND niche_id = :n AND data_origin = :o AND dedup_key"
                    " = :k"
                ),
                {"p": project_id, "n": niche_id, "o": origin, "k": kw.dedup_key},
            )
        ).scalar_one()
        await session.execute(
            text(
                "UPDATE keywords SET risk_flags = coalesce((SELECT array_agg(DISTINCT f ORDER BY f) FROM"
                " unnest(risk_flags || CAST(:rf AS text[])) f), '{}'),"
                " ai_levels = CASE WHEN ai_levels ? 'fit' OR CAST(:lv AS text) = '{}' THEN ai_levels ELSE CAST(:lv AS"
                " jsonb) END,"
                " updated_at = now() WHERE id = :id"
            ),
            {"rf": kw.risk_flags, "lv": json.dumps(ai_levels, default=str), "id": row},
        )
    kid = uuid.UUID(str(row))
    for o in kw.origins:
        await session.execute(
            text(
                "INSERT INTO keyword_origins (keyword_id, origin_type, pain_point_id, product_id, persona_attribute,"
                " reason)"
                " VALUES (:k, :t, :pp, :pr, :pa, :r) ON CONFLICT DO NOTHING"
            ),
            {
                "k": kid,
                "t": o["origin_type"],
                "pp": o.get("pain_point_id"),
                "pr": o.get("product_id"),
                "pa": o.get("persona_attribute"),
                "r": (o.get("reason") or None),
            },
        )
    return kid, created


async def keyword_origins(session: AsyncSession, keyword_ids: Sequence[uuid.UUID]) -> dict[str, list[dict[str, Any]]]:
    rows = (
        await session.execute(
            text(
                "SELECT keyword_id, origin_type, pain_point_id, product_id, persona_attribute, reason FROM"
                " keyword_origins"
                " WHERE keyword_id = ANY(:ids) ORDER BY created_at, id"
            ),
            {"ids": list(keyword_ids)},
        )
    ).all()
    out: dict[str, list[dict[str, Any]]] = {}
    for kid, t, pp, pr, pa, r in rows:
        out.setdefault(str(kid), []).append(
            {
                "origin_type": t,
                "pain_point_id": str(pp) if pp else None,
                "product_id": str(pr) if pr else None,
                "persona_attribute": pa,
                "reason": r,
            }
        )
    return out


async def assign_clusters(session: AsyncSession, niche_id: uuid.UUID, origin: str) -> list[uuid.UUID]:
    """Gán mỗi keyword (cùng `data_origin`) vào đúng một cluster theo nguồn gốc chính + intent (idempotent)."""
    kws = (
        await session.execute(
            text(
                "SELECT k.id, k.intent, k.project_id FROM keywords k WHERE k.niche_id = :n AND k.data_origin = :o"
                " ORDER BY k.created_at, k.id"
            ),
            {"n": niche_id, "o": origin},
        )
    ).all()
    origins = await keyword_origins(session, [r[0] for r in kws])
    touched: set[uuid.UUID] = set()
    for kid, intent, project_id in kws:
        ors = origins.get(str(kid)) or []
        if not ors:
            continue
        key = cluster_key(ors, intent)
        kind, ref = primary_origin(ors)
        cid = (
            await session.execute(
                text(
                    "INSERT INTO keyword_clusters (project_id, niche_id, cluster_key, intent, pain_point_id,"
                    " product_id,"
                    " data_origin) VALUES (:p, :n, :k, :i, :pp, :pr, :o)"
                    " ON CONFLICT (niche_id, data_origin, cluster_key) DO UPDATE SET updated_at ="
                    " keyword_clusters.updated_at"
                    " RETURNING id"
                ),
                {
                    "p": project_id,
                    "n": niche_id,
                    "k": key,
                    "i": intent,
                    "pp": ref if kind == "PAIN_POINT" else None,
                    "pr": ref if kind == "PRODUCT" else None,
                    "o": origin,
                },
            )
        ).scalar_one()
        cid = uuid.UUID(str(cid))
        touched.add(cid)
        await session.execute(
            text("UPDATE keywords SET cluster_id = :c WHERE id = :k AND cluster_id IS DISTINCT FROM :c"),
            {"c": cid, "k": kid},
        )
    return sorted(touched, key=str)


async def set_primary(session: AsyncSession, cluster_id: uuid.UUID, keyword_id: str) -> None:
    await session.execute(
        text(
            "UPDATE keyword_clusters SET primary_keyword_id = :k, updated_at = now() WHERE id = :c"
            " AND primary_keyword_id IS DISTINCT FROM :k"
        ),
        {"k": uuid.UUID(keyword_id), "c": cluster_id},
    )


async def merge_insights(session: AsyncSession, cluster_id: uuid.UUID, patch: Mapping[str, Any]) -> None:
    await session.execute(
        text("UPDATE keyword_clusters SET insights = insights || CAST(:p AS jsonb), updated_at = now() WHERE id = :c"),
        {"p": json.dumps(dict(patch), default=str, ensure_ascii=False), "c": cluster_id},
    )


async def record_serp(
    session: AsyncSession,
    *,
    keyword_id: uuid.UUID,
    results: list[dict[str, Any]],
    source_policy_id: uuid.UUID | None,
    job_id: uuid.UUID | None,
    origin: str,
) -> tuple[int, bool]:
    """Phiên bản SERP mới chỉ khi lần đầu hoặc kết quả đổi (R-09). Trả (phiên bản hiện hành, có tạo mới?)."""
    last = (
        await session.execute(
            text("SELECT version, results FROM serp_observations WHERE keyword_id = :k ORDER BY version DESC LIMIT 1"),
            {"k": keyword_id},
        )
    ).first()
    if last is not None and not diff_results(last[1], results):
        return int(last[0]), False
    version = 1 if last is None else int(last[0]) + 1
    changes = {} if last is None else diff_results(last[1], results)
    await session.execute(
        text(
            "INSERT INTO serp_observations (keyword_id, version, results, source_policy_id, collected_at, changes,"
            " job_id,"
            " data_origin) VALUES (:k, :v, CAST(:r AS jsonb), :sp, :at, CAST(:c AS jsonb), :j, :o)"
            " ON CONFLICT (keyword_id, version) DO NOTHING"
        ),
        {
            "k": keyword_id,
            "v": version,
            "r": json.dumps(results, ensure_ascii=False),
            "sp": source_policy_id,
            "at": datetime.now(UTC),
            "c": json.dumps(changes),
            "j": job_id,
            "o": origin,
        },
    )
    return version, True


async def upsert_competitor_page(
    session: AsyncSession,
    *,
    keyword_id: uuid.UUID,
    url: str,
    domain: str,
    evidence_id: str,
    summary: Mapping[str, Any],
    origin: str,
) -> None:
    await session.execute(
        text(
            "INSERT INTO competitor_pages (keyword_id, url, domain, evidence_id, summary, data_origin)"
            " VALUES (:k, :u, :d, :e, CAST(:s AS jsonb), :o) ON CONFLICT (keyword_id, url) DO UPDATE"
            " SET evidence_id = EXCLUDED.evidence_id, summary = EXCLUDED.summary, updated_at = now()"
        ),
        {
            "k": keyword_id,
            "u": url,
            "d": domain,
            "e": uuid.UUID(evidence_id),
            "s": json.dumps(dict(summary), ensure_ascii=False),
            "o": origin,
        },
    )


async def page_excerpts(
    session: AsyncSession, run_id: uuid.UUID, evidence_ids: list[str] | None = None
) -> list[PageExcerpt]:
    """Trích đoạn trang ACTIVE + REDACTED của lượt (đọc lại ngay trước khi dùng – xóa giữa chừng được tôn trọng)."""
    rows = (
        await session.execute(
            text(
                "SELECT e.id, e.source_id, e.excerpt, s.url, s.registered_domain, e.data_origin FROM research_evidence"
                " e"
                " JOIN research_sources s ON s.id = e.source_id WHERE e.subject_type = 'keyword_run' AND e.subject_id ="
                " :r"
                " AND e.lifecycle_status = 'ACTIVE' AND e.redaction_status = 'REDACTED' AND e.excerpt IS NOT NULL"
                " ORDER BY e.created_at, e.id"
            ),
            {"r": run_id},
        )
    ).all()
    out = [PageExcerpt(str(r[0]), str(r[1]), r[2], r[3], r[4], r[5]) for r in rows]
    if evidence_ids is not None:
        wanted = set(evidence_ids)
        out = [p for p in out if p.evidence_id in wanted]
    return out
