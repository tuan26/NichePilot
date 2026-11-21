"""T075 – Khôi phục backup cũ hơn yêu cầu xóa (FR-013f, SC-016): sau restore + `apply --strict`, bằng chứng vẫn ERASED, ngách được
tính lại, API không trả trích đoạn; trước khi áp dụng, API bị chặn (503).

Restore được MÔ PHỎNG ở mức DB (ghi lại các hàng như trong dump trước khi xóa + `erasure_ledger_state = BLOCKED` như `restore.sh`);
không chạy `pg_dump/pg_restore` thật trong test này (đã kiểm tra thủ công ở smoke US1 – docs/operations/discovery.md)."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.discovery_helpers import allow_test_source, discovery_client
from tests.discovery_run import FORUM, REVIEW, bakery_evidence, erase, niche_status, run_discovery, set_search

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]
FORUM_TEXT = "We lose about three hours each week"
# cột mà việc xóa/tính lại thay đổi – được ghi lại về giá trị trong "backup"
RESTORE_COLUMNS = {
    "research_sources": ("url", "canonical_url", "title", "lifecycle_status", "erased_at"),
    "research_evidence": ("excerpt", "lifecycle_status", "erased_at"),
    "niche_evidence_links": ("independence_group", "counted_for_threshold"),
    "niches": ("evidence_status", "monetization_status"),
    "pain_points": ("evidence_count", "verification_status"),
}


async def _snapshot(engine: AsyncEngine) -> dict[str, list[dict[str, object]]]:
    async with engine.connect() as conn:
        snap = {
            t: [dict(r) for r in (await conn.execute(text(f"SELECT id, {', '.join(c)} FROM {t}"))).mappings().all()]  # noqa: S608
            for t, c in RESTORE_COLUMNS.items()
        }
        snap["erasure_ledger_state"] = [
            dict(r) for r in (await conn.execute(text("SELECT * FROM erasure_ledger_state"))).mappings().all()
        ]
    return snap


async def _restore(engine: AsyncEngine, snap: dict[str, list[dict[str, object]]]) -> None:
    """Ghi đè các hàng về trạng thái trong 'backup' và đánh dấu sổ BLOCKED (như deploy/restore.sh)."""
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM evidence_erasure_requests"))
        for table, cols in RESTORE_COLUMNS.items():
            sets = ", ".join(f"{c} = :{c}" for c in cols)
            for row in snap[table]:
                await conn.execute(text(f"UPDATE {table} SET {sets} WHERE id = :id"), row)  # noqa: S608
        st = snap["erasure_ledger_state"][0]
        await conn.execute(
            text("UPDATE erasure_ledger_state SET applied_seq = :s, applied_hash = :h, status = 'BLOCKED'"),
            {"s": st["applied_seq"], "h": st["applied_hash"]},
        )


async def test_TC_E1_FR013f_09_TC_E1_SC016_03_restore_older_backup_reapplies_erasure(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        await run_discovery(client)
        backup = await _snapshot(clean_db)  # backup TRƯỚC yêu cầu xóa
        forum_ids = await bakery_evidence(clean_db, "forum.example")
        assert (await erase(client, forum_ids[0], scope="SOURCE")).status_code == 202
        await _restore(clean_db, backup)
        assert await bakery_evidence(clean_db, "forum.example") == forum_ids  # dữ liệu đã xóa "quay lại" trong DB
        ds = client.services.discovery  # type: ignore[attr-defined]
        ds._health = None
        async with clean_db.connect() as conn:
            niche_id = (await conn.execute(text("SELECT id FROM niches WHERE name LIKE '%bakery%'"))).scalar_one()
        blocked = await client.get(f"/api/v1/niches/{niche_id}")
        assert blocked.status_code == 503 and blocked.json()["code"] == "ERASURE_LEDGER_NOT_APPLIED"
        assert FORUM_TEXT not in blocked.text
        res = await ds.apply_ledger()  # = python -m nichepilot.jobs.erasure_ledger --strict sau restore
        assert res.applied == 1
        assert await bakery_evidence(clean_db, "forum.example") == []
        assert await niche_status(clean_db) == "INSUFFICIENT_EVIDENCE"
        detail = await client.get(f"/api/v1/niches/{niche_id}")
        assert detail.status_code == 200 and FORUM_TEXT not in detail.text
        assert all(e["source_domain"] != "forum.example" for e in detail.json()["evidence"])


async def test_TC_E1_FR013f_10_missing_ledger_after_restore_fails_safe(clean_db: AsyncEngine, migrated_db: str) -> None:
    from nichepilot.modules.discovery.erasure import LedgerError

    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW])
        await run_discovery(client)
        forum_ids = await bakery_evidence(clean_db, "forum.example")
        assert (await erase(client, forum_ids[0])).status_code == 202
        ds = client.services.discovery  # type: ignore[attr-defined]
        ds.ledger.path.unlink()  # sổ bị mất (volume không được khôi phục)
        with pytest.raises(LedgerError) as exc:
            await ds.apply_ledger()
        assert exc.value.code == "LEDGER_MISSING"
        r = await client.get("/api/v1/discovery/runs")
        assert r.status_code == 503 and r.json()["code"] == "ERASURE_LEDGER_NOT_APPLIED"
