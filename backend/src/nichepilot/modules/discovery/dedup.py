"""Phát hiện ngách trùng/tương đồng (T113; scoring-rubric §5; FR-022, FR-029, SC-010) – mã xác định, AI không quyết
định.

`sim = w_problem · token_set_ratio(core_problem) + w_customer · token_set_ratio(customer_group)` trên dạng chuẩn hóa
(chữ thường, bỏ
từ dừng, cắt hậu tố đơn giản), chỉ so ngách cùng `country` và `data_origin`, chưa bị gộp.
- `sim ≥ duplicate` **và** cả hai thành phần ≥ `component_min` → trùng chắc chắn: dùng lại ngách cũ (liên kết lượt mới).
  Điều kiện thành phần (bổ sung 2026-11-21) chặn gộp nhầm hai nhóm khách hàng khác nhau có cùng vấn đề (vd. designer
  ↔ photographer).
- `possible ≤ sim` (hoặc đạt `duplicate` nhưng thiếu điều kiện thành phần) → `niche_similarity POSSIBLE` chờ chủ sở
  hữu, không tự gộp.
Không dùng lời gọi AI `discovery.normalize` (chuẩn hóa xác định đủ cho bộ kiểm thử; tiết kiệm chi phí).
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from rapidfuzz import fuzz
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

Verdict = Literal["DUPLICATE", "POSSIBLE", "DISTINCT"]
STOPWORDS = frozenset(
    "the a an of for and to in with their who on at from any each every do does not dont t s is are by or".split()
)
TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class DedupParams:
    duplicate: float = 0.85
    possible: float = 0.60
    w_problem: float = 0.6
    w_customer: float = 0.4
    component_min: float = 0.80

    @classmethod
    def from_json(cls, d: Mapping[str, Any] | None) -> DedupParams:
        d = dict(d or {})
        return cls(
            duplicate=float(d.get("duplicate", cls.duplicate)),
            possible=float(d.get("possible", cls.possible)),
            w_problem=float(d.get("w_problem", cls.w_problem)),
            w_customer=float(d.get("w_customer", cls.w_customer)),
            component_min=float(d.get("component_min", cls.component_min)),
        )


@dataclass(frozen=True)
class Similarity:
    score: float
    problem: float
    customer: float


def normalize(s: str) -> str:
    out: list[str] = []
    for tok in TOKEN_RE.findall(s.lower().replace("'", "")):
        if tok in STOPWORDS:
            continue
        for suf in ("ing", "es", "s"):
            if len(tok) > 4 and tok.endswith(suf):
                tok = tok[: -len(suf)]
                break
        out.append(tok)
    return " ".join(out)


def similarity(a: Mapping[str, str], b: Mapping[str, str], params: DedupParams | None = None) -> Similarity:
    p = params or DedupParams()
    sp = fuzz.token_set_ratio(normalize(a["core_problem"]), normalize(b["core_problem"])) / 100
    sc = fuzz.token_set_ratio(normalize(a["customer_group"]), normalize(b["customer_group"])) / 100
    return Similarity(round(p.w_problem * sp + p.w_customer * sc, 3), sp, sc)


def classify(sim: Similarity, params: DedupParams | None = None) -> Verdict:
    p = params or DedupParams()
    if sim.score >= p.duplicate and sim.problem >= p.component_min and sim.customer >= p.component_min:
        return "DUPLICATE"
    if sim.score >= p.possible:
        return "POSSIBLE"
    return "DISTINCT"


@dataclass(frozen=True)
class Match:
    niche_id: uuid.UUID
    similarity: Similarity
    verdict: Verdict


async def find_matches(
    session: AsyncSession,
    *,
    project_id: uuid.UUID,
    country: str,
    data_origin: str,
    customer_group: str,
    core_problem: str,
    params: DedupParams,
    exclude: uuid.UUID | None = None,
) -> list[Match]:
    rows = (
        await session.execute(
            text(
                "SELECT id, customer_group, core_problem FROM niches WHERE project_id = :p AND country = :c"
                " AND data_origin = :o AND merged_into_id IS NULL AND (CAST(:x AS uuid) IS NULL OR id <> :x)"
                " ORDER BY created_at LIMIT 5000"
            ),
            {"p": project_id, "c": country, "o": data_origin, "x": exclude},
        )
    ).all()
    me = {"customer_group": customer_group, "core_problem": core_problem}
    out: list[Match] = []
    for r in rows:
        sim = similarity(me, {"customer_group": r.customer_group, "core_problem": r.core_problem}, params)
        verdict = classify(sim, params)
        if verdict != "DISTINCT":
            out.append(Match(uuid.UUID(str(r.id)), sim, verdict))
    return sorted(out, key=lambda m: (-m.similarity.score, str(m.niche_id)))


async def record_possible(session: AsyncSession, a: uuid.UUID, b: uuid.UUID, score: float) -> None:
    lo, hi = sorted((a, b), key=str)
    await session.execute(
        text(
            "INSERT INTO niche_similarity (niche_a_id, niche_b_id, score) VALUES (:a, :b, :s)"
            " ON CONFLICT (niche_a_id, niche_b_id) DO NOTHING"
        ),
        {"a": lo, "b": hi, "s": round(score, 3)},
    )


def similarity_dto(r: Any) -> dict[str, Any]:
    return {
        "id": str(r["id"]),
        "niche_a_id": str(r["niche_a_id"]),
        "niche_b_id": str(r["niche_b_id"]),
        "niche_a_name": r.get("a_name"),
        "niche_b_name": r.get("b_name"),
        "score": float(r["score"]),
        "status": r["status"],
    }


SIM_SELECT = (
    "SELECT s.*, a.name AS a_name, b.name AS b_name FROM niche_similarity s JOIN niches a ON a.id = s.niche_a_id"
    " JOIN niches b ON b.id = s.niche_b_id"
)


async def list_similarities(
    session: AsyncSession, *, status: str = "POSSIBLE", niche_id: uuid.UUID | None = None
) -> list[dict[str, Any]]:
    where = " WHERE s.status = :st"
    params: dict[str, Any] = {"st": status}
    if niche_id is not None:
        where += " AND (s.niche_a_id = :n OR s.niche_b_id = :n)"
        params["n"] = niche_id
    rows = (await session.execute(text(SIM_SELECT + where + " ORDER BY s.score DESC"), params)).mappings().all()
    return [similarity_dto(r) for r in rows]
