"""Nạp keyword DEMO gắn `MOCK` cho E2E/dev (R-10): `python -m nichepilot.jobs.keywords_demo_seed`.

Cần ngách demo E1 (`discovery_demo_seed`) và sản phẩm demo E2 (`products_demo_seed`). Quy tắc như lệnh seed E1/E2:
- TỪ CHỐI khi `APP_ENV=production` (thoát mã 2) – không bao giờ chạy trên dữ liệu thật.
- Mọi bản ghi `data_origin = MOCK`; SERP demo chỉ trên tên miền `.example` – ẩn khỏi danh sách/báo cáo mặc định; không
phải kết quả
  nghiên cứu, không dùng cho SC-008. Search Volume/CPC/KD KHÔNG được ghi (luôn UNKNOWN).
- Đi qua đúng đường lưu/chấm điểm hiện có (store, evaluation) – không ghi thẳng điểm số; không AI, không mạng.
- Idempotent: đã có keyword demo → bỏ qua.
"""

from __future__ import annotations

import asyncio
import json
import sys
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nichepilot.core.config import get_settings
from nichepilot.core.db import dispose_db, init_db
from nichepilot.db_models import import_all_models
from nichepilot.jobs.discovery_demo_seed import DEMO_NAME
from nichepilot.modules.keywords import evaluation, store
from nichepilot.modules.keywords import weights as weights_mod
from nichepilot.modules.keywords.analysis import channels
from nichepilot.modules.keywords.generation import CandidateKeyword, commercial_keywords, load_inputs
from nichepilot.modules.keywords.serp import results_from_hits

DEMO_PROBLEMS = [
    ("how to stop running out of ingredients in a micro bakery", "PROBLEM", "INFORMATIONAL"),
    ("low stock alert app for small bakeries", "SOLUTION", "COMMERCIAL_INVESTIGATION"),
    ("weekly ingredient count checklist for bakeries", "SOLUTION", "INFORMATIONAL"),
]
DEMO_SERP = [
    "https://bakersforum-demo.example/t/flour-ran-out",
    "https://bakeryblog-demo.example/blog/stop-running-out",
    "https://appreviews-demo.example/review/bakery-stock-apps",
]


class DemoSeedRefusedError(RuntimeError):
    pass


async def seed() -> dict[str, object]:
    settings = get_settings()
    if settings.is_production:
        raise DemoSeedRefusedError("APP_ENV=production")
    import_all_models()
    sm = init_db(settings.database_url.get_secret_value())
    try:
        return await seed_demo(sm)
    finally:
        await dispose_db()


async def seed_demo(sm: async_sessionmaker[AsyncSession]) -> dict[str, object]:
    async with sm() as s:
        niche = (await s.execute(text("SELECT id, project_id FROM niches WHERE name = :n"), {"n": DEMO_NAME})).first()
        if niche is None:
            return {"status": "MISSING_DISCOVERY_DEMO", "hint": "run nichepilot.jobs.discovery_demo_seed first"}
        existing = (
            await s.execute(
                text("SELECT count(*) FROM keywords WHERE niche_id = :n AND data_origin = 'MOCK'"), {"n": niche.id}
            )
        ).scalar_one()
        if existing:
            return {"status": "EXISTS", "keywords": int(existing)}
        inputs = await load_inputs(s, niche.id)
        w = await weights_mod.active(s)
    if not inputs.pain_points:
        return {"status": "MISSING_PAIN_POINTS"}
    pp = next(iter(inputs.pain_points.values()))
    cands: list[CandidateKeyword] = [
        CandidateKeyword(
            text=t,
            keyword_type=kt,
            intent=intent,
            intent_reason="[MOCK DEMO] problem-solving query",
            origins=[{"origin_type": "PAIN_POINT", "pain_point_id": pp.id, "reason": "[MOCK DEMO]"}],
            fit={
                "level": 75,
                "reason": "[MOCK DEMO] matches the stock-out pain",
                "evidence_ids": sorted(pp.evidence_ids)[:1],
            },
        )
        for t, kt, intent in DEMO_PROBLEMS
    ]
    cands += commercial_keywords(inputs, list(w.templates.get("commercial") or []))
    ids: list[uuid.UUID] = []
    async with sm() as s, s.begin():
        for kw in cands:
            kid, _ = await store.upsert_keyword(
                s,
                project_id=niche.project_id,
                niche_id=niche.id,
                kw=kw,
                market=inputs.country,
                origin="MOCK",
                run_id=None,
            )
            ids.append(kid)
        results = results_from_hits(
            [{"url": u, "title": "[MOCK DEMO]", "redaction_status": "REDACTED"} for u in DEMO_SERP]
        )
        await store.record_serp(
            s, keyword_id=ids[0], results=results, source_policy_id=None, job_id=None, origin="MOCK"
        )
        clusters = await store.assign_clusters(s, niche.id, "MOCK")
        await evaluation.evaluate_keywords(s, ids)
        await evaluation.refresh_clusters(s, clusters)
        main_cluster = (
            await s.execute(text("SELECT cluster_id FROM keywords WHERE id = :k"), {"k": ids[0]})
        ).scalar_one()
        await store.merge_insights(s, main_cluster, {"channels": channels(results)})
    out: dict[str, Any] = {"status": "CREATED", "keywords": len(set(ids)), "clusters": len(clusters)}
    return out


def main() -> None:
    try:
        out = asyncio.run(seed())
    except DemoSeedRefusedError:
        print(json.dumps({"status": "REFUSED", "reason": "APP_ENV=production"}), file=sys.stderr)
        sys.exit(2)
    print(json.dumps(out, default=str))


if __name__ == "__main__":
    main()
