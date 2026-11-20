"""T023 – select_pii_engine fail-closed (FR-012a; quyết định I2): production không kích hoạt engine chưa phê duyệt."""

from __future__ import annotations

import pytest

from nichepilot.core.config import ConfigError
from nichepilot.core.discovery_config import DiscoverySettings, validate_discovery_settings
from nichepilot.tools.privacy.pii import RegexPhonePiiEngine, select_pii_engine

pytestmark = pytest.mark.discovery


def test_TC_E1_FR012a_05_production_rejects_unapproved_engine() -> None:
    ok = DiscoverySettings(app_env="production", pii_engine="regex-phone", pii_approved_engines="regex-phone")
    validate_discovery_settings(ok)
    assert isinstance(select_pii_engine(ok), RegexPhonePiiEngine)

    bad = DiscoverySettings(app_env="production", pii_engine="spacy-en-sm", pii_approved_engines="regex-phone")
    with pytest.raises(ConfigError) as exc:
        validate_discovery_settings(bad)
    assert exc.value.code == "PII_ENGINE_NOT_APPROVED"
    with pytest.raises(ConfigError):
        select_pii_engine(bad)

    # Kể cả khi được thêm vào danh sách phê duyệt: model không có sẵn trong image → từ chối, KHÔNG tải mạng.
    approved_missing = DiscoverySettings(
        app_env="production", pii_engine="spacy-en-sm", pii_approved_engines="regex-phone,spacy-en-sm"
    )
    with pytest.raises(ConfigError) as exc2:
        select_pii_engine(approved_missing, model_available=lambda: False)
    assert exc2.value.code == "PII_ENGINE_NOT_APPROVED"


def test_TC_E1_FR012a_09_unknown_engine_and_mock_sources_rejected_in_production() -> None:
    with pytest.raises(ConfigError):
        validate_discovery_settings(
            DiscoverySettings(app_env="production", pii_engine="nope", pii_approved_engines="nope")
        )
    with pytest.raises(ConfigError) as exc:
        validate_discovery_settings(DiscoverySettings(app_env="production", discovery_source_mode="mock"))
    assert exc.value.code == "MOCK_NOT_ALLOWED"
    validate_discovery_settings(DiscoverySettings(app_env="development", discovery_source_mode="mock"))
