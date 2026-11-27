"""Router API v1. Các router con được thêm theo từng user story."""

from __future__ import annotations

from fastapi import APIRouter

from nichepilot.api.v1 import (
    audit,
    auth,
    costs,
    discovery,
    jobs,
    models,
    products,
    providers,
    schedules,
    settings,
    system,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(system.router)
api_router.include_router(jobs.router)
api_router.include_router(costs.router)
api_router.include_router(schedules.router)
api_router.include_router(settings.router)
api_router.include_router(models.router)
api_router.include_router(providers.router)
api_router.include_router(audit.router)
api_router.include_router(discovery.router)  # E1
api_router.include_router(products.router)  # E2
