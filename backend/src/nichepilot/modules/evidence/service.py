"""EvidenceService – lưu/truy vấn nguồn và bằng chứng (T122 – FR-007, BR-02, BR-09).

Quy tắc: VERIFIED bắt buộc có nguồn; UNKNOWN không có giá trị (không bịa dữ liệu); trích đoạn giới hạn độ dài;
truy vấn mặc định loại dữ liệu MOCK để mock không bao giờ lẫn vào nghiên cứu thật.
E1 (X3, FR-013e): truy vấn mặc định chỉ trả bằng chứng `ACTIVE` – bằng chứng đã xóa không được dùng ở bất kỳ phân tích nào;
`include_erased=True` chỉ dành cho audit.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nichepilot.modules.evidence.models import (
    MAX_EXCERPT_CHARS,
    SOURCE_TYPES,
    VERIFICATION_STATUSES,
    ResearchEvidence,
    ResearchSource,
)

TRACKING_PARAMS = ("fbclid", "gclid", "msclkid", "mc_cid", "mc_eid", "ref_src", "igshid")


class EvidenceError(ValueError):
    pass


def canonicalize_url(url: str) -> str:
    """Chuẩn hóa URL: scheme/host chữ thường, bỏ fragment, bỏ tham số tracking, sắp xếp query, bỏ '/' cuối path."""
    parts = urlsplit(url.strip())
    query = sorted(
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_") and k.lower() not in TRACKING_PARAMS
    )
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(query), ""))


@dataclass(frozen=True)
class Evidence:
    id: uuid.UUID
    claim_key: str
    value: Any
    verification_status: str
    source_id: uuid.UUID | None
    excerpt: str | None
    data_origin: str


class EvidenceService:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self.sessionmaker = sessionmaker

    async def add_source(
        self,
        project_id: uuid.UUID,
        source_type: str,
        url: str,
        *,
        content: str | bytes,
        data_origin: str,
        title: str | None = None,
        publisher: str | None = None,
        fetched_at: datetime | None = None,
    ) -> uuid.UUID:
        if source_type not in SOURCE_TYPES:
            raise EvidenceError(f"source_type không hợp lệ: {source_type}")
        raw = content.encode("utf-8") if isinstance(content, str) else content
        values = {
            "project_id": project_id,
            "source_type": source_type,
            "url": url,
            "canonical_url": canonicalize_url(url),
            "title": title,
            "publisher": publisher,
            "fetched_at": fetched_at or datetime.now(UTC),
            "content_hash": hashlib.sha256(raw).hexdigest(),
            "data_origin": data_origin,
        }
        async with self.sessionmaker() as s, s.begin():
            new_id = (
                await s.execute(
                    insert(ResearchSource)
                    .values(**values)
                    .on_conflict_do_nothing(index_elements=["project_id", "canonical_url", "content_hash"])
                    .returning(ResearchSource.id)
                )
            ).scalar_one_or_none()
            if new_id is not None:
                return new_id
            return (
                await s.execute(
                    select(ResearchSource.id).where(
                        ResearchSource.project_id == project_id,
                        ResearchSource.canonical_url == values["canonical_url"],
                        ResearchSource.content_hash == values["content_hash"],
                    )
                )
            ).scalar_one()

    async def add_evidence(
        self,
        project_id: uuid.UUID,
        claim_key: str,
        value: Any,
        verification_status: str,
        *,
        data_origin: str,
        source_id: uuid.UUID | None = None,
        excerpt: str | None = None,
        subject_type: str | None = None,
        subject_id: uuid.UUID | None = None,
        job_id: uuid.UUID | None = None,
    ) -> uuid.UUID:
        if verification_status not in VERIFICATION_STATUSES:
            raise EvidenceError("verification_status không hợp lệ")
        if verification_status == "VERIFIED" and source_id is None:
            raise EvidenceError("VERIFIED bắt buộc có nguồn")
        if verification_status == "UNKNOWN" and value is not None:
            raise EvidenceError("UNKNOWN không được có giá trị – không bịa dữ liệu")
        if excerpt is not None and len(excerpt) > MAX_EXCERPT_CHARS:
            raise EvidenceError(f"trích đoạn tối đa {MAX_EXCERPT_CHARS} ký tự")
        row = ResearchEvidence(
            project_id=project_id,
            source_id=source_id,
            subject_type=subject_type,
            subject_id=subject_id,
            claim_key=claim_key,
            value=value,
            excerpt=excerpt,
            verification_status=verification_status,
            verified_at=datetime.now(UTC) if verification_status == "VERIFIED" else None,
            collected_by_job_id=job_id,
            data_origin=data_origin,
        )
        async with self.sessionmaker() as s, s.begin():
            s.add(row)
            await s.flush()
            return row.id

    async def query(
        self,
        project_id: uuid.UUID,
        *,
        claim_key: str | None = None,
        subject_type: str | None = None,
        subject_id: uuid.UUID | None = None,
        include_mock: bool = False,
        include_erased: bool = False,
    ) -> list[Evidence]:
        stmt = select(ResearchEvidence).where(ResearchEvidence.project_id == project_id)
        if not include_erased:
            stmt = stmt.where(ResearchEvidence.lifecycle_status == "ACTIVE")
        if not include_mock:
            stmt = stmt.where(ResearchEvidence.data_origin == "REAL")
        if claim_key is not None:
            stmt = stmt.where(ResearchEvidence.claim_key == claim_key)
        if subject_type is not None:
            stmt = stmt.where(ResearchEvidence.subject_type == subject_type)
        if subject_id is not None:
            stmt = stmt.where(ResearchEvidence.subject_id == subject_id)
        async with self.sessionmaker() as s:
            rows = (await s.execute(stmt.order_by(ResearchEvidence.created_at))).scalars().all()
        return [
            Evidence(r.id, r.claim_key, r.value, r.verification_status, r.source_id, r.excerpt, r.data_origin)
            for r in rows
        ]
