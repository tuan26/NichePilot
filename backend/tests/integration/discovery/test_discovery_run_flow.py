"""T058 – Luồng `discovery.run` với nguồn + AI giả lập (FR-002, FR-006a, FR-006b, SC-002).

Không truy cập mạng; mọi dữ liệu gắn MOCK (nguồn giả lập + AI kịch bản). KHÔNG chứng minh nguồn thật hay Claude API thật.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import csrf_headers, run_worker_once
from tests.discovery_helpers import allow_test_source, discovery_client
from tests.fakes.discovery_ai import ScriptedDiscoveryAI

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]


async def _run(client: object, clean_db: AsyncEngine, body: dict[str, object]) -> dict[str, object]:
    r = await client.post("/api/v1/discovery/runs", json=body, headers=csrf_headers(client))  # type: ignore[attr-defined]
    assert r.status_code == 201, r.text
    await run_worker_once(client)  # type: ignore[arg-type]
    got = await client.get(f"/api/v1/discovery/runs/{r.json()['id']}")  # type: ignore[attr-defined]
    return dict(got.json())


async def test_TC_E1_FR002_02_open_domain_run_collects_sources_and_creates_candidates(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    ai = ScriptedDiscoveryAI()
    async with discovery_client(migrated_db, ai=ai) as client:
        await allow_test_source(clean_db)
        run = await _run(client, clean_db, {"market": "US"})
        assert run["job"]["status"] == "SUCCEEDED", run
        assert run["outcome"] == "COMPLETED" and run["stop_reason"] == "CANDIDATES_EXHAUSTED"
        m = run["metrics"]
        assert m["candidates"] == 3 and m["pages_succeeded"] >= 2 and m["ai_calls"] >= 1
        assert float(m["cost_real_usd"]) == 0 and float(m["cost_mock_usd"]) > 0
        async with clean_db.connect() as conn:
            niches = (await conn.execute(text("SELECT name, data_origin, country FROM niches"))).all()
            sources = (
                await conn.execute(
                    text(
                        "SELECT source_policy_id IS NOT NULL, policy_verified_at, registered_domain FROM research_sources"
                    )
                )
            ).all()
            ev = (await conn.execute(text("SELECT redaction_status, pii_engine, excerpt FROM research_evidence"))).all()
            links = (
                await conn.execute(text("SELECT count(*) FROM niche_run_links WHERE role = 'DISCOVERED'"))
            ).scalar_one()
        assert (
            len(niches) == 3 and {n.data_origin for n in niches} == {"MOCK"} and {n.country for n in niches} == {"US"}
        )
        assert links == 3
        assert sources and all(s[0] and s[1] is not None for s in sources)
        assert {s[2] for s in sources} >= {"forum.example", "reviews.example"}
        assert ev and all(e[0] == "REDACTED" and e[1] == "regex-phone/1" for e in ev)


async def test_TC_E1_SC002_01_open_domain_candidates_span_three_domains(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    ai = ScriptedDiscoveryAI()
    async with discovery_client(migrated_db, ai=ai) as client:
        await allow_test_source(clean_db)
        run = await _run(client, clean_db, {"market": "US"})
        assert run["metrics"]["candidate_domains"] >= 3
        cand_req = next(r for r in ai.requests if r.task_type == "discovery.candidates")
        prompt = "\n".join(str(m.content) for m in cand_req.messages)
        assert "at least 3 different domains" in prompt and "US" in prompt


async def test_TC_E1_FR006a_01_source_failures_recorded_without_substitute_data(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        web = client.services.discovery.backends.mock_web  # type: ignore[attr-defined]
        web.search["default"] = [
            "https://blocked.example/page",
            "https://broken.example/page",
            "https://slow.example/page",
        ]
        run = await _run(client, clean_db, {"market": "US", "max_candidates": 3})
        m = run["metrics"]
        assert m["pages_succeeded"] == 0 and m["pages_skipped"] + m["pages_failed"] == 3
        assert m["skipped_by_reason"].get("ACCESS_RESTRICTED") == 1
        async with clean_db.connect() as conn:
            assert (await conn.execute(text("SELECT count(*) FROM research_evidence"))).scalar_one() == 0
            reasons = {r[0] for r in (await conn.execute(text("SELECT reason FROM page_fetch_log"))).all()}
        assert reasons == {"ACCESS_RESTRICTED", "HTTP_ERROR", "RATE_LIMITED"}


async def test_TC_E1_FR006b_01_real_collection_keeps_mock_label_when_ai_is_mock(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    """Nguồn giả lập trong test → MOCK; dữ liệu thu thập và phân tích AI giả lập không được trình bày như nghiên cứu thật."""
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        run = await _run(client, clean_db, {"market": "US"})
        assert run["data_origin"] == "MOCK"
        async with clean_db.connect() as conn:
            origins = {r[0] for r in (await conn.execute(text("SELECT data_origin FROM research_sources"))).all()}
            ckpt = (await conn.execute(text("SELECT checkpoint FROM agent_jobs"))).scalar_one()
        assert origins == {"MOCK"}
        assert "run out of flour" not in json.dumps(ckpt)  # checkpoint không chứa văn bản
