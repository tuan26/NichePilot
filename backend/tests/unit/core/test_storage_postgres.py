"""FR-003 – Toàn bộ dữ liệu vận hành lưu trong PostgreSQL: cấu hình chỉ nhận URL PostgreSQL (psycopg)."""

from __future__ import annotations

import pytest

from nichepilot.core.config import ConfigError, Settings


@pytest.mark.parametrize(
    "url", ["sqlite+aiosqlite:///./np.db", "mysql+aiomysql://u:p@h/db", "postgresql+asyncpg://u:p@h/db"]
)
def test_TC_FR003_01_only_postgresql_psycopg_accepted(url: str) -> None:
    with pytest.raises((ConfigError, ValueError)):
        Settings(_env_file=None, _secrets_dir=None, database_url=url, app_env="test")


def test_TC_FR003_02_postgresql_accepted() -> None:
    s = Settings(_env_file=None, _secrets_dir=None, database_url="postgresql+psycopg://u:p@db:5432/np", app_env="test")
    assert s.database_url.get_secret_value().startswith("postgresql+psycopg://")
