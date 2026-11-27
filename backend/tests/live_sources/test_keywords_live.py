"""T039 – SC-008: với nguồn ALLOWED thật + AI thật, ≥ 70% keyword ưu tiên có quan sát SERP và intent có tín hiệu quan sát.
Chỉ chạy thủ công; thiếu điều kiện → BLOCKED (skip "BLOCKED:"), KHÔNG bao giờ được báo cáo là PASS bằng dữ liệu MOCK."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

pytestmark = [pytest.mark.live_sources, pytest.mark.keywords]


def test_TC_E3_SC008_01_real_sources_serp_coverage() -> None:
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
            total, with_serp, verified = conn.execute(
                text(
                    "SELECT count(*), count(*) FILTER (WHERE EXISTS (SELECT 1 FROM serp_observations s WHERE s.keyword_id = k.id)),"
                    " count(*) FILTER (WHERE k.intent_status = 'VERIFIED') FROM keywords k JOIN keyword_clusters c"
                    " ON c.primary_keyword_id = k.id WHERE k.data_origin = 'REAL'"
                )
            ).one()
            if not total:
                pytest.skip("BLOCKED: chưa có lượt nghiên cứu keyword nguồn thật")
        assert with_serp / total >= 0.7 and verified / total >= 0.7
    finally:
        eng.dispose()
