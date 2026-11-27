"""Báo cáo keyword theo ngách (FR-026; FR-021; FR-027): JSON hoặc Markdown, VI/EN.

Gồm cluster xếp hạng, keyword (intent, độ dài, chỉ số kèm nguồn hoặc `UNKNOWN`), gap, kênh, strategy, nguồn SERP. MOCK
bị loại mặc định
(chỉ hiện khi `include_mock` – kèm cảnh báo). Không có số liệu nào ngoài DB.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nichepilot.modules.keywords.service import DISCLAIMER_KEY, cluster_detail, list_clusters

Lang = Literal["vi", "en"]
LABELS: dict[str, dict[str, str]] = {
    "vi": {
        "title": "Báo cáo keyword & audience",
        "niche": "Ngách",
        "generated": "Tạo lúc",
        "ranked": "Cluster xếp hạng",
        "needs_research": "Cần nghiên cứu thêm",
        "empty": "(không có cluster)",
        "keyword": "Keyword",
        "intent": "Intent",
        "length": "Độ dài",
        "volume": "Search Volume",
        "cpc": "CPC",
        "kd": "KD",
        "opportunity": "Opportunity",
        "confidence": "Confidence",
        "gaps": "Content gap",
        "channels": "Kênh tiếp cận",
        "strategy": "Content strategy",
        "sources": "Nguồn SERP",
        "mock": "Dữ liệu giả lập (MOCK) – không phải kết quả nghiên cứu thật.",
        "disclaimer": (
            "Keyword Opportunity Score là điểm ưu tiên nghiên cứu, không phải dự báo traffic hay doanh thu. Search"
            " Volume,"
            " CPC và KD là UNKNOWN khi không có nguồn dữ liệu keyword hợp lệ."
        ),
    },
    "en": {
        "title": "Keyword & audience report",
        "niche": "Niche",
        "generated": "Generated at",
        "ranked": "Ranked clusters",
        "needs_research": "Needs more research",
        "empty": "(no clusters)",
        "keyword": "Keyword",
        "intent": "Intent",
        "length": "Length",
        "volume": "Search Volume",
        "cpc": "CPC",
        "kd": "KD",
        "opportunity": "Opportunity",
        "confidence": "Confidence",
        "gaps": "Content gaps",
        "channels": "Channels",
        "strategy": "Content strategy",
        "sources": "SERP sources",
        "mock": "Simulated data (MOCK) – not real research results.",
        "disclaimer": (
            "Keyword Opportunity Score is a research priority score, not a traffic or revenue forecast. Search Volume,"
            " CPC and KD are UNKNOWN when no valid keyword data source exists."
        ),
    },
}


async def build_report(session: AsyncSession, niche_id: uuid.UUID, *, include_mock: bool) -> dict[str, Any]:
    name = (await session.execute(text("SELECT name FROM niches WHERE id = :n"), {"n": niche_id})).scalar_one_or_none()
    out: dict[str, Any] = {
        "niche_id": str(niche_id),
        "niche_name": name,
        "generated_at": datetime.now(UTC).isoformat(),
        "include_mock": include_mock,
        "disclaimer_key": DISCLAIMER_KEY,
    }
    for key in ("ranked", "needs_research"):
        items = await list_clusters(session, niche_id, list_name=key, intent=None, include_mock=include_mock)
        out[key] = [await cluster_detail(session, uuid.UUID(i["cluster_id"])) for i in items]
    return out


def _fmt(v: Any) -> str:
    return "UNKNOWN" if v is None else (f"{v:.2f}" if isinstance(v, float) else str(v))


def to_markdown(report: dict[str, Any], lang: Lang) -> str:
    t = LABELS[lang]
    lines = [
        f"# {t['title']}",
        "",
        f"- {t['niche']}: {report['niche_name']}",
        f"- {t['generated']}: {report['generated_at']}",
        "",
    ]
    if report["include_mock"]:
        lines += [f"> {t['mock']}", ""]
    for key in ("ranked", "needs_research"):
        lines += [f"## {t[key]}", ""]
        if not report[key]:
            lines += [t["empty"], ""]
            continue
        for c in report[key]:
            mock = " [MOCK]" if c["data_origin"] == "MOCK" else ""
            lines += [
                f"### {c['name']}{mock} ({c['intent']})",
                "",
                f"- {t['opportunity']}: {_fmt(c['opportunity_score'])} · {t['confidence']}:"
                f" {_fmt(c['confidence_score'])}",
                "",
                f"| {t['keyword']} | {t['intent']} | {t['length']} | {t['volume']} | {t['cpc']} | {t['kd']} |"
                f" {t['opportunity']} |",
                "|---|---|---|---|---|---|---|",
            ]
            for k in c["keywords"]:
                m = k["metrics"]
                ev = k["evaluation"] or {}
                lines.append(
                    f"| {k['text']} | {k['intent']} | {k['length_class']} | {_fmt(m['search_volume']['value'])} |"
                    f" {_fmt(m['cpc']['value'])} | {_fmt(m['keyword_difficulty']['value'])} |"
                    f" {_fmt(ev.get('opportunity_score'))} |"
                )
            gaps = c["content_gaps"]
            gap_text = ", ".join(g["title"] for g in gaps.get("items") or []) or "-"
            lines += ["", f"- {t['gaps']}: {gap_text if gaps['status'] != 'UNKNOWN' else 'UNKNOWN'}"]
            ch = c["channels"]
            ch_text = ", ".join(i["domain"] for i in ch.get("items") or []) or "-"
            lines.append(f"- {t['channels']}: {ch_text if ch['status'] != 'UNKNOWN' else 'UNKNOWN'}")
            st = c["strategy"]
            st_text = f"{st['content_type']} – {st['angle']}" if st.get("status") == "INFERRED" else "UNKNOWN"
            lines.append(f"- {t['strategy']}: {st_text}")
            urls = sorted({r["url"] for s in c["serp"] for r in s["results"]})
            lines += [f"- {t['sources']}: {', '.join(urls) or '-'}", ""]
    lines += [f"_{t['disclaimer']}_", ""]
    return "\n".join(lines)
