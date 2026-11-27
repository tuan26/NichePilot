"""T033 – không đăng ký/đăng nhập/gửi form (FR-025; SC-002; BR-08, AC-19). MOCK."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.discovery_helpers import allow_test_source
from tests.products_helpers import products_client, run_products, seed_niche

pytestmark = [pytest.mark.integration, pytest.mark.products, pytest.mark.mock]


async def test_TC_E2_FR025_02_TC_E2_SC002_01_only_read_only_tools_used(clean_db: AsyncEngine, migrated_db: str) -> None:
    async with products_client(migrated_db) as client:
        await allow_test_source(clean_db)
        niche = await seed_niche(client)
        run = await run_products(client, niche)
        async with clean_db.connect() as conn:
            tools = set(
                (
                    await conn.execute(
                        text("SELECT DISTINCT tool_name FROM tool_executions WHERE job_id = :j"), {"j": run["job_id"]}
                    )
                ).scalars()
            )
        assert tools <= {"source.query", "page.fetch", "robots.fetch"} and "page.fetch" in tools
        fetched = client.mock_fetcher.requested  # type: ignore[attr-defined]
        assert fetched and all(u.startswith("https://") for u in fetched)
        assert not any(w in u for u in fetched for w in ("signup", "register", "login", "apply"))
        # chỉ có thao tác ĐỌC trang: MockPageFetcher chỉ có fetch (GET) – không có phương thức gửi form
        assert not hasattr(client.mock_fetcher, "post")  # type: ignore[attr-defined]
