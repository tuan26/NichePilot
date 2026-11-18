"""Router cấu hình không bí mật và project mặc định (T112 – FR-055, FR-051, FR-057, BR-10)."""

from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from nichepilot.api.deps import MetaDep, SessionDep, UserDep
from nichepilot.core.errors import AppError
from nichepilot.modules.audit.service import record_audit
from nichepilot.modules.settings.models import Project, Setting
from nichepilot.modules.settings.service import (
    SettingValidationError,
    VersionConflictError,
    get_default_project,
    list_settings,
    update_settings,
)

router = APIRouter(tags=["settings"])
LANG_RE = re.compile(r"^[a-z]{2,3}(-[A-Z]{2})?$")


class SettingPatch(BaseModel):
    key: str
    value: Any
    version: int = Field(ge=1)


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    target_market: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    research_language: str | None = None
    content_language: str | None = None

    @field_validator("research_language")
    @classmethod
    def _research(cls, v: str | None) -> str | None:
        if v is not None and v != "auto" and not LANG_RE.match(v):
            raise ValueError("language code or 'auto'")
        return v

    @field_validator("content_language")
    @classmethod
    def _content(cls, v: str | None) -> str | None:
        if v is not None and not LANG_RE.match(v):
            raise ValueError("language code")
        return v


def setting_dict(s: Setting) -> dict[str, Any]:
    return {"key": s.key, "value": s.value, "version": s.version, "updated_at": s.updated_at.isoformat()}


def project_dict(p: Project) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "slug": p.slug,
        "name": p.name,
        "target_market": p.target_market,
        "research_language": p.research_language,
        "content_language": p.content_language,
    }


@router.get("/settings")
async def get_settings(_user: UserDep, session: SessionDep) -> list[dict[str, Any]]:
    return [setting_dict(s) for s in await list_settings(session)]


@router.patch("/settings")
async def patch_settings(
    items: list[SettingPatch], user: UserDep, session: SessionDep, meta: MetaDep
) -> list[dict[str, Any]]:
    if not items or len({i.key for i in items}) != len(items):
        raise AppError("VALIDATION_ERROR", errors=[{"field": "body", "code": "empty_or_duplicate_keys"}])
    try:
        before, after = await update_settings(session, [(i.key, i.value, i.version) for i in items], user_id=user.id)
    except SettingValidationError as exc:
        await session.rollback()
        raise AppError("VALIDATION_ERROR", errors=[{"field": exc.key, "code": exc.code}]) from None
    except VersionConflictError as exc:
        await session.rollback()  # cả lô không được ghi
        raise AppError("VERSION_CONFLICT", params={"key": exc.key}) from None
    await record_audit(
        session,
        action="settings.updated",
        actor_type="USER",
        actor_id=user.id,
        entity_type="setting",
        before=before,
        after=after,
        request_id=meta.request_id,
    )
    await session.flush()
    session.expire_all()
    return [setting_dict(s) for s in await list_settings(session)]


@router.get("/projects/default")
async def get_project(_user: UserDep, session: SessionDep) -> dict[str, Any]:
    return project_dict(await get_default_project(session))


@router.patch("/projects/default")
async def patch_project(body: ProjectUpdate, user: UserDep, session: SessionDep, meta: MetaDep) -> dict[str, Any]:
    project = await get_default_project(session)
    changes = body.model_dump(exclude_none=True)
    before = {k: getattr(project, k) for k in changes}
    for k, v in changes.items():  # chỉ đổi trường được gửi – các ngôn ngữ độc lập nhau
        setattr(project, k, v)
    if changes:
        await session.flush()
        await record_audit(
            session,
            action="project.updated",
            actor_type="USER",
            actor_id=user.id,
            entity_type="project",
            entity_id=project.id,
            before=before,
            after=changes,
            request_id=meta.request_id,
        )
    return project_dict(project)
