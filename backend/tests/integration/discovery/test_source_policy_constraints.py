"""T013 – Ràng buộc DB của source_policies (FR-006c, FR-006d; quyết định A1)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = [pytest.mark.integration, pytest.mark.discovery]
INSERT = (
    "INSERT INTO source_policies (source_key, display_name, adapter_type, config, tos_url, compliance_status, enabled,"
    " verified_at, verified_by, verification_note, allowed_access_methods, permitted_use_scope)"
    " VALUES (:k, 'T', 'searxng_engine', '{\"engine_name\": \"x\"}', 'https://tos.example', :s, :e, :va, :vb, :n,"
    " CAST(:m AS text[]), :sc)"
)


@pytest.fixture
async def db(clean_db: AsyncEngine) -> AsyncIterator[AsyncEngine]:
    yield clean_db


async def _user(conn: object) -> object:
    return (
        await conn.execute(  # type: ignore[attr-defined]
            text("INSERT INTO users (username, password_hash) VALUES ('owner_sp', 'x') RETURNING id")
        )
    ).scalar_one()


def _row(key: str, status: str, enabled: bool, user: object = None, full: bool = False) -> dict[str, object]:
    return {
        "k": key,
        "s": status,
        "e": enabled,
        "va": "2026-11-01" if full else None,
        "vb": user if full else None,
        "n": "Điều khoản §3 cho phép truy vấn tự động qua API" if full else None,
        "m": "{OFFICIAL_API}" if full else "{}",
        "sc": "Nghiên cứu nội bộ, lưu trích đoạn có ghi nguồn" if full else None,
    }


@pytest.mark.parametrize("status", ["UNVERIFIED", "PROHIBITED"])
async def test_TC_E1_FR006c_01_only_allowed_can_be_enabled(db: AsyncEngine, status: str) -> None:
    async with db.connect() as conn:
        user = await _user(conn)
        with pytest.raises(IntegrityError, match=r"enabled_only_allowed|prohibited_has_evidence"):
            await conn.execute(text(INSERT), _row(f"test:{status.lower()}", status, True, user, full=True))
        await conn.rollback()


async def test_TC_E1_FR006c_02_allowed_requires_full_evidence(db: AsyncEngine) -> None:
    async with db.connect() as conn:
        user = await _user(conn)
        with pytest.raises(IntegrityError, match="allowed_has_evidence"):
            await conn.execute(text(INSERT), _row("test:incomplete", "ALLOWED", False))
        await conn.rollback()
    async with db.begin() as conn:
        user = await _user(conn)
        await conn.execute(text(INSERT), _row("test:complete", "ALLOWED", True, user, full=True))


async def test_TC_E1_FR006c_03_prohibited_requires_evidence_and_config_is_object(db: AsyncEngine) -> None:
    async with db.connect() as conn:
        with pytest.raises(IntegrityError, match="prohibited_has_evidence"):
            await conn.execute(text(INSERT), _row("test:prohibited", "PROHIBITED", False))
        await conn.rollback()


async def test_TC_E1_FR006d_01_seed_sources_are_unverified_and_disabled(db: AsyncEngine) -> None:
    async with db.connect() as conn:
        rows = (await conn.execute(text("SELECT compliance_status, enabled FROM source_policies"))).all()
    assert len(rows) >= 11 and all(r == ("UNVERIFIED", False) for r in rows)
