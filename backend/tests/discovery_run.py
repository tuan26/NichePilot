"""Tiện ích chạy một lượt khám phá giả lập trong test E1 (MOCK – không mạng, không API có phí)."""

from __future__ import annotations

from typing import Any

import httpx

from tests.api_helpers import csrf_headers, run_worker_once


async def run_discovery(client: httpx.AsyncClient, body: dict[str, Any] | None = None) -> dict[str, Any]:
    r = await client.post("/api/v1/discovery/runs", json=body or {"market": "US"}, headers=csrf_headers(client))
    assert r.status_code == 201, r.text
    await run_worker_once(client)
    got = await client.get(f"/api/v1/discovery/runs/{r.json()['id']}")
    return dict(got.json())


def set_search(client: httpx.AsyncClient, urls: list[str]) -> None:
    client.services.discovery.backends.mock_web.search["default"] = urls  # type: ignore[attr-defined]


FORUM = "https://forum.example/t/bakery-inventory"
REVIEW = "https://reviews.example/stockpal-micro-bakery"
COPY = "https://aggregator.example/copy/bakery-inventory"
PII_PAGE = "https://forum.example/t/grooming-chaos"
NAMES_PAGE = "https://tutors.example/scheduling"


async def bakery_evidence(engine: object, domain: str) -> list[str]:
    """ID bằng chứng ACTIVE của ngách bakery từ một tên miền (MOCK fixture)."""
    from sqlalchemy import text

    async with engine.connect() as conn:  # type: ignore[attr-defined]
        rows = (
            (
                await conn.execute(
                    text(
                        "SELECT e.id FROM research_evidence e JOIN research_sources s ON s.id = e.source_id"
                        " JOIN niches n ON n.id = e.subject_id WHERE n.name LIKE '%bakery%' AND s.registered_domain = :d"
                        " AND e.lifecycle_status = 'ACTIVE' ORDER BY e.created_at"
                    ),
                    {"d": domain},
                )
            )
            .scalars()
            .all()
        )
    return [str(r) for r in rows]


async def niche_status(engine: object, name_like: str = "%bakery%") -> str:
    from sqlalchemy import text

    async with engine.connect() as conn:  # type: ignore[attr-defined]
        return str(
            (
                await conn.execute(text("SELECT evidence_status FROM niches WHERE name LIKE :n"), {"n": name_like})
            ).scalar_one()
        )


async def erase(client: httpx.AsyncClient, evidence_id: str, **body: Any) -> httpx.Response:
    return await client.post(
        f"/api/v1/evidence/{evidence_id}/erase",
        json={"reason": "Owner request (test)", **body},
        headers=csrf_headers(client),
    )
