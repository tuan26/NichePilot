"""Báo cáo sản phẩm theo ngách (FR-032; FR-031; FR-035): JSON hoặc Markdown, VI/EN, hai danh sách tách biệt.

MOCK bị loại mặc định (chỉ hiện khi `include_mock` – kèm cảnh báo). Không có số liệu nào ngoài DB; thuộc tính UNKNOWN
ghi rõ.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nichepilot.modules.products.service import list_products

Lang = Literal["vi", "en"]
LABELS: dict[str, dict[str, str]] = {
    "vi": {
        "title": "Báo cáo sản phẩm & affiliate",
        "niche": "Ngách",
        "generated": "Tạo lúc",
        "ranked": "Xếp hạng sản phẩm",
        "needs_research": "Cần nghiên cứu thêm",
        "empty": "(không có sản phẩm)",
        "name": "Sản phẩm",
        "opportunity": "Opportunity",
        "confidence": "Confidence",
        "coverage": "Coverage",
        "readiness": "Sẵn sàng affiliate",
        "missing": "Còn thiếu",
        "decision": "Quyết định",
        "mock": "Dữ liệu giả lập (MOCK) – không phải kết quả nghiên cứu thật.",
        "disclaimer": (
            "Product Opportunity Score là điểm ưu tiên nghiên cứu, không phải dự báo doanh thu. READY_TO_PROMOTE chỉ là"
            " điều"
            " kiện tham gia, không phải khuyến nghị quảng bá."
        ),
    },
    "en": {
        "title": "Product & affiliate report",
        "niche": "Niche",
        "generated": "Generated at",
        "ranked": "Product ranking",
        "needs_research": "Needs more research",
        "empty": "(no products)",
        "name": "Product",
        "opportunity": "Opportunity",
        "confidence": "Confidence",
        "coverage": "Coverage",
        "readiness": "Affiliate readiness",
        "missing": "Missing",
        "decision": "Decision",
        "mock": "Simulated data (MOCK) – not real research results.",
        "disclaimer": (
            "Product Opportunity Score is a research priority score, not a revenue forecast. READY_TO_PROMOTE is only"
            " an"
            " eligibility condition, not a recommendation to promote."
        ),
    },
}


async def build_report(session: AsyncSession, niche_id: uuid.UUID, *, include_mock: bool) -> dict[str, Any]:
    name = (await session.execute(text("SELECT name FROM niches WHERE id = :n"), {"n": niche_id})).scalar_one_or_none()
    return {
        "niche_id": str(niche_id),
        "niche_name": name,
        "generated_at": datetime.now(UTC).isoformat(),
        "include_mock": include_mock,
        "ranked": await list_products(session, niche_id, list_name="ranked", include_mock=include_mock),
        "needs_research": await list_products(session, niche_id, list_name="needs_research", include_mock=include_mock),
        "disclaimer_key": "products.opportunity.disclaimer",
    }


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
        items = report[key]
        if not items:
            lines += [t["empty"], ""]
            continue
        lines += [
            f"| {t['name']} | {t['opportunity']} | {t['confidence']} | {t['coverage']} | {t['readiness']} |"
            f" {t['missing']} | {t['decision']} |",
            "|---|---|---|---|---|---|---|",
        ]
        for i in items:
            ev = i["evaluation"] or {}
            mock = " [MOCK]" if i["data_origin"] == "MOCK" else ""
            lines.append(
                f"| {i['name']}{mock} | {_fmt(ev.get('opportunity_score'))} | {_fmt(ev.get('confidence_score'))} |"
                f" {_fmt(ev.get('coverage'))}% | {i['readiness_status']} | {', '.join(ev.get('missing') or []) or '-'}"
                " |"
                f" {i['decision_status']} |"
            )
        lines.append("")
    lines += [f"_{t['disclaimer']}_", ""]
    return "\n".join(lines)
