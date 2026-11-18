"""Dependency dùng chung cho router: session DB, settings, người dùng hiện tại, CSRF (FR-052)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from nichepilot.core.config import Settings
from nichepilot.core.db import get_sessionmaker
from nichepilot.core.errors import AppError
from nichepilot.core.logging import bind_context
from nichepilot.core.security import CSRF_COOKIE, CSRF_HEADER, SAFE_METHODS, SESSION_COOKIE, csrf_valid
from nichepilot.modules.identity.models import User
from nichepilot.modules.identity.service import RequestMeta, resolve_session


async def get_session() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def request_meta(request: Request) -> RequestMeta:
    return RequestMeta(
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        request_id=getattr(request.state, "request_id", None),
    )


# scope="function": commit TRƯỚC khi gửi response – lỗi commit phải trả về client, không trả 2xx giả.
SessionDep = Annotated[AsyncSession, Depends(get_session, scope="function")]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
MetaDep = Annotated[RequestMeta, Depends(request_meta)]


async def current_user(request: Request, session: SessionDep) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise AppError("AUTH_REQUIRED")
    user = await resolve_session(session, token)
    if user is None:
        raise AppError("AUTH_REQUIRED")
    if request.method not in SAFE_METHODS and not csrf_valid(
        request.cookies.get(CSRF_COOKIE), request.headers.get(CSRF_HEADER)
    ):
        raise AppError("CSRF_INVALID")
    bind_context(user_id=str(user.id))
    return user


UserDep = Annotated[User, Depends(current_user)]
