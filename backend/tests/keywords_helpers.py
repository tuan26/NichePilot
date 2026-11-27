"""Tiện ích test E3: client API với nguồn giả lập E3 + AI kịch bản; ngách + sản phẩm MOCK từ lệnh seed demo E1/E2 (không AI, không mạng)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx

from nichepilot.jobs import discovery_demo_seed, products_demo_seed
from nichepilot.tools.mock_sources import MockPageFetcher, MockSourceAdapter, MockWeb
from tests.api_helpers import api_client, csrf_headers, make_discovery_settings, run_worker_once, setup_owner
from tests.fakes.keywords_ai import ScriptedKeywordsAI

FIXTURES = Path(__file__).resolve().parents[0] / "fixtures" / "keywords"


@asynccontextmanager
async def keywords_client(
    migrated_db: str, *, ai: ScriptedKeywordsAI | None = None, **ds: Any
) -> AsyncIterator[httpx.AsyncClient]:
    from nichepilot.tools.builtin.page_fetch import build_page_fetch_tool
    from nichepilot.tools.builtin.robots_fetch import build_robots_fetch_tool
    from nichepilot.tools.builtin.source_query import build_source_query_tool

    settings = make_discovery_settings(**ds)
    async with api_client(migrated_db, discovery_settings=settings) as client:
        services = client.services  # type: ignore[attr-defined]
        web = MockWeb.from_json(FIXTURES / "web.json")
        disc = services.discovery
        disc.backends.mock_web = web
        for t in list(disc.backends.adapters):
            disc.backends.adapters[t] = MockSourceAdapter(web, adapter_type=t)
        fetcher = MockPageFetcher(web)
        disc.backends.fetcher = fetcher
        reg = services.tools
        reg._tools["page.fetch"] = build_page_fetch_tool(settings, fetcher=fetcher, pii=disc.pii)
        reg._tools["robots.fetch"] = build_robots_fetch_tool(settings, fetcher=fetcher)
        reg._tools["source.query"] = build_source_query_tool(settings, adapters=disc.backends.adapters, pii=disc.pii)
        services.gateway.providers["mock"] = ai or ScriptedKeywordsAI()
        await setup_owner(client)
        await disc.apply_ledger()
        client.mock_web = web  # type: ignore[attr-defined]
        yield client


async def seed_niche_with_products(client: httpx.AsyncClient) -> str:
    """Ngách MOCK đủ bằng chứng + 2 sản phẩm MOCK DEMO (lệnh seed E1/E2 – qua pipeline chấm điểm thật). Trả niche_id."""
    sm = client.services.discovery.sessionmaker  # type: ignore[attr-defined]
    niche_id = str((await discovery_demo_seed.seed_demo(sm))["niche_id"])
    await products_demo_seed.seed_demo(sm)
    return niche_id


async def start_run(client: httpx.AsyncClient, niche_id: str, **body: Any) -> httpx.Response:
    return await client.post("/api/v1/keyword-runs", json={"niche_id": niche_id, **body}, headers=csrf_headers(client))


async def run_keywords(client: httpx.AsyncClient, niche_id: str, **body: Any) -> dict[str, Any]:
    r = await start_run(client, niche_id, **body)
    assert r.status_code == 202, r.text
    await run_worker_once(client)
    got = await client.get(f"/api/v1/keyword-runs/{r.json()['run_id']}")
    assert got.status_code == 200, got.text
    return dict(got.json())
