"""Báo cáo xếp hạng theo lượt (T117; FR-024, FR-019c, SC-009): JSON hoặc Markdown, ba danh sách tách biệt, chú thích
Opportunity.

MOCK bị loại mặc định (chỉ hiện khi `include_mock` – mọi dòng ghi nhãn). Nhãn/tiêu đề song ngữ VI/EN; nội dung trích
dẫn giữ ngôn ngữ
gốc. Không có số liệu nào không có trong DB (không bịa search volume/doanh thu).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from nichepilot.modules.discovery import ranking
from nichepilot.modules.discovery.service import get_run

Lang = Literal["vi", "en"]
LABELS: dict[str, dict[str, str]] = {
    "vi": {
        "title": "Báo cáo xếp hạng ngách",
        "run": "Lượt khám phá",
        "market": "Thị trường",
        "outcome": "Kết quả",
        "generated": "Tạo lúc",
        "research_ranking": "Bảng xếp hạng cơ hội nghiên cứu",
        "affiliate_priority": "Danh sách ưu tiên affiliate",
        "needs_research": "Cần nghiên cứu thêm",
        "empty": "(không có ngách)",
        "name": "Ngách",
        "opportunity": "Opportunity",
        "confidence": "Confidence",
        "coverage": "Coverage",
        "monetization": "Monetization",
        "evidence": "Bằng chứng",
        "recommendation": "Đề xuất AI",
        "decision": "Quyết định",
        "unknown": "UNKNOWN",
        "mock": "Dữ liệu giả lập (MOCK) – không phải kết quả nghiên cứu thật.",
        "disclaimer": (
            "Opportunity Score là điểm ưu tiên nghiên cứu, không phải dự báo doanh thu hay khả năng sinh lợi đã xác"
            " minh. "
            "Đạt ngưỡng bằng chứng không có nghĩa là ngách sinh lợi."
        ),
    },
    "en": {
        "title": "Niche ranking report",
        "run": "Discovery run",
        "market": "Market",
        "outcome": "Outcome",
        "generated": "Generated at",
        "research_ranking": "Research opportunity ranking",
        "affiliate_priority": "Affiliate priority list",
        "needs_research": "Needs more research",
        "empty": "(no niches)",
        "name": "Niche",
        "opportunity": "Opportunity",
        "confidence": "Confidence",
        "coverage": "Coverage",
        "monetization": "Monetization",
        "evidence": "Evidence",
        "recommendation": "AI recommendation",
        "decision": "Decision",
        "unknown": "UNKNOWN",
        "mock": "Simulated (MOCK) data – not real research results.",
        "disclaimer": (
            "The Opportunity Score is a research priority score, not a revenue forecast or verified profitability. "
            "Meeting the evidence threshold does not mean the niche is profitable."
        ),
    },
}
LISTS: tuple[tuple[str, ranking.ListName], ...] = (
    ("research_ranking", "research"),
    ("affiliate_priority", "affiliate"),
    ("needs_research", "needs_research"),
)


async def build_report(
    session: AsyncSession, run_id: uuid.UUID, *, include_mock: bool = False
) -> dict[str, Any] | None:
    run = await get_run(session, run_id)
    if run is None:
        return None
    out: dict[str, Any] = {"run": run}
    for key, lst in LISTS:
        items, _ = await ranking.list_niches(
            session, list_name=lst, run_id=run_id, include_mock=include_mock, limit=200
        )
        out[key] = items
    out["disclaimer_key"] = ranking.DISCLAIMER_KEY
    out["generated_at"] = datetime.now(UTC).isoformat()
    out["include_mock"] = include_mock
    return out


def _cell(v: Any, unknown: str) -> str:
    return unknown if v is None else str(v).replace("|", "\\|")


def to_markdown(report: dict[str, Any], lang: Lang = "vi") -> str:
    lb = LABELS[lang]
    run = report["run"]
    lines = [
        f"# {lb['title']}",
        "",
        f"- {lb['run']}: `{run['id']}`",
        f"- {lb['market']}: {run['market']}",
        f"- {lb['outcome']}: {run['outcome'] or lb['unknown']} ({run['stop_reason'] or lb['unknown']})",
        f"- {lb['generated']}: {report['generated_at']}",
        "",
        f"> {lb['disclaimer']}",
        "",
    ]
    if report.get("include_mock") or run["data_origin"] == "MOCK":
        lines += [f"> **{lb['mock']}**", ""]
    for key, _ in LISTS:
        lines += [f"## {lb[key]}", ""]
        items = report[key]
        if not items:
            lines += [lb["empty"], ""]
            continue
        lines += [
            f"| # | {lb['name']} | {lb['opportunity']} | {lb['confidence']} | {lb['coverage']} | {lb['monetization']} |"
            f" {lb['evidence']} | {lb['recommendation']} | {lb['decision']} |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for i, n in enumerate(items, 1):
            name = n["name"] + (" [MOCK]" if n["data_origin"] == "MOCK" and "[MOCK]" not in n["name"] else "")
            cov = None if n["coverage"] is None else f"{n['coverage']}%"
            cells = [
                str(i),
                _cell(name, lb["unknown"]),
                _cell(n["opportunity_score"], lb["unknown"]),
                _cell(n["confidence_score"], lb["unknown"]),
                _cell(cov, lb["unknown"]),
                n["monetization_status"],
                n["evidence_status"],
                n["ai_recommendation"],
                n["decision_status"],
            ]
            lines.append("| " + " | ".join(cells) + " |")
        lines.append("")
    return "\n".join(lines)
