"""PageCollector – tải trang cho agent E2 theo đúng chuỗi tuân thủ của E1 (research R-01; internal-interfaces §3;
FR-006, FR-010).

Thứ tự mỗi URL: giới hạn trang/thời gian → đã tải trong lượt → `DomainAccessService.permit` (robots.txt + mức trần 1
request/2 s/tên
miền, `robots.fetch` khi cần) → chờ/hoãn theo tên miền → `page.fetch` (trích nội dung + CHE PII trong handler) → bỏ
nội dung đã xóa →
lưu nguồn + trích đoạn (REDACTED, ≤ 1000 ký tự, chống trùng theo `content_hash`). Không vượt CAPTCHA/đăng
nhập/paywall: trang lỗi hoặc
bị chặn chỉ được ghi lý do. Checkpoint (state) chỉ chứa URL công khai, ID và bộ đếm – không chứa nội dung trang.
Logic lặp lại `NicheDiscoveryAgent._fetch` (E1) có chủ đích để không sửa agent E1 đã nghiệm thu (plan Y6). E3 dùng lại
với
`subject_type = keyword_run` (tham số bổ sung, mặc định giữ hành vi E2).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

from nichepilot.jobs.runtime import JobContext
from nichepilot.modules.discovery import service as disc_svc
from nichepilot.modules.discovery.access import DomainAccessService, domain_of
from nichepilot.modules.discovery.fingerprint import content_hash, registered_domain, simhash64, url_hash
from nichepilot.modules.evidence.service import EvidenceService
from nichepilot.tools.privacy.pii import PROFILE_URL_RE

MAX_RATE_RETRIES = 2
DEFAULT_RETRY_AFTER_S = 30.0
MAX_DEFERRALS = 3
MAX_WAIT_IN_STEP_S = 30.0
MIN_SEGMENT_CHARS = 40
MAX_SEGMENTS_PER_PAGE = 6


@dataclass
class CollectResult:
    processed: int
    time_up: bool
    page_limit_hit: bool


def _count(m: dict[str, Any], outcome: str, reason: str | None) -> None:
    m["pages_attempted"] = int(m.get("pages_attempted", 0)) + 1
    key = {"SUCCESS": "pages_succeeded", "FAILED": "pages_failed", "SKIPPED": "pages_skipped"}[outcome]
    m[key] = int(m.get(key, 0)) + 1
    if reason:
        sk = m.setdefault("skipped_by_reason", {})
        sk[reason] = int(sk.get(reason, 0)) + 1


def enqueue(state: dict[str, Any], url: str, policy_id: str, tag: str) -> bool:
    """Thêm URL vào hàng đợi (bỏ trùng, bỏ URL hồ sơ cá nhân – FR-010/E1 FR-012c). `tag` = nhóm (niche | product
    index)."""
    seen: list[str] = state.setdefault("seen_urls", [])
    if url in seen or PROFILE_URL_RE.match(url):
        return False
    seen.append(url)
    state.setdefault("queue", []).append({"url": url, "policy_id": policy_id, "tag": tag, "d": 0, "r": 0})
    return True


async def collect(
    ctx: JobContext,
    state: dict[str, Any],
    *,
    project_id: uuid.UUID,
    run_origin: str,
    run_id: uuid.UUID,
    page_limit: int,
    interval_s: float,
    language: str,
    country: str,
    time_left: Callable[[], float],
    batch: int = 5,
    subject_type: str = "product_run",
) -> CollectResult:
    access = DomainAccessService(ctx.sessionmaker)
    m: dict[str, Any] = state["metrics"]
    fetched: list[str] = state.setdefault("fetched", [])
    pages: dict[str, list[str]] = state.setdefault("pages", {})  # tag → [evidence_id]
    async with ctx.sessionmaker() as s:
        policies = {str(r.id): r for r in (await s.execute(text("SELECT id, verified_at FROM source_policies"))).all()}
    processed = 0
    while state["queue"] and processed < batch:
        if int(m.get("pages_attempted", 0)) >= page_limit:
            state["queue"] = []
            return CollectResult(processed, False, True)
        if time_left() <= 0:
            return CollectResult(processed, True, False)
        item = state["queue"].pop(0)
        url, domain, uh = item["url"], domain_of(item["url"]), url_hash(item["url"])
        if uh in fetched:
            continue
        decision = await access.permit(url, interval_ceiling_s=interval_s)
        if decision.reason == "ROBOTS_PENDING":
            robots = await ctx.call_tool("robots.fetch", {"domain": domain})
            await access.record_robots(domain, robots["status"], robots["content"])
            decision = await access.permit(url, interval_ceiling_s=interval_s)
        if decision.reason == "WAIT":
            wait = decision.wait_s
            if wait <= min(MAX_WAIT_IN_STEP_S, max(0.0, time_left())):
                await asyncio.sleep(wait)
                decision = await access.permit(url, interval_ceiling_s=interval_s)
            if decision.reason == "WAIT":
                if item["d"] < MAX_DEFERRALS and wait <= time_left():
                    state["queue"].append({**item, "d": item["d"] + 1})
                    continue
                fetched.append(uh)
                _count(m, "SKIPPED", "RATE_LIMITED")
                processed += 1
                continue
        if not decision.allowed:
            fetched.append(uh)
            _count(m, "SKIPPED", "ROBOTS_DISALLOWED")
            processed += 1
            continue
        await access.record_request(domain)
        page = await ctx.call_tool("page.fetch", {"url": url, "language": language, "country": country})
        processed += 1
        m["needs_review_segments"] = int(m.get("needs_review_segments", 0)) + int(page.get("needs_review_segments", 0))
        if page["status"] != "SUCCESS":
            if page["reason"] == "RATE_LIMITED" and int(item.get("r", 0)) < MAX_RATE_RETRIES:
                retry_after = float(page.get("retry_after_s") or DEFAULT_RETRY_AFTER_S)
                await access.record_retry_after(domain, retry_after)
                if retry_after <= time_left():
                    state["queue"].append({**item, "r": int(item.get("r", 0)) + 1, "d": 0})
                    continue
            fetched.append(uh)
            _count(m, page["status"], page["reason"])
            continue
        seg_hashes = [content_hash(str(seg["text"])) for seg in page["segments"]]
        async with ctx.sessionmaker() as s:
            erased = await disc_svc.erased_among(s, [str(page.get("content_hash") or ""), *seg_hashes])
        kept = [seg for seg, h in zip(page["segments"], seg_hashes, strict=True) if h not in erased]
        if page.get("content_hash") in erased or (erased and not kept):
            fetched.append(uh)
            _count(m, "SKIPPED", "ERASED_CONTENT")
            continue
        ids = await _store(
            ctx, {**page, "segments": kept}, item, project_id, run_origin, run_id, policies, subject_type
        )
        pages.setdefault(item["tag"], []).extend(i for i in ids if i not in pages.get(item["tag"], []))
        fetched.append(uh)
        _count(m, "SUCCESS", None)
    return CollectResult(processed, False, False)


async def _store(
    ctx: JobContext,
    page: dict[str, Any],
    item: dict[str, Any],
    project_id: uuid.UUID,
    run_origin: str,
    run_id: uuid.UUID,
    policies: dict[str, Any],
    subject_type: str = "product_run",
) -> list[str]:
    ev = EvidenceService(ctx.sessionmaker)
    texts = [str(seg["text"]) for seg in page["segments"]]
    joined = "\n".join(texts)
    origin = "MOCK" if "MOCK" in (page.get("data_origin"), run_origin) else "REAL"
    policy = policies.get(item["policy_id"])
    source_id = await ev.add_source(
        project_id,
        "WEB_PAGE",
        page.get("final_url") or item["url"],
        content=joined,
        data_origin=origin,
        title=page.get("title"),
        registered_domain=registered_domain(item["url"]),
        simhash=simhash64(joined),
        source_policy_id=uuid.UUID(item["policy_id"]),
        policy_verified_at=policy.verified_at if policy else None,
    )
    ids: list[str] = []
    for seg in [t for t in texts if len(t) >= MIN_SEGMENT_CHARS][:MAX_SEGMENTS_PER_PAGE]:
        h = content_hash(seg)
        async with ctx.sessionmaker() as s:
            dup = (
                await s.execute(
                    text(
                        "SELECT id FROM research_evidence WHERE source_id = :s AND subject_id = :r AND content_hash ="
                        " :h"
                    ),
                    {"s": source_id, "r": run_id, "h": h},
                )
            ).scalar_one_or_none()
        if dup is not None:
            ids.append(str(dup))
            continue
        eid = await ev.add_evidence(
            project_id,
            "page_excerpt",
            None,
            "VERIFIED",  # trích dẫn trực tiếp từ nguồn có URL (BR-02)
            data_origin=origin,
            source_id=source_id,
            excerpt=seg[:1000],
            subject_type=subject_type,
            subject_id=run_id,
            job_id=ctx.job_id,
            redaction_status="REDACTED",
            redaction_counts=page.get("redaction_counts") or {},
            pii_engine=page.get("pii_engine"),
            content_hash=h,
        )
        ids.append(str(eid))
    return ids
