"""T122 – Kho bằng chứng dùng chung (FR-007, BR-02): ràng buộc DB và EvidenceService. E0 không tạo dữ liệu nghiên cứu;
mọi bản ghi trong test là dữ liệu test gắn MOCK hoặc giá trị giả định rõ ràng.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from nichepilot.modules.evidence.service import EvidenceError, EvidenceService, canonicalize_url

pytestmark = [pytest.mark.integration]


async def _project(engine: AsyncEngine) -> uuid.UUID:
    async with engine.connect() as conn:
        return (await conn.execute(text("SELECT id FROM projects WHERE is_default"))).scalar_one()


def test_TC_FR007_01_canonical_url() -> None:
    assert (
        canonicalize_url("HTTPS://Example.COM/a/b/?utm_source=x&b=2&a=1&fbclid=z#frag")
        == "https://example.com/a/b?a=1&b=2"
    )
    assert canonicalize_url("https://example.com/") == "https://example.com/"


async def test_TC_FR007_02_db_constraints(clean_db: AsyncEngine) -> None:
    pid = await _project(clean_db)
    bad = [
        # VERIFIED bắt buộc có nguồn
        "INSERT INTO research_evidence (project_id, claim_key, value, verification_status, data_origin)"
        " VALUES (:p, 'x', '1', 'VERIFIED', 'MOCK')",
        # UNKNOWN bắt buộc value NULL
        "INSERT INTO research_evidence (project_id, claim_key, value, verification_status, data_origin)"
        " VALUES (:p, 'x', '1', 'UNKNOWN', 'MOCK')",
        "INSERT INTO research_evidence (project_id, claim_key, verification_status, data_origin)"
        " VALUES (:p, 'x', 'MAYBE', 'MOCK')",
        "INSERT INTO research_sources (project_id, source_type, url, canonical_url, content_hash, data_origin)"
        " VALUES (:p, 'BLOG', 'u', 'u', 'h', 'MOCK')",
    ]
    for sql in bad:
        with pytest.raises(IntegrityError):
            async with clean_db.begin() as conn:
                await conn.execute(text(sql), {"p": pid})
    async with clean_db.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO research_evidence (project_id, claim_key, verification_status, data_origin)"
                " VALUES (:p, 'x', 'UNKNOWN', 'MOCK')"
            ),
            {"p": pid},
        )
    sql = (
        "INSERT INTO research_sources (project_id, source_type, url, canonical_url, content_hash, data_origin)"
        " VALUES (:p, 'WEB_PAGE', 'u', 'https://e.com/a', 'h1', 'MOCK')"
    )
    async with clean_db.begin() as conn:
        await conn.execute(text(sql), {"p": pid})
    with pytest.raises(IntegrityError):  # unique (project, canonical_url, content_hash)
        async with clean_db.begin() as conn:
            await conn.execute(text(sql), {"p": pid})


async def test_TC_FR007_03_service_rules_and_mock_excluded(clean_db: AsyncEngine) -> None:
    pid = await _project(clean_db)
    svc = EvidenceService(async_sessionmaker(clean_db, expire_on_commit=False))
    src = await svc.add_source(
        pid, "WEB_PAGE", "https://example.com/p?utm_campaign=1", content="nội dung test", data_origin="MOCK"
    )
    again = await svc.add_source(pid, "WEB_PAGE", "https://example.com/p", content="nội dung test", data_origin="MOCK")
    assert again == src  # trùng nguồn → dùng lại
    await svc.add_evidence(pid, "commission_rate", None, "UNKNOWN", data_origin="MOCK")
    await svc.add_evidence(
        pid, "commission_rate", {"pct": 1}, "VERIFIED", source_id=src, excerpt="x" * 50, data_origin="MOCK"
    )
    with pytest.raises(EvidenceError):
        await svc.add_evidence(pid, "c", {"v": 1}, "VERIFIED", data_origin="MOCK")
    with pytest.raises(EvidenceError):
        await svc.add_evidence(pid, "c", {"v": 1}, "UNKNOWN", data_origin="MOCK")
    with pytest.raises(EvidenceError):
        await svc.add_evidence(pid, "c", {"v": 1}, "INFERRED", source_id=src, excerpt="y" * 1001, data_origin="MOCK")
    assert await svc.query(pid, claim_key="commission_rate") == []  # mặc định loại MOCK
    found = await svc.query(pid, claim_key="commission_rate", include_mock=True)
    assert {e.verification_status for e in found} == {"UNKNOWN", "VERIFIED"}
    assert all(e.data_origin == "MOCK" for e in found)
