"""Tool `page.fetch` (FR-005, FR-012a, FR-012b, FR-031; research R-03, R-05; internal-interfaces §2).

Tải trang (fetcher mặc định httpx – không trình duyệt), trích nội dung chính bằng trafilatura (bỏ metadata tác giả)
và CHE PII
TRONG handler. Văn bản thô chỉ là biến cục bộ: output (được Tool Registry E0 lưu vào `tool_executions`) chỉ chứa đoạn
`REDACTED`; đoạn NEEDS_REVIEW/UNSAFE bị bỏ, chỉ đếm số lượng (FR-032 `needs_review_segments`).
Robots/khoảng cách tên miền do agent kiểm tra TRƯỚC khi gọi tool này.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal

import trafilatura
from pydantic import BaseModel, ConfigDict, Field

from nichepilot.core.discovery_config import DiscoverySettings
from nichepilot.tools.fetchers.http_fetcher import PageFetcher
from nichepilot.tools.privacy.pii import PROFILE_URL_RE, PiiEngine, select_pii_engine
from nichepilot.tools.registry import ToolContext, ToolDefinition
from nichepilot.tools.sources.searxng_engine import looks_like_challenge

TOOL_NAME = "page.fetch"
MAX_SEGMENT_CHARS = 1000  # BR-09 / research_evidence.excerpt ≤ 1000
MAX_TOTAL_CHARS = 20000
LOGIN_FORM_RE = re.compile(r"<input[^>]+type=[\"']?password", re.IGNORECASE)


class PageFetchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str = Field(pattern=r"^https?://", max_length=2000)
    language: str = Field(pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
    country: str = Field(pattern=r"^[A-Z]{2}$")


class Segment(BaseModel):
    text: str
    redaction_status: Literal["REDACTED"]


class PageFetchOutput(BaseModel):
    status: Literal["SUCCESS", "FAILED", "SKIPPED"]
    reason: str | None
    http_status: int | None
    final_url: str | None
    retry_after_s: float | None = None
    title: str | None = None
    published_at: str | None = None
    segments: list[Segment] = Field(default_factory=list)
    needs_review_segments: int = 0
    unsafe_segments: int = 0
    redaction_counts: dict[str, int] = Field(default_factory=dict)
    pii_engine: str | None = None
    content_hash: str | None = None
    data_origin: Literal["REAL", "MOCK"] = "REAL"


def _split_segments(text: str) -> list[str]:
    parts: list[str] = []
    for para in (p.strip() for p in text.split("\n")):
        while len(para) > MAX_SEGMENT_CHARS:
            cut = para.rfind(". ", 0, MAX_SEGMENT_CHARS)
            cut = cut + 1 if cut > 200 else MAX_SEGMENT_CHARS
            parts.append(para[:cut].strip())
            para = para[cut:].strip()
        if para:
            parts.append(para)
    return parts


def build_page_fetch_tool(
    settings: DiscoverySettings, *, fetcher: PageFetcher, pii: PiiEngine | None = None
) -> ToolDefinition:
    engine = pii or select_pii_engine(settings)

    async def handler(inp: BaseModel, ctx: ToolContext) -> BaseModel:
        assert isinstance(inp, PageFetchInput)
        origin = fetcher.data_origin
        raw = await fetcher.fetch(inp.url, timeout_s=settings.fetch_timeout_s)
        profile_redirect = bool(raw.final_url and PROFILE_URL_RE.match(raw.final_url))

        def out(status: Literal["SUCCESS", "FAILED", "SKIPPED"], reason: str | None, **kw: object) -> PageFetchOutput:
            return PageFetchOutput(
                status=status,
                reason=reason,
                http_status=raw.http_status,
                final_url=None if profile_redirect else raw.final_url,  # FR-012c: không lưu URL hồ sơ cá nhân
                retry_after_s=raw.retry_after_s,
                data_origin=origin,
                **kw,
            )

        if raw.error:
            return out("FAILED", raw.error)
        if profile_redirect:  # chuyển hướng tới trang hồ sơ cá nhân → không thu thập (FR-012c)
            return out("SKIPPED", "PII_UNSAFE")
        if raw.http_status in (429, 503):
            return out("SKIPPED", "RATE_LIMITED")
        body = raw.body or ""
        if raw.http_status in (401, 403) or looks_like_challenge(body):
            return out("SKIPPED", "ACCESS_RESTRICTED")  # không thử vượt CAPTCHA/đăng nhập (FR-005, FR-006f)
        if raw.http_status != 200:
            return out("FAILED", "HTTP_ERROR")
        if "html" not in (raw.content_type or "").lower():
            return out("SKIPPED", "NON_HTML")
        if LOGIN_FORM_RE.search(body):
            return out("SKIPPED", "ACCESS_RESTRICTED")
        extracted = trafilatura.extract(
            body, url=inp.url, output_format="json", with_metadata=True, include_comments=False, include_tables=False
        )
        if not extracted:
            return out("SKIPPED", "NON_HTML")
        doc = json.loads(extracted)  # có trường "author" – KHÔNG được dùng/lưu
        text = str(doc.get("text") or "")[:MAX_TOTAL_CHARS]
        lang = inp.language.split("-")[0]
        segments: list[Segment] = []
        counts: dict[str, int] = {}
        needs_review = unsafe = 0
        for part in _split_segments(text):
            r = engine.redact(part, language=lang, country=inp.country)
            for k, v in r.counts.items():
                counts[k] = counts.get(k, 0) + v
            if r.status == "REDACTED":
                segments.append(Segment(text=str(r.text), redaction_status="REDACTED"))
            elif r.status == "NEEDS_REVIEW":
                needs_review += 1
            else:
                unsafe += 1
        title = None
        if doc.get("title"):
            t = engine.redact(str(doc["title"]), language=lang, country=inp.country)
            title = str(t.text) if t.status == "REDACTED" else None
        if not segments and unsafe:
            return out("SKIPPED", "PII_UNSAFE", unsafe_segments=unsafe, needs_review_segments=needs_review)
        joined = "\n".join(s.text for s in segments)
        return out(
            "SUCCESS",
            None,
            title=title,
            published_at=doc.get("date"),
            segments=segments,
            needs_review_segments=needs_review,
            unsafe_segments=unsafe,
            redaction_counts=counts,
            pii_engine=engine.name,
            content_hash=hashlib.sha256(joined.encode("utf-8")).hexdigest() if joined else None,
        )

    return ToolDefinition(
        name=TOOL_NAME,
        version="1",
        description="Fetch one public web page and return its main content with personal data redacted.",
        input_model=PageFetchInput,
        output_model=PageFetchOutput,
        handler=handler,
        timeout_s=60,
    )
