"""Tiện ích test E2: client API với nguồn giả lập E2 + AI kịch bản, ngách MOCK đủ điều kiện (dùng lệnh seed demo E1)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from nichepilot.jobs import discovery_demo_seed
from nichepilot.tools.mock_sources import MockPageFetcher, MockSourceAdapter, MockWeb
from tests.api_helpers import api_client, csrf_headers, make_discovery_settings, run_worker_once, setup_owner
from tests.fakes.products_ai import ScriptedProductsAI

FIXTURES = Path(__file__).resolve().parents[0] / "fixtures" / "products"


@asynccontextmanager
async def products_client(
    migrated_db: str, *, ai: ScriptedProductsAI | None = None, **ds: Any
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
        services.gateway.providers["mock"] = ai or ScriptedProductsAI()
        await setup_owner(client)
        await disc.apply_ledger()
        client.mock_fetcher = fetcher  # type: ignore[attr-defined]
        client.mock_web = web  # type: ignore[attr-defined]
        yield client


async def seed_niche(client: httpx.AsyncClient) -> str:
    """Ngách MOCK đủ bằng chứng (lệnh seed demo E1 – qua pipeline chấm điểm thật). Trả niche_id."""
    sm = client.services.discovery.sessionmaker  # type: ignore[attr-defined]
    return str((await discovery_demo_seed.seed_demo(sm))["niche_id"])


async def start_run(client: httpx.AsyncClient, niche_id: str, **body: Any) -> httpx.Response:
    return await client.post("/api/v1/product-runs", json={"niche_id": niche_id, **body}, headers=csrf_headers(client))


async def run_products(client: httpx.AsyncClient, niche_id: str, **body: Any) -> dict[str, Any]:
    r = await start_run(client, niche_id, **body)
    assert r.status_code == 202, r.text
    await run_worker_once(client)
    got = await client.get(f"/api/v1/product-runs/{r.json()['run_id']}")
    assert got.status_code == 200, got.text
    return dict(got.json())


async def product_id(engine: AsyncEngine, name: str) -> str:
    async with engine.connect() as conn:
        return str(
            (
                await conn.execute(
                    text("SELECT id FROM products WHERE name = :n AND merged_into_id IS NULL"), {"n": name}
                )
            ).scalar_one()
        )


def uid(x: str) -> uuid.UUID:
    return uuid.UUID(x)
