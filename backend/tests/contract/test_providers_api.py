"""T110 – Contract test /providers, test-connection, verify-models (FR-054, FR-056, FR-019c).

Provider thật được thay bằng adapter dùng transport HTTP giả lập (httpx2.MockTransport) – KHÔNG gọi API thật,
KHÔNG phát sinh chi phí. Kết quả ở đây không chứng minh tích hợp với API thật.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
import httpx2
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from nichepilot.ai.providers.anthropic_api import AnthropicAPIProvider
from nichepilot.ai.providers.openai_api import OpenAIAPIProvider
from tests.api_helpers import api_client, csrf_headers, setup_owner
from tests.config_snapshot import restore, snapshot
from tests.fakes.http import Handler, json_response, mock_client

pytestmark = [pytest.mark.integration, pytest.mark.mock]
ANTHROPIC_KEY = "sk-ant-test-provider-key-zz91"
OPENAI_KEY = "sk-proj-test-provider-key-qq42"


@pytest.fixture
async def snap(clean_db: AsyncEngine) -> AsyncIterator[AsyncEngine]:
    s = await snapshot(clean_db)
    try:
        yield clean_db
    finally:
        await restore(clean_db, s)


@pytest.fixture
async def client(snap: AsyncEngine, migrated_db: str) -> AsyncIterator[httpx.AsyncClient]:
    async with api_client(migrated_db, anthropic_api_key=ANTHROPIC_KEY, openai_api_key=OPENAI_KEY) as c:
        await setup_owner(c)
        yield c


def _install(client: httpx.AsyncClient, provider: str, responder: Handler | Exception) -> None:
    http, _ = mock_client(responder)
    svc = client.services  # type: ignore[attr-defined]
    if provider == "anthropic":
        svc.gateway.providers["anthropic"] = AnthropicAPIProvider(ANTHROPIC_KEY, http_client=http)
    else:
        svc.gateway.providers["openai"] = OpenAIAPIProvider(OPENAI_KEY, http_client=http)


async def test_TC_FR054_10_providers_never_return_key(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/v1/providers")
    assert r.status_code == 200
    body = r.text
    assert ANTHROPIC_KEY not in body and OPENAI_KEY not in body
    by = {p["provider"]: p for p in r.json()}
    assert by["anthropic"] == {
        "provider": "anthropic",
        "configured": True,
        "key_hint": "…zz91",
        "last_check": None,
        "last_checked_at": None,
    }
    assert by["openai"]["key_hint"] == "…qq42" and by["mock"]["last_check"] == "MOCK"


async def test_TC_FR054_11_not_configured(snap: AsyncEngine, migrated_db: str) -> None:
    async with api_client(migrated_db) as c:
        await setup_owner(c)
        by = {p["provider"]: p for p in (await c.get("/api/v1/providers")).json()}
        assert by["anthropic"]["configured"] is False and by["anthropic"]["key_hint"] is None
        r = await c.post("/api/v1/providers/anthropic/test-connection", headers=csrf_headers(c))
        assert r.status_code == 200 and r.json()["result"] == "NOT_CONFIGURED"
        r = await c.post("/api/v1/providers/openai/verify-models", headers=csrf_headers(c))
        assert r.status_code == 409 and r.json()["code"] == "PROVIDER_NOT_CONFIGURED"


@pytest.mark.parametrize(
    ("responder", "expected"),
    [
        (json_response(200, {"data": [], "has_more": False, "first_id": None, "last_id": None}), "OK"),
        (
            json_response(401, {"type": "error", "error": {"type": "authentication_error", "message": "bad"}}),
            "INVALID_KEY",
        ),
        (httpx2.ConnectError("offline"), "NETWORK_ERROR"),
        (json_response(500, {"type": "error", "error": {"type": "api_error", "message": "x"}}), "PROVIDER_ERROR"),
    ],
)
async def test_TC_FR056_10_test_connection_results_and_audit(
    client: httpx.AsyncClient, snap: AsyncEngine, responder: Any, expected: str
) -> None:
    _install(client, "anthropic", responder)
    r = await client.post("/api/v1/providers/anthropic/test-connection", headers=csrf_headers(client))
    assert r.status_code == 200 and r.json()["result"] == expected and r.json()["checked_at"]
    by = {p["provider"]: p for p in (await client.get("/api/v1/providers")).json()}
    assert by["anthropic"]["last_check"] == expected and by["anthropic"]["last_checked_at"]
    async with snap.connect() as conn:
        after = (
            await conn.execute(text("SELECT after FROM audit_logs WHERE action = 'provider.connection_tested'"))
        ).scalar_one()
    assert after == {"provider": "anthropic", "result": expected}


async def test_TC_FR056_11_mock_connection(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/v1/providers/mock/test-connection", headers=csrf_headers(client))
    assert r.json()["result"] == "MOCK"


def _anthropic_models(request: httpx2.Request) -> httpx2.Response:
    model_id = request.url.path.rsplit("/", 1)[-1]
    if model_id == "claude-opus-5-5":
        return httpx2.Response(404, json={"type": "error", "error": {"type": "not_found_error", "message": "nf"}})
    supported = {"supported": True}
    caps: dict[str, Any] = {
        "batch": supported,
        "citations": supported,
        "code_execution": supported,
        "context_management": {"supported": True},
        "image_input": supported,
        "pdf_input": supported,
        "server_tools": {"supported": True},
        "thinking": {"supported": True},
        "structured_outputs": {"supported": model_id != "claude-sonnet-5-5"},
        "effort": {
            "supported": True,
            "low": supported,
            "medium": supported,
            "high": supported,
            "xhigh": supported,
            "max": supported,
        },
    }
    return httpx2.Response(
        200,
        json={
            "id": model_id,
            "type": "model",
            "display_name": model_id,
            "created_at": "2026-01-01T00:00:00Z",
            "max_input_tokens": 200000,
            "max_tokens": 64000,
            "capabilities": caps,
        },
    )


async def test_TC_FR019c_20_verify_models_anthropic(client: httpx.AsyncClient, snap: AsyncEngine) -> None:
    _install(client, "anthropic", _anthropic_models)
    r = await client.post("/api/v1/providers/anthropic/verify-models", headers=csrf_headers(client))
    assert r.status_code == 200, r.text
    results = {i["model_id"]: i["result"] for i in r.json()}
    assert results == {
        "claude-haiku-5-5": "VERIFIED",
        "claude-sonnet-5-5": "CAPABILITY_MISMATCH",  # nền tảng bắt buộc structured output (FR-021)
        "claude-opus-5-5": "NOT_FOUND",
    }
    models = {m["model_id"]: m for m in (await client.get("/api/v1/models")).json()}
    haiku = models["claude-haiku-5-5"]
    assert haiku["verified"] is True and "Models API" in haiku["verification_source"]
    assert haiku["supports_structured_output"] is True and haiku["max_input_tokens"] == 200000
    assert haiku["supports_tools"] is None  # Models API không công bố – không tự suy đoán
    assert models["claude-opus-5-5"]["verified"] is False and models["claude-sonnet-5-5"]["verified"] is False
    # Không xác minh giá: bảng giá vẫn chưa xác minh
    prices = [p for p in (await client.get("/api/v1/model-pricing")).json() if p["model"] == "claude-haiku-5-5"]
    assert all(p["verified"] is False for p in prices)
    async with snap.connect() as conn:
        n = (
            await conn.execute(text("SELECT COUNT(*) FROM audit_logs WHERE action = 'provider.models_verified'"))
        ).scalar_one()
    assert n == 1


async def test_TC_FR019c_21_verify_models_network_error(client: httpx.AsyncClient) -> None:
    _install(client, "anthropic", httpx2.ConnectError("offline"))
    r = await client.post("/api/v1/providers/anthropic/verify-models", headers=csrf_headers(client))
    assert r.status_code == 200
    assert {i["result"] for i in r.json()} == {"ERROR"}
    assert all(not m["verified"] for m in (await client.get("/api/v1/models")).json() if m["provider"] == "anthropic")
    assert (await client.post("/api/v1/providers/mock/verify-models", headers=csrf_headers(client))).status_code == 422
