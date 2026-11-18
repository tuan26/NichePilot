"""T016 – Dữ liệu seed mặc định (FR-006, FR-042, FR-049, FR-053, FR-055, FR-057)."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

pytestmark = pytest.mark.integration

EXPECTED_SETTINGS = {
    "budget.daily_usd": "3.00",
    "budget.monthly_usd": "30.00",
    "budget.per_job_default_usd": "2.00",
    "budget.warning_threshold": 0.8,
    "budget.reservation_margin_s": 60,
    "budget.max_uncertain_per_job": 3,
    "system.timezone": "Asia/Ho_Chi_Minh",
    "agent.default_max_steps": 20,
    "agent.default_max_ai_calls": 30,
    "agent.default_job_timeout_s": 1800,
    "worker.max_concurrent_jobs": 1,
    "schedule.misfire_policy_default": "RUN_ONCE",
    "ui.default_locale": "vi",
    "auth.session_idle_timeout_hours": 12,
    "auth.lockout_threshold": 5,
    "auth.lockout_minutes": 15,
    "logging.retention_days": 90,
    "logging.disk_warn_gb": 2,
    "billing.error_responses_not_billed_verified": {"anthropic": False, "openai": False},
}


async def test_TC_FR006_01_exactly_one_default_project(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        rows = (
            await conn.execute(
                text("SELECT slug, target_market, research_language, content_language FROM projects WHERE is_default")
            )
        ).all()
    assert rows == [("default", "US", "auto", "en")]


async def test_TC_FR055_01_default_settings_seeded(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        rows = dict((await conn.execute(text("SELECT key, value FROM settings"))).all())
    for key, expected in EXPECTED_SETTINGS.items():
        assert key in rows, key
        assert rows[key] == expected, (key, rows[key])


async def test_TC_FR055_02_secret_like_keys_rejected(engine: AsyncEngine) -> None:
    from sqlalchemy.exc import IntegrityError

    async with engine.connect() as conn:
        with pytest.raises(IntegrityError):
            await conn.execute(text("INSERT INTO settings (key, value) VALUES ('provider.anthropic_api_key', '\"x\"')"))
        await conn.rollback()
