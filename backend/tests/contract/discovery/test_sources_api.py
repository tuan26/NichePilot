"""T106 – `GET/POST /api/v1/sources`, `PUT /api/v1/sources/{source_id}` (FR-006c, FR-006d, FR-006g, FR-036, SC-017).

Mọi nguồn seed vẫn UNVERIFIED (test KHÔNG đổi trạng thái nguồn seed thật – chỉ thao tác trên nguồn test tạo trong DB test)."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.api_helpers import csrf_headers
from tests.discovery_helpers import discovery_client

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]
NEW = {
    "source_key": "test:owner-added",
    "display_name": "Owner added engine (test)",
    "adapter_type": "searxng_engine",
    "tos_url": "https://tos.example/owner",
    "config": {"engine_name": "ownerengine"},
}
ALLOW = {
    "compliance_status": "ALLOWED",
    "verified_at": "2026-11-01",
    "verification_note": "Đã đọc ToS (test) – chỉ dùng trong DB test",
    "allowed_access_methods": ["SEARXNG_ENGINE"],
    "permitted_use_scope": "Chỉ dùng trong test tự động",
}


async def _put(client: object, sid: str, body: dict[str, object]) -> object:
    return await client.put(f"/api/v1/sources/{sid}", json=body, headers=csrf_headers(client))  # type: ignore[attr-defined]


async def test_TC_E1_FR006d_03_TC_E1_SC017_03_only_allowed_can_be_enabled(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with discovery_client(migrated_db) as client:
        listed = (await client.get("/api/v1/sources")).json()
        assert listed and all(s["compliance_status"] == "UNVERIFIED" and not s["usable"] for s in listed)  # seed
        r = await client.post("/api/v1/sources", json=NEW, headers=csrf_headers(client))
        assert r.status_code == 201 and r.json()["compliance_status"] == "UNVERIFIED" and r.json()["enabled"] is False
        sid = r.json()["id"]
        for status in ("UNVERIFIED", "PROHIBITED"):
            body = (
                {"enabled": True}
                if status == "UNVERIFIED"
                else {
                    "compliance_status": "PROHIBITED",
                    "verified_at": "2026-11-01",
                    "verification_note": "ToS cấm truy cập tự động (test)",
                    "enabled": True,
                }
            )
            resp = await _put(client, sid, body)
            assert resp.status_code == 409 and resp.json()["code"] == "SOURCE_NOT_ALLOWED", status  # type: ignore[attr-defined]
        assert (await _put(client, sid, {"enabled": True, "confirm_warning": True})).status_code == 422  # type: ignore[attr-defined]
        seed = next(s for s in listed if s["source_key"] == "searxng:wikipedia")
        assert (await _put(client, seed["id"], {"enabled": True})).status_code == 409  # type: ignore[attr-defined]


async def test_TC_E1_FR006c_04_allowed_requires_full_evidence_and_leaving_allowed_disables(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with discovery_client(migrated_db) as client:
        sid = (await client.post("/api/v1/sources", json=NEW, headers=csrf_headers(client))).json()["id"]
        partial = {k: v for k, v in ALLOW.items() if k != "permitted_use_scope"}
        resp = await _put(client, sid, partial)
        assert resp.status_code == 422 and resp.json()["code"] == "SOURCE_VERIFICATION_INCOMPLETE"  # type: ignore[attr-defined]
        ok = await _put(client, sid, {**ALLOW, "enabled": True})
        body = ok.json()  # type: ignore[attr-defined]
        assert ok.status_code == 200 and body["usable"] and body["verified_by"]  # type: ignore[attr-defined]
        assert body["requires_service_restart"] is True  # bật engine → sinh lại settings.yml của SearXNG
        settings_file = client.services.discovery.settings.searxng_config_dir / "settings.yml"  # type: ignore[attr-defined]
        content = settings_file.read_text()
        assert "ownerengine" in content and "plugins: {}" in content
        down = (await _put(client, sid, {"compliance_status": "UNVERIFIED"})).json()  # type: ignore[attr-defined]
        assert down["enabled"] is False and down["usable"] is False and down["requires_service_restart"] is True
        assert "ownerengine" not in settings_file.read_text()


async def test_TC_E1_FR006g_03_TC_E1_FR036_01_config_validation_and_audit(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with discovery_client(migrated_db) as client:
        bad = {**NEW, "source_key": "test:bad", "config": {"engine_name": "x", "api_key": "sk-not-allowed"}}
        r = await client.post("/api/v1/sources", json=bad, headers=csrf_headers(client))
        assert r.status_code == 422 and r.json()["code"] == "SOURCE_CONFIG_INVALID"
        api = {
            **NEW,
            "source_key": "test:api",
            "adapter_type": "http_json_api",
            "config": {"base_url": "https://api.example/search", "auth_env_var": "TEST_SOURCE_TOKEN"},
        }
        created = await client.post("/api/v1/sources", json=api, headers=csrf_headers(client))
        assert created.status_code in (201, 422)
        sid = (await client.post("/api/v1/sources", json=NEW, headers=csrf_headers(client))).json()["id"]
        dup = await client.post("/api/v1/sources", json=NEW, headers=csrf_headers(client))
        assert dup.status_code == 409 and dup.json()["code"] == "SOURCE_EXISTS"
        await _put(client, sid, {**ALLOW})
        assert (
            await client.put(
                "/api/v1/sources/00000000-0000-0000-0000-000000000000",
                json={"enabled": False},
                headers=csrf_headers(client),
            )
        ).status_code == 404
        async with clean_db.connect() as conn:
            audits = (
                await conn.execute(
                    text("SELECT action, before, after FROM audit_logs WHERE entity_id = :i ORDER BY created_at"),
                    {"i": sid},
                )
            ).all()
        assert [a.action for a in audits] == ["source.created", "source.updated"]
        assert (
            audits[1].before["compliance_status"] == "UNVERIFIED" and audits[1].after["compliance_status"] == "ALLOWED"
        )
        listed = (await client.get("/api/v1/sources")).text
        assert "sk-not-allowed" not in listed
