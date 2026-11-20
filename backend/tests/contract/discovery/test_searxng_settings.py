"""E1 Phase 1 (T003, T004) – kiểm tra tĩnh cấu hình SearXNG trong Compose (FR-006c, FR-006d, research R-02).

Không engine, không plugin nào được nạp khi chưa có nguồn ALLOWED; service chỉ trong mạng nội bộ; secret không commit.
Kiểm chứng động (chạy image thật trong mạng Docker --internal, 2026-11-20) ghi ở research R-02.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.discovery
DEPLOY = Path(__file__).resolve().parents[4] / "deploy"


def _compose() -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load((DEPLOY / "docker-compose.yml").read_text(encoding="utf-8"))
    return data


def test_TC_E1_FR006d_05_base_settings_load_no_engine_and_no_plugin() -> None:
    cfg = yaml.safe_load((DEPLOY / "searxng" / "settings.base.yml").read_text(encoding="utf-8"))
    assert cfg["use_default_settings"]["engines"]["keep_only"] == []  # không engine nào
    assert cfg["plugins"] == {}  # plugin tracker_url_remover tự tải dữ liệu từ Internet khi khởi tạo
    assert "json" in cfg["search"]["formats"]
    assert cfg["server"]["public_instance"] is False and cfg["server"]["image_proxy"] is False
    assert "secret_key" not in cfg["server"]  # secret qua biến môi trường SEARXNG_SECRET


def test_TC_E1_FR006c_05_searxng_service_internal_pinned_and_limited() -> None:
    compose = _compose()
    svc = compose["services"]["searxng"]
    assert svc["image"] == "searxng/searxng:2026.11.18-b867c56a5"  # ghim phiên bản đã đánh giá
    assert "ports" not in svc  # không mở cổng ra ngoài
    assert svc["mem_limit"] == "256m"
    assert svc["environment"]["GRANIAN_HOST"] == "0.0.0.0"  # noqa: S104 – chỉ trong mạng nội bộ Compose
    assert "${SEARXNG_SECRET" in svc["environment"]["SEARXNG_SECRET"]
    assert {"erasure-ledger", "searxng-config"} <= set(compose["volumes"])
    example = (DEPLOY / "env" / ".env.example").read_text(encoding="utf-8")
    assert "\nSEARXNG_SECRET=\n" in example  # mẫu không chứa secret thật
