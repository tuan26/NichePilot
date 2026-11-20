"""Router E1 – Autonomous Niche Discovery (contracts/openapi.yaml; T041 khung + trạng thái).

Endpoint dữ liệu nghiên cứu dùng `LedgerGate`: erasure ledger chưa áp dụng đầy đủ → 503 `ERASURE_LEDGER_NOT_APPLIED`
(X4).
`GET /api/v1/discovery/status` luôn trả (để chủ sở hữu thấy lỗi) và KHÔNG sửa `/api/v1/system/status` của E0 (H1).
"""

from __future__ import annotations

from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy import text

from nichepilot.api.deps import SessionDep, UserDep
from nichepilot.core.errors import AppError
from nichepilot.discovery_wiring import DiscoveryServices

router = APIRouter(tags=["discovery"])


def discovery_services(request: Request) -> DiscoveryServices:
    ds = getattr(request.app.state.services, "discovery", None)
    if ds is None:
        raise AppError("SERVICE_UNAVAILABLE")
    return ds  # type: ignore[no-any-return]


DiscoveryDep = Annotated[DiscoveryServices, Depends(discovery_services)]


async def ledger_gate(ds: DiscoveryDep) -> None:
    await ds.require_ledger_ok()


LedgerGate = Depends(ledger_gate)


async def _searxng_status(ds: DiscoveryServices) -> str:
    if ds.backends.data_origin == "MOCK":
        return "NOT_CONFIGURED"
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            r = await client.get(f"{ds.settings.searxng_url.rstrip('/')}/healthz")
        return "OK" if r.status_code == 200 else "UNAVAILABLE"
    except Exception:
        return "UNAVAILABLE"


@router.get("/discovery/status")
async def discovery_status(_user: UserDep, session: SessionDep, ds: DiscoveryDep) -> dict[str, Any]:
    health = await ds.ledger_health(force=True)
    usable = (
        await session.execute(
            text("SELECT count(*) FROM source_policies WHERE enabled AND compliance_status = 'ALLOWED'")
        )
    ).scalar_one()
    return {
        "erasure_ledger": {
            "status": health.status,
            "applied_seq": health.applied_seq,
            "ledger_tail_seq": health.ledger_tail_seq,
        },
        "searxng": await _searxng_status(ds),
        "pii_engine": ds.pii.name,
        "usable_sources": int(usable),
        "source_mode": ds.backends.data_origin,
    }
