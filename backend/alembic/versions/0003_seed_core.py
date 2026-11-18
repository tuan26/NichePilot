"""0003_seed_core – project mặc định + khóa settings mặc định (data-model.md §3, §4).

Ngân sách mặc định $3/ngày, $30/tháng, $2/job; giới hạn UNCERTAIN 3/job; log ứng dụng 90 ngày.
Tiền lưu dạng chuỗi thập phân trong JSON để tránh sai số float.

Revision ID: 0003_seed_core
Revises: 0002_procrastinate
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "0003_seed_core"
down_revision = "0002_procrastinate"
branch_labels = None
depends_on = None

DEFAULT_SETTINGS: dict[str, object] = {
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
    # Chính sách tính phí khi phản hồi lỗi CHƯA được xác minh → phản hồi lỗi bị coi là UNCERTAIN (R-06)
    "billing.error_responses_not_billed_verified": {"anthropic": False, "openai": False},
}


def upgrade() -> None:
    op.execute(
        "INSERT INTO projects (slug, name, is_default, target_market, research_language, content_language) "
        "VALUES ('default', 'Default project', true, 'US', 'auto', 'en')"
    )
    stmt = sa.text("INSERT INTO settings (key, value) VALUES (:k, CAST(:v AS jsonb))")
    for key, value in DEFAULT_SETTINGS.items():
        op.get_bind().execute(stmt, {"k": key, "v": json.dumps(value)})


def downgrade() -> None:
    keys = ", ".join(f"'{k}'" for k in DEFAULT_SETTINGS)
    op.execute(f"DELETE FROM settings WHERE key IN ({keys})")  # noqa: S608 – khóa là hằng số
    op.execute("DELETE FROM projects WHERE slug = 'default'")
