"""T028 – Nguồn giả lập bị cấm ở production (FR-016), như MockAIProvider của E0."""

from __future__ import annotations

import pytest

from nichepilot.core.config import ConfigError
from nichepilot.core.discovery_config import DiscoverySettings
from nichepilot.tools.sources.backends import build_source_backends

pytestmark = pytest.mark.discovery


def test_TC_E1_FR016_01_mock_sources_rejected_in_production() -> None:
    with pytest.raises(ConfigError) as exc:
        build_source_backends(DiscoverySettings(app_env="production", discovery_source_mode="mock"))
    assert exc.value.code == "MOCK_NOT_ALLOWED"
    dev = build_source_backends(DiscoverySettings(app_env="development", discovery_source_mode="mock"))
    assert dev.data_origin == "MOCK"
    real = build_source_backends(DiscoverySettings(app_env="production", discovery_source_mode="real"))
    assert real.data_origin == "REAL"
