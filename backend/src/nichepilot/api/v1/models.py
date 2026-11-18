"""Router model theo tác vụ, catalog model, xác minh model và bảng giá (T113 – FR-012, FR-019c, FR-041, FR-051).

- Model mới luôn bắt đầu ở trạng thái CHƯA xác minh; xác minh thủ công bắt buộc ghi nguồn chính thức.
- Bảng giá chỉ thêm phiên bản mới (append-only); `verified=true` bắt buộc ghi nguồn.
- Đổi model của profile sang model có phí bắt buộc bảng giá đã xác minh; hệ thống không bao giờ tự đổi model.
- Mọi thay đổi đều ghi audit (before/after).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from nichepilot.ai.catalog import validate_model_id
from nichepilot.ai.pricing import load_price
from nichepilot.api.deps import MetaDep, SessionDep, SettingsDep, UserDep
from nichepilot.core.errors import AppError
from nichepilot.modules.audit.service import record_audit

router = APIRouter(tags=["settings"])
Provider = Literal["anthropic", "openai", "mock"]
MONEY_PATTERN = r"^\d+(\.\d{1,6})?$"


def _money(v: Any) -> str | None:
    return str(Decimal(v).quantize(Decimal("0.000001"))) if v is not None else None


def _iso(v: datetime | None) -> str | None:
    return v.isoformat() if v else None


# ------------------------------------------------------------------ profiles
class ProfileInput(BaseModel):
    task_type: str | None = None
    provider: Provider
    model: str = Field(min_length=1)
    effort: Literal["low", "medium", "high", "xhigh", "max"] | None = None
    max_output_tokens: int = Field(ge=1, le=128000)
    timeout_s: int = Field(ge=5, le=900)
    schema_retry_max: int = Field(ge=0, le=5)
    fallback_provider: Literal["anthropic", "openai"] | None = None
    fallback_model: str | None = None
    fallback_on: list[Literal["PROVIDER_UNAVAILABLE"]] = Field(default_factory=list)
    enabled: bool

    @model_validator(mode="after")
    def _fallback(self) -> ProfileInput:
        if self.fallback_provider is not None and (self.fallback_provider == self.provider or not self.fallback_model):
            raise ValueError("fallback_provider must differ from provider and have fallback_model")
        return self


PROFILE_FIELDS = (
    "provider", "model", "effort", "max_output_tokens", "timeout_s", "schema_retry_max",
    "fallback_provider", "fallback_model", "fallback_on", "enabled",
)  # fmt: skip


def profile_dict(r: Any) -> dict[str, Any]:
    return {"task_type": r["task_type"], **{k: (list(r[k]) if k == "fallback_on" else r[k]) for k in PROFILE_FIELDS}}


@router.get("/model-profiles")
async def list_profiles(_user: UserDep, session: SessionDep) -> list[dict[str, Any]]:
    rows = (await session.execute(text("SELECT * FROM model_task_profiles ORDER BY task_type"))).mappings().all()
    return [profile_dict(r) for r in rows]


async def _require_verified_price(session: Any, provider: str, model: str, field: str) -> None:
    price = await load_price(session, provider, model)
    if price is None or not price.verified:
        raise AppError("VALIDATION_ERROR", errors=[{"field": field, "code": "pricing_not_verified"}])


@router.put("/model-profiles/{task_type}")
async def put_profile(
    task_type: str, body: ProfileInput, user: UserDep, session: SessionDep, settings: SettingsDep, meta: MetaDep
) -> dict[str, Any]:
    if settings.is_production and "mock" in (body.provider, body.fallback_provider):
        raise AppError("MOCK_NOT_ALLOWED")
    before = (
        (await session.execute(text("SELECT * FROM model_task_profiles WHERE task_type = :t"), {"t": task_type}))
        .mappings()
        .first()
    )
    if before is None:
        raise AppError("NOT_FOUND")
    for prov, model, field in (
        (body.provider, body.model, "model"),
        (body.fallback_provider, body.fallback_model, "fallback_model"),
    ):
        if prov is None or model is None:
            continue
        exists = (
            await session.execute(
                text("SELECT 1 FROM ai_models WHERE provider = :p AND model_id = :m"), {"p": prov, "m": model}
            )
        ).first()
        if exists is None:
            raise AppError("VALIDATION_ERROR", errors=[{"field": field, "code": "not_in_catalog"}])
        changed = (prov, model) != (
            (before["provider"], before["model"])
            if field == "model"
            else (before["fallback_provider"], before["fallback_model"])
        )
        if prov != "mock" and changed:  # đổi sang model có phí → giá phải đã xác minh
            await _require_verified_price(session, prov, model, field)
    values = body.model_dump(exclude={"task_type"})
    try:
        async with session.begin_nested():
            row = (
                (
                    await session.execute(
                        text(
                            "UPDATE model_task_profiles SET provider = :provider, model = :model, effort = :effort,"
                            " max_output_tokens = :max_output_tokens, timeout_s = :timeout_s,"
                            " schema_retry_max = :schema_retry_max, fallback_provider = :fallback_provider,"
                            " fallback_model = :fallback_model, fallback_on = :fallback_on, enabled = :enabled,"
                            " updated_at = now() WHERE task_type = :task_type RETURNING *"
                        ),
                        {**values, "task_type": task_type},
                    )
                )
                .mappings()
                .one()
            )
    except IntegrityError:
        raise AppError("VALIDATION_ERROR", errors=[{"field": "body", "code": "constraint"}]) from None
    await record_audit(
        session,
        action="model_profile.updated",
        actor_type="USER",
        actor_id=user.id,
        entity_type="model_task_profile",
        entity_id=row["id"],
        before=profile_dict(before),
        after=profile_dict(row),
        request_id=meta.request_id,
    )
    return profile_dict(row)


# ------------------------------------------------------------------ catalog
class ModelInput(BaseModel):
    provider: Literal["anthropic", "openai"]
    model_id: str = Field(min_length=1, max_length=200)
    display_name: str | None = None
    supports_structured_output: bool | None = None
    supports_tools: bool | None = None
    supports_effort: bool | None = None
    max_input_tokens: int | None = Field(default=None, ge=1)
    max_output_tokens: int | None = Field(default=None, ge=1)
    status: Literal["ACTIVE", "DEPRECATED", "UNAVAILABLE"] = "ACTIVE"

    @model_validator(mode="after")
    def _id(self) -> ModelInput:
        validate_model_id(self.model_id)  # không chấp nhận alias kiểu "latest"
        return self


MODEL_FIELDS = (
    "provider", "model_id", "display_name", "verified", "verification_source", "verified_by",
    "supports_structured_output", "supports_tools", "supports_effort", "max_input_tokens", "max_output_tokens",
    "status",
)  # fmt: skip


def model_dict(r: Any) -> dict[str, Any]:
    return {"id": str(r["id"]), **{k: r[k] for k in MODEL_FIELDS}, "verified_at": _iso(r["verified_at"])}


def model_audit(r: Any) -> dict[str, Any]:
    return {**{k: r[k] for k in MODEL_FIELDS}, "verified_at": _iso(r["verified_at"])}


@router.get("/models")
async def list_models(_user: UserDep, session: SessionDep) -> list[dict[str, Any]]:
    rows = (await session.execute(text("SELECT * FROM ai_models ORDER BY provider, model_id"))).mappings().all()
    return [model_dict(r) for r in rows]


@router.post("/models", status_code=status.HTTP_201_CREATED)
async def create_model(body: ModelInput, user: UserDep, session: SessionDep, meta: MetaDep) -> dict[str, Any]:
    try:
        async with session.begin_nested():
            row = (
                (
                    await session.execute(
                        text(
                            "INSERT INTO ai_models (provider, model_id, display_name, verified,"
                            " supports_structured_output, supports_tools, supports_effort, max_input_tokens,"
                            " max_output_tokens, status) VALUES (:provider, :model_id, :display_name, false,"
                            " :supports_structured_output, :supports_tools, :supports_effort, :max_input_tokens,"
                            " :max_output_tokens, :status) RETURNING *"
                        ),
                        body.model_dump(),
                    )
                )
                .mappings()
                .one()
            )
    except IntegrityError:
        raise AppError("MODEL_EXISTS") from None
    await record_audit(
        session,
        action="model.created",
        actor_type="USER",
        actor_id=user.id,
        entity_type="ai_model",
        entity_id=row["id"],
        after=model_audit(row),
        request_id=meta.request_id,
    )
    return model_dict(row)


class VerificationInput(BaseModel):
    verified: bool
    verification_source: str = Field(min_length=5, max_length=1000)
    supports_structured_output: bool | None = None
    supports_tools: bool | None = None
    supports_effort: bool | None = None
    max_input_tokens: int | None = Field(default=None, ge=1)
    max_output_tokens: int | None = Field(default=None, ge=1)


async def _get_model(session: Any, ai_model_id: uuid.UUID) -> Any:
    row = (await session.execute(text("SELECT * FROM ai_models WHERE id = :i"), {"i": ai_model_id})).mappings().first()
    if row is None:
        raise AppError("NOT_FOUND")
    return row


@router.put("/models/{ai_model_id}/verification")
async def verify_model(
    ai_model_id: uuid.UUID, body: VerificationInput, user: UserDep, session: SessionDep, meta: MetaDep
) -> dict[str, Any]:
    before = await _get_model(session, ai_model_id)
    caps = {
        k: v for k, v in body.model_dump().items() if k not in ("verified", "verification_source") and v is not None
    }
    sets = "".join(f", {k} = :{k}" for k in caps)
    row = (
        (
            await session.execute(
                text(
                    "UPDATE ai_models SET verified = :v, verification_source = :src, verified_at = now(),"  # noqa: S608
                    f" verified_by = :by{sets}, updated_at = now() WHERE id = :i RETURNING *"
                ),
                {
                    "v": body.verified,
                    "src": body.verification_source,
                    "by": f"user:{user.id}",
                    "i": ai_model_id,
                    **caps,
                },
            )
        )
        .mappings()
        .one()
    )
    await record_audit(
        session,
        action="model.verification_updated",
        actor_type="USER",
        actor_id=user.id,
        entity_type="ai_model",
        entity_id=ai_model_id,
        before=model_audit(before),
        after=model_audit(row),
        request_id=meta.request_id,
    )
    return model_dict(row)


# ------------------------------------------------------------------ pricing
class PricingInput(BaseModel):
    provider: Provider
    model: str = Field(min_length=1)
    effective_from: datetime
    input_per_mtok: str = Field(pattern=MONEY_PATTERN)
    output_per_mtok: str = Field(pattern=MONEY_PATTERN)
    cache_read_per_mtok: str | None = Field(default=None, pattern=MONEY_PATTERN)
    cache_write_per_mtok: str | None = Field(default=None, pattern=MONEY_PATTERN)
    long_context_threshold_tokens: int | None = Field(default=None, ge=1)
    long_input_per_mtok: str | None = Field(default=None, pattern=MONEY_PATTERN)
    long_output_per_mtok: str | None = Field(default=None, pattern=MONEY_PATTERN)
    source_note: str = Field(max_length=2000)
    verified: bool

    @model_validator(mode="after")
    def _rules(self) -> PricingInput:
        if len(self.source_note.strip()) < (5 if self.verified else 1):
            raise ValueError("source_note is required (min 5 chars when verified)")
        if self.long_context_threshold_tokens is not None and not (
            self.long_input_per_mtok and self.long_output_per_mtok
        ):
            raise ValueError("long context pricing incomplete")
        return self


PRICE_MONEY = (
    "input_per_mtok", "output_per_mtok", "cache_read_per_mtok", "cache_write_per_mtok",
    "long_input_per_mtok", "long_output_per_mtok",
)  # fmt: skip


def pricing_dict(r: Any) -> dict[str, Any]:
    return {
        "id": str(r["id"]),
        "provider": r["provider"],
        "model": r["model"],
        "version": r["version"],
        "effective_from": r["effective_from"].isoformat(),
        **{k: _money(r[k]) for k in PRICE_MONEY},
        "long_context_threshold_tokens": r["long_context_threshold_tokens"],
        "source_note": r["source_note"],
        "verified": r["verified"],
    }


@router.get("/model-pricing")
async def list_pricing(_user: UserDep, session: SessionDep) -> list[dict[str, Any]]:
    rows = (
        (await session.execute(text("SELECT * FROM model_pricing ORDER BY provider, model, version DESC")))
        .mappings()
        .all()
    )
    return [pricing_dict(r) for r in rows]


@router.post("/model-pricing", status_code=status.HTTP_201_CREATED)
async def create_pricing(body: PricingInput, user: UserDep, session: SessionDep, meta: MetaDep) -> dict[str, Any]:
    exists = (
        await session.execute(
            text("SELECT 1 FROM ai_models WHERE provider = :p AND model_id = :m"), {"p": body.provider, "m": body.model}
        )
    ).first()
    if exists is None:
        raise AppError("VALIDATION_ERROR", errors=[{"field": "model", "code": "not_in_catalog"}])
    # Khóa theo model để hai yêu cầu song song không cùng lấy một version.
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtext('model_pricing:' || :p || ':' || :m))"),
        {"p": body.provider, "m": body.model},
    )
    values = body.model_dump()
    for k in PRICE_MONEY:
        values[k] = Decimal(values[k]) if values[k] is not None else None
    row = (
        (
            await session.execute(
                text(
                    "INSERT INTO model_pricing (provider, model, version, effective_from, input_per_mtok,"
                    " output_per_mtok, cache_read_per_mtok, cache_write_per_mtok, long_context_threshold_tokens,"
                    " long_input_per_mtok, long_output_per_mtok, source_note, verified)"
                    " SELECT :provider, :model, COALESCE(MAX(version), 0) + 1, :effective_from, :input_per_mtok,"
                    " :output_per_mtok, :cache_read_per_mtok, :cache_write_per_mtok, :long_context_threshold_tokens,"
                    " :long_input_per_mtok, :long_output_per_mtok, :source_note, :verified"
                    " FROM model_pricing WHERE provider = :provider AND model = :model RETURNING *"
                ),
                values,
            )
        )
        .mappings()
        .one()
    )
    await record_audit(
        session,
        action="model_pricing.created",
        actor_type="USER",
        actor_id=user.id,
        entity_type="model_pricing",
        entity_id=row["id"],
        after=pricing_dict(row),
        request_id=meta.request_id,
    )
    return pricing_dict(row)
