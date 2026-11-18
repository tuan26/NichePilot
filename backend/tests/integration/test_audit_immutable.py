"""T017 – Audit log append-only (FR-051)."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration


async def test_TC_FR051_01_audit_rows_cannot_be_updated_or_deleted(clean_db: AsyncEngine) -> None:
    async with clean_db.begin() as conn:
        audit_id = (
            await conn.execute(
                text("INSERT INTO audit_logs (actor_type, action) VALUES ('SYSTEM', 'test.created') RETURNING id")
            )
        ).scalar_one()

    for stmt in (
        "UPDATE audit_logs SET action = 'tampered' WHERE id = :id",
        "DELETE FROM audit_logs WHERE id = :id",
    ):
        async with clean_db.connect() as conn:
            with pytest.raises(DBAPIError, match="append-only"):
                await conn.execute(text(stmt), {"id": audit_id})
            await conn.rollback()

    async with clean_db.connect() as conn:
        with pytest.raises(DBAPIError, match="append-only"):
            await conn.execute(text("TRUNCATE audit_logs"))
        await conn.rollback()

    async with clean_db.connect() as conn:
        action = (await conn.execute(text("SELECT action FROM audit_logs WHERE id = :id"), {"id": audit_id})).scalar()
    assert action == "test.created"


async def test_TC_FR051_02_actor_type_constrained(clean_db: AsyncEngine) -> None:
    async with clean_db.connect() as conn:
        with pytest.raises(DBAPIError):
            await conn.execute(text("INSERT INTO audit_logs (actor_type, action) VALUES ('ROBOT', 'x')"))
        await conn.rollback()
