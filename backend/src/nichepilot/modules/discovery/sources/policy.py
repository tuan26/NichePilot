"""SourcePolicyService (FR-006c…FR-006g, FR-036; quyết định A1 2026-11-20 (b); internal-interfaces §1).

- `usable_for_run()` chỉ trả nguồn `enabled ∧ ALLOWED` – cho MỌI loại lượt; không có tham số/cờ nào đưa nguồn khác vào.
- Không có hàm nào tự bật nguồn hay tự nâng trạng thái. Chỉ `update_policy` (API của chủ sở hữu) ghi
`compliance_status`/
  `enabled`, kèm căn cứ bắt buộc và audit trước/sau. Rời `ALLOWED` → tắt ngay trong cùng transaction.
- Nguồn mới (`create_policy`) luôn `UNVERIFIED`, tắt.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nichepilot.core.errors import AppError
from nichepilot.core.source_config import SourceConfigError, validate_source_config
from nichepilot.modules.audit.service import record_audit

ComplianceStatus = Literal["ALLOWED", "UNVERIFIED", "PROHIBITED"]
AccessMethod = Literal["SEARXNG_ENGINE", "OFFICIAL_API", "DATASET_DOWNLOAD"]
AUDITED_FIELDS = (
    "compliance_status",
    "enabled",
    "verified_at",
    "verification_note",
    "allowed_access_methods",
    "permitted_use_scope",
    "tos_url",
    "known_limits",
    "config",
)
_TOKEN = object()


@dataclass(frozen=True)
class PolicyView:
    policy_id: uuid.UUID
    source_key: str
    adapter_type: str
    config: dict[str, Any]
    compliance_status: str
    verified_at: date | None


class UsableSourcePolicy:
    """Kiểu đóng: chỉ `SourcePolicyService.usable_for_run` tạo được – luôn là nguồn ALLOWED đang bật."""

    __slots__ = ("_view",)

    def __init__(self, token: object, row: Any) -> None:
        if token is not _TOKEN:
            raise TypeError("UsableSourcePolicy chỉ được tạo bởi SourcePolicyService.usable_for_run")
        if row["compliance_status"] != "ALLOWED" or not row["enabled"]:
            raise TypeError("chỉ nguồn ALLOWED đang bật")
        self._view = PolicyView(
            row["id"], row["source_key"], row["adapter_type"], dict(row["config"]), "ALLOWED", row["verified_at"]
        )

    @property
    def policy_id(self) -> uuid.UUID:
        return self._view.policy_id

    @property
    def source_key(self) -> str:
        return self._view.source_key

    @property
    def adapter_type(self) -> str:
        return self._view.adapter_type

    @property
    def config(self) -> dict[str, Any]:
        return dict(self._view.config)

    def snapshot(self) -> PolicyView:
        return self._view

    def tool_input(self) -> dict[str, Any]:
        """Input `policy` cho tool `source.query` (tool kiểm tra lại trạng thái – phòng thủ lớp 2)."""
        v = self._view
        return {
            "policy_id": str(v.policy_id),
            "source_key": v.source_key,
            "adapter_type": v.adapter_type,
            "config": v.config,
            "compliance_status": v.compliance_status,
            "verified_at": v.verified_at.isoformat() if v.verified_at else None,
        }


class PolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")  # không có trường xác nhận cảnh báo nào (A1)
    compliance_status: ComplianceStatus | None = None
    verified_at: date | None = None
    verification_note: str | None = Field(default=None, min_length=10, max_length=2000)
    allowed_access_methods: list[AccessMethod] | None = None
    permitted_use_scope: str | None = Field(default=None, min_length=10, max_length=1000)
    tos_url: str | None = Field(default=None, pattern=r"^https://", max_length=2000)
    known_limits: str | None = Field(default=None, max_length=1000)
    config: dict[str, Any] | None = None
    enabled: bool | None = None


class PolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_key: str = Field(pattern=r"^[a-z0-9_:.-]{2,64}$")
    display_name: str = Field(min_length=1, max_length=120)
    adapter_type: Literal["searxng_engine", "http_json_api", "open_dataset", "licensed_data"]
    tos_url: str = Field(pattern=r"^https://", max_length=2000)
    config: dict[str, Any]


def _jsonable(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k in AUDITED_FIELDS:
        v = row.get(k)
        out[k] = v.isoformat() if isinstance(v, date) else (list(v) if isinstance(v, tuple) else v)
    return out


class SourcePolicyService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_policies(self) -> list[dict[str, Any]]:
        rows = (await self.session.execute(text("SELECT * FROM source_policies ORDER BY source_key"))).mappings().all()
        return [dict(r) for r in rows]

    async def get(self, policy_id: uuid.UUID) -> dict[str, Any] | None:
        row = (
            (await self.session.execute(text("SELECT * FROM source_policies WHERE id = :i"), {"i": policy_id}))
            .mappings()
            .first()
        )
        return dict(row) if row else None

    async def usable_for_run(self) -> list[UsableSourcePolicy]:
        rows = (
            (
                await self.session.execute(
                    text(
                        "SELECT * FROM source_policies WHERE enabled AND compliance_status = 'ALLOWED'"
                        " ORDER BY source_key"
                    )
                )
            )
            .mappings()
            .all()
        )
        return [UsableSourcePolicy(_TOKEN, r) for r in rows]

    async def create_policy(
        self, actor_id: uuid.UUID, data: PolicyCreate, *, request_id: str | None = None
    ) -> dict[str, Any]:
        try:
            config = validate_source_config(data.adapter_type, data.config)
        except SourceConfigError as exc:
            raise AppError("SOURCE_CONFIG_INVALID", detail=str(exc)) from None
        row = (
            (
                await self.session.execute(
                    text(
                        "INSERT INTO source_policies (source_key, display_name, adapter_type, config, tos_url,"
                        " compliance_status, enabled, updated_by) VALUES (:k, :n, :a, CAST(:c AS jsonb), :t,"
                        " 'UNVERIFIED', false, :u) ON CONFLICT (source_key) DO NOTHING RETURNING *"
                    ),
                    {
                        "k": data.source_key,
                        "n": data.display_name,
                        "a": data.adapter_type,
                        "c": json.dumps(config),
                        "t": data.tos_url,
                        "u": actor_id,
                    },
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise AppError("SOURCE_EXISTS")
        await record_audit(
            self.session,
            action="source.created",
            actor_type="USER",
            actor_id=actor_id,
            entity_type="source_policy",
            entity_id=row["id"],
            after=_jsonable(dict(row)),
            request_id=request_id,
        )
        return dict(row)

    async def update_policy(
        self, actor_id: uuid.UUID, policy_id: uuid.UUID, upd: PolicyUpdate, *, request_id: str | None = None
    ) -> dict[str, Any]:
        current = (
            (
                await self.session.execute(
                    text("SELECT * FROM source_policies WHERE id = :i FOR UPDATE"), {"i": policy_id}
                )
            )
            .mappings()
            .first()
        )
        if current is None:
            raise AppError("NOT_FOUND")
        before = dict(current)
        new = dict(before)
        changes = upd.model_dump(exclude_unset=True)
        if "config" in changes and changes["config"] is not None:
            try:
                changes["config"] = validate_source_config(before["adapter_type"], changes["config"])
            except SourceConfigError as exc:
                raise AppError("SOURCE_CONFIG_INVALID", detail=str(exc)) from None
        new.update({k: v for k, v in changes.items() if v is not None or k in {"known_limits"}})
        status = new["compliance_status"]
        if status != "ALLOWED" and before["compliance_status"] == "ALLOWED":
            new["enabled"] = False  # rời ALLOWED → tắt ngay (FR-006d)
        if new["enabled"] and status != "ALLOWED":
            raise AppError("SOURCE_NOT_ALLOWED")
        if status == "ALLOWED":
            complete = (
                new["verified_at"]
                and new["verification_note"]
                and len(new["allowed_access_methods"] or []) > 0
                and new["permitted_use_scope"]
            )
            if not complete:
                raise AppError("SOURCE_VERIFICATION_INCOMPLETE")
            if before["compliance_status"] != "ALLOWED" or "verified_at" in changes:
                new["verified_by"] = actor_id
        if status == "PROHIBITED" and not (new["verified_at"] and new["verification_note"]):
            raise AppError("SOURCE_VERIFICATION_INCOMPLETE")
        row = (
            (
                await self.session.execute(
                    text(
                        "UPDATE source_policies SET compliance_status = :s, enabled = :e,"  # write-ok: update_policy
                        " verified_at = :va, verified_by = :vb, verification_note = :vn,"
                        " allowed_access_methods = CAST(:am AS text[]), permitted_use_scope = :sc, tos_url = :t,"
                        " known_limits = :kl, config = CAST(:c AS jsonb), updated_by = :u, updated_at = now()"
                        " WHERE id = :i RETURNING *"
                    ),
                    {
                        "s": status,
                        "e": bool(new["enabled"]),
                        "va": new["verified_at"],
                        "vb": new.get("verified_by"),
                        "vn": new["verification_note"],
                        "am": list(new["allowed_access_methods"] or []),
                        "sc": new["permitted_use_scope"],
                        "t": new["tos_url"],
                        "kl": new["known_limits"],
                        "c": json.dumps(new["config"]),
                        "u": actor_id,
                        "i": policy_id,
                    },
                )
            )
            .mappings()
            .one()
        )
        await record_audit(
            self.session,
            action="source.updated",
            actor_type="USER",
            actor_id=actor_id,
            entity_type="source_policy",
            entity_id=policy_id,
            before=_jsonable(before),
            after=_jsonable(dict(row)),
            request_id=request_id,
        )
        return dict(row)
