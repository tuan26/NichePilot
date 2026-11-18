"""Router provider AI (T114 – FR-054, FR-056, FR-019c).

- Không bao giờ trả giá trị key, chỉ `key_hint` (tối đa 4 ký tự cuối).
- `test-connection` và `verify-models` chỉ dùng Models API – không tính phí token; mỗi lần đều ghi audit.
- `verify-models` xác minh model ID và khả năng được công bố; KHÔNG xác minh giá, KHÔNG đổi model của profile.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from nichepilot.api.deps import MetaDep, SessionDep, SettingsDep, UserDep
from nichepilot.api.v1.jobs import services
from nichepilot.core.config import Settings
from nichepilot.core.errors import AppError
from nichepilot.core.logging import get_logger
from nichepilot.core.security import key_hint
from nichepilot.modules.audit.service import record_audit

router = APIRouter(tags=["providers"])
log = get_logger(__name__)
ProviderName = Literal["anthropic", "openai", "mock"]


class ProviderStatus(BaseModel):
    provider: ProviderName
    configured: bool
    key_hint: str | None = None
    last_check: str | None = None
    last_checked_at: datetime | None = None


async def provider_statuses(session: AsyncSession, settings: Settings) -> list[ProviderStatus]:
    last: dict[str, tuple[str, datetime]] = {}
    try:
        rows = (
            await session.execute(
                text(
                    "SELECT DISTINCT ON (after->>'provider') after->>'provider', after->>'result', created_at"
                    " FROM audit_logs WHERE action = 'provider.connection_tested'"
                    " ORDER BY after->>'provider', created_at DESC"
                )
            )
        ).all()
        last = {p: (r, at) for p, r, at in rows}
    except Exception as exc:  # DB không khả dụng → vẫn trả trạng thái cấu hình
        log.warning("provider status: last check unavailable", error_type=type(exc).__name__)
    out: list[ProviderStatus] = []
    for name, secret in (("anthropic", settings.anthropic_api_key), ("openai", settings.openai_api_key)):
        value = secret.get_secret_value() if secret else None
        check = last.get(name)
        out.append(
            ProviderStatus(
                provider=name,
                configured=value is not None,
                key_hint=key_hint(value),
                last_check=check[0] if check else None,
                last_checked_at=check[1] if check else None,
            )
        )
    if not settings.is_production:
        out.append(ProviderStatus(provider="mock", configured=True, last_check="MOCK"))
    return out


@router.get("/providers")
async def list_providers(_user: UserDep, session: SessionDep, settings: SettingsDep) -> list[ProviderStatus]:
    return await provider_statuses(session, settings)


@router.post("/providers/{provider}/test-connection")
async def test_connection(
    provider: ProviderName,
    request: Request,
    user: UserDep,
    session: SessionDep,
    settings: SettingsDep,
    meta: MetaDep,
) -> dict[str, Any]:
    impl = services(request).gateway.providers.get(provider)
    if provider == "mock":
        result = "MOCK" if impl is not None and not settings.is_production else "NOT_CONFIGURED"
    elif impl is None:
        result = "NOT_CONFIGURED"
    else:
        result = (await impl.check_connection()).result
    checked_at = datetime.now(UTC)
    await record_audit(
        session,
        action="provider.connection_tested",
        actor_type="USER",
        actor_id=user.id,
        entity_type="provider",
        after={"provider": provider, "result": result},
        request_id=meta.request_id,
    )
    log.info("provider.connection_tested", provider=provider, result=result)
    return {"provider": provider, "result": result, "checked_at": checked_at.isoformat()}


def _anthropic_caps(info: dict[str, Any]) -> dict[str, Any]:
    caps = info.get("capabilities") or {}
    out: dict[str, Any] = {}
    if isinstance(caps.get("structured_outputs"), dict) and "supported" in caps["structured_outputs"]:
        out["supports_structured_output"] = bool(caps["structured_outputs"]["supported"])
    if isinstance(caps.get("effort"), dict) and "supported" in caps["effort"]:
        out["supports_effort"] = bool(caps["effort"]["supported"])
    if info.get("max_input_tokens"):
        out["max_input_tokens"] = int(info["max_input_tokens"])
    if info.get("max_tokens"):
        out["max_output_tokens"] = int(info["max_tokens"])
    return out  # tool calling không được Models API công bố → giữ nguyên (xác minh thủ công)


@router.post("/providers/{provider}/verify-models")
async def verify_models(
    provider: Literal["anthropic", "openai"], request: Request, user: UserDep, session: SessionDep, meta: MetaDep
) -> list[dict[str, Any]]:
    impl = services(request).gateway.providers.get(provider)
    retrieve = getattr(impl, "retrieve_model", None)
    if impl is None or retrieve is None:
        raise AppError("PROVIDER_NOT_CONFIGURED", params={"provider": provider})
    models = (
        (await session.execute(text("SELECT * FROM ai_models WHERE provider = :p ORDER BY model_id"), {"p": provider}))
        .mappings()
        .all()
    )
    results: list[dict[str, Any]] = []
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    for m in models:
        model_id = m["model_id"]
        try:
            info = await retrieve(model_id)
        except Exception as exc:
            results.append({"model_id": model_id, "result": "ERROR", "detail": type(exc).__name__})
            continue
        if info is None:
            await session.execute(
                text("UPDATE ai_models SET verified = false, updated_at = now() WHERE id = :i"), {"i": m["id"]}
            )
            results.append({"model_id": model_id, "result": "NOT_FOUND", "detail": "Models API: not found"})
            continue
        caps = _anthropic_caps(info) if provider == "anthropic" else {}
        uses_effort = (
            await session.execute(
                text(
                    "SELECT EXISTS (SELECT 1 FROM model_task_profiles WHERE provider = :p AND model = :m"
                    " AND enabled AND effort IS NOT NULL)"
                ),
                {"p": provider, "m": model_id},
            )
        ).scalar_one()
        mismatch = [
            name
            for name, ok in (
                ("structured_output", caps.get("supports_structured_output", True)),
                ("effort", caps.get("supports_effort", True) or not uses_effort),
            )
            if not ok
        ]
        verified = not mismatch
        sets = "".join(f", {k} = :{k}" for k in caps)
        await session.execute(
            text(
                "UPDATE ai_models SET verified = :v, verification_source = :src, verified_at = now(),"  # noqa: S608
                f" verified_by = 'models_api'{sets}, updated_at = now() WHERE id = :i"
            ),
            {"v": verified, "src": f"{provider} Models API GET /v1/models/{model_id} ({stamp})", "i": m["id"], **caps},
        )
        if verified:
            detail = "model ID confirmed" + (
                "" if provider == "anthropic" else "; capabilities need manual confirmation"
            )
            results.append({"model_id": model_id, "result": "VERIFIED", "detail": detail})
        else:
            results.append(
                {"model_id": model_id, "result": "CAPABILITY_MISMATCH", "detail": "unsupported: " + ",".join(mismatch)}
            )
    await record_audit(
        session,
        action="provider.models_verified",
        actor_type="USER",
        actor_id=user.id,
        entity_type="provider",
        after={"provider": provider, "results": {r["model_id"]: r["result"] for r in results}},
        request_id=meta.request_id,
    )
    return results
