"""Nạp sản phẩm DEMO gắn `MOCK` cho E2E/dev (R-10): `python -m nichepilot.jobs.products_demo_seed`.

Cần ngách demo E1 (`python -m nichepilot.jobs.discovery_demo_seed`). Quy tắc như lệnh seed E1:
- TỪ CHỐI khi `APP_ENV=production` (thoát mã 2) – không bao giờ chạy trên dữ liệu thật.
- Mọi bản ghi `data_origin = MOCK`, tên bắt đầu `[MOCK DEMO]`, nguồn trên tên miền `.example` – ẩn khỏi danh sách/báo
cáo mặc định; không
  phải kết quả nghiên cứu, không phải doanh thu, không dùng cho SC-008.
- Đi qua đúng đường lưu/chấm điểm hiện có (store, evaluation.evaluate_pair) – không ghi thẳng điểm số.
- Idempotent: đã có sản phẩm demo → bỏ qua.
Kết quả: một sản phẩm `READY_TO_PROMOTE`, một sản phẩm `ELIGIBILITY_UNVERIFIED`.
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
from nichepilot.modules.discovery.fingerprint import content_hash, registered_domain, simhash64
from nichepilot.modules.evidence.service import EvidenceService
from nichepilot.modules.products import evaluation, store

PRODUCTS: list[dict[str, Any]] = [
    {
        "name": "[MOCK DEMO] ShelfAlert",
        "domain": "shelfalert-demo.example",
        "pages": {
            "pricing": "[MOCK DEMO] ShelfAlert Mini costs $15 per month for bakeries with up to five staff,"
            " with low-stock alerts, phone app and expiry tracking included.",
            "partners": "[MOCK DEMO] ShelfAlert Partners earn 30% recurring commission for 12 months"
            " with a 60-day cookie; partners from any country including Vietnam may promote worldwide;"
            " brand keyword bidding is not allowed.",
        },
        "price": {"plan": "Mini", "amount": 15, "currency": "USD", "period": "month", "promo": False},
        "features": ["low-stock alerts", "phone app", "expiry tracking"],
        "program": {
            "commission": {"kind": "recurring", "value": 30, "recurring_months": 12},
            "cookie_days": {"days": 60},
            "vn_eligibility": {"status": "ALLOWED"},
            "promotion_regions": {"global": True, "include": [], "exclude": []},
            "ad_restrictions": {"codes": ["NO_BRAND_BIDDING"]},
        },
    },
    {
        "name": "[MOCK DEMO] CrumbCount",
        "domain": "crumbcount-demo.example",
        "pages": {
            "pricing": "[MOCK DEMO] CrumbCount Starter is $8 per month for simple stock counts"
            " in very small bakeries and home bakers.",
            "partners": "[MOCK DEMO] CrumbCount affiliates earn 20% commission per sale with a 30-day cookie window on"
            " referred customers.",
        },
        "price": {"plan": "Starter", "amount": 8, "currency": "USD", "period": "month", "promo": False},
        "features": ["stock counts"],
        "program": {"commission": {"kind": "percent", "value": 20}, "cookie_days": {"days": 30}},
    },
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


async def _page(
    ev: EvidenceService, project_id: uuid.UUID, run_id: uuid.UUID, url: str, excerpt: str
) -> store.PageExcerpt:
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
    eid = await ev.add_evidence(
        project_id,
        "page_excerpt",
        None,
        "VERIFIED",
        data_origin="MOCK",
        source_id=source_id,
        excerpt=excerpt,
        subject_type="product_run",
        subject_id=run_id,
        redaction_status="REDACTED",
        redaction_counts={},
        pii_engine="mock-demo",
        content_hash=content_hash(excerpt),
    )
    return store.PageExcerpt(str(eid), str(source_id), excerpt, url, registered_domain(url), {}, "mock-demo", "MOCK")


async def seed_demo(sm: async_sessionmaker[AsyncSession]) -> dict[str, object]:
    async with sm() as s:
        niche = (await s.execute(text("SELECT id, project_id FROM niches WHERE name = :n"), {"n": DEMO_NAME})).first()
        if niche is None:
            return {"status": "MISSING_DISCOVERY_DEMO", "hint": "run nichepilot.jobs.discovery_demo_seed first"}
        existing = (await s.execute(text("SELECT count(*) FROM products WHERE name LIKE '[MOCK DEMO]%'"))).scalar_one()
        if existing:
            return {"status": "EXISTS", "products": int(existing)}
        pain = (
            await s.execute(
                text("SELECT id FROM pain_points WHERE niche_id = :n ORDER BY created_at LIMIT 1"), {"n": niche.id}
            )
        ).scalar_one()
    niche_id, project_id = niche.id, niche.project_id
    run_id = (
        uuid.uuid4()
    )  # chủ thể nhóm trích đoạn demo (không có job thật) – chỉ dùng làm subject_id của bằng chứng trang
    ev = EvidenceService(sm)
    created: list[dict[str, Any]] = []
    for spec in PRODUCTS:
        dom = spec["domain"]
        pricing = await _page(ev, project_id, run_id, f"https://{dom}/pricing", spec["pages"]["pricing"])
        partners = await _page(ev, project_id, run_id, f"https://{dom}/partners", spec["pages"]["partners"])
        async with sm() as s, s.begin():
            pid = await store.upsert_product(
                s,
                project_id=project_id,
                origin="MOCK",
                name=spec["name"],
                vendor=None,
                official_domain=dom,
                official_url=f"https://{dom}",
                category="SOFTWARE",
                risk_flags=[],
            )
            pair = await store.ensure_pair(s, product_id=pid, niche_id=niche_id, run_id=None, origin="MOCK")
            await store.add_pain_link(
                s, pair_id=pair, pain_point_id=pain, evidence_id=uuid.UUID(pricing.evidence_id), status="VERIFIED"
            )
            attrs: list[tuple[str, dict[str, Any], store.PageExcerpt]] = [
                ("official_website", {"url": f"https://{dom}"}, pricing),
                ("price", spec["price"], pricing),
                *[("feature", {"text": f}, pricing) for f in spec["features"]],
            ]
            for key, value, page in attrs:
                await store.add_attribute(
                    s,
                    project_id=project_id,
                    subject_type="product",
                    subject_id=pid,
                    claim_key=key,
                    value=value,
                    page=page,
                    status="VERIFIED",
                    job_id=None,
                )
            prog = await store.upsert_program(
                s,
                project_id=project_id,
                origin="MOCK",
                name=f"{spec['name']} Partners",
                operator_type="VENDOR",
                operator_name=None,
                operator_domain=dom,
                terms_url=f"https://{dom}/partners",
            )
            await store.link_product_program(s, pid, prog)
            for key, value in spec["program"].items():
                await store.add_attribute(
                    s,
                    project_id=project_id,
                    subject_type="affiliate_program",
                    subject_id=prog,
                    claim_key=key,
                    value=value,
                    page=partners,
                    status="VERIFIED",
                    job_id=None,
                )
            levels = {
                "fit": {
                    "level": 75,
                    "reason": "[MOCK DEMO] stock alerts for micro bakeries",
                    "evidence_ids": [pricing.evidence_id],
                },
                "price_fit": {"level": None, "reason": "", "evidence_ids": []},
                "persona_match": "MATCH",
            }
            res = await evaluation.evaluate_pair(
                s, pair, ai_levels=levels, ai_decision=("SELECT", "[MOCK DEMO] solves the main pain point")
            )
        created.append({"product_id": str(pid), "readiness": res.readiness, "opportunity": str(res.opportunity)})
    return {"status": "CREATED", "products": created}


def main() -> None:
    try:
        out = asyncio.run(seed())
    except DemoSeedRefusedError:
        print(json.dumps({"status": "REFUSED", "reason": "APP_ENV=production"}), file=sys.stderr)
        raise SystemExit(2) from None
    print(json.dumps(out))
    if out.get("status") == "MISSING_DISCOVERY_DEMO":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
