"""T029 – SourceAdapter thay thế được (FR-006): mỗi adapter_type có bản mock đạt Protocol; nghiệp vụ không phụ thuộc adapter."""

from __future__ import annotations

import pytest

from nichepilot.tools.mock_sources import MockSourceAdapter, MockWeb
from nichepilot.tools.sources.base import ADAPTER_CONFIG_MODELS, SourceAdapter

pytestmark = pytest.mark.discovery


def test_TC_E1_FR006_03_every_adapter_type_has_config_model_and_mock() -> None:
    assert set(ADAPTER_CONFIG_MODELS) == {"searxng_engine", "http_json_api", "open_dataset", "licensed_data"}
    web = MockWeb.builtin()
    for adapter_type in ADAPTER_CONFIG_MODELS:
        adapter: SourceAdapter = MockSourceAdapter(web, adapter_type=adapter_type)
        assert adapter.adapter_type == adapter_type and adapter.data_origin == "MOCK"
