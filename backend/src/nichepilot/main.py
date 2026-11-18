"""FastAPI app factory (T039 – FR-002).

Chạy: `uvicorn nichepilot.main:create_app --factory`. Cấu hình và kết nối DB chỉ khởi tạo trong lifespan,
nên có thể tạo app trong test mà không cần biến môi trường.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response

from nichepilot.api.v1 import api_router
from nichepilot.core.config import Settings, detect_ignored_credentials, get_settings
from nichepilot.core.db import dispose_db, init_db
from nichepilot.core.errors import install_error_handlers
from nichepilot.core.logging import bind_context, clear_context, configure_logging, get_logger

REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
log = get_logger(__name__)


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings or get_settings()
    app.state.settings = settings
    configure_logging(
        level=settings.log_level,
        fmt=settings.log_format,
        log_dir=settings.log_dir,
        secret_values=settings.secret_values(),
    )
    for name in detect_ignored_credentials():
        log.warning("ignored credential variable", variable=name, reason="chỉ dùng API key chính thức (FR-019b)")
    if app.state.check_database:
        init_db(settings.database_url.get_secret_value())
    log.info("api started", app_env=settings.app_env, version=settings.app_version)
    try:
        yield
    finally:
        await dispose_db()


def create_app(*, settings: Settings | None = None, check_database: bool = True) -> FastAPI:
    app = FastAPI(
        title="NichePilot API",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=_lifespan,
    )
    app.state.check_database = check_database
    app.state.settings = settings
    install_error_handlers(app)

    @app.middleware("http")
    async def request_context(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        incoming = request.headers.get("x-request-id", "")
        request_id = incoming if REQUEST_ID_RE.match(incoming) else uuid.uuid4().hex
        request.state.request_id = request_id
        clear_context()
        bind_context(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            clear_context()
        response.headers["X-Request-ID"] = request_id
        return response

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        """Liveness tối giản – công khai, không lộ chi tiết."""
        return {"status": "ok"}

    app.include_router(api_router, prefix="/api/v1")
    return app
