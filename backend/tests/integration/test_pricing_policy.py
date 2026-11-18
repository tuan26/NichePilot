"""C3 – Chính sách giá đã được chủ sở hữu phê duyệt có điều kiện (2026-11-18).

- Giá đã xác minh của provider thật phải có nguồn chính thức (URL) và ngày xác minh (YYYY-MM-DD) – ở API và ở DB.
- Giữ chỗ của mock tính theo công thức từ bảng giá trong DB, không hardcode.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from decimal import ROUND_UP, Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from nichepilot.ai.gateway import AIGateway, CallContext
from nichepilot.ai.providers.base import LLMMessage
from nichepilot.ai.providers.mock import DEFAULT_USAGE, MockAIProvider
from tests.api_helpers import api_client, csrf_headers, make_settings, setup_owner
from tests.config_snapshot import restore, snapshot
from tests.integration.budget_helpers import insert_job

pytestmark = [pytest.mark.integration, pytest.mark.mock]
GOOD_NOTE = "https://platform.claude.com/docs/en/about-claude/pricing – chủ sở hữu xác minh 2026-11-18"


@pytest.fixture
async def snap(clean_db: AsyncEngine) -> AsyncIterator[AsyncEngine]:
    s = await snapshot(clean_db)
    try:
        yield clean_db
    finally:
        await restore(clean_db, s)


@pytest.mark.parametrize(
    "note",
    [
        "Trang giá chính thức (owner)",  # không URL, không ngày
        "https://platform.claude.com/docs/en/about-claude/pricing",  # thiếu ngày xác minh
        "xác minh 2026-11-18",  # thiếu URL nguồn
    ],
)
async def test_TC_FR041_20_verified_price_requires_source_url_and_date(
    snap: AsyncEngine, migrated_db: str, note: str
) -> None:
    body = {
        "provider": "anthropic",
        "model": "claude-haiku-5-5",
        "input_per_mtok": "0.10",
        "output_per_mtok": "0.50",
        "effective_from": "2026-11-18T00:00:00Z",
        "source_note": note,
        "verified": True,
    }
    async with api_client(migrated_db) as client:
        await setup_owner(client)
        r = await client.post("/api/v1/model-pricing", json=body, headers=csrf_headers(client))
        assert r.status_code == 422, r.text
        ok = await client.post(
            "/api/v1/model-pricing", json={**body, "source_note": GOOD_NOTE}, headers=csrf_headers(client)
        )
        assert ok.status_code == 201, ok.text
        draft = await client.post(  # bản giá CHƯA xác minh vẫn được lưu để chờ xác minh
            "/api/v1/model-pricing", json={**body, "verified": False}, headers=csrf_headers(client)
        )
        assert draft.status_code == 201


async def test_TC_FR041_21_db_rejects_verified_real_price_without_source_and_date(snap: AsyncEngine) -> None:
    with pytest.raises(IntegrityError):
        async with snap.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE model_pricing SET verified = true, source_note = 'giá tham khảo, chưa có nguồn/ngày'"
                    " WHERE provider = 'anthropic'"
                )
            )
    async with snap.begin() as conn:  # mock được miễn (giá giả lập nội bộ, không phải chi phí thật)
        n = (await conn.execute(text("SELECT COUNT(*) FROM model_pricing WHERE provider='mock' AND verified"))).scalar()
    assert n and n >= 1


async def test_TC_FR043_20_mock_reservation_follows_formula(clean_db: AsyncEngine, migrated_db: str) -> None:
    """Giữ chỗ = token prompt × max(input, cache read, cache write) + max_output × output, làm tròn lên 6 chữ số.
    Mọi giá trị lấy từ DB (bảng giá mock, profile), không hardcode số tiền."""
    async with clean_db.connect() as conn:
        p = (
            await conn.execute(
                text(
                    "SELECT input_per_mtok, output_per_mtok, cache_read_per_mtok, cache_write_per_mtok FROM model_pricing"
                    " WHERE provider='mock' ORDER BY version DESC LIMIT 1"
                )
            )
        ).one()
        max_out = (
            await conn.execute(
                text("SELECT max_output_tokens FROM model_task_profiles WHERE task_type='system.diagnostic'")
            )
        ).scalar_one()
    in_rate = Decimal(p.input_per_mtok)
    read = Decimal(p.cache_read_per_mtok) if p.cache_read_per_mtok is not None else in_rate
    write = Decimal(p.cache_write_per_mtok) if p.cache_write_per_mtok is not None else in_rate * 2
    per_prompt = max(in_rate, read, write)
    expected = (
        (Decimal(DEFAULT_USAGE.input_tokens) * per_prompt + Decimal(max_out) * Decimal(p.output_per_mtok))
        / Decimal(1_000_000)
    ).quantize(Decimal("0.000001"), rounding=ROUND_UP)

    job = await insert_job(clean_db)
    gw = AIGateway(
        make_settings(migrated_db),
        async_sessionmaker(clean_db, expire_on_commit=False),
        {"mock": MockAIProvider()},
        backoff_base_s=0,
    )  # type: ignore[dict-item]
    await gw.call(
        "system.diagnostic", system="s", messages=[LLMMessage(role="user", content="hi")], ctx=CallContext(job_id=job)
    )
    async with clean_db.connect() as conn:
        amount = (
            await conn.execute(text("SELECT amount_usd FROM budget_reservations WHERE job_id=:j"), {"j": job})
        ).scalar_one()
    assert Decimal(amount) == expected
