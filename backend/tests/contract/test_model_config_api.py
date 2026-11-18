"""T109 – Contract test /model-profiles, /models, /models/{id}/verification, /model-pricing
(FR-012, FR-019c, FR-041, FR-018f). Không gọi API thật; không tự đổi model của profile.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import api_client, csrf_headers, setup_owner
from tests.config_snapshot import restore, snapshot

pytestmark = [pytest.mark.integration, pytest.mark.mock]


@pytest.fixture
async def snap(clean_db: AsyncEngine) -> AsyncIterator[AsyncEngine]:
    s = await snapshot(clean_db)
    try:
        yield clean_db
    finally:
        await restore(clean_db, s)


@pytest.fixture
async def client(snap: AsyncEngine, migrated_db: str) -> AsyncIterator[httpx.AsyncClient]:
    async with api_client(migrated_db) as c:
        await setup_owner(c)
        yield c


def _h(client: httpx.AsyncClient) -> dict[str, str]:
    return csrf_headers(client)


async def _actions(engine: AsyncEngine) -> list[str]:
    async with engine.connect() as conn:
        return [r[0] for r in (await conn.execute(text("SELECT action FROM audit_logs ORDER BY created_at"))).all()]


async def _model(client: httpx.AsyncClient, model_id: str) -> dict[str, Any]:
    return next(m for m in (await client.get("/api/v1/models")).json() if m["model_id"] == model_id)


async def test_TC_FR019c_10_catalog_seeded_unverified(client: httpx.AsyncClient) -> None:
    haiku = await _model(client, "claude-haiku-5-5")
    assert haiku["verified"] is False and haiku["verification_source"] is None


async def test_TC_FR019c_11_add_model_unverified_no_latest(client: httpx.AsyncClient, snap: AsyncEngine) -> None:
    r = await client.post(
        "/api/v1/models",
        json={"provider": "anthropic", "model_id": "claude-test-9-9", "verified": True},
        headers=_h(client),
    )
    assert r.status_code == 201, r.text
    assert r.json()["verified"] is False  # verified là readOnly – luôn bắt đầu chưa xác minh
    dup = await client.post(
        "/api/v1/models",
        json={"provider": "anthropic", "model_id": "claude-test-9-9", "verified": False},
        headers=_h(client),
    )
    assert dup.status_code == 409 and dup.json()["code"] == "MODEL_EXISTS"
    latest = await client.post(
        "/api/v1/models",
        json={"provider": "anthropic", "model_id": "claude-latest", "verified": False},
        headers=_h(client),
    )
    assert latest.status_code == 422
    assert "model.created" in await _actions(snap)


async def test_TC_FR019c_12_manual_verification_requires_source(client: httpx.AsyncClient, snap: AsyncEngine) -> None:
    mid = (await _model(client, "claude-haiku-5-5"))["id"]
    r = await client.put(f"/api/v1/models/{mid}/verification", json={"verified": True}, headers=_h(client))
    assert r.status_code == 422
    r = await client.put(
        f"/api/v1/models/{mid}/verification",
        json={"verified": True, "verification_source": "abc"},  # < 5 ký tự
        headers=_h(client),
    )
    assert r.status_code == 422
    r = await client.put(
        f"/api/v1/models/{mid}/verification",
        json={
            "verified": True,
            "verification_source": "https://docs.example/models (owner check)",
            "supports_structured_output": True,
            "supports_tools": True,
        },
        headers=_h(client),
    )
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["verified"] is True and m["verified_at"] and m["supports_tools"] is True
    async with snap.connect() as conn:
        before, after = (
            await conn.execute(text("SELECT before, after FROM audit_logs WHERE action = 'model.verification_updated'"))
        ).one()
    assert before["verified"] is False and after["verified"] is True


async def test_TC_FR041_10_pricing_append_only(client: httpx.AsyncClient, snap: AsyncEngine) -> None:
    body = {
        "provider": "anthropic",
        "model": "claude-haiku-5-5",
        "input_per_mtok": "1.00",
        "output_per_mtok": "5.00",
        "effective_from": "2026-01-01T00:00:00Z",
        "source_note": "",
        "verified": True,
    }
    r = await client.post("/api/v1/model-pricing", json=body, headers=_h(client))
    assert r.status_code == 422  # verified=true bắt buộc source_note
    before = [p for p in (await client.get("/api/v1/model-pricing")).json() if p["model"] == "claude-haiku-5-5"]
    r = await client.post(
        "/api/v1/model-pricing", json={**body, "source_note": "Trang giá chính thức (owner)"}, headers=_h(client)
    )
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["version"] == max([p["version"] for p in before] or [0]) + 1
    after = [p for p in (await client.get("/api/v1/model-pricing")).json() if p["model"] == "claude-haiku-5-5"]
    assert len(after) == len(before) + 1  # bản cũ giữ nguyên
    unknown = await client.post(
        "/api/v1/model-pricing", json={**body, "model": "no-such-model", "source_note": "x source"}, headers=_h(client)
    )
    assert unknown.status_code == 422
    assert "model_pricing.created" in await _actions(snap)


async def test_TC_FR012_10_profiles_update_and_rules(client: httpx.AsyncClient, snap: AsyncEngine) -> None:
    profiles = {p["task_type"]: p for p in (await client.get("/api/v1/model-profiles")).json()}
    assert {"system.diagnostic", "extract.simple", "analyze.standard", "reason.complex"} <= profiles.keys()
    diag = profiles["system.diagnostic"]
    # model có phí chưa có giá đã xác minh → 422
    r = await client.put(
        "/api/v1/model-profiles/system.diagnostic", json={**diag, "model": "claude-sonnet-5-5"}, headers=_h(client)
    )
    assert r.status_code == 422, r.text
    r = await client.put(
        "/api/v1/model-profiles/system.diagnostic", json={**diag, "model": "not-in-catalog"}, headers=_h(client)
    )
    assert r.status_code == 422
    r = await client.put(
        "/api/v1/model-profiles/system.diagnostic", json={**diag, "max_output_tokens": 512}, headers=_h(client)
    )
    assert r.status_code == 200 and r.json()["max_output_tokens"] == 512
    assert r.json()["model"] == diag["model"]  # không tự đổi model
    assert (await client.put("/api/v1/model-profiles/nope", json=diag, headers=_h(client))).status_code == 404
    assert "model_profile.updated" in await _actions(snap)


async def test_TC_FR012_11_mock_profile_rejected_in_production(snap: AsyncEngine, migrated_db: str) -> None:
    async with api_client(migrated_db) as dev:  # tạo chủ sở hữu ở môi trường test
        await setup_owner(dev)
        diag = next(
            p for p in (await dev.get("/api/v1/model-profiles")).json() if p["task_type"] == "system.diagnostic"
        )
    async with api_client(migrated_db, app_env="production", ai_provider_override=None) as prod:
        from tests.api_helpers import PASSWORD

        r = await prod.post("/api/v1/auth/login", json={"username": "owner", "password": PASSWORD})
        assert r.status_code == 200, r.text
        r = await prod.put(
            "/api/v1/model-profiles/system.diagnostic",
            json={**diag, "provider": "mock", "model": "mock-model"},
            headers=csrf_headers(prod),
        )
        assert r.status_code == 409 and r.json()["code"] == "MOCK_NOT_ALLOWED"
