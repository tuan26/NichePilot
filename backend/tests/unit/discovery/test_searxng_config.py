"""T019 – Sinh settings.yml SearXNG từ nguồn ALLOWED đang bật (FR-006g, FR-006d)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from nichepilot.modules.discovery.sources.searxng_config import render_settings, write_settings

pytestmark = pytest.mark.discovery
BASE = Path(__file__).resolve().parents[4] / "deploy" / "searxng" / "settings.base.yml"


def test_TC_E1_FR006g_01_keep_only_lists_enabled_allowed_engines(tmp_path: Path) -> None:
    empty = yaml.safe_load(render_settings(BASE.read_text(encoding="utf-8"), []))
    assert empty["use_default_settings"]["engines"]["keep_only"] == [] and empty["plugins"] == {}
    rendered = yaml.safe_load(render_settings(BASE.read_text(encoding="utf-8"), ["wikipedia", "mojeek", "wikipedia"]))
    assert rendered["use_default_settings"]["engines"]["keep_only"] == ["mojeek", "wikipedia"]
    assert rendered["plugins"] == {} and "json" in rendered["search"]["formats"]
    changed = write_settings(tmp_path, BASE, ["wikipedia"])
    assert changed and (tmp_path / "settings.yml").is_file()
    assert write_settings(tmp_path, BASE, ["wikipedia"]) is False  # không đổi → không cần khởi động lại
