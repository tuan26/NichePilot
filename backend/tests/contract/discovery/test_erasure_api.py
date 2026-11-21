"""T074 – `POST /api/v1/evidence/{evidence_id}/erase` (FR-013e): EVIDENCE/SOURCE; 409 khi đã xóa; audit không nội dung; ngách
đủ đúng 2 nhóm → INSUFFICIENT_EVIDENCE; không thu thập lại cùng nội dung; lỗi ghi sổ / sổ lệch → thất bại an toàn. MOCK."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import run_worker_once
from tests.discovery_helpers import allow_test_source, discovery_client
from tests.discovery_run import FORUM, REVIEW, bakery_evidence, erase, niche_status, run_discovery, set_search

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]
FORUM_TEXT = "We lose about three hours each week"


async def test_TC_E1_FR013e_02_erase_source_recomputes_niche_and_audits_without_content(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        await run_discovery(client)
        assert await niche_status(clean_db) == "EVIDENCE_SUFFICIENT"  # đúng 2 nhóm độc lập
        forum_ids = await bakery_evidence(clean_db, "forum.example")
        r = await erase(client, forum_ids[0], scope="SOURCE")
        assert r.status_code == 202, r.text
        body = r.json()
        assert set(body) >= {"erasure_id", "affected_niche_ids", "recompute_job"}
        assert body["recompute_job"]["job_type"] == "discovery.recompute"
        assert len(body["affected_niche_ids"]) == 1
        # tính lại NGAY (đồng bộ) – không chờ job
        assert await niche_status(clean_db) == "INSUFFICIENT_EVIDENCE"
        async with clean_db.connect() as conn:
            ev = (
                await conn.execute(
                    text(
                        "SELECT excerpt, value, lifecycle_status, erased_at FROM research_evidence WHERE id = ANY(:i)"
                    ),
                    {"i": forum_ids},
                )
            ).all()
            src = (
                await conn.execute(
                    text(
                        "SELECT s.url, s.title, s.lifecycle_status FROM research_sources s JOIN research_evidence e"
                        " ON e.source_id = s.id WHERE e.id = :i"
                    ),
                    {"i": forum_ids[0]},
                )
            ).one()
            req = (await conn.execute(text("SELECT * FROM evidence_erasure_requests"))).mappings().one()
            audit = (
                (
                    await conn.execute(
                        text("SELECT row_to_json(a)::text FROM audit_logs a WHERE action = 'evidence.erased'")
                    )
                )
                .scalars()
                .all()
            )
            links = (
                (
                    await conn.execute(
                        text("SELECT counted_for_threshold FROM niche_evidence_links WHERE evidence_id = ANY(:i)"),
                        {"i": forum_ids},
                    )
                )
                .scalars()
                .all()
            )
        assert all(e.excerpt is None and e.value is None and e.lifecycle_status == "ERASED" and e.erased_at for e in ev)
        assert src.url.startswith("erased:") and src.title is None and src.lifecycle_status == "ERASED"
        assert req["target_type"] == "SOURCE" and req["ledger_seq"] == 1 and req["applied_at"] is not None
        assert len(audit) == 1 and FORUM_TEXT not in audit[0] and "forum.example/t" not in audit[0]
        assert json.loads(audit[0])["after"]["reason"] == "Owner request (test)"
        assert links and not any(links)
        ledger_lines = client.services.discovery.ledger.path.read_text().splitlines()  # type: ignore[attr-defined]
        assert len(ledger_lines) == 2 and FORUM_TEXT not in "\n".join(ledger_lines)
        assert (await client.get("/api/v1/discovery/status")).json()["erasure_ledger"]["status"] == "OK"
        # job tính lại: chạy được, 0 lời gọi AI
        await run_worker_once(client)
        async with clean_db.connect() as conn:
            job = (
                await conn.execute(
                    text("SELECT status FROM agent_jobs WHERE id = :j"), {"j": body["recompute_job"]["job_id"]}
                )
            ).scalar_one()
            ai = (
                await conn.execute(
                    text("SELECT count(*) FROM ai_usage_logs WHERE job_id = :j"), {"j": body["recompute_job"]["job_id"]}
                )
            ).scalar_one()
        assert job == "SUCCEEDED" and ai == 0


async def test_TC_E1_FR013e_03_conflicts_validation_and_single_evidence_scope(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        await run_discovery(client)
        forum_ids = await bakery_evidence(clean_db, "forum.example")
        assert len(forum_ids) >= 2
        r = await erase(client, forum_ids[0])  # mặc định EVIDENCE
        assert r.status_code == 202
        assert await bakery_evidence(clean_db, "forum.example") == forum_ids[1:]  # chỉ 1 bằng chứng bị xóa
        again = await erase(client, forum_ids[0])
        assert again.status_code == 409 and again.json()["code"] == "EVIDENCE_ALREADY_ERASED"
        missing = await erase(client, "00000000-0000-0000-0000-000000000000")
        assert missing.status_code == 404 and missing.json()["code"] == "EVIDENCE_NOT_FOUND"
        assert (await erase(client, forum_ids[1], reason="ab")).status_code == 422
        assert (await erase(client, forum_ids[1], scope="ALL")).status_code == 422
        assert len(client.services.discovery.ledger.path.read_text().splitlines()) == 2  # type: ignore[attr-defined]


async def test_TC_E1_FR013e_04_erased_content_not_collected_again(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        await run_discovery(client)
        forum_ids = await bakery_evidence(clean_db, "forum.example")
        assert (await erase(client, forum_ids[0], scope="SOURCE")).status_code == 202
        run2 = await run_discovery(client)
        assert run2["metrics"]["skipped_by_reason"].get("ERASED_CONTENT") == 1
        assert await bakery_evidence(clean_db, "forum.example") == []
        async with clean_db.connect() as conn:
            leaked = (
                await conn.execute(
                    text("SELECT count(*) FROM research_evidence WHERE excerpt LIKE :t"), {"t": f"%{FORUM_TEXT}%"}
                )
            ).scalar_one()
        assert leaked == 0


async def test_TC_E1_FR013e_06_ledger_write_failure_leaves_data_untouched(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        await run_discovery(client)
        forum_ids = await bakery_evidence(clean_db, "forum.example")
        ledger = client.services.discovery.ledger  # type: ignore[attr-defined]

        def broken(*_a: object, **_k: object) -> None:
            raise OSError(28, "No space left on device")

        ledger.append = broken
        r = await erase(client, forum_ids[0], scope="SOURCE")
        assert r.status_code == 503 and r.json()["code"] == "ERASURE_LEDGER_WRITE_FAILED"
        assert await bakery_evidence(clean_db, "forum.example") == forum_ids  # DB không đổi (sổ ghi trước)
        assert await niche_status(clean_db) == "EVIDENCE_SUFFICIENT"
        async with clean_db.connect() as conn:
            assert (await conn.execute(text("SELECT count(*) FROM evidence_erasure_requests"))).scalar_one() == 0


async def test_TC_E1_FR013e_07_out_of_sync_ledger_blocks_until_applied(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        await run_discovery(client)
        forum_ids = await bakery_evidence(clean_db, "forum.example")
        async with clean_db.connect() as conn:
            niche_id = (await conn.execute(text("SELECT id FROM niches WHERE name LIKE '%bakery%'"))).scalar_one()
            source_id = (
                await conn.execute(text("SELECT source_id FROM research_evidence WHERE id = :i"), {"i": forum_ids[0]})
            ).scalar_one()
        ds = client.services.discovery  # type: ignore[attr-defined]
        # dòng sổ đã ghi nhưng DB chưa áp dụng (vd. tiến trình chết giữa ghi sổ và commit)
        ds.ledger.append("SOURCE", source_id, content_hash=None, url_hash=None, requested_by=None)
        ds._health = None
        r = await erase(client, forum_ids[0])
        assert r.status_code == 503 and r.json()["code"] == "ERASURE_LEDGER_NOT_APPLIED"
        assert (await client.get(f"/api/v1/niches/{niche_id}")).status_code == 503
        await ds.apply_ledger()  # lần áp dụng sau hoàn tất (migrate/restore)
        assert await bakery_evidence(clean_db, "forum.example") == []
        assert await niche_status(clean_db) == "INSUFFICIENT_EVIDENCE"  # áp dụng sổ cũng tính lại ngách
        assert (await client.get(f"/api/v1/niches/{niche_id}")).status_code == 200


async def test_TC_E1_FR013e_08_db_failure_after_ledger_write_is_completed_by_next_apply(
    clean_db: AsyncEngine, migrated_db: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from nichepilot.modules.discovery import erasure

    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        await run_discovery(client)
        forum_ids = await bakery_evidence(clean_db, "forum.example")
        real_apply = erasure.apply_entry

        async def failing(*_a: object, **_k: object) -> None:
            raise RuntimeError("simulated DB failure")

        monkeypatch.setattr(erasure, "apply_entry", failing)
        r = await erase(client, forum_ids[0], scope="SOURCE")
        assert r.status_code == 500
        assert await bakery_evidence(clean_db, "forum.example") == forum_ids  # transaction rollback
        ds = client.services.discovery  # type: ignore[attr-defined]
        assert (await ds.ledger_health(force=True)).status == "OUT_OF_SYNC"
        monkeypatch.setattr(erasure, "apply_entry", real_apply)
        await ds.apply_ledger()
        assert await bakery_evidence(clean_db, "forum.example") == []
        assert await niche_status(clean_db) == "INSUFFICIENT_EVIDENCE"
        assert (await ds.ledger_health(force=True)).status == "OK"
