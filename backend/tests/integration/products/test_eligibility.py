"""T010 – ngách đủ điều kiện cho Product Discovery (FR-001; Clarification Q1). MOCK."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from nichepilot.core.errors import AppError
from nichepilot.jobs import discovery_demo_seed
from nichepilot.modules.products.eligibility import check_niche_eligible
from tests.products_helpers import products_client

pytestmark = [pytest.mark.integration, pytest.mark.products, pytest.mark.mock]


async def _set(engine: AsyncEngine, niche: str, **cols: object) -> None:
    sets = ", ".join(f"{k} = :{k}" for k in cols)
    async with engine.begin() as conn:
        user = (await conn.execute(text("SELECT id FROM users LIMIT 1"))).scalar_one()
        sql = f"UPDATE niches SET {sets}, decided_by = :u WHERE id = :n"  # noqa: S608 – tên cột là hằng số trong test
        await conn.execute(text(sql), {**cols, "u": user, "n": niche})


async def test_TC_E2_FR001_01_sufficient_and_not_rejected_is_eligible(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        sm = client.services.discovery.sessionmaker  # type: ignore[attr-defined]
        niche = (await discovery_demo_seed.seed_demo(sm))["niche_id"]
        for decision in ("CANDIDATE", "WATCH", "PURSUE"):
            await _set(clean_db, str(niche), decision_status=decision)
            async with async_sessionmaker(clean_db)() as s:
                got = await check_niche_eligible(s, uuid.UUID(str(niche)))
            assert got.country == "US" and got.data_origin == "MOCK"


async def test_TC_E2_FR001_02_ineligible_niches_rejected(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        sm = client.services.discovery.sessionmaker  # type: ignore[attr-defined]
        niche = str((await discovery_demo_seed.seed_demo(sm))["niche_id"])
        cases = [
            ({"decision_status": "REJECTED", "owner_decision_reason": "[MOCK] no"}, "REJECTED"),
            ({"decision_status": "HIDDEN", "owner_decision_reason": "[MOCK] hide"}, "HIDDEN"),
            ({"decision_status": "CANDIDATE", "evidence_status": "INSUFFICIENT_EVIDENCE"}, "INSUFFICIENT_EVIDENCE"),
        ]
        for cols, reason in cases:
            await _set(clean_db, niche, **cols)
            async with async_sessionmaker(clean_db)() as s:
                with pytest.raises(AppError) as exc:
                    await check_niche_eligible(s, uuid.UUID(niche))
            assert exc.value.code == "NICHE_NOT_ELIGIBLE" and exc.value.params == {"reason": reason}
        async with async_sessionmaker(clean_db)() as s:
            with pytest.raises(AppError) as exc:
                await check_niche_eligible(s, uuid.uuid4())
        assert exc.value.code == "NICHE_NOT_FOUND"
