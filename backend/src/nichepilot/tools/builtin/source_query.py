"""Tool `source.query` (FR-006, FR-006d, FR-006f, FR-012b; internal-interfaces §1).

- Chỉ nhận policy `ALLOWED` – mọi trạng thái khác bị từ chối trước khi có request nào (phòng thủ lớp 2, quyết định A1).
- Tiêu đề/đoạn trích được che PII TRONG handler: Tool Registry E0 lưu output vào `tool_executions`.
  Đoạn NEEDS_REVIEW/UNSAFE bị bỏ (None) – không lưu, không gửi AI.
"""

from __future__ import annotations

import asyncio
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from nichepilot.core.discovery_config import DiscoverySettings
from nichepilot.tools.privacy.pii import PROFILE_URL_RE, PiiEngine, select_pii_engine
from nichepilot.tools.registry import ToolContext, ToolDefinition
from nichepilot.tools.sources.base import PolicySnapshot, Sleep, SourceAdapter

TOOL_NAME = "source.query"


class SourceQueryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy: PolicySnapshot
    query: str = Field(min_length=1, max_length=300)
    market: str = Field(pattern=r"^[A-Z]{2}$")
    language: str = Field(pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
    max_results: int = Field(default=10, ge=1, le=30)


class SourceHitOut(BaseModel):
    url: str
    title: str | None
    snippet: str | None
    published_at: str | None
    redaction_status: Literal["REDACTED", "NEEDS_REVIEW", "UNSAFE"]


class SourceQueryOutput(BaseModel):
    source_key: str
    status: Literal["OK", "NO_RESULTS", "UNAVAILABLE", "RATE_LIMITED", "ACCESS_RESTRICTED"]
    reason: str | None
    data_origin: Literal["REAL", "MOCK"]
    hits: list[SourceHitOut]
    skipped_pii_urls: int = 0
    needs_review_segments: int = 0


def build_source_query_tool(
    settings: DiscoverySettings,
    *,
    adapters: dict[str, SourceAdapter],
    pii: PiiEngine | None = None,
    sleep: Sleep = asyncio.sleep,
) -> ToolDefinition:
    engine = pii or select_pii_engine(settings)

    def _clean(text: str | None, language: str, market: str) -> tuple[str | None, str]:
        if not text:
            return None, "REDACTED"
        r = engine.redact(text, language=language.split("-")[0], country=market)
        return (str(r.text) if r.status == "REDACTED" else None), r.status

    async def handler(inp: BaseModel, ctx: ToolContext) -> BaseModel:
        assert isinstance(inp, SourceQueryInput)
        policy = inp.policy
        if policy.compliance_status != "ALLOWED":
            raise PermissionError(f"SOURCE_NOT_ALLOWED: {policy.source_key} ({policy.compliance_status})")
        adapter = adapters.get(policy.adapter_type)
        if adapter is None:
            return SourceQueryOutput(
                source_key=policy.source_key,
                status="UNAVAILABLE",
                reason="ADAPTER_MISSING",
                data_origin="REAL",
                hits=[],
            )
        result = await adapter.query(
            policy, inp.query, market=inp.market, language=inp.language, max_results=inp.max_results
        )
        hits: list[SourceHitOut] = []
        needs_review = 0
        skipped_pii_urls = 0
        for h in result.hits:
            # FR-012c: URL hồ sơ cá nhân / URL chứa PII không được trả ra (output tool được lưu vào tool_executions)
            url_clean, url_status = _clean(h.url, inp.language, inp.market)
            if PROFILE_URL_RE.match(h.url) or url_clean != h.url or url_status != "REDACTED":
                skipped_pii_urls += 1
                continue
            title, t_status = _clean(h.title, inp.language, inp.market)
            snippet, s_status = _clean(h.snippet, inp.language, inp.market)
            worst = max((t_status, s_status), key=("REDACTED", "NEEDS_REVIEW", "UNSAFE").index)
            needs_review += worst != "REDACTED"
            hits.append(
                SourceHitOut(
                    url=h.url, title=title, snippet=snippet, published_at=h.published_at, redaction_status=worst
                )
            )
        return SourceQueryOutput(
            source_key=policy.source_key,
            status=result.status,
            reason=result.reason,
            data_origin=adapter.data_origin,
            hits=hits,
            needs_review_segments=needs_review,
            skipped_pii_urls=skipped_pii_urls,
        )

    return ToolDefinition(
        name=TOOL_NAME,
        version="1",
        description="Query one ALLOWED data source (SearXNG engine or official API) and return redacted hits.",
        input_model=SourceQueryInput,
        output_model=SourceQueryOutput,
        handler=handler,
        timeout_s=120,
    )
