"""T108 – Contract test /settings và /projects/default (FR-055, FR-051, FR-057, BR-10)."""

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
async def client(clean_db: AsyncEngine, migrated_db: str) -> AsyncIterator[httpx.AsyncClient]:
    snap = await snapshot(clean_db)
    try:
        async with api_client(migrated_db) as c:
            await setup_owner(c)
            yield c
    finally:
        await restore(clean_db, snap)


async def _settings(client: httpx.AsyncClient) -> dict[str, dict[str, Any]]:
    r = await client.get("/api/v1/settings")
    assert r.status_code == 200
    return {s["key"]: s for s in r.json()}


async def _patch(client: httpx.AsyncClient, items: list[dict[str, Any]]) -> httpx.Response:
    return await client.patch("/api/v1/settings", json=items, headers=csrf_headers(client))


async def test_TC_FR055_01_get_settings_has_no_secrets(client: httpx.AsyncClient) -> None:
    s = await _settings(client)
    assert s["logging.retention_days"]["value"] == 90 and s["logging.retention_days"]["version"] == 1
    assert s["system.timezone"]["value"] == "Asia/Ho_Chi_Minh"
    assert not [k for k in s if any(w in k.lower() for w in ("api_key", "apikey", "secret", "token", "password"))]


async def test_TC_FR055_02_patch_with_audit_and_optimistic_lock(
    client: httpx.AsyncClient, clean_db: AsyncEngine
) -> None:
    v = (await _settings(client))["agent.default_max_steps"]["version"]
    r = await _patch(client, [{"key": "agent.default_max_steps", "value": 25, "version": v}])
    assert r.status_code == 200, r.text
    updated = {i["key"]: i for i in r.json()}["agent.default_max_steps"]
    assert updated["value"] == 25 and updated["version"] == v + 1
    stale = await _patch(client, [{"key": "agent.default_max_steps", "value": 30, "version": v}])
    assert stale.status_code == 409 and stale.json()["code"] == "VERSION_CONFLICT"
    async with clean_db.connect() as conn:
        before, after = (
            await conn.execute(
                text("SELECT before, after FROM audit_logs WHERE action = 'settings.updated' ORDER BY created_at")
            )
        ).one()
    assert before == {"agent.default_max_steps": 20} and after == {"agent.default_max_steps": 25}


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("logging.retention_days", 30),  # FR-057: không thấp hơn 90 ngày
        ("logging.retention_days", "90"),
        ("system.timezone", "Mars/Olympus"),
        ("ui.default_locale", "fr"),
        ("budget.daily_usd", "-1"),
        ("agent.default_max_steps", 0),
        ("auth.lockout_threshold", 0),
        ("anthropic.api_key", "sk-ant-x"),  # khóa giống secret bị từ chối
        ("unknown.key", 1),
    ],
)
async def test_TC_FR055_03_validation(client: httpx.AsyncClient, key: str, value: Any) -> None:
    r = await _patch(client, [{"key": key, "value": value, "version": 1}])
    assert r.status_code == 422, (key, value, r.text)
    assert r.json()["code"] == "VALIDATION_ERROR"


async def test_TC_FR055_04_cross_constraints_are_atomic(client: httpx.AsyncClient) -> None:
    s = await _settings(client)
    # ngày > tháng → từ chối; cả lô không được ghi
    r = await _patch(
        client,
        [
            {"key": "agent.default_max_steps", "value": 21, "version": s["agent.default_max_steps"]["version"]},
            {"key": "budget.daily_usd", "value": "50", "version": s["budget.daily_usd"]["version"]},
        ],
    )
    assert r.status_code == 422
    after = await _settings(client)
    assert after["agent.default_max_steps"]["value"] == s["agent.default_max_steps"]["value"]
    assert after["budget.daily_usd"]["value"] == "3.00"


async def test_TC_FR057_01_retention_can_increase(client: httpx.AsyncClient) -> None:
    v = (await _settings(client))["logging.retention_days"]["version"]
    r = await _patch(client, [{"key": "logging.retention_days", "value": 120, "version": v}])
    assert r.status_code == 200


async def test_TC_BR10_01_project_languages_independent(client: httpx.AsyncClient, clean_db: AsyncEngine) -> None:
    p = (await client.get("/api/v1/projects/default")).json()
    assert (p["target_market"], p["research_language"], p["content_language"]) == ("US", "auto", "en")
    r = await client.patch("/api/v1/projects/default", json={"content_language": "vi"}, headers=csrf_headers(client))
    assert r.status_code == 200
    p2 = r.json()
    assert (p2["target_market"], p2["research_language"], p2["content_language"]) == ("US", "auto", "vi")
    ui = (await _settings(client))["ui.default_locale"]["value"]
    assert ui == "vi"  # ngôn ngữ giao diện không đổi theo ngôn ngữ nội dung
    bad = await client.patch("/api/v1/projects/default", json={"target_market": "usa"}, headers=csrf_headers(client))
    assert bad.status_code == 422
    async with clean_db.connect() as conn:
        n = (await conn.execute(text("SELECT COUNT(*) FROM audit_logs WHERE action = 'project.updated'"))).scalar_one()
    assert n == 1


async def test_TC_FR051_10_audit_logs_read_only_filter_page(client: httpx.AsyncClient) -> None:
    v = (await _settings(client))["agent.default_max_steps"]["version"]
    await _patch(client, [{"key": "agent.default_max_steps", "value": 22, "version": v}])
    r = await client.get("/api/v1/audit-logs", params={"action": "settings.updated"})
    assert r.status_code == 200
    page = r.json()
    assert page["total"] == 1 and page["items"][0]["entity_type"] == "setting"
    assert page["items"][0]["after"] == {"agent.default_max_steps": 22}
    all_ = (await client.get("/api/v1/audit-logs", params={"page_size": 1})).json()
    assert all_["total"] >= 2 and len(all_["items"]) == 1  # gồm auth.setup + settings.updated
    future = (await client.get("/api/v1/audit-logs", params={"from": "2999-01-01T00:00:00Z"})).json()
    assert future["total"] == 0
    # chỉ đọc: không có phương thức sửa/xóa
    assert (await client.delete("/api/v1/audit-logs", headers=csrf_headers(client))).status_code == 405
