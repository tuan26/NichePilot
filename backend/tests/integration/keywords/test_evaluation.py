"""T026 – đánh giá keyword: tái lập, đổi trọng số tạo phiên bản mới + tính lại không AI, bằng chứng bị xóa → tính lại (FR-017, FR-020; SC-004)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from nichepilot.modules.keywords import evaluation
from tests.api_helpers import csrf_headers, run_worker_once
from tests.discovery_helpers import allow_test_source
from tests.fakes.keywords_ai import ScriptedKeywordsAI
from tests.keywords_helpers import keywords_client, run_keywords, seed_niche_with_products

pytestmark = [pytest.mark.integration, pytest.mark.keywords, pytest.mark.mock]
MAIN = "how to stop running out of ingredients in a micro bakery"


async def _kw(engine: AsyncEngine, kw_text: str) -> uuid.UUID:
    async with engine.connect() as conn:
        return uuid.UUID(
            str((await conn.execute(text("SELECT id FROM keywords WHERE text = :t"), {"t": kw_text})).scalar_one())
        )


async def test_TC_E3_SC004_01_reproducible_scores(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with keywords_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche_with_products(client)
        await run_keywords(client, niche)
        kid = await _kw(clean_db, MAIN)
        async with clean_db.connect() as conn:
            ev = (
                await conn.execute(
                    text(
                        "SELECT opportunity_score, coverage, scoring_status, criteria FROM keyword_evaluations"
                        " WHERE keyword_id = :k ORDER BY created_at DESC LIMIT 1"
                    ),
                    {"k": kid},
                )
            ).one()
            n = (
                await conn.execute(text("SELECT count(*) FROM keyword_evaluations WHERE keyword_id = :k"), {"k": kid})
            ).scalar_one()
        crit = ev.criteria
        # fit 75; INFORMATIONAL+PROBLEM 75; SERP 4 kết quả: forum, qa + review không phủ pain point → 3/4 → 100;
        # content gap: article phủ pain point gốc → ratio 0 → 0; demand: nhóm nguồn E1 + 2 forum/qa
        assert [crit[k]["level"] for k in ("fit", "intent_value", "competition")] == [75, 75, 100]
        assert crit["content_gap"]["level"] == 0 and crit["demand"]["level"] is not None
        assert ev.scoring_status == "SCORED" and float(ev.coverage) == 100.0
        async with async_sessionmaker(clean_db)() as s, s.begin():
            again = await evaluation.evaluate_keywords(s, [kid])
        assert not again[0].created and again[0].opportunity == ev.opportunity_score
        async with clean_db.connect() as conn:
            n2 = (
                await conn.execute(text("SELECT count(*) FROM keyword_evaluations WHERE keyword_id = :k"), {"k": kid})
            ).scalar_one()
        assert n2 == n


async def test_TC_E3_FR017_04_weights_version_recompute_without_ai(clean_db: AsyncEngine, migrated_db: str) -> None:
    ai = ScriptedKeywordsAI()
    async with keywords_client(migrated_db, ai=ai) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche_with_products(client)
        await run_keywords(client, niche)
        calls = len(ai.requests)
        bad = await client.post(
            "/api/v1/keyword-scoring/weights",
            json={"weights": {"fit": 50, "intent_value": 50}},
            headers=csrf_headers(client),
        )
        assert bad.status_code == 422 and bad.json()["code"] == "KEYWORD_WEIGHTS_INVALID"
        w = {"fit": 40, "intent_value": 10, "competition": 20, "content_gap": 15, "demand": 15}
        r = await client.post("/api/v1/keyword-scoring/weights", json={"weights": w}, headers=csrf_headers(client))
        assert r.status_code == 201, r.text
        assert r.json()["version"] == 2
        await run_worker_once(client)
        assert len(ai.requests) == calls  # tính lại không gọi AI
        kid = await _kw(clean_db, MAIN)
        async with clean_db.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT w.version, e.computed_without_ai FROM keyword_evaluations e JOIN keyword_scoring_weights w"
                        " ON w.id = e.weights_version_id WHERE e.keyword_id = :k ORDER BY e.created_at"
                    ),
                    {"k": kid},
                )
            ).all()
            audit = (
                await conn.execute(text("SELECT count(*) FROM audit_logs WHERE action = 'keyword.weights_created'"))
            ).scalar_one()
        assert rows[0].version == 1 and rows[-1].version == 2 and rows[-1].computed_without_ai
        assert audit == 1
        hist = (await client.get("/api/v1/keyword-scoring/weights")).json()
        assert hist["active"]["version"] == 2 and [h["version"] for h in hist["history"]] == [2, 1]


async def test_TC_E3_FR020_03_erased_competitor_evidence_recomputed_on_read(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with keywords_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche_with_products(client)
        await run_keywords(client, niche)
        kid = await _kw(clean_db, MAIN)
        async with clean_db.connect() as conn:
            ids = (
                (await conn.execute(text("SELECT evidence_id FROM competitor_pages WHERE keyword_id = :k"), {"k": kid}))
                .scalars()
                .all()
            )
            cid = (await conn.execute(text("SELECT cluster_id FROM keywords WHERE id = :k"), {"k": kid})).scalar_one()
        assert ids
        for eid in ids:
            r = await client.post(
                f"/api/v1/evidence/{eid}/erase", json={"reason": "Owner request (test)"}, headers=csrf_headers(client)
            )
            assert r.status_code in (200, 202), r.text
        detail = (await client.get(f"/api/v1/keyword-clusters/{cid}")).json()
        kw = next(k for k in detail["keywords"] if k["text"] == MAIN)
        assert kw["evaluation"]["criteria"]["content_gap"]["level"] is None
        assert "content_gap" in kw["evaluation"]["missing"]
        assert all(p["keyword_id"] != str(kid) for p in detail["competitor_pages"])
