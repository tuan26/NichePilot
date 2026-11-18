"""T014 – Định dạng lỗi problem+json (FR-061)."""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel

from nichepilot.core.errors import ERROR_CATALOG, AppError, install_error_handlers


class Body(BaseModel):
    n: int


def _app() -> FastAPI:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/app-error")
    async def app_error() -> None:
        raise AppError("BUDGET_DAILY_EXCEEDED", params={"limit": "3.00"})

    @app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("internal detail /etc/passwd stack")

    @app.post("/validate")
    async def validate(body: Body) -> Body:
        return body

    return app


@pytest.fixture
async def client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=_app(), raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_TC_FR061_01_app_error_is_problem_json(client: httpx.AsyncClient) -> None:
    r = await client.get("/app-error")
    assert r.status_code == ERROR_CATALOG["BUDGET_DAILY_EXCEEDED"].status
    assert r.headers["content-type"].startswith("application/problem+json")
    body = r.json()
    assert body["code"] == "BUDGET_DAILY_EXCEEDED"
    assert body["params"] == {"limit": "3.00"}
    assert {"type", "title", "status", "code"} <= body.keys()


async def test_TC_FR061_02_unhandled_error_hides_details(client: httpx.AsyncClient) -> None:
    r = await client.get("/boom")
    assert r.status_code == 500
    body = r.json()
    assert body["code"] == "INTERNAL_ERROR"
    assert "passwd" not in r.text
    assert "Traceback" not in r.text


async def test_TC_FR061_03_validation_error_lists_fields(client: httpx.AsyncClient) -> None:
    r = await client.post("/validate", json={"n": "not-int"})
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "VALIDATION_ERROR"
    assert body["errors"][0]["field"].endswith("n")


def test_TC_FR061_04_catalog_contains_contract_codes() -> None:
    required = {
        "AUTH_REQUIRED",
        "SERVICE_UNAVAILABLE",
        "INTERNAL_ERROR",
        "MOCK_NOT_ALLOWED",
        "UNCERTAIN_RESERVATION_LIMIT",
        "UNCERTAIN_RESERVATIONS_UNRESOLVED",
        "MODEL_NOT_VERIFIED",
        "PRICING_NOT_VERIFIED",
        "PAID_CALLS_DISABLED",
    }
    assert required <= ERROR_CATALOG.keys()


def test_TC_FR061_05_unknown_code_rejected() -> None:
    with pytest.raises(KeyError):
        AppError("NOT_A_REAL_CODE")
