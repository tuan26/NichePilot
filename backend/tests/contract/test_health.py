"""T018 – Contract `GET /health` (FR-002)."""

from __future__ import annotations

import httpx
import yaml

from nichepilot.main import create_app
from tests.conftest import SPEC_DIR


def _openapi() -> dict[str, object]:
    return yaml.safe_load((SPEC_DIR / "contracts" / "openapi.yaml").read_text())


async def test_TC_FR002_01_health_is_public_and_minimal() -> None:
    app = create_app(check_database=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert "x-request-id" in r.headers

    spec = _openapi()
    paths = spec["paths"]
    assert isinstance(paths, dict)
    health = paths["/health"]["get"]
    assert health["security"] == []
    schema = health["responses"]["200"]["content"]["application/json"]["schema"]
    assert set(r.json()) == set(schema["required"])


async def test_TC_FR002_02_openapi_docs_served_under_api_prefix() -> None:
    app = create_app(check_database=False)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as client:
        r = await client.get("/api/openapi.json")
    assert r.status_code == 200
    assert "/health" in r.json()["paths"]
