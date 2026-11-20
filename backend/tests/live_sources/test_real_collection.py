"""T061 – Thu thập từ nguồn ALLOWED thật (SC-013, FR-006b). Chỉ chạy thủ công: `NICHEPILOT_RUN_LIVE_SOURCES=1`.

Khi chưa có nguồn ALLOWED đang bật → BLOCKED (skip với lý do "BLOCKED:"), KHÔNG bao giờ được báo cáo là PASS.
Hiện mọi nguồn đều UNVERIFIED (xác minh BLOCKED do mạng – specs/002-niche-discovery/source-verification.md).
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

pytestmark = [pytest.mark.live_sources, pytest.mark.discovery]


def test_TC_E1_SC013_01_real_sources_cover_80_percent_of_candidates() -> None:
    url = os.environ.get("NICHEPILOT_LIVE_DATABASE_URL")
    if not url:
        pytest.skip("BLOCKED: cần NICHEPILOT_LIVE_DATABASE_URL trỏ tới stack có nguồn ALLOWED đã xác minh")
    eng = create_engine(url)
    try:
        with eng.connect() as conn:
            allowed = conn.execute(
                text("SELECT count(*) FROM source_policies WHERE enabled AND compliance_status = 'ALLOWED'")
            ).scalar_one()
            if not allowed:
                pytest.skip("BLOCKED: chưa có nguồn ALLOWED đang bật – không được coi là PASS")
            run = conn.execute(
                text(
                    "SELECT id, source_mode FROM discovery_runs WHERE source_mode = 'REAL' AND outcome IS NOT NULL"
                    " ORDER BY created_at DESC LIMIT 1"
                )
            ).first()
            if run is None:
                pytest.skip("BLOCKED: chưa có lượt khám phá nguồn thật đã kết thúc")
            total, covered = conn.execute(
                text(
                    "SELECT count(DISTINCT n.id), count(DISTINCT e.subject_id) FROM niche_run_links l"
                    " JOIN niches n ON n.id = l.niche_id LEFT JOIN research_evidence e ON e.subject_id = n.id"
                    " AND e.data_origin = 'REAL' WHERE l.run_id = :r"
                ),
                {"r": run.id},
            ).one()
            captcha_bypass = conn.execute(
                text(
                    "SELECT count(*) FROM page_fetch_log WHERE run_id = :r AND reason = 'ACCESS_RESTRICTED'"
                    " AND outcome = 'SUCCESS'"
                ),
                {"r": run.id},
            ).scalar_one()
        assert total > 0 and covered / total >= 0.8
        assert captcha_bypass == 0
    finally:
        eng.dispose()
