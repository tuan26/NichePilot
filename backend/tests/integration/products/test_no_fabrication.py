"""T063 – SC-001: mọi giá trị hoa hồng/cookie/giá truy về bằng chứng chứa chính giá trị đó (Constitution I; FR-009). MOCK."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from nichepilot.modules.products.extraction import numbers_in
from tests.discovery_helpers import allow_test_source
from tests.products_helpers import products_client, run_products, seed_niche

pytestmark = [pytest.mark.integration, pytest.mark.products, pytest.mark.mock]
NUMERIC = {
    "price": ("amount",),
    "commission": ("value", "min", "max"),
    "cookie_days": ("days",),
    "payment": ("min_payout",),
}


async def test_TC_E2_SC001_01_every_number_traceable_to_excerpt(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        await run_products(client, niche)
        async with clean_db.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT claim_key, value, excerpt, source_id, verification_status FROM research_evidence"
                        " WHERE claim_key = ANY(:k) AND lifecycle_status = 'ACTIVE'"
                    ),
                    {"k": list(NUMERIC)},
                )
            ).all()
        assert rows
        from decimal import Decimal

        for key, value, excerpt, source_id, status in rows:
            assert source_id is not None and excerpt and status in ("VERIFIED", "INFERRED")
            for field in NUMERIC[key]:
                n = value.get(field)
                if n is not None:
                    assert Decimal(str(n)).normalize() in numbers_in(excerpt), (key, field, n, excerpt)
