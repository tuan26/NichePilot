"""T015/T021 – lượt `keywords.run` đầy đủ với nguồn + AI giả lập (FR-001, FR-002, FR-005, FR-009…FR-013, FR-030, SC-001…SC-003).

Không mạng, không API có phí; mọi dữ liệu gắn MOCK. KHÔNG chứng minh nguồn thật hay Claude API thật.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.discovery_helpers import allow_test_source
from tests.fakes.keywords_ai import ScriptedKeywordsAI
from tests.keywords_helpers import keywords_client, run_keywords, seed_niche_with_products, start_run

pytestmark = [pytest.mark.integration, pytest.mark.keywords, pytest.mark.mock]


async def test_TC_E3_FR005_03_TC_E3_SC001_01_full_run_keywords_traceable_to_origins(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    """TC_E3_FR005_03 / SC-001: 100% keyword có ≥ 1 nguồn gốc thuộc ngách; TC_E3_SC003_01: ≥ 50% long-tail, commercial cho mọi sản phẩm."""
    ai = ScriptedKeywordsAI()
    async with keywords_client(migrated_db, ai=ai) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche_with_products(client)
        run = await run_keywords(client, niche)
        assert run["status"] == "SUCCEEDED", run
        assert (run["outcome"], run["stop_reason"]) == ("COMPLETED", "KEYWORDS_ANALYZED"), run
        async with clean_db.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT k.id, k.length_class, k.data_origin, count(o.id) AS n FROM keywords k"
                        " LEFT JOIN keyword_origins o ON o.keyword_id = k.id WHERE k.niche_id = :n GROUP BY k.id"
                    ),
                    {"n": niche},
                )
            ).all()
            foreign = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM keyword_origins o JOIN keywords k ON k.id = o.keyword_id"
                        " LEFT JOIN pain_points p ON p.id = o.pain_point_id LEFT JOIN product_niches pn"
                        " ON pn.product_id = o.product_id AND pn.niche_id = k.niche_id"
                        " WHERE (o.origin_type = 'PAIN_POINT' AND p.niche_id IS DISTINCT FROM k.niche_id)"
                        " OR (o.origin_type = 'PRODUCT' AND pn.id IS NULL)"
                    )
                )
            ).scalar_one()
            commercial = (
                await conn.execute(
                    text(
                        "SELECT count(DISTINCT pn.product_id) FROM product_niches pn WHERE pn.niche_id = :n AND EXISTS"
                        " (SELECT 1 FROM keyword_origins o JOIN keywords k ON k.id = o.keyword_id WHERE o.product_id ="
                        " pn.product_id AND k.intent IN ('COMMERCIAL_INVESTIGATION','TRANSACTIONAL'))"
                    ),
                    {"n": niche},
                )
            ).scalar_one()
        assert rows and all(r.n >= 1 for r in rows)
        assert foreign == 0
        assert {r.data_origin for r in rows} == {"MOCK"}
        assert sum(1 for r in rows if r.length_class == "LONG_TAIL") / len(rows) >= 0.5
        assert commercial == 2


async def test_TC_E3_FR012_02_serp_and_competitor_pages_observed(clean_db: AsyncEngine, migrated_db: str) -> None:
    """TC_E3_FR012_02 SERP qua nguồn ALLOWED; TC_E3_FR013_02 trích đoạn ≤ 1000 ký tự (SC-007); TC_E3_FR011_02 intent VERIFIED khi có tín hiệu."""
    async with keywords_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche_with_products(client)
        await run_keywords(client, niche)
        async with clean_db.connect() as conn:
            serp = (
                await conn.execute(
                    text(
                        "SELECT k.text, s.results, s.version, s.source_policy_id FROM serp_observations s"
                        " JOIN keywords k ON k.id = s.keyword_id ORDER BY k.text"
                    )
                )
            ).all()
            pages = (
                await conn.execute(
                    text(
                        "SELECT c.url, c.summary, length(e.excerpt) AS n, e.subject_type FROM competitor_pages c"
                        " JOIN research_evidence e ON e.id = c.evidence_id"
                    )
                )
            ).all()
            intents = dict(
                (
                    await conn.execute(
                        text("SELECT text, intent_status FROM keywords WHERE niche_id = :n"), {"n": niche}
                    )
                ).all()
            )
        by_kw = {r.text: r for r in serp}
        main = by_kw["how to stop running out of ingredients in a micro bakery"]
        assert [r["page_type"] for r in main.results] == ["forum", "qa", "article", "review"]
        assert main.version == 1 and main.source_policy_id is not None
        assert {p.url for p in pages} >= {
            "https://bakeryblog.example/blog/stop-running-out",
            "https://appreviews.example/review/bakery-stock-apps",
        }
        assert all(p.n <= 1000 and p.subject_type == "keyword_run" for p in pages)
        assert intents["how to stop running out of ingredients in a micro bakery"] == "VERIFIED"
        assert intents["track ingredient stock without a spreadsheet"] == "INFERRED"  # không có SERP → chưa xác minh


async def test_TC_E3_FR009_02_TC_E3_SC002_01_ai_metrics_rejected_and_metrics_unknown(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    """AI trả thêm search_volume → cả đầu ra bị loại; chỉ còn keyword mẫu; 0 chỉ số không nguồn (SC-002). TC_E3_FR010_01: không lọc theo volume."""

    def fabricated(req: object) -> dict[str, object]:
        return {
            "keywords": [
                {
                    "text": "bakery inventory software",
                    "keyword_type": "SOLUTION",
                    "intent": "COMMERCIAL_INVESTIGATION",
                    "origins": [{"origin_type": "PAIN_POINT", "pain_point_id": "x"}],
                    "search_volume": 12000,
                    "cpc": 4.5,
                }
            ]
        }

    ai = ScriptedKeywordsAI({"keywords.generate": fabricated})
    async with keywords_client(migrated_db, ai=ai) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche_with_products(client)
        run = await run_keywords(client, niche)
        assert run["metrics"]["ai_outputs_rejected"] >= 1
        async with clean_db.connect() as conn:
            n_metrics = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM keywords WHERE search_volume IS NOT NULL OR cpc IS NOT NULL"
                        " OR keyword_difficulty IS NOT NULL"
                    )
                )
            ).scalar_one()
            texts = (await conn.execute(text("SELECT text FROM keywords"))).scalars().all()
        assert n_metrics == 0
        assert "bakery inventory software" not in texts and texts  # keyword mẫu commercial vẫn có
        clusters = (await client.get(f"/api/v1/niches/{niche}/keyword-clusters", params={"include_mock": True})).json()
        cid = (clusters["items"] or [None])[0]
        assert cid is not None
        detail = (await client.get(f"/api/v1/keyword-clusters/{cid['cluster_id']}")).json()
        for k in detail["keywords"]:
            for m in ("search_volume", "cpc", "keyword_difficulty"):
                assert k["metrics"][m] == {"value": None, "source": None, "collected_at": None, "market": None}


async def test_TC_E3_FR012_03_no_allowed_source_internal_keywords_only(clean_db: AsyncEngine, migrated_db: str) -> None:
    """Clarification (b): không nguồn ALLOWED → PARTIAL_COMPLETED / NO_COMPLIANT_SEARCH_SOURCE; keyword nội bộ vẫn có, SERP/gap UNKNOWN."""
    ai = ScriptedKeywordsAI()
    async with keywords_client(migrated_db, ai=ai) as client:
        niche = await seed_niche_with_products(client)
        run = await run_keywords(client, niche)
        assert (run["outcome"], run["stop_reason"]) == ("PARTIAL_COMPLETED", "NO_COMPLIANT_SEARCH_SOURCE"), run
        async with clean_db.connect() as conn:
            n_kw = (await conn.execute(text("SELECT count(*) FROM keywords"))).scalar_one()
            n_serp = (await conn.execute(text("SELECT count(*) FROM serp_observations"))).scalar_one()
            n_fetch = (
                await conn.execute(text("SELECT count(*) FROM tool_executions WHERE tool_name = 'page.fetch'"))
            ).scalar_one()
        assert n_kw > 0 and n_serp == 0 and n_fetch == 0
        items = (await client.get(f"/api/v1/niches/{niche}/keyword-clusters", params={"include_mock": True})).json()[
            "items"
        ]
        assert items  # vẫn xếp hạng được từ dữ liệu nội bộ (Coverage thấp hơn)
        detail = (await client.get(f"/api/v1/keyword-clusters/{items[0]['cluster_id']}")).json()
        assert detail["content_gaps"]["status"] == "UNKNOWN" and detail["channels"]["status"] == "UNKNOWN"
        assert all("competition" in (k["evaluation"] or {}).get("missing", []) for k in detail["keywords"])


async def test_TC_E3_FR001_01_create_run_rules(clean_db: AsyncEngine, migrated_db: str) -> None:
    """202 khi đủ điều kiện; 409 NICHE_NOT_ELIGIBLE khi ngách không đủ bằng chứng; 409 KEYWORD_RUN_ACTIVE khi đang có lượt."""
    async with keywords_client(migrated_db) as client:
        niche = await seed_niche_with_products(client)
        first = await start_run(client, niche)
        assert first.status_code == 202, first.text
        again = await start_run(client, niche)
        assert again.status_code == 409 and again.json()["code"] == "KEYWORD_RUN_ACTIVE"
        async with clean_db.begin() as conn:
            await conn.execute(
                text("UPDATE niches SET evidence_status = 'INSUFFICIENT_EVIDENCE' WHERE id = :n"), {"n": niche}
            )
            await conn.execute(text("UPDATE agent_jobs SET status = 'CANCELLED' WHERE job_type = 'keywords.run'"))
        bad = await start_run(client, niche)
        assert bad.status_code == 409 and bad.json()["code"] == "NICHE_NOT_ELIGIBLE"


async def test_TC_E3_FR030_01_run_metrics_and_no_e1_e2_writes(clean_db: AsyncEngine, migrated_db: str) -> None:
    """TC_E3_FR030_01 số liệu lượt; TC_E3_FR002_02 E3 không ghi bảng E1/E2 (so sánh updated_at trước/sau)."""
    async with keywords_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche_with_products(client)
        snap_sql = text(
            "SELECT (SELECT max(updated_at) FROM niches), (SELECT max(updated_at) FROM pain_points),"
            " (SELECT max(updated_at) FROM product_niches), (SELECT max(updated_at) FROM products),"
            " (SELECT count(*) FROM product_evaluations), (SELECT count(*) FROM niche_evaluations)"
        )
        async with clean_db.connect() as conn:
            before = tuple((await conn.execute(snap_sql)).one())
        run = await run_keywords(client, niche)
        async with clean_db.connect() as conn:
            after = tuple((await conn.execute(snap_sql)).one())
        assert before == after
        m = run["metrics"]
        for key in (
            "ai_calls",
            "cost_real_usd",
            "cost_mock_usd",
            "pages_attempted",
            "pages_succeeded",
            "keywords_found",
            "keywords_by_type",
            "keywords_by_length",
            "serp_observed",
            "competitor_pages",
            "clusters",
        ):
            assert key in m, key
        assert m["cost_real_usd"] == "0" and m["ai_calls"] >= 3 and m["keywords_found"] > 0
        assert sum(m["keywords_by_length"].values()) == m["keywords_found"]
