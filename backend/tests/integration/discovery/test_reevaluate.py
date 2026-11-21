"""T121 – Đánh giá lại ngách (FR-034): `POST /api/v1/niches/{id}/reevaluate` → job `discovery.reevaluate`; đánh giá mới, giữ đánh
giá cũ, so sánh thay đổi; mọi lời gọi AI qua Gateway (giữ chỗ ngân sách); liên kết lượt REEVALUATED. MOCK."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import csrf_headers, run_worker_once
from tests.discovery_helpers import allow_test_source, discovery_client
from tests.discovery_run import FORUM, REVIEW, run_discovery, set_search
from tests.fakes.discovery_ai import ScriptedDiscoveryAI

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]


async def test_TC_E1_FR034_01_reevaluation_creates_new_evaluation_and_keeps_history(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    ai = ScriptedDiscoveryAI()
    async with discovery_client(migrated_db, ai=ai) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM])  # lượt đầu: một nguồn → chưa đủ bằng chứng
        await run_discovery(client)
        async with clean_db.connect() as conn:
            nid, old_eval = (
                await conn.execute(text("SELECT id, latest_evaluation_id FROM niches WHERE name LIKE '%bakery%'"))
            ).one()
        set_search(client, [FORUM, REVIEW])  # dữ liệu mới
        r = await client.post(f"/api/v1/niches/{nid}/reevaluate", headers=csrf_headers(client))
        assert r.status_code == 202 and r.json()["job_type"] == "discovery.reevaluate"
        before_calls = len(ai.requests)
        await run_worker_once(client)
        job = (await client.get(f"/api/v1/jobs/{r.json()['job_id']}")).json()
        assert job["status"] == "SUCCEEDED", job
        comparison = job["result"]["comparison"]
        assert comparison["before"]["evaluation_id"] == str(old_eval)
        assert comparison["before"]["evidence_status"] == "INSUFFICIENT_EVIDENCE"
        assert comparison["after"]["evidence_status"] == "EVIDENCE_SUFFICIENT"
        assert comparison["after"]["confidence_score"] > comparison["before"]["confidence_score"]  # trần 30 được gỡ
        assert {r.task_type for r in ai.requests[before_calls:]} <= {
            "discovery.extract",
            "discovery.assess",
        }  # không đề xuất ứng viên
        async with clean_db.connect() as conn:
            evals = (
                await conn.execute(text("SELECT count(*) FROM niche_evaluations WHERE niche_id = :n"), {"n": nid})
            ).scalar_one()
            role = (
                await conn.execute(
                    text("SELECT role FROM niche_run_links WHERE niche_id = :n ORDER BY created_at DESC LIMIT 1"),
                    {"n": nid},
                )
            ).scalar_one()
            status = (
                await conn.execute(text("SELECT evidence_status FROM niches WHERE id = :n"), {"n": nid})
            ).scalar_one()
            logs = (
                await conn.execute(
                    text("SELECT count(*) FROM ai_usage_logs WHERE job_id = :j"), {"j": r.json()["job_id"]}
                )
            ).scalar_one()
            held = (
                await conn.execute(
                    text("SELECT count(*) FROM budget_reservations WHERE job_id = :j"), {"j": r.json()["job_id"]}
                )
            ).scalar_one()
        assert evals >= 2 and role == "REEVALUATED" and status == "EVIDENCE_SUFFICIENT"
        assert logs == held == len(ai.requests) - before_calls  # mỗi lời gọi có giữ chỗ ngân sách
        history = (await client.get(f"/api/v1/niches/{nid}/evaluations")).json()
        assert history[-1]["id"] == str(old_eval)  # đánh giá cũ vẫn còn


async def test_TC_E1_FR034_02_reevaluate_preconditions(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with discovery_client(migrated_db) as client:
        r = await client.post(
            "/api/v1/niches/00000000-0000-0000-0000-000000000000/reevaluate", headers=csrf_headers(client)
        )
        assert r.status_code == 404
        await allow_test_source(clean_db)
        set_search(client, [FORUM])
        await run_discovery(client)
        async with clean_db.begin() as conn:
            nid = (await conn.execute(text("SELECT id FROM niches LIMIT 1"))).scalar_one()
            await conn.execute(text("UPDATE source_policies SET enabled = false WHERE source_key = 'test:mock-engine'"))
        r2 = await client.post(f"/api/v1/niches/{nid}/reevaluate", headers=csrf_headers(client))
        assert r2.status_code == 409 and r2.json()["code"] == "NO_COMPLIANT_SEARCH_SOURCE"
