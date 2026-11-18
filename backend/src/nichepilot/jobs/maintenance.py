"""Tác vụ bảo trì định kỳ chạy trong worker (T089 – FR-048).

Các tác vụ khác (stalled job, retention log) được thêm ở US4/US7.
"""

from __future__ import annotations

import procrastinate

from nichepilot.ai.budget import BudgetService

MAINTENANCE_QUEUE = "maintenance"


def register_maintenance(app: procrastinate.App, budget: BudgetService) -> None:
    @app.periodic(cron="* * * * *", periodic_id="budget_sweep_stale")
    @app.task(name="budget_sweep_stale", queue=MAINTENANCE_QUEUE, pass_context=False)
    async def budget_sweep_stale(timestamp: int) -> None:
        # ACTIVE quá hạn → RELEASED (chưa gửi) hoặc UNCERTAIN (đã gửi); không bao giờ tự giải phóng UNCERTAIN.
        await budget.sweep_stale()
