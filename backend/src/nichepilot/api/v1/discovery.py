"""Router E1 – Autonomous Niche Discovery (contracts/openapi.yaml; T041 khung + trạng thái).

Endpoint dữ liệu nghiên cứu dùng `LedgerGate`: erasure ledger chưa áp dụng đầy đủ → 503 `ERASURE_LEDGER_NOT_APPLIED`
(X4).
`GET /api/v1/discovery/status` luôn trả (để chủ sở hữu thấy lỗi) và KHÔNG sửa `/api/v1/system/status` của E0 (H1).
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated, Any, Literal

import httpx
from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from nichepilot.api.deps import MetaDep, SessionDep, SettingsDep, UserDep
from nichepilot.api.v1.jobs import CreateJobRequest, create_job
from nichepilot.core.errors import AppError
from nichepilot.core.logging import get_logger
from nichepilot.discovery_wiring import DiscoveryServices
from nichepilot.jobs.scheduler import budget_configured
from nichepilot.modules.audit.service import record_audit
from nichepilot.modules.discovery import dedup, ranking, report, weights
from nichepilot.modules.discovery import evaluation as evaluation_svc
from nichepilot.modules.discovery.schemas import DiscoveryRunParams
from nichepilot.modules.discovery.service import (
    create_run_record,
    get_run,
    get_run_by_job,
    list_runs,
    niche_detail,
    record_decision,
)
from nichepilot.modules.discovery.sources.policy import PolicyCreate, PolicyUpdate, SourcePolicyService
from nichepilot.modules.discovery.sources.searxng_config import write_settings
from nichepilot.modules.settings.service import get_setting_values

router = APIRouter(tags=["discovery"])
log = get_logger(__name__)


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


# ---------------------------------------------------------------------------------------------------------------------
# US1 – lượt khám phá (T055/T066; FR-001…FR-004, FR-006e, FR-026)
# ---------------------------------------------------------------------------------------------------------------------
class DiscoveryRunCreate(BaseModel):
    """Không có trường chọn nguồn chưa xác minh (A1) – trường lạ → 422."""

    model_config = ConfigDict(extra="forbid")
    market: str = Field(pattern=r"^[A-Z]{2}$")
    research_language: str = Field(default="en", pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
    seed_topic: str | None = Field(default=None, max_length=200)
    max_candidates: int = Field(default=20, ge=1, le=50)
    budget_usd: Decimal = Field(default=Decimal("2.00"), gt=0, max_digits=14, decimal_places=6)
    time_limit_minutes: int = Field(default=90, ge=5, le=240)
    page_limit: int = Field(default=300, ge=10, le=2000)
    per_domain_interval_s: float = Field(default=2.0, ge=1)


@router.post("/discovery/runs", status_code=status.HTTP_201_CREATED, dependencies=[LedgerGate])
async def create_discovery_run(
    body: DiscoveryRunCreate,
    request: Request,
    response: Response,
    user: UserDep,
    session: SessionDep,
    settings: SettingsDep,
    meta: MetaDep,
    ds: DiscoveryDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=128)] = None,
) -> dict[str, Any]:
    if not await budget_configured(session):
        raise AppError("BUDGET_NOT_CONFIGURED")
    daily = Decimal(str((await get_setting_values(session, ["budget.daily_usd"]))["budget.daily_usd"]))
    if body.budget_usd > daily:
        raise AppError("RUN_BUDGET_EXCEEDS_DAILY_LIMIT")
    usable = await SourcePolicyService(session).usable_for_run()
    if not usable:  # FR-006e: chỉ nguồn ALLOWED đang bật; từ chối sớm – không job, không lời gọi AI
        raise AppError("NO_COMPLIANT_SEARCH_SOURCE")
    params = DiscoveryRunParams(
        market=body.market,
        research_language=body.research_language,
        seed_topic=body.seed_topic,
        max_candidates=body.max_candidates,
        time_limit_s=body.time_limit_minutes * 60,
        page_limit=body.page_limit,
        per_domain_interval_s=body.per_domain_interval_s,
    ).model_dump(exclude_none=True)
    job = await create_job(  # tái dùng E0: idempotency, audit job.created, xếp hàng sau commit
        CreateJobRequest(
            job_type="discovery.run",
            params=params,
            idempotency_key=f"discovery:{idempotency_key}" if idempotency_key else None,
            budget_limit_usd=body.budget_usd,
        ),
        request,
        response,
        user,
        session,
        settings,
        meta,
    )
    job_id = uuid.UUID(job["id"])
    async with ds.sessionmaker() as s, s.begin():
        await create_run_record(s, job_id=job_id, params=params, usable=usable, source_mode=ds.backends.data_origin)
        run = await get_run_by_job(s, job_id)
    assert run is not None
    return run


@router.get("/discovery/runs", dependencies=[LedgerGate])
async def list_discovery_runs(
    _user: UserDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    include_mock: bool = True,
) -> dict[str, Any]:
    return {"items": await list_runs(session, limit=limit, include_mock=include_mock), "next_cursor": None}


@router.get("/discovery/runs/{run_id}", dependencies=[LedgerGate])
async def get_discovery_run(run_id: uuid.UUID, _user: UserDep, session: SessionDep) -> dict[str, Any]:
    run = await get_run(session, run_id)
    if run is None:
        raise AppError("DISCOVERY_RUN_NOT_FOUND")
    return run


# ---------------------------------------------------------------------------------------------------------------------
# US2 – chi tiết ngách + xóa bằng chứng (T083; FR-013e, FR-023)
# ---------------------------------------------------------------------------------------------------------------------
@router.get("/niches", dependencies=[LedgerGate])
async def list_niches(
    _user: UserDep,
    session: SessionDep,
    list_: Annotated[ranking.ListName, Query(alias="list")] = "research",
    run_id: uuid.UUID | None = None,
    country: Annotated[str | None, Query(pattern=r"^[A-Z]{2}$")] = None,
    decision_status: Annotated[list[str] | None, Query()] = None,
    include_mock: bool = False,
    sort: ranking.SortName | None = None,
    min_opportunity: Annotated[float | None, Query(ge=0, le=100)] = None,
    min_confidence: Annotated[float | None, Query(ge=0, le=100)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    cursor: Annotated[str | None, Query(pattern=r"^[0-9]{1,9}$")] = None,
) -> dict[str, Any]:
    items, nxt = await ranking.list_niches(
        session,
        list_name=list_,
        run_id=run_id,
        country=country,
        decision_status=decision_status,
        include_mock=include_mock,
        sort=sort,
        limit=limit,
        offset=int(cursor or 0),
        min_opportunity=min_opportunity,
        min_confidence=min_confidence,
    )
    return {
        "items": items,
        "next_cursor": str(nxt) if nxt is not None else None,
        "disclaimer_key": ranking.DISCLAIMER_KEY,
    }


@router.get("/niches/{niche_id}/evaluations", dependencies=[LedgerGate])
async def niche_evaluations(niche_id: uuid.UUID, _user: UserDep, session: SessionDep) -> list[dict[str, Any]]:
    if (await niche_detail(session, niche_id)) is None:
        raise AppError("NICHE_NOT_FOUND")
    return await evaluation_svc.list_evaluations(session, niche_id)


@router.get("/scoring/weights")
async def list_weights(_user: UserDep, session: SessionDep) -> list[dict[str, Any]]:
    return await weights.list_versions(session)


class WeightsCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    weights: dict[str, float]
    coverage_threshold: float | None = Field(default=None, gt=0, le=100)
    recompute_existing: bool = False


@router.post("/scoring/weights", status_code=status.HTTP_201_CREATED)
async def create_weights(
    body: WeightsCreate,
    request: Request,
    response: Response,
    user: UserDep,
    session: SessionDep,
    settings: SettingsDep,
    meta: MetaDep,
) -> dict[str, Any]:
    version = await weights.create_version(
        session,
        weights=body.weights,
        coverage_threshold=body.coverage_threshold,
        actor_id=user.id,
        request_id=meta.request_id,
    )
    if body.recompute_existing:
        ids = [
            str(r[0])
            for r in (
                await session.execute(text("SELECT id FROM niches WHERE merged_into_id IS NULL ORDER BY id"))
            ).all()
        ]
        jobs = []
        for i in range(0, len(ids), 500):  # tính lại theo phiên bản mới – job không AI (FR-018), tối đa 500 ngách/job
            job = await create_job(
                CreateJobRequest(
                    job_type="discovery.recompute",
                    params={"niche_ids": ids[i : i + 500], "reason": "WEIGHTS_CHANGED"},
                    idempotency_key=f"recompute:weights:{version['id']}:{i // 500}",
                ),
                request,
                response,
                user,
                session,
                settings,
                meta,
            )
            jobs.append({"job_id": job["id"], "job_type": job["job_type"], "status": job["status"]})
        version["recompute_jobs"] = jobs
    response.status_code = status.HTTP_201_CREATED
    return version


@router.get("/niches/{niche_id}", dependencies=[LedgerGate])
async def get_niche(niche_id: uuid.UUID, _user: UserDep, session: SessionDep) -> dict[str, Any]:
    detail = await niche_detail(session, niche_id)
    if detail is None:
        raise AppError("NICHE_NOT_FOUND")
    return detail


class EraseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=3, max_length=500)
    scope: Literal["EVIDENCE", "SOURCE"] = "EVIDENCE"


@router.post("/evidence/{evidence_id}/erase", status_code=status.HTTP_202_ACCEPTED, dependencies=[LedgerGate])
async def erase_evidence(
    evidence_id: uuid.UUID,
    body: EraseRequest,
    request: Request,
    response: Response,
    user: UserDep,
    session: SessionDep,
    settings: SettingsDep,
    meta: MetaDep,
    ds: DiscoveryDep,
) -> dict[str, Any]:
    result = await ds.erase(
        evidence_id, scope=body.scope, reason=body.reason, actor_id=user.id, request_id=meta.request_id
    )
    recompute: dict[str, Any] | None = None
    if result.affected_niche_ids:
        # ngách đã được tính lại đồng bộ trong transaction xóa; job `discovery.recompute` (0 lời gọi AI) tái dùng
        # đường tạo job
        # của E0 (audit, idempotency, hàng đợi). Không tạo được job → không ảnh hưởng việc xóa đã hoàn tất.
        try:
            job = await create_job(
                CreateJobRequest(
                    job_type="discovery.recompute",
                    params={"niche_ids": [str(n) for n in result.affected_niche_ids], "reason": "EVIDENCE_ERASED"},
                    idempotency_key=f"recompute:erasure:{result.erasure_id}",
                ),
                request,
                response,
                user,
                session,
                settings,
                meta,
            )
            recompute = {"job_id": job["id"], "job_type": job["job_type"], "status": job["status"]}
        except AppError as exc:
            log.warning("discovery.recompute_not_queued", code=exc.code)
    response.status_code = status.HTTP_202_ACCEPTED
    return {
        "erasure_id": str(result.erasure_id),
        "affected_niche_ids": [str(n) for n in result.affected_niche_ids],
        "recompute_job": recompute,
    }


# ---------------------------------------------------------------------------------------------------------------------
# US4 – hồ sơ tuân thủ nguồn (T109; FR-006c, FR-006d, FR-006g, FR-036). Chỉ ALLOWED mới bật được; không có cờ xác
# nhận cảnh báo.
# ---------------------------------------------------------------------------------------------------------------------
SOURCE_FIELDS = (
    "source_key",
    "display_name",
    "adapter_type",
    "config",
    "tos_url",
    "verified_at",
    "verification_note",
    "allowed_access_methods",
    "permitted_use_scope",
    "compliance_status",
    "known_limits",
    "enabled",
)


def source_dto(row: dict[str, Any], *, requires_service_restart: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {"id": str(row["id"])}
    for k in SOURCE_FIELDS:
        v: Any = row.get(k)
        out[k] = (
            v.isoformat()
            if v is not None and hasattr(v, "isoformat")
            else (list(v) if isinstance(v, tuple | list) else v)
        )
    out["verified_by"] = str(row["verified_by"]) if row.get("verified_by") else None
    out["usable"] = bool(row["enabled"]) and row["compliance_status"] == "ALLOWED"
    out["requires_service_restart"] = requires_service_restart
    return out


async def _regenerate_searxng(session: Any, ds: DiscoveryServices) -> bool:
    """Sinh lại settings.yml của SearXNG từ nguồn searxng_engine ALLOWED đang bật; True nếu đổi (cần khởi động lại
    `searxng`)."""
    engines = [
        str(r[0])
        for r in (
            await session.execute(
                text(
                    "SELECT config->>'engine_name' FROM source_policies WHERE adapter_type = 'searxng_engine' AND"
                    " enabled"
                    " AND compliance_status = 'ALLOWED' AND config ? 'engine_name'"
                )
            )
        ).all()
    ]
    try:
        return write_settings(ds.settings.searxng_config_dir, ds.settings.searxng_base_settings, engines)
    except OSError as exc:  # volume không ghi được: không chặn cập nhật hồ sơ nguồn, nhưng báo rõ để chủ sở hữu xử lý
        log.error("searxng.settings_write_failed", error=type(exc).__name__)
        raise AppError("SERVICE_UNAVAILABLE") from None


@router.get("/sources")
async def list_sources(_user: UserDep, session: SessionDep) -> list[dict[str, Any]]:
    return [source_dto(r) for r in await SourcePolicyService(session).list_policies()]


@router.post("/sources", status_code=status.HTTP_201_CREATED)
async def create_source(body: PolicyCreate, user: UserDep, session: SessionDep, meta: MetaDep) -> dict[str, Any]:
    row = await SourcePolicyService(session).create_policy(user.id, body, request_id=meta.request_id)
    return source_dto(row)  # luôn UNVERIFIED + tắt


@router.put("/sources/{source_id}")
async def update_source(
    source_id: uuid.UUID, body: PolicyUpdate, user: UserDep, session: SessionDep, meta: MetaDep, ds: DiscoveryDep
) -> dict[str, Any]:
    svc = SourcePolicyService(session)
    if await svc.get(source_id) is None:
        raise AppError("SOURCE_NOT_FOUND")
    row = await svc.update_policy(user.id, source_id, body, request_id=meta.request_id)
    restart = False
    if row["adapter_type"] == "searxng_engine":
        restart = await _regenerate_searxng(session, ds)
    return source_dto(row, requires_service_restart=restart)


# ---------------------------------------------------------------------------------------------------------------------
# US5 – ngách có thể tương đồng (T114; FR-022). Chủ sở hữu quyết định gộp; AI không tự gộp.
# ---------------------------------------------------------------------------------------------------------------------
@router.get("/niche-similarities", dependencies=[LedgerGate])
async def list_similarities(
    _user: UserDep,
    session: SessionDep,
    status_: Annotated[Literal["POSSIBLE", "CONFIRMED_DUPLICATE", "NOT_DUPLICATE"], Query(alias="status")] = "POSSIBLE",
    niche_id: uuid.UUID | None = None,
) -> list[dict[str, Any]]:
    return await dedup.list_similarities(session, status=status_, niche_id=niche_id)


class SimilarityResolve(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["CONFIRMED_DUPLICATE", "NOT_DUPLICATE"]
    keep_niche_id: uuid.UUID | None = None


@router.put("/niche-similarities/{similarity_id}", dependencies=[LedgerGate])
async def resolve_similarity(
    similarity_id: uuid.UUID, body: SimilarityResolve, user: UserDep, session: SessionDep, meta: MetaDep
) -> dict[str, Any]:
    row = (
        (await session.execute(text("SELECT * FROM niche_similarity WHERE id = :i FOR UPDATE"), {"i": similarity_id}))
        .mappings()
        .first()
    )
    if row is None:
        raise AppError("SIMILARITY_NOT_FOUND")
    if row["status"] != "POSSIBLE":
        raise AppError("SIMILARITY_ALREADY_RESOLVED")
    pair = {row["niche_a_id"], row["niche_b_id"]}
    merged: uuid.UUID | None = None
    if body.status == "CONFIRMED_DUPLICATE":
        if body.keep_niche_id not in pair:
            raise AppError("VALIDATION_ERROR", errors=[{"field": "keep_niche_id", "code": "not_in_pair"}])
        merged = next(n for n in pair if n != body.keep_niche_id)
        await session.execute(  # ngách bị gộp ẩn khỏi xếp hạng; bằng chứng/đánh giá cũ vẫn giữ để truy vết
            text("UPDATE niches SET merged_into_id = :k, updated_at = now() WHERE id = :m"),
            {"k": body.keep_niche_id, "m": merged},
        )
        await session.execute(
            text(
                "INSERT INTO niche_run_links (niche_id, run_id, role) SELECT :k, run_id, role FROM niche_run_links"
                " WHERE niche_id = :m ON CONFLICT (niche_id, run_id) DO NOTHING"
            ),
            {"k": body.keep_niche_id, "m": merged},
        )
    updated = (
        (
            await session.execute(
                text(
                    "UPDATE niche_similarity SET status = :s, resolved_by = :u, resolved_at = now(), updated_at = now()"
                    " WHERE id = :i RETURNING *"
                ),
                {"s": body.status, "u": user.id, "i": similarity_id},
            )
        )
        .mappings()
        .one()
    )
    await record_audit(
        session,
        action="niche.similarity_resolved",
        actor_type="USER",
        actor_id=user.id,
        entity_type="niche_similarity",
        entity_id=similarity_id,
        before={"status": "POSSIBLE"},
        after={
            "status": body.status,
            "keep_niche_id": str(body.keep_niche_id) if body.keep_niche_id else None,
            "merged_niche_id": str(merged) if merged else None,
        },
        request_id=meta.request_id,
    )
    return dedup.similarity_dto(dict(updated))


# ---------------------------------------------------------------------------------------------------------------------
# US6 – báo cáo theo lượt + quyết định chủ sở hữu (T117, T118; FR-024, FR-025)
# ---------------------------------------------------------------------------------------------------------------------
@router.get("/discovery/runs/{run_id}/report", dependencies=[LedgerGate], response_model=None)
async def run_report(
    run_id: uuid.UUID,
    _user: UserDep,
    session: SessionDep,
    format_: Annotated[Literal["json", "markdown"], Query(alias="format")] = "json",
    include_mock: bool = False,
    lang: Literal["vi", "en"] = "vi",
) -> dict[str, Any] | Response:
    data = await report.build_report(session, run_id, include_mock=include_mock)
    if data is None:
        raise AppError("DISCOVERY_RUN_NOT_FOUND")
    if format_ == "markdown":
        return Response(
            report.to_markdown(data, lang),
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="niche-report-{run_id}.md"'},
        )
    return data


class DecisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["CANDIDATE", "WATCH", "PURSUE", "REJECTED", "HIDDEN"]
    reason: str | None = Field(default=None, max_length=2000)


@router.put("/niches/{niche_id}/decision", dependencies=[LedgerGate])
async def niche_decision(
    niche_id: uuid.UUID, body: DecisionBody, user: UserDep, session: SessionDep, meta: MetaDep
) -> dict[str, Any]:
    reason = (body.reason or "").strip() or None
    if body.decision != "CANDIDATE" and (reason is None or len(reason) < 3):  # quyết định phải kèm lý do (FR-025)
        raise AppError("VALIDATION_ERROR", errors=[{"field": "reason", "code": "required"}])
    if not await record_decision(
        session, niche_id, decision=body.decision, reason=reason, actor_id=user.id, request_id=meta.request_id
    ):
        raise AppError("NICHE_NOT_FOUND")
    detail = await niche_detail(session, niche_id)
    assert detail is not None
    return detail


# ---------------------------------------------------------------------------------------------------------------------
# US7 – đánh giá lại ngách (T123; FR-034): job `discovery.reevaluate` qua đường tạo job E0 (giữ chỗ ngân sách khi gọi
# AI)
# ---------------------------------------------------------------------------------------------------------------------
@router.post("/niches/{niche_id}/reevaluate", status_code=status.HTTP_202_ACCEPTED, dependencies=[LedgerGate])
async def reevaluate_niche(
    niche_id: uuid.UUID,
    request: Request,
    response: Response,
    user: UserDep,
    session: SessionDep,
    settings: SettingsDep,
    meta: MetaDep,
) -> dict[str, Any]:
    niche = (
        await session.execute(text("SELECT country, merged_into_id FROM niches WHERE id = :n"), {"n": niche_id})
    ).first()
    if niche is None or niche.merged_into_id is not None:
        raise AppError("NICHE_NOT_FOUND")
    if not await budget_configured(session):
        raise AppError("BUDGET_NOT_CONFIGURED")
    if not await SourcePolicyService(session).usable_for_run():
        raise AppError("NO_COMPLIANT_SEARCH_SOURCE")
    job = await create_job(
        CreateJobRequest(job_type="discovery.reevaluate", params={"niche_id": str(niche_id), "market": niche.country}),
        request,
        response,
        user,
        session,
        settings,
        meta,
    )
    response.status_code = status.HTTP_202_ACCEPTED
    return {"job_id": job["id"], "job_type": job["job_type"], "status": job["status"]}
