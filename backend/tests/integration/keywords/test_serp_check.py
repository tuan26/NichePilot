"""T033 – theo dõi SERP (FR-031, Should): đổi → phiên bản + changes; không đổi → không phiên bản; lỗi → giữ cũ; watch/acknowledge có audit."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import csrf_headers, run_worker_once
from tests.discovery_helpers import allow_test_source
from tests.fakes.keywords_ai import ScriptedKeywordsAI
from tests.keywords_helpers import keywords_client, run_keywords, seed_niche_with_products

pytestmark = [pytest.mark.integration, pytest.mark.keywords, pytest.mark.mock]
MAIN = "how to stop running out of ingredients in a micro bakery"


async def _check(client: object, cluster_id: str) -> dict[str, object]:
    r = await client.post(  # type: ignore[attr-defined]
        "/api/v1/jobs",
        json={"job_type": "keywords.serp_check", "params": {"cluster_id": cluster_id}},
        headers=csrf_headers(client),  # type: ignore[arg-type]
    )
    assert r.status_code in (200, 201, 202), r.text
    await run_worker_once(client)  # type: ignore[arg-type]
    return dict((await client.get(f"/api/v1/jobs/{r.json()['id']}")).json())  # type: ignore[attr-defined]


async def test_TC_E3_FR031_01_serp_watch_versions_and_alerts(clean_db: AsyncEngine, migrated_db: str) -> None:
    ai = ScriptedKeywordsAI()
    async with keywords_client(migrated_db, ai=ai) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche_with_products(client)
        await run_keywords(client, niche)
        async with clean_db.connect() as conn:
            cid = str(
                (
                    await conn.execute(
                        text(
                            "SELECT c.id FROM keyword_clusters c JOIN keywords k ON k.id = c.primary_keyword_id WHERE k.text = :t"
                        ),
                        {"t": MAIN},
                    )
                ).scalar_one()
            )
        w = await client.put(
            f"/api/v1/keyword-clusters/{cid}/watch", json={"enabled": True}, headers=csrf_headers(client)
        )
        assert w.status_code == 200 and w.json()["watch_enabled"] is True
        calls = len(ai.requests)
        job = await _check(client, cid)  # không đổi → không phiên bản mới
        assert job["status"] == "SUCCEEDED", job
        assert job["result"]["new_version"] is None
        client.mock_web.search[MAIN] = [  # type: ignore[attr-defined]
            "https://bakersforum.example/t/flour-ran-out-again",
            "https://newguide.example/blog/flour-par-levels",
        ]
        job = await _check(client, cid)
        assert job["result"]["new_version"] == 2 and job["result"]["outcome"] == "COMPLETED"
        assert len(ai.requests) == calls  # serp_check không gọi AI
        detail = (await client.get(f"/api/v1/keyword-clusters/{cid}")).json()
        v2 = next(s for s in detail["serp"] if s["version"] == 2)
        assert v2["changes"]["added"] == ["https://newguide.example/blog/flour-par-levels"]
        assert "https://cooking.stackexchange.com/questions/101/track-flour" in v2["changes"]["removed"]
        assert detail["serp_alert"] is True
        ack = await client.post(
            f"/api/v1/keyword-clusters/{cid}/serp-versions/2/acknowledge", headers=csrf_headers(client)
        )
        assert ack.status_code == 200 and ack.json()["serp_alert"] is False
        async with clean_db.begin() as conn:  # nguồn bị tắt → lỗi được ghi, quan sát cũ giữ nguyên
            await conn.execute(text("UPDATE source_policies SET enabled = false"))
        job = await _check(client, cid)
        assert job["result"]["outcome"] == "PARTIAL_COMPLETED"
        detail = (await client.get(f"/api/v1/keyword-clusters/{cid}")).json()
        assert (
            detail["last_check_error"] == "NO_COMPLIANT_SEARCH_SOURCE"
            and len([s for s in detail["serp"] if s["keyword_id"] == v2["keyword_id"]]) == 2
        )
        async with clean_db.connect() as conn:
            actions = set(
                (await conn.execute(text("SELECT action FROM audit_logs WHERE action LIKE 'keyword.%'")))
                .scalars()
                .all()
            )
        assert {"keyword.watch_changed", "keyword.serp_acknowledged", "keyword.run_created"} <= actions
