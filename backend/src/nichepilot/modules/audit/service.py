"""Audit service (T036 – FR-051). Ghi trong cùng transaction với thay đổi được audit; before/after được che."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession

from nichepilot.core.logging import redact_payload
from nichepilot.modules.audit.models import AuditLog


async def record_audit(
    session: AsyncSession,
    *,
    action: str,
    actor_type: Literal["USER", "SYSTEM"] = "SYSTEM",
    actor_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: uuid.UUID | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
    request_id: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_type=actor_type,
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before=redact_payload(before) if before is not None else None,
        after=redact_payload(after) if after is not None else None,
        request_id=request_id,
        ip=ip,
        user_agent=user_agent,
    )
    session.add(entry)
    await session.flush()
    return entry
