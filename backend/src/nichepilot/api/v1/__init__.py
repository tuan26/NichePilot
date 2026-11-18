"""Router API v1. Các router con được thêm theo từng user story."""

from __future__ import annotations

from fastapi import APIRouter

from nichepilot.api.v1 import auth, system

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(system.router)
