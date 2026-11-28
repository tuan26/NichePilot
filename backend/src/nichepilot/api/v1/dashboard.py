"""Router E4 – Bilingual Dashboard (specs/005-bilingual-dashboard/contracts/openapi.yaml): 2 endpoint chỉ đọc.

Có dữ liệu nghiên cứu → cổng erasure ledger E1 (503 `ERASURE_LEDGER_NOT_APPLIED`). Chi phí lấy từ `/api/v1/budget` (E0).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Query

from nichepilot.api.deps import SessionDep, UserDep
from nichepilot.api.v1.discovery import LedgerGate
from nichepilot.modules.dashboard import queries

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/overview", dependencies=[LedgerGate])
async def dashboard_overview(_user: UserDep, session: SessionDep, include_mock: bool = False) -> dict[str, Any]:
    return await queries.overview(session, include_mock=include_mock)


@router.get("/dashboard/niches", dependencies=[LedgerGate])
async def dashboard_niches(
    _user: UserDep,
    session: SessionDep,
    include_mock: bool = False,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> dict[str, Any]:
    return await queries.research_niches(session, include_mock=include_mock, limit=limit)
