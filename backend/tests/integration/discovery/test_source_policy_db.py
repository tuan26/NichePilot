"""T018 (phần DB) – usable_for_run và update_policy trên PostgreSQL thật (FR-006c, FR-006d, FR-036, SC-017)."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from nichepilot.core.errors import AppError
from nichepilot.modules.discovery.sources.policy import PolicyUpdate, SourcePolicyService

pytestmark = [pytest.mark.integration, pytest.mark.discovery]
ALLOW = PolicyUpdate(
    compliance_status="ALLOWED",
    verified_at="2026-11-01",
    verification_note="Điều khoản §4 cho phép truy vấn tự động qua API công khai",
    allowed_access_methods=["SEARXNG_ENGINE"],
    permitted_use_scope="Nghiên cứu nội bộ; lưu trích đoạn ≤ 1000 ký tự có ghi nguồn",
)


async def test_TC_E1_FR006d_03_usable_only_allowed_enabled_and_audited(clean_db: AsyncEngine) -> None:
    sm = async_sessionmaker(clean_db, expire_on_commit=False)
    async with sm() as s:
        user = (
            await s.execute(text("INSERT INTO users (username, password_hash) VALUES ('owner_p', 'x') RETURNING id"))
        ).scalar_one()
        svc = SourcePolicyService(s)
        assert await svc.usable_for_run() == []  # seed: mọi nguồn UNVERIFIED
        wiki = (
            await s.execute(text("SELECT id FROM source_policies WHERE source_key = 'searxng:wikipedia'"))
        ).scalar_one()
        with pytest.raises(AppError) as exc:
            await svc.update_policy(user, wiki, PolicyUpdate(enabled=True))  # UNVERIFIED không bật được
        assert exc.value.code == "SOURCE_NOT_ALLOWED"
        with pytest.raises(AppError) as exc2:
            await svc.update_policy(user, wiki, PolicyUpdate(compliance_status="ALLOWED"))  # thiếu căn cứ
        assert exc2.value.code == "SOURCE_VERIFICATION_INCOMPLETE"
        await svc.update_policy(user, wiki, ALLOW)
        await svc.update_policy(user, wiki, PolicyUpdate(enabled=True))
        usable = await svc.usable_for_run()
        assert [u.source_key for u in usable] == ["searxng:wikipedia"] and usable[
            0
        ].snapshot().compliance_status == "ALLOWED"
        await svc.update_policy(user, wiki, PolicyUpdate(compliance_status="UNVERIFIED"))  # rời ALLOWED → tự tắt
        row = (await s.execute(text("SELECT enabled FROM source_policies WHERE id = :i"), {"i": wiki})).scalar_one()
        assert row is False and await svc.usable_for_run() == []
        actions = (await s.execute(text("SELECT action, before, after FROM audit_logs ORDER BY created_at"))).all()
        await s.rollback()
    assert [a[0] for a in actions] == ["source.updated"] * 3
    assert actions[0][1]["compliance_status"] == "UNVERIFIED" and actions[0][2]["compliance_status"] == "ALLOWED"
