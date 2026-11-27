"""T057 – theo dõi thay đổi điều khoản (FR-040, Should; FR-037). MOCK."""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from nichepilot.tools.mock_sources import MockPage
from tests.api_helpers import csrf_headers, run_worker_once
from tests.discovery_helpers import allow_test_source
from tests.products_helpers import products_client, run_products, seed_niche

pytestmark = [pytest.mark.integration, pytest.mark.products, pytest.mark.mock]
TERMS = "https://stockpal.example/partners"


async def _check(client: Any, program_id: str) -> dict[str, Any]:
    r = await client.post(
        "/api/v1/jobs",
        json={"job_type": "products.terms_check", "params": {"program_id": program_id}},
        headers=csrf_headers(client),
    )
    assert r.status_code in (200, 201, 202), r.text
    await run_worker_once(client)
    return dict((await client.get(f"/api/v1/affiliate-programs/{program_id}")).json())


async def _program(engine: AsyncEngine) -> str:
    async with engine.connect() as conn:
        return str(
            (
                await conn.execute(text("SELECT id FROM affiliate_programs WHERE terms_url = :u"), {"u": TERMS})
            ).scalar_one()
        )


async def test_TC_E2_FR040_01_changed_terms_create_version(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        await run_products(client, niche)
        prog = await _program(clean_db)
        first = await _check(client, prog)
        assert [v["version"] for v in first["terms_versions"]] == [1] and first["last_check_error"] is None
        web = client.mock_web  # type: ignore[attr-defined]
        old = web.pages[TERMS]
        web.pages[TERMS] = MockPage(
            200, (old.html or "").replace("30% recurring commission", "20% recurring commission")
        )
        second = await _check(client, prog)
        latest = second["terms_versions"][0]
        assert latest["version"] == 2 and latest["acknowledged_at"] is None
        changes = {c["claim_key"]: c for c in latest["changes"]}
        assert changes["commission"]["old"]["value"] == 30.0 and changes["commission"]["new"]["value"] == 20.0
        attrs = {a["key"]: a for a in second["attributes"]}
        assert attrs["commission"]["value"]["value"] == 20.0  # giá trị mới nhất của cùng URL thay thế giá trị cũ


async def test_TC_E2_FR040_02_unchanged_terms_no_new_version(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        await run_products(client, niche)
        prog = await _program(clean_db)
        await _check(client, prog)
        again = await _check(client, prog)
        assert [v["version"] for v in again["terms_versions"]] == [1]


async def test_TC_E2_FR040_03_unreachable_terms_keep_old_values(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        await run_products(client, niche)
        prog = await _program(clean_db)
        before = {
            a["key"]: a["value"] for a in (await client.get(f"/api/v1/affiliate-programs/{prog}")).json()["attributes"]
        }
        client.mock_web.pages[TERMS] = MockPage(500)  # type: ignore[attr-defined]
        after = await _check(client, prog)
        assert after["last_check_error"] and after["terms_versions"] == []
        assert {a["key"]: a["value"] for a in after["attributes"]} == before


async def test_TC_E2_FR040_04_watch_and_acknowledge_audited(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        await run_products(client, niche)
        prog = await _program(clean_db)
        w = await client.put(
            f"/api/v1/affiliate-programs/{prog}/watch", json={"enabled": True}, headers=csrf_headers(client)
        )
        assert w.status_code == 200 and w.json()["watch_enabled"] is True
        await _check(client, prog)
        ack = await client.post(
            f"/api/v1/affiliate-programs/{prog}/terms-versions/1/acknowledge", headers=csrf_headers(client)
        )
        assert ack.status_code == 200 and ack.json()["terms_versions"][0]["acknowledged_at"]
        async with clean_db.connect() as conn:
            actions = set((await conn.execute(text("SELECT action FROM audit_logs"))).scalars())
        assert {"program.watch_changed", "program.terms_acknowledged"} <= actions
