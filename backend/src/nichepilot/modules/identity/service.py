"""Dịch vụ xác thực single-owner (T048 – FR-052, FR-053).

Khóa tạm và thời hạn phiên đọc từ settings `auth.*` (cấu hình được). Mọi sự kiện đăng nhập được ghi audit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from nichepilot.core.errors import AppError
from nichepilot.core.security import hash_password, hash_token, new_token, verify_password
from nichepilot.modules.audit.service import record_audit
from nichepilot.modules.identity.models import AuthSession, User
from nichepilot.modules.settings.service import get_setting_values

SESSION_TOUCH_INTERVAL = timedelta(seconds=60)


@dataclass(frozen=True)
class AuthPolicy:
    lockout_threshold: int
    lockout_minutes: int
    session_idle_hours: int


@dataclass(frozen=True)
class RequestMeta:
    ip: str | None = None
    user_agent: str | None = None
    request_id: str | None = None


def _now() -> datetime:
    return datetime.now(UTC)


async def load_policy(session: AsyncSession) -> AuthPolicy:
    v = await get_setting_values(
        session, ["auth.lockout_threshold", "auth.lockout_minutes", "auth.session_idle_timeout_hours"]
    )
    return AuthPolicy(
        lockout_threshold=int(v["auth.lockout_threshold"]),
        lockout_minutes=int(v["auth.lockout_minutes"]),
        session_idle_hours=int(v["auth.session_idle_timeout_hours"]),
    )


async def setup_required(session: AsyncSession) -> bool:
    return (await session.execute(select(func.count()).select_from(User))).scalar_one() == 0


async def create_owner(session: AsyncSession, username: str, password: str, ui_locale: str, meta: RequestMeta) -> User:
    # Khóa bảng users để hai yêu cầu khởi tạo đồng thời không tạo ra hai chủ sở hữu.
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtext("nichepilot.owner_setup"))))
    if not await setup_required(session):
        raise AppError("ALREADY_SETUP")
    user = User(username=username, password_hash=hash_password(password), ui_locale=ui_locale)
    session.add(user)
    await session.flush()
    await record_audit(
        session,
        action="auth.owner_created",
        actor_type="USER",
        actor_id=user.id,
        entity_type="user",
        entity_id=user.id,
        after={"username": username, "ui_locale": ui_locale},
        request_id=meta.request_id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    return user


async def authenticate(session: AsyncSession, username: str, password: str, meta: RequestMeta) -> User:
    policy = await load_policy(session)
    now = _now()
    user = (await session.execute(select(User).where(User.username == username).with_for_update())).scalar_one_or_none()

    if user is not None and user.locked_until is not None and user.locked_until > now:
        raise AppError("AUTH_LOCKED", params={"locked_until": user.locked_until.isoformat()})

    if user is None or not verify_password(user.password_hash if user else None, password):
        if user is not None:
            user.failed_login_count += 1
            locked = user.failed_login_count >= policy.lockout_threshold
            if locked:
                user.locked_until = now + timedelta(minutes=policy.lockout_minutes)
                user.failed_login_count = 0
        await record_audit(
            session,
            action="auth.login_failed",
            actor_type="SYSTEM",
            entity_type="user",
            entity_id=user.id if user else None,
            after={"username": username},
            request_id=meta.request_id,
            ip=meta.ip,
            user_agent=meta.user_agent,
        )
        if user is not None and user.locked_until is not None and user.locked_until > now:
            await record_audit(
                session,
                action="auth.account_locked",
                actor_type="SYSTEM",
                entity_type="user",
                entity_id=user.id,
                after={"locked_until": user.locked_until.isoformat()},
                request_id=meta.request_id,
                ip=meta.ip,
            )
        await session.commit()  # lưu bộ đếm/khóa trước khi trả lỗi
        raise AppError("AUTH_INVALID_CREDENTIALS")

    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    await record_audit(
        session,
        action="auth.login_succeeded",
        actor_type="USER",
        actor_id=user.id,
        entity_type="user",
        entity_id=user.id,
        request_id=meta.request_id,
        ip=meta.ip,
        user_agent=meta.user_agent,
    )
    return user


async def open_session(session: AsyncSession, user: User, meta: RequestMeta) -> str:
    policy = await load_policy(session)
    token = new_token()
    now = _now()
    session.add(
        AuthSession(
            user_id=user.id,
            token_hash=hash_token(token),
            last_seen_at=now,
            expires_at=now + timedelta(hours=policy.session_idle_hours),
            ip=meta.ip,
            user_agent=meta.user_agent,
        )
    )
    await session.flush()
    return token


async def resolve_session(session: AsyncSession, token: str) -> User | None:
    now = _now()
    row = (
        await session.execute(
            select(AuthSession, User)
            .join(User, User.id == AuthSession.user_id)
            .where(
                AuthSession.token_hash == hash_token(token),
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
            )
        )
    ).first()
    if row is None:
        return None
    auth_session, user = row
    if now - auth_session.last_seen_at >= SESSION_TOUCH_INTERVAL:
        policy = await load_policy(session)
        auth_session.last_seen_at = now
        auth_session.expires_at = now + timedelta(hours=policy.session_idle_hours)
    return user


async def revoke_session(session: AsyncSession, token: str, user: User, meta: RequestMeta) -> None:
    auth_session = (
        await session.execute(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    ).scalar_one_or_none()
    if auth_session is not None and auth_session.revoked_at is None:
        auth_session.revoked_at = _now()
    await record_audit(
        session,
        action="auth.logout",
        actor_type="USER",
        actor_id=user.id,
        entity_type="user",
        entity_id=user.id,
        request_id=meta.request_id,
        ip=meta.ip,
    )


async def update_locale(session: AsyncSession, user: User, ui_locale: str, meta: RequestMeta) -> User:
    before = user.ui_locale
    user.ui_locale = ui_locale
    await record_audit(
        session,
        action="user.locale_updated",
        actor_type="USER",
        actor_id=user.id,
        entity_type="user",
        entity_id=user.id,
        before={"ui_locale": before},
        after={"ui_locale": ui_locale},
        request_id=meta.request_id,
    )
    return user
