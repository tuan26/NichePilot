"""Nạp ngách DEMO gắn `MOCK` cho E2E/dev (chủ sở hữu duyệt 2026-11-25): `python -m nichepilot.jobs.discovery_demo_seed`.

Lý do: stack E2E dùng MockAIProvider (luôn trả 0 ứng viên) nên không có ngách để kiểm thử màn hình chi tiết/quyết định.
Quy tắc:
- TỪ CHỐI khi `APP_ENV=production` (thoát mã 2) – không bao giờ chạy trên dữ liệu thật.
- Mọi bản ghi `data_origin = MOCK`, tên bắt đầu `[MOCK DEMO]`, URL nguồn trên tên miền `.example` (không tồn tại) –
  bị ẩn khỏi xếp hạng và báo cáo mặc định; không phải kết quả nghiên cứu, không dùng cho SC-013.
- Đi qua đúng pipeline lưu/chấm điểm hiện có (EvidenceService, analysis, evaluation) – không ghi thẳng điểm số.
- Idempotent: đã có ngách demo → bỏ qua.
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nichepilot.core.config import get_settings
from nichepilot.core.db import dispose_db, init_db
from nichepilot.db_models import import_all_models
from nichepilot.modules.discovery import analysis, evaluation
from nichepilot.modules.discovery.fingerprint import content_hash, registered_domain, simhash64
from nichepilot.modules.discovery.schemas import AssessOutput, ExtractOutput
from nichepilot.modules.discovery.scoring.opportunity import CRITERIA, Criterion
from nichepilot.modules.evidence.service import EvidenceService
from nichepilot.modules.settings.service import get_default_project

DEMO_NAME = "[MOCK DEMO] Small bakery stock alerts"
PAGES = (
    (
        "https://forum-demo.example/t/bakery-stock",
        "[MOCK DEMO] Two-person bakery runs out of flour every week; spreadsheets take too long after the morning rush"
        " and the big restaurant apps are too expensive for a micro bakery.",
    ),
    (
        "https://reviews-demo.example/stock-apps",
        "[MOCK DEMO] Reviewer: existing inventory apps target restaurant chains, setup took a full weekend and they"
        " still do not warn before dairy expires, so cream is thrown away every Friday.",
    ),
)


class DemoSeedRefusedError(RuntimeError):
    pass


async def seed() -> dict[str, object]:
    settings = get_settings()
    if settings.is_production:
        raise DemoSeedRefusedError("APP_ENV=production")
    import_all_models()  # CLI chạy độc lập: đăng ký đủ mapper (FK research_evidence → agent_jobs)
    sm = init_db(settings.database_url.get_secret_value())
    try:
        return await seed_demo(sm)
    finally:
        await dispose_db()


async def seed_demo(sm: async_sessionmaker[AsyncSession]) -> dict[str, object]:
    async with sm() as s:
        existing = (
            await s.execute(text("SELECT id FROM niches WHERE name = :n"), {"n": DEMO_NAME})
        ).scalar_one_or_none()
        if existing:
            return {"status": "EXISTS", "niche_id": str(existing)}
        project = await get_default_project(s)
    async with sm() as s, s.begin():
        niche_id = uuid.UUID(
            str(
                (
                    await s.execute(
                        text(
                            "INSERT INTO niches (project_id, name, micro_niche, country, customer_group, core_problem,"
                            " dedup_key, data_origin) VALUES (:p, :n, :mn, 'US', :cg, :cp, :k, 'MOCK') RETURNING id"
                        ),
                        {
                            "p": project.id,
                            "n": DEMO_NAME,
                            "mn": "[MOCK DEMO] Phone-first stock alerts for micro bakeries",
                            "cg": "owners of one- to three-person bakeries",
                            "cp": "running out of ingredients without warning",
                            "k": f"mock-demo|{uuid.uuid4()}",
                        },
                    )
                ).scalar_one()
            )
        )
    try:
        return await _fill(sm, project.id, niche_id)
    except BaseException:
        # Không để lại ngách dở dang (lần chạy sau sẽ tưởng đã có) – xóa ngách DEMO + nguồn/bằng chứng MOCK vừa tạo.
        async with sm() as s, s.begin():
            await s.execute(
                text("DELETE FROM research_evidence WHERE subject_type = 'niche' AND subject_id = :n"), {"n": niche_id}
            )
            await s.execute(text("DELETE FROM niches WHERE id = :n"), {"n": niche_id})
        raise


async def _fill(sm: async_sessionmaker[AsyncSession], project_id: uuid.UUID, niche_id: uuid.UUID) -> dict[str, object]:
    ev = EvidenceService(sm)
    ids: list[str] = []
    for url, excerpt in PAGES:
        source_id = await ev.add_source(
            project_id,
            "WEB_PAGE",
            url,
            content=excerpt,
            data_origin="MOCK",
            title="[MOCK DEMO] page",
            registered_domain=registered_domain(url),
            simhash=simhash64(excerpt),
        )
        ids.append(
            str(
                await ev.add_evidence(
                    project_id,
                    "page_excerpt",
                    None,
                    "VERIFIED",
                    data_origin="MOCK",
                    source_id=source_id,
                    excerpt=excerpt,
                    subject_type="niche",
                    subject_id=niche_id,
                    redaction_status="REDACTED",
                    redaction_counts={},
                    pii_engine="mock-demo",
                    content_hash=content_hash(excerpt),
                )
            )
        )
    finding = {"status": "VERIFIED", "evidence_ids": ids[:1]}
    extract = ExtractOutput.model_validate(
        {
            "pain_points": [
                {
                    "title": "[MOCK DEMO] Ingredients run out without warning",
                    "description": "[MOCK DEMO] Manual stock counting after busy mornings misses shortages.",
                    "severity": 4,
                    "severity_reason": "[MOCK DEMO] weekly losses",
                    "status": "VERIFIED",
                    "evidence_ids": ids,
                }
            ],
            "persona": {"segment": {**finding, "value": "[MOCK DEMO] micro bakery owners"}},
            "findings": {"CURRENT_SOLUTIONS": {**finding, "value": ["[MOCK DEMO] spreadsheets"]}},
            "competitors": [
                {
                    "name": "[MOCK DEMO] Spreadsheet",
                    "kind": "MANUAL_WORKAROUND",
                    "weaknesses": ["slow"],
                    "evidence_ids": ids[:1],
                }
            ],
        }
    )
    assess = AssessOutput.model_validate(
        {
            "evidence": [
                {"evidence_id": i, "relevance": 0.9, "quality": 0.8, "copy_suspected": False, "reason": "[MOCK DEMO]"}
                for i in ids
            ]
        }
    )
    levels = {"problem_severity": 75, "market_gap": 50, "reachability": 75, "competition_opportunity": 25}
    criteria = {
        k: Criterion(levels[k], "INFERRED", "[MOCK DEMO]", tuple(ids[:1]))
        if k in levels
        else Criterion(None, "UNKNOWN")
        for k in CRITERIA
    }
    async with sm() as s, s.begin():
        await analysis.save_extraction(s, niche_id=niche_id, out=extract, data_origin="MOCK")
        await analysis.save_assessment(s, niche_id=niche_id, assessments=assess.evidence)
        res = await evaluation.evaluate_and_store(
            s,
            niche_id,
            criteria=criteria,
            recommendation=("PURSUE", "[MOCK DEMO] repeated pain in two independent sources"),
            computed_without_ai=True,
        )
    return {"status": "CREATED", "niche_id": str(niche_id), "evidence_status": res.evidence_status}


def main() -> None:
    try:
        out = asyncio.run(seed())
    except DemoSeedRefusedError:
        print(json.dumps({"status": "REFUSED", "reason": "APP_ENV=production"}), file=sys.stderr)
        raise SystemExit(2) from None
    print(json.dumps(out))


if __name__ == "__main__":
    main()
