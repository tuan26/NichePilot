"""T014 – EvidenceService chỉ trả bằng chứng ACTIVE (X3, FR-013e); CHECK ERASED ⇒ không còn nội dung."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from nichepilot.modules.evidence.service import EvidenceService

pytestmark = [pytest.mark.integration, pytest.mark.discovery]


async def test_TC_E1_FR013e_01_query_hides_erased_and_check_blocks_content(clean_db: AsyncEngine) -> None:
    sm = async_sessionmaker(clean_db, expire_on_commit=False)
    svc = EvidenceService(sm)
    async with clean_db.connect() as conn:
        project = (await conn.execute(text("SELECT id FROM projects LIMIT 1"))).scalar_one()
    src = await svc.add_source(project, "FORUM", "https://forum.example/t/1", content="x", data_origin="REAL")
    keep = await svc.add_evidence(project, "pain", "a", "INFERRED", data_origin="REAL", source_id=src, excerpt="ok")
    gone = await svc.add_evidence(project, "pain", "b", "INFERRED", data_origin="REAL", source_id=src, excerpt="bye")
    async with clean_db.begin() as conn:
        await conn.execute(
            text(
                "UPDATE research_evidence SET lifecycle_status = 'ERASED', erased_at = now(), excerpt = NULL,"
                " value = NULL WHERE id = :i"
            ),
            {"i": gone},
        )
    ids = [e.id for e in await svc.query(project)]
    assert ids == [keep]  # mặc định chỉ ACTIVE
    assert {e.id for e in await svc.query(project, include_erased=True)} == {keep, gone}  # chỉ cho audit
    async with clean_db.connect() as conn:
        with pytest.raises(IntegrityError, match="erased_no_content"):
            await conn.execute(
                text("UPDATE research_evidence SET lifecycle_status = 'ERASED', erased_at = now() WHERE id = :i"),
                {"i": keep},
            )
        await conn.rollback()
