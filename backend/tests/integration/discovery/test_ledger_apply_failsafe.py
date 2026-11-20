"""T016 – apply_erasure_ledger --strict thất bại an toàn (FR-013f; X4): mọi tình huống → rollback, BLOCKED, mã lỗi."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from nichepilot.modules.discovery.erasure import Ledger, LedgerError, apply_erasure_ledger, ledger_health

pytestmark = [pytest.mark.integration, pytest.mark.discovery]


async def _state(engine: AsyncEngine) -> tuple[object, ...]:
    async with engine.connect() as conn:
        return tuple(
            (
                await conn.execute(text("SELECT ledger_id, applied_seq, status, last_error FROM erasure_ledger_state"))
            ).one()
        )


async def _evidence(engine: AsyncEngine) -> uuid.UUID:
    async with engine.begin() as conn:
        project = (await conn.execute(text("SELECT id FROM projects LIMIT 1"))).scalar_one()
        src = (
            await conn.execute(
                text(
                    "INSERT INTO research_sources (project_id, source_type, url, canonical_url, content_hash, data_origin)"
                    " VALUES (:p, 'FORUM', :u, :u, 'c', 'REAL') RETURNING id"
                ),
                {"p": project, "u": f"https://f.example/{uuid.uuid4().hex}"},
            )
        ).scalar_one()
        return (
            await conn.execute(
                text(
                    "INSERT INTO research_evidence (project_id, source_id, claim_key, value, excerpt, verification_status,"
                    " data_origin) VALUES (:p, :s, 'pain', '\"x\"', 'đoạn trích', 'INFERRED', 'REAL') RETURNING id"
                ),
                {"p": project, "s": src},
            )
        ).scalar_one()


async def test_TC_E1_FR013f_02_fresh_install_initializes_ledger(clean_db: AsyncEngine, tmp_path: Path) -> None:
    sm = async_sessionmaker(clean_db)
    res = await apply_erasure_ledger(sm, Ledger(tmp_path))
    assert res.applied == 0 and Ledger(tmp_path).exists()
    lid, seq, status, _ = await _state(clean_db)
    assert lid is not None and seq == 0 and status == "OK"
    assert (await ledger_health(sm, Ledger(tmp_path))).status == "OK"


async def test_TC_E1_FR013f_03_missing_ledger_with_known_ledger_id_blocks(
    clean_db: AsyncEngine, tmp_path: Path
) -> None:
    sm = async_sessionmaker(clean_db)
    await apply_erasure_ledger(sm, Ledger(tmp_path))
    (tmp_path / "ledger.jsonl").unlink()
    with pytest.raises(LedgerError) as exc:
        await apply_erasure_ledger(sm, Ledger(tmp_path))
    assert exc.value.code == "LEDGER_MISSING"
    assert (await _state(clean_db))[2:] == ("BLOCKED", "LEDGER_MISSING")
    assert (await ledger_health(sm, Ledger(tmp_path))).status == "BLOCKED"


async def test_TC_E1_FR013f_04_ledger_id_mismatch_and_tampered_chain_block(
    clean_db: AsyncEngine, tmp_path: Path
) -> None:
    sm = async_sessionmaker(clean_db)
    await apply_erasure_ledger(sm, Ledger(tmp_path))
    other = tmp_path / "other"
    Ledger(other).init(uuid.uuid4())
    with pytest.raises(LedgerError) as exc:
        await apply_erasure_ledger(sm, Ledger(other))
    assert exc.value.code == "LEDGER_ID_MISMATCH"
    ledger = Ledger(tmp_path)
    ledger.append("EVIDENCE", uuid.uuid4(), content_hash=None, url_hash=None, requested_by=None)
    path = tmp_path / "ledger.jsonl"
    lines = path.read_text().splitlines()
    doc = json.loads(lines[-1])
    doc["target_type"] = "SOURCE"
    lines[-1] = json.dumps(doc)
    path.write_text("\n".join(lines) + "\n")
    with pytest.raises(LedgerError) as exc2:
        await apply_erasure_ledger(sm, Ledger(tmp_path))
    assert exc2.value.code == "LEDGER_CORRUPT" and (await _state(clean_db))[2] == "BLOCKED"


async def test_TC_E1_FR013f_05_ledger_older_than_db_blocks(clean_db: AsyncEngine, tmp_path: Path) -> None:
    sm = async_sessionmaker(clean_db)
    ledger = Ledger(tmp_path)
    await apply_erasure_ledger(sm, ledger)
    backup = (tmp_path / "ledger.jsonl").read_text()  # bản sổ cũ (seq 0)
    ledger.append("EVIDENCE", uuid.uuid4(), content_hash=None, url_hash=None, requested_by=None)
    await apply_erasure_ledger(sm, ledger)  # DB applied_seq = 1
    (tmp_path / "ledger.jsonl").write_text(backup)  # thay bằng sổ cũ hơn DB
    with pytest.raises(LedgerError) as exc:
        await apply_erasure_ledger(sm, Ledger(tmp_path))
    assert exc.value.code == "LEDGER_OLDER_THAN_DB"


async def test_TC_E1_FR013f_06_apply_erases_atomically_or_rolls_back(clean_db: AsyncEngine, tmp_path: Path) -> None:
    sm = async_sessionmaker(clean_db)
    ledger = Ledger(tmp_path)
    await apply_erasure_ledger(sm, ledger)
    ev = await _evidence(clean_db)
    ledger.append("EVIDENCE", ev, content_hash=None, url_hash=None, requested_by=None)
    ledger.append(
        "EVIDENCE", uuid.uuid4(), content_hash=None, url_hash=None, requested_by=None
    )  # đích không tồn tại: OK
    res = await apply_erasure_ledger(sm, ledger)
    assert res.applied == 2
    async with clean_db.connect() as conn:
        row = (
            await conn.execute(
                text("SELECT lifecycle_status, excerpt, value FROM research_evidence WHERE id = :i"), {"i": ev}
            )
        ).one()
    assert tuple(row) == ("ERASED", None, None)
    assert (await _state(clean_db))[1:3] == (2, "OK")
    # lỗi giữa chừng (loại đích không hợp lệ được ghi thẳng vào sổ) → rollback toàn bộ, BLOCKED
    ev2 = await _evidence(clean_db)
    ledger.append("EVIDENCE", ev2, content_hash=None, url_hash=None, requested_by=None)
    ledger._append_raw({"target_type": "BOGUS", "target_id": str(uuid.uuid4())})
    with pytest.raises(LedgerError) as exc:
        await apply_erasure_ledger(sm, ledger)
    assert exc.value.code == "LEDGER_APPLY_FAILED"
    async with clean_db.connect() as conn:
        status = (
            await conn.execute(text("SELECT lifecycle_status FROM research_evidence WHERE id = :i"), {"i": ev2})
        ).scalar_one()
    assert status == "ACTIVE"  # rollback: ev2 chưa bị xóa nửa vời
    assert (await _state(clean_db))[1:3] == (2, "BLOCKED")
