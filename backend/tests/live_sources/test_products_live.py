"""T064 – SC-008: với nguồn ALLOWED thật + AI thật, ≥ 70% sản phẩm có website chính thức VERIFIED và ≥ 50% có chương trình
VERIFIED/PARTIAL. Chỉ chạy thủ công; thiếu điều kiện → BLOCKED (skip "BLOCKED:"), KHÔNG bao giờ được báo cáo là PASS bằng dữ liệu MOCK."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

pytestmark = [pytest.mark.live_sources, pytest.mark.products]


def test_TC_E2_SC008_01_real_sources_product_coverage() -> None:
    url = os.environ.get("NICHEPILOT_LIVE_DATABASE_URL")
    if not url:
        pytest.skip("BLOCKED: cần NICHEPILOT_LIVE_DATABASE_URL trỏ tới stack có nguồn ALLOWED và AI thật")
    eng = create_engine(url)
    try:
        with eng.connect() as conn:
            if not conn.execute(
                text("SELECT count(*) FROM source_policies WHERE enabled AND compliance_status = 'ALLOWED'")
            ).scalar_one():
                pytest.skip("BLOCKED: chưa có nguồn ALLOWED đang bật – không được coi là PASS")
            total, official, programs = conn.execute(
                text(
                    "SELECT count(DISTINCT p.id), count(DISTINCT p.id) FILTER (WHERE EXISTS (SELECT 1 FROM research_evidence e"
                    " WHERE e.subject_id = p.id AND e.claim_key = 'official_website' AND e.verification_status = 'VERIFIED'"
                    " AND e.lifecycle_status = 'ACTIVE')), count(DISTINCT p.id) FILTER (WHERE EXISTS (SELECT 1 FROM"
                    " product_programs pp JOIN affiliate_programs ap ON ap.id = pp.program_id WHERE pp.product_id = p.id"
                    " AND ap.verification_status IN ('VERIFIED','PARTIAL'))) FROM products p WHERE p.data_origin = 'REAL'"
                )
            ).one()
            if not total:
                pytest.skip("BLOCKED: chưa có lượt tìm sản phẩm nguồn thật")
        assert official / total >= 0.7 and programs / total >= 0.5
    finally:
        eng.dispose()
