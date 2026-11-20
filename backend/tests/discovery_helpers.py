"""Tiện ích test E1: bật nguồn ALLOWED giả lập (chỉ trong DB test), client API với nguồn giả lập + AI kịch bản."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from nichepilot.tools.mock_sources import MockWeb
from tests.api_helpers import api_client, make_discovery_settings, setup_owner
from tests.fakes.discovery_ai import ScriptedDiscoveryAI

FIXTURES = Path(__file__).resolve().parents[0] / "fixtures" / "discovery"


async def allow_test_source(engine: AsyncEngine, key: str = "test:mock-engine") -> None:
    """Tạo một nguồn ALLOWED CHỈ TRONG DB TEST (adapter giả lập). Không đụng tới nguồn seed thật (vẫn UNVERIFIED)."""
    async with engine.begin() as conn:
        user = (await conn.execute(text("SELECT id FROM users ORDER BY created_at LIMIT 1"))).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO source_policies (source_key, display_name, adapter_type, config, tos_url,"
                " compliance_status, enabled, verified_at, verified_by, verification_note, allowed_access_methods,"
                " permitted_use_scope) VALUES (:k, 'Test engine (MOCK)', 'searxng_engine',"
                " '{\"engine_name\": \"mockengine\"}', 'https://tos.example/test', 'ALLOWED', true, '2026-11-01', :u,"
                " 'Nguồn giả lập chỉ dùng trong test tự động', '{SEARXNG_ENGINE}', 'Chỉ dùng trong test tự động')"
                " ON CONFLICT (source_key) DO NOTHING"
            ),
            {"k": key, "u": user},
        )


@asynccontextmanager
async def discovery_client(
    migrated_db: str, *, ai: ScriptedDiscoveryAI | None = None, **ds: Any
) -> AsyncIterator[httpx.AsyncClient]:
    from nichepilot.tools.mock_sources import MockPageFetcher, MockSourceAdapter

    settings = make_discovery_settings(**ds)
    async with api_client(migrated_db, discovery_settings=settings) as client:
        services = client.services  # type: ignore[attr-defined]
        web = MockWeb.from_json(FIXTURES / "mock_web.json")
        disc = services.discovery
        disc.backends.mock_web = web
        for t in list(disc.backends.adapters):
            disc.backends.adapters[t] = MockSourceAdapter(web, adapter_type=t)
        fetcher = MockPageFetcher(web)
        disc.backends.fetcher = fetcher
        # tool giữ tham chiếu fetcher/adapter lúc đăng ký → đăng ký lại với dữ liệu fixture
        from nichepilot.tools.builtin.page_fetch import build_page_fetch_tool
        from nichepilot.tools.builtin.robots_fetch import build_robots_fetch_tool
        from nichepilot.tools.builtin.source_query import build_source_query_tool

        reg = services.tools
        reg._tools["page.fetch"] = build_page_fetch_tool(settings, fetcher=fetcher, pii=disc.pii)
        reg._tools["robots.fetch"] = build_robots_fetch_tool(settings, fetcher=fetcher)
        reg._tools["source.query"] = build_source_query_tool(settings, adapters=disc.backends.adapters, pii=disc.pii)
        services.gateway.providers["mock"] = ai or ScriptedDiscoveryAI()
        await setup_owner(client)
        await disc.apply_ledger()
        client.mock_fetcher = fetcher  # type: ignore[attr-defined]
        yield client
