"""Router xác thực (T050 – FR-051, FR-052, FR-053; contracts/openapi.yaml tag auth)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel, Field

from nichepilot.api.deps import MetaDep, SessionDep, SettingsDep, UserDep
from nichepilot.core.security import CSRF_COOKIE, SESSION_COOKIE, new_token
from nichepilot.modules.identity import service as identity
from nichepilot.modules.identity.models import User

router = APIRouter(prefix="/auth", tags=["auth"])
UiLocale = Literal["vi", "en"]


class SetupStatus(BaseModel):
    setup_required: bool


class SetupRequest(BaseModel):
    username: str = Field(pattern=r"^[a-z0-9._-]{3,64}$")
    password: str = Field(min_length=12, max_length=256)
    ui_locale: UiLocale


class LoginRequest(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=256)


class MeUpdate(BaseModel):
    ui_locale: UiLocale


class Me(BaseModel):
    id: UUID
    username: str
    ui_locale: UiLocale
    last_login_at: datetime | None

    @classmethod
    def of(cls, user: User) -> Me:
        return cls(id=user.id, username=user.username, ui_locale=user.ui_locale, last_login_at=user.last_login_at)


def _set_auth_cookies(response: Response, token: str, secure: bool, max_age_s: int) -> None:
    response.set_cookie(
        SESSION_COOKIE, token, httponly=True, samesite="lax", secure=secure, path="/", max_age=max_age_s
    )
    # Cookie CSRF đọc được bởi JS (double-submit), không chứa thông tin phiên.
    response.set_cookie(CSRF_COOKIE, new_token(), httponly=False, samesite="lax", secure=secure, path="/")


@router.get("/setup-status", response_model=SetupStatus)
async def setup_status(session: SessionDep) -> SetupStatus:
    return SetupStatus(setup_required=await identity.setup_required(session))


@router.post("/setup", response_model=Me, status_code=status.HTTP_201_CREATED)
async def setup(
    body: SetupRequest, response: Response, session: SessionDep, settings: SettingsDep, meta: MetaDep
) -> Me:
    user = await identity.create_owner(session, body.username, body.password, body.ui_locale, meta)
    user.last_login_at = identity._now()
    token = await identity.open_session(session, user, meta)
    policy = await identity.load_policy(session)
    _set_auth_cookies(response, token, settings.cookie_secure, policy.session_idle_hours * 3600)
    return Me.of(user)


@router.post("/login", response_model=Me)
async def login(
    body: LoginRequest, response: Response, session: SessionDep, settings: SettingsDep, meta: MetaDep
) -> Me:
    user = await identity.authenticate(session, body.username, body.password, meta)
    token = await identity.open_session(session, user, meta)
    policy = await identity.load_policy(session)
    _set_auth_cookies(response, token, settings.cookie_secure, policy.session_idle_hours * 3600)
    return Me.of(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, user: UserDep, session: SessionDep, meta: MetaDep) -> Response:
    await identity.revoke_session(session, request.cookies.get(SESSION_COOKIE, ""), user, meta)
    response.status_code = status.HTTP_204_NO_CONTENT
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return response


@router.get("/me", response_model=Me)
async def me(user: UserDep) -> Me:
    return Me.of(user)


@router.patch("/me", response_model=Me)
async def update_me(body: MeUpdate, user: UserDep, session: SessionDep, meta: MetaDep) -> Me:
    await identity.update_locale(session, user, body.ui_locale, meta)
    return Me.of(user)
