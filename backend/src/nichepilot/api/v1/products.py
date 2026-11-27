"""Router E2 – Product & Affiliate Discovery (specs/003-product-affiliate-discovery/contracts/openapi.yaml).

Endpoint dữ liệu nghiên cứu dùng cổng erasure ledger của E1 (503 `ERASURE_LEDGER_NOT_APPLIED`). Không có endpoint đăng
ký affiliate,
chấp nhận điều khoản, đăng nhập mạng affiliate hay tạo link (FR-025).
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, Request, Response, status
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from nichepilot.api.deps import MetaDep, SessionDep, SettingsDep, UserDep
from nichepilot.api.v1.discovery import DiscoveryDep, LedgerGate
from nichepilot.api.v1.jobs import CreateJobRequest, create_job
from nichepilot.core.errors import AppError
from nichepilot.jobs.scheduler import budget_configured
from nichepilot.modules.audit.service import record_audit
from nichepilot.modules.discovery.sources.policy import SourcePolicyService
from nichepilot.modules.products import report, service, store
from nichepilot.modules.products import weights as weights_mod
from nichepilot.modules.products.schemas import ProductRunParams

router = APIRouter(tags=["products"])


class ProductRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    niche_id: uuid.UUID
    max_products: int = Field(default=10, ge=1, le=20)
    page_limit: int = Field(default=60, ge=5, le=200)
    time_limit_s: int = Field(default=1800, ge=60, le=5400)


@router.post("/product-runs", status_code=status.HTTP_202_ACCEPTED, dependencies=[LedgerGate])
async def create_product_run(
    body: ProductRunCreate,
    request: Request,
    response: Response,
    user: UserDep,
    session: SessionDep,
    settings: SettingsDep,
    meta: MetaDep,
    ds: DiscoveryDep,
) -> dict[str, Any]:
    await service.ensure_can_start(session, body.niche_id)  # FR-001 (ngách đủ điều kiện), 1 lượt hoạt động/ngách
    if not await budget_configured(session):
        raise AppError("BUDGET_NOT_CONFIGURED")  # FR-004
    if not await SourcePolicyService(session).usable_for_run():
        raise AppError("NO_COMPLIANT_SEARCH_SOURCE")  # FR-006: chỉ nguồn ALLOWED – không job, không AI
    params = ProductRunParams(
        niche_id=str(body.niche_id),
        max_products=body.max_products,
        page_limit=body.page_limit,
        time_limit_s=body.time_limit_s,
    ).model_dump(exclude_none=True)
    job = await create_job(
        CreateJobRequest(job_type="products.run", params=params), request, response, user, session, settings, meta
    )
    job_id = uuid.UUID(job["id"])
    async with ds.sessionmaker() as s, s.begin():
        run_id = await store.ensure_run(
            s, job_id=job_id, niche_id=body.niche_id, params=params, origin=ds.backends.data_origin
        )
        await record_audit(
            s,
            action="product.run_created",
            actor_type="USER",
            actor_id=user.id,
            entity_type="product_run",
            entity_id=run_id,
            after={"niche_id": str(body.niche_id), "job_id": str(job_id)},
            request_id=meta.request_id,
        )
    return {"job_id": str(job_id), "run_id": str(run_id)}


@router.get("/product-runs", dependencies=[LedgerGate])
async def list_product_runs(
    _user: UserDep, session: SessionDep, niche_id: uuid.UUID | None = None, include_mock: bool = False
) -> dict[str, Any]:
    return {"items": await service.list_runs(session, niche_id=niche_id, include_mock=include_mock)}


@router.get("/product-runs/{run_id}", dependencies=[LedgerGate])
async def get_product_run(run_id: uuid.UUID, _user: UserDep, session: SessionDep) -> dict[str, Any]:
    return await service.get_run(session, run_id)


@router.get("/niches/{niche_id}/products", dependencies=[LedgerGate])
async def niche_products(
    niche_id: uuid.UUID,
    _user: UserDep,
    session: SessionDep,
    list_name: Annotated[Literal["ranked", "needs_research"], Query(alias="list")] = "ranked",
    include_mock: bool = False,
) -> dict[str, Any]:
    return {"items": await service.list_products(session, niche_id, list_name=list_name, include_mock=include_mock)}


@router.get("/niches/{niche_id}/product-summary", dependencies=[LedgerGate])
async def niche_product_summary(
    niche_id: uuid.UUID, _user: UserDep, session: SessionDep, include_mock: bool = False
) -> dict[str, Any]:
    return await service.niche_summary(session, niche_id, include_mock=include_mock)


@router.get("/niches/{niche_id}/product-report", dependencies=[LedgerGate], response_model=None)
async def niche_product_report(
    niche_id: uuid.UUID,
    _user: UserDep,
    session: SessionDep,
    format: Literal["json", "markdown"] = "json",
    lang: Literal["vi", "en"] = "vi",
    include_mock: bool = False,
) -> dict[str, Any] | PlainTextResponse:
    data = await report.build_report(session, niche_id, include_mock=include_mock)
    if format == "markdown":
        return PlainTextResponse(report.to_markdown(data, lang), media_type="text/markdown; charset=utf-8")
    return data


@router.get("/products/{product_id}", dependencies=[LedgerGate])
async def get_product(
    product_id: uuid.UUID, niche_id: uuid.UUID, _user: UserDep, session: SessionDep
) -> dict[str, Any]:
    return await service.product_detail(session, product_id, niche_id)


class ProductDecisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    niche_id: uuid.UUID
    decision: Literal["SELECTED", "WATCH", "REJECTED"]
    reason: str = Field(min_length=1, max_length=1000)


@router.post("/products/{product_id}/decision", dependencies=[LedgerGate])
async def product_decision(
    product_id: uuid.UUID, body: ProductDecisionBody, user: UserDep, session: SessionDep, meta: MetaDep
) -> dict[str, Any]:
    await service.record_decision(
        session,
        product_id,
        body.niche_id,
        decision=body.decision,
        reason=body.reason,
        actor_id=user.id,
        request_id=meta.request_id,
    )
    return await service.product_detail(session, product_id, body.niche_id)


@router.get("/affiliate-programs/{program_id}", dependencies=[LedgerGate])
async def get_program(program_id: uuid.UUID, _user: UserDep, session: SessionDep) -> dict[str, Any]:
    return await service.program_detail(session, program_id)


class WatchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


@router.put("/affiliate-programs/{program_id}/watch", dependencies=[LedgerGate])
async def watch_program(
    program_id: uuid.UUID, body: WatchBody, user: UserDep, session: SessionDep, meta: MetaDep
) -> dict[str, Any]:
    await service.set_watch(session, program_id, enabled=body.enabled, actor_id=user.id, request_id=meta.request_id)
    return await service.program_detail(session, program_id)


@router.post("/affiliate-programs/{program_id}/terms-versions/{version}/acknowledge", dependencies=[LedgerGate])
async def acknowledge_terms(
    program_id: uuid.UUID, version: int, user: UserDep, session: SessionDep, meta: MetaDep
) -> dict[str, Any]:
    await service.acknowledge(session, program_id, version, actor_id=user.id, request_id=meta.request_id)
    return await service.program_detail(session, program_id)


def _weights_json(w: weights_mod.WeightsVersion) -> dict[str, Any]:
    return {
        "id": str(w.id),
        "version": w.version,
        "weights": w.weights,
        "coverage_min": float(w.coverage_min),
        "rubric": w.rubric,
    }


@router.get("/product-scoring/weights")
async def get_product_weights(_user: UserDep, session: SessionDep) -> dict[str, Any]:
    active = await weights_mod.active(session)
    return {"active": _weights_json(active), "history": [_weights_json(w) for w in await weights_mod.history(session)]}


class WeightsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    weights: dict[str, float]
    coverage_min: float | None = None


@router.post("/product-scoring/weights", status_code=status.HTTP_201_CREATED)
async def create_product_weights(
    body: WeightsBody,
    request: Request,
    response: Response,
    user: UserDep,
    session: SessionDep,
    settings: SettingsDep,
    meta: MetaDep,
) -> dict[str, Any]:
    before = await weights_mod.active(session)
    w = await weights_mod.create_version(session, body.weights, coverage_min=body.coverage_min, actor_id=user.id)
    await record_audit(
        session,
        action="product.weights_created",
        actor_type="USER",
        actor_id=user.id,
        entity_type="product_scoring_weights",
        entity_id=w.id,
        before={"version": before.version, "weights": before.weights},
        after={"version": w.version, "weights": w.weights, "coverage_min": float(w.coverage_min)},
        request_id=meta.request_id,
    )
    job = await create_job(  # tính lại điểm (không AI) theo phiên bản mới
        CreateJobRequest(job_type="products.recompute", params={}), request, response, user, session, settings, meta
    )
    return {**_weights_json(w), "recompute_job_id": job["id"]}
