"""Router E3 – Keyword & Audience Research (specs/004-keyword-audience-research/contracts/openapi.yaml).

Endpoint dữ liệu nghiên cứu dùng cổng erasure ledger E1 (503 `ERASURE_LEDGER_NOT_APPLIED`). Lượt vẫn được tạo khi chưa
có nguồn
`ALLOWED` (Clarification (b)): keyword sinh từ dữ liệu nội bộ, bước SERP bị bỏ qua với `NO_COMPLIANT_SEARCH_SOURCE`.
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
from nichepilot.modules.keywords import report, service, store
from nichepilot.modules.keywords import weights as weights_mod
from nichepilot.modules.keywords.schemas import KeywordRunParams

router = APIRouter(tags=["keywords"])
IntentQ = Literal["INFORMATIONAL", "COMMERCIAL_INVESTIGATION", "TRANSACTIONAL", "NAVIGATIONAL"]


class KeywordRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    niche_id: uuid.UUID
    max_keywords: int = Field(default=60, ge=5, le=200)
    serp_keywords: int = Field(default=10, ge=0, le=30)
    competitor_pages: int = Field(default=3, ge=0, le=5)
    page_limit: int = Field(default=60, ge=5, le=200)
    time_limit_s: int = Field(default=1800, ge=60, le=5400)


@router.post("/keyword-runs", status_code=status.HTTP_202_ACCEPTED, dependencies=[LedgerGate])
async def create_keyword_run(
    body: KeywordRunCreate,
    request: Request,
    response: Response,
    user: UserDep,
    session: SessionDep,
    settings: SettingsDep,
    meta: MetaDep,
    ds: DiscoveryDep,
) -> dict[str, Any]:
    await service.ensure_can_start(session, body.niche_id)
    if not await budget_configured(session):
        raise AppError("BUDGET_NOT_CONFIGURED")
    params = KeywordRunParams(
        niche_id=str(body.niche_id),
        max_keywords=body.max_keywords,
        serp_keywords=body.serp_keywords,
        competitor_pages=body.competitor_pages,
        page_limit=body.page_limit,
        time_limit_s=body.time_limit_s,
    ).model_dump(exclude_none=True)
    job = await create_job(
        CreateJobRequest(job_type="keywords.run", params=params), request, response, user, session, settings, meta
    )
    job_id = uuid.UUID(job["id"])
    async with ds.sessionmaker() as s, s.begin():
        run_id = await store.ensure_run(
            s, job_id=job_id, niche_id=body.niche_id, params=params, origin=ds.backends.data_origin
        )
        await record_audit(
            s,
            action="keyword.run_created",
            actor_type="USER",
            actor_id=user.id,
            entity_type="keyword_run",
            entity_id=run_id,
            after={"niche_id": str(body.niche_id), "job_id": str(job_id)},
            request_id=meta.request_id,
        )
    return {"job_id": str(job_id), "run_id": str(run_id)}


@router.get("/keyword-runs", dependencies=[LedgerGate])
async def list_keyword_runs(
    _user: UserDep, session: SessionDep, niche_id: uuid.UUID | None = None, include_mock: bool = False
) -> dict[str, Any]:
    return {"items": await service.list_runs(session, niche_id=niche_id, include_mock=include_mock)}


@router.get("/keyword-runs/{run_id}", dependencies=[LedgerGate])
async def get_keyword_run(run_id: uuid.UUID, _user: UserDep, session: SessionDep) -> dict[str, Any]:
    return await service.get_run(session, run_id)


@router.get("/niches/{niche_id}/keyword-clusters", dependencies=[LedgerGate])
async def niche_keyword_clusters(
    niche_id: uuid.UUID,
    _user: UserDep,
    session: SessionDep,
    list_name: Annotated[Literal["ranked", "needs_research"], Query(alias="list")] = "ranked",
    intent: IntentQ | None = None,
    include_mock: bool = False,
) -> dict[str, Any]:
    items = await service.list_clusters(
        session, niche_id, list_name=list_name, intent=intent, include_mock=include_mock
    )
    return {"items": items, "disclaimer_key": service.DISCLAIMER_KEY}


@router.get("/niches/{niche_id}/keyword-summary", dependencies=[LedgerGate])
async def niche_keyword_summary(
    niche_id: uuid.UUID, _user: UserDep, session: SessionDep, include_mock: bool = False
) -> dict[str, Any]:
    return await service.niche_summary(session, niche_id, include_mock=include_mock)


@router.get("/niches/{niche_id}/keyword-report", dependencies=[LedgerGate], response_model=None)
async def niche_keyword_report(
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


@router.get("/keyword-clusters/{cluster_id}", dependencies=[LedgerGate])
async def get_keyword_cluster(cluster_id: uuid.UUID, _user: UserDep, session: SessionDep) -> dict[str, Any]:
    return await service.cluster_detail(session, cluster_id)


class DecisionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["SELECTED", "WATCH", "REJECTED"]
    reason: str = Field(min_length=1, max_length=1000)


@router.post("/keyword-clusters/{cluster_id}/decision", dependencies=[LedgerGate])
async def keyword_cluster_decision(
    cluster_id: uuid.UUID, body: DecisionBody, user: UserDep, session: SessionDep, meta: MetaDep
) -> dict[str, Any]:
    await service.record_decision(
        session, cluster_id, decision=body.decision, reason=body.reason, actor_id=user.id, request_id=meta.request_id
    )
    return await service.cluster_detail(session, cluster_id)


class WatchBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool


@router.put("/keyword-clusters/{cluster_id}/watch", dependencies=[LedgerGate])
async def watch_keyword_cluster(
    cluster_id: uuid.UUID, body: WatchBody, user: UserDep, session: SessionDep, meta: MetaDep
) -> dict[str, Any]:
    await service.set_watch(session, cluster_id, enabled=body.enabled, actor_id=user.id, request_id=meta.request_id)
    return await service.cluster_detail(session, cluster_id)


@router.post("/keyword-clusters/{cluster_id}/serp-versions/{version}/acknowledge", dependencies=[LedgerGate])
async def acknowledge_serp(
    cluster_id: uuid.UUID, version: int, user: UserDep, session: SessionDep, meta: MetaDep
) -> dict[str, Any]:
    await service.acknowledge(session, cluster_id, version, actor_id=user.id, request_id=meta.request_id)
    return await service.cluster_detail(session, cluster_id)


def _weights_json(w: weights_mod.WeightsVersion) -> dict[str, Any]:
    return {
        "id": str(w.id),
        "version": w.version,
        "weights": w.weights,
        "coverage_min": float(w.coverage_min),
        "rubric": w.rubric,
    }


@router.get("/keyword-scoring/weights")
async def get_keyword_weights(_user: UserDep, session: SessionDep) -> dict[str, Any]:
    active = await weights_mod.active(session)
    return {"active": _weights_json(active), "history": [_weights_json(w) for w in await weights_mod.history(session)]}


class WeightsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    weights: dict[str, float]
    coverage_min: float | None = None


@router.post("/keyword-scoring/weights", status_code=status.HTTP_201_CREATED)
async def create_keyword_weights(
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
        action="keyword.weights_created",
        actor_type="USER",
        actor_id=user.id,
        entity_type="keyword_scoring_weights",
        entity_id=w.id,
        before={"version": before.version, "weights": before.weights},
        after={"version": w.version, "weights": w.weights, "coverage_min": float(w.coverage_min)},
        request_id=meta.request_id,
    )
    job = await create_job(  # tính lại điểm keyword (không AI) theo phiên bản mới
        CreateJobRequest(job_type="keywords.recompute", params={}), request, response, user, session, settings, meta
    )
    return {**_weights_json(w), "recompute_job_id": job["id"]}
