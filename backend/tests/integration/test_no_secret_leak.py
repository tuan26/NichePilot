"""T111 – Quét secret (FR-054, SC-008): response mọi endpoint chính, file log và stdout/stderr không chứa giá trị secret.

Provider thật được thay bằng transport HTTP giả lập; phản hồi lỗi giả lập cố ý lặp lại key để kiểm tra che giấu.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import httpx2
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from nichepilot.ai.providers.anthropic_api import AnthropicAPIProvider
from nichepilot.core.logging import configure_logging
from tests.api_helpers import PASSWORD, api_client, csrf_headers, run_worker_once, setup_owner
from tests.config_snapshot import restore, snapshot
from tests.fakes.http import mock_client

pytestmark = [pytest.mark.integration, pytest.mark.mock]
ANTHROPIC_KEY = "sk-ant-leakcheck-9f8e7d6c5b4a3210"
OPENAI_KEY = "sk-proj-leakcheck-0a1b2c3d4e5f6789"
SECRETS = [ANTHROPIC_KEY, OPENAI_KEY, PASSWORD]


@pytest.fixture
async def snap(clean_db: AsyncEngine) -> AsyncIterator[AsyncEngine]:
    s = await snapshot(clean_db)
    try:
        yield clean_db
    finally:
        await restore(clean_db, s)


def _echo_key(request: httpx2.Request) -> httpx2.Response:
    # Provider giả lập trả lỗi có chứa key nhận được (trường hợp xấu nhất).
    sent = request.headers.get("x-api-key") or request.headers.get("authorization", "")
    return httpx2.Response(401, json={"type": "error", "error": {"type": "authentication_error", "message": sent}})


async def test_TC_SC008_01_no_secret_in_responses_logs_stdout(
    snap: AsyncEngine, migrated_db: str, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    bodies: list[str] = []
    async with api_client(
        migrated_db, anthropic_api_key=ANTHROPIC_KEY, openai_api_key=OPENAI_KEY, log_dir=str(tmp_path)
    ) as client:
        configure_logging(level="DEBUG", fmt="json", log_dir=tmp_path, secret_values=SECRETS[:2])
        http, _ = mock_client(_echo_key)
        client.services.gateway.providers["anthropic"] = AnthropicAPIProvider(  # type: ignore[attr-defined]
            ANTHROPIC_KEY, http_client=http
        )

        async def call(method: str, url: str, **kw: object) -> httpx.Response:
            r = await client.request(method, url, headers=csrf_headers(client), **kw)  # type: ignore[arg-type]
            bodies.append(r.text)
            bodies.extend(f"{k}: {v}" for k, v in r.headers.items())
            return r

        await call("POST", "/api/v1/auth/setup", json={"username": "owner", "password": PASSWORD, "ui_locale": "vi"})
        await call("POST", "/api/v1/auth/login", json={"username": "owner", "password": "wrong-password-x"})
        for url in (
            "/api/v1/system/status",
            "/api/v1/providers",
            "/api/v1/settings",
            "/api/v1/projects/default",
            "/api/v1/models",
            "/api/v1/model-profiles",
            "/api/v1/model-pricing",
            "/api/v1/budget",
            "/api/v1/costs/summary?period=day",
            "/api/v1/audit-logs",
            "/api/v1/job-types",
            "/api/v1/tools",
            "/api/v1/schedules",
            "/api/v1/auth/me",
        ):
            r = await call("GET", url)
            assert r.status_code == 200, (url, r.text)
        r = await call("POST", "/api/v1/providers/anthropic/test-connection")
        assert r.json()["result"] == "INVALID_KEY"
        await call("POST", "/api/v1/providers/anthropic/verify-models")
        job = (await call("POST", "/api/v1/jobs", json={"job_type": "system.diagnostic"})).json()
        await run_worker_once(client)
        await call("GET", f"/api/v1/jobs/{job['id']}")
        await call("GET", f"/api/v1/jobs/{job['id']}/steps")
        await call("GET", "/api/v1/audit-logs?page_size=200")
        _ = setup_owner  # tài khoản đã tạo ở trên

    captured = capfd.readouterr()
    log_text = "\n".join(p.read_text(encoding="utf-8") for p in tmp_path.glob("*.jsonl"))  # noqa: ASYNC240
    assert log_text, "phải có file log để quét"
    haystacks = {"responses": "\n".join(bodies), "logs": log_text, "stdout": captured.out, "stderr": captured.err}
    for name, hay in haystacks.items():
        for secret in SECRETS:
            assert secret not in hay, f"secret lộ trong {name}"
        assert "leakcheck" not in hay, f"một phần key lộ trong {name}"
