"""Router tra cứu audit log – chỉ đọc (T115 – FR-051). Không có endpoint sửa/xóa."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query
from sqlalchemy import text

from nichepilot.api.deps import SessionDep, UserDep

router = APIRouter(tags=["audit"])


def audit_dict(r: Any) -> dict[str, Any]:
    return {
        "id": str(r["id"]),
        "actor_type": r["actor_type"],
        "actor_id": str(r["actor_id"]) if r["actor_id"] else None,
        "action": r["action"],
        "entity_type": r["entity_type"],
        "entity_id": str(r["entity_id"]) if r["entity_id"] else None,
        "before": r["before"],
        "after": r["after"],
        "request_id": r["request_id"],
        "created_at": r["created_at"].isoformat(),
    }


@router.get("/audit-logs")
async def list_audit_logs(
    _user: UserDep,
    session: SessionDep,
    action: str | None = None,
    entity_type: str | None = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    where = (
        "WHERE (CAST(:a AS text) IS NULL OR action = :a) AND (CAST(:e AS text) IS NULL OR entity_type = :e)"
        " AND (CAST(:f AS timestamptz) IS NULL OR created_at >= :f)"
        " AND (CAST(:t AS timestamptz) IS NULL OR created_at < :t)"
    )
    params = {"a": action, "e": entity_type, "f": from_, "t": to}
    total = (await session.execute(text(f"SELECT COUNT(*) FROM audit_logs {where}"), params)).scalar_one()  # noqa: S608
    rows = (
        (
            await session.execute(
                text(f"SELECT * FROM audit_logs {where} ORDER BY created_at DESC, id DESC LIMIT :l OFFSET :o"),  # noqa: S608
                {**params, "l": page_size, "o": (page - 1) * page_size},
            )
        )
        .mappings()
        .all()
    )
    return {"page": page, "page_size": page_size, "total": total, "items": [audit_dict(r) for r in rows]}
