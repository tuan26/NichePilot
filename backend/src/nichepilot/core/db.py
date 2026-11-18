"""Kết nối PostgreSQL (T027 – FR-003, QA-08).

SQLAlchemy async + psycopg 3. `pool_pre_ping` để tự kết nối lại sau khi DB gián đoạn; lỗi mất kết nối được
xử lý thành `SERVICE_UNAVAILABLE` ở tầng API (core.errors).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def make_engine(url: str, *, pool_size: int = 5) -> AsyncEngine:
    return create_async_engine(
        url,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=5,
        pool_recycle=1800,
        connect_args={"connect_timeout": 5},
    )


def init_db(url: str, *, pool_size: int = 5) -> async_sessionmaker[AsyncSession]:
    global _engine, _sessionmaker
    _engine = make_engine(url, pool_size=pool_size)
    _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _sessionmaker


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    if _sessionmaker is None:
        raise RuntimeError("Database chưa được khởi tạo (init_db)")
    return _sessionmaker


def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Database chưa được khởi tạo (init_db)")
    return _engine


async def dispose_db() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None


async def session_dependency() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: một session cho mỗi request, commit khi thành công."""
    async with get_sessionmaker()() as session:
        try:
            yield session
            await session.commit()
        except BaseException:
            await session.rollback()
            raise
