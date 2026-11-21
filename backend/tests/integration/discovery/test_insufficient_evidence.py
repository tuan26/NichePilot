"""T070 – INSUFFICIENT_EVIDENCE (FR-013c): lưu cùng bằng chứng để nghiên cứu, không đếm là ngách hợp lệ; bản sao khác tên miền
không tạo nguồn độc lập (FR-013b, SC-003a). Dữ liệu MOCK – không chứng minh nguồn thật."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.discovery_helpers import allow_test_source, discovery_client
from tests.discovery_run import COPY, FORUM, REVIEW, run_discovery, set_search

pytestmark = [pytest.mark.integration, pytest.mark.discovery, pytest.mark.mock]

BAKERY = "[MOCK] Small bakery inventory"


async def _niche(conn: object, name: str) -> dict[str, object]:
    row = (
        (
            await conn.execute(  # type: ignore[attr-defined]
                text("SELECT id, evidence_status, monetization_status, risk_flags FROM niches WHERE name = :n"),
                {"n": name},
            )
        )
        .mappings()
        .one()
    )
    return dict(row)


async def test_TC_E1_FR013c_01_copy_only_niche_is_insufficient_but_keeps_evidence(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, COPY])  # bản gốc + bản sao khác tên miền
        run = await run_discovery(client)
        assert run["job"]["status"] == "SUCCEEDED", run
        m = run["metrics"]
        assert m["evidence_sufficient"] == 0 and m["insufficient_evidence"] == 3
        async with clean_db.connect() as conn:
            niche = await _niche(conn, BAKERY)
            links = (
                await conn.execute(
                    text(
                        "SELECT l.independence_group, l.counted_for_threshold, s.registered_domain FROM niche_evidence_links l"
                        " JOIN research_evidence e ON e.id = l.evidence_id JOIN research_sources s ON s.id = e.source_id"
                        " WHERE l.niche_id = :n"
                    ),
                    {"n": niche["id"]},
                )
            ).all()
            stored = (
                await conn.execute(
                    text(
                        "SELECT count(*) FROM research_evidence WHERE subject_id = :n AND lifecycle_status = 'ACTIVE'"
                    ),
                    {"n": niche["id"]},
                )
            ).scalar_one()
        assert niche["evidence_status"] == "INSUFFICIENT_EVIDENCE"
        assert stored >= 2  # vẫn lưu bằng chứng để nghiên cứu/đánh giá lại
        assert {r[2] for r in links} == {"forum.example", "aggregator.example"}
        assert len({r[0] for r in links}) == 1, "bản sao khác tên miền phải cùng nhóm độc lập"


async def test_TC_E1_FR013c_02_two_independent_sources_make_niche_sufficient(
    clean_db: AsyncEngine, migrated_db: str
) -> None:
    async with discovery_client(migrated_db) as client:
        await allow_test_source(clean_db)
        set_search(client, [FORUM, REVIEW, COPY])
        run = await run_discovery(client)
        m = run["metrics"]
        assert m["evidence_sufficient"] == 1 and m["insufficient_evidence"] == 2
        assert m["independent_sources"] == 2  # forum(+bản sao) và reviews – không đếm bản sao
        async with clean_db.connect() as conn:
            niche = await _niche(conn, BAKERY)
            others = (
                (
                    await conn.execute(
                        text("SELECT DISTINCT evidence_status FROM niches WHERE name <> :n"), {"n": BAKERY}
                    )
                )
                .scalars()
                .all()
            )
        assert niche["evidence_status"] == "EVIDENCE_SUFFICIENT" and others == ["INSUFFICIENT_EVIDENCE"]
