"""T012 – Cấu hình ứng dụng (FR-018f, FR-019b, FR-054, FR-057)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from nichepilot.core.config import ConfigError, Settings, detect_ignored_credentials

BASE_ENV = {"DATABASE_URL": "postgresql+psycopg://u:p@localhost:5432/db"}


def _clear(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in [
        "APP_ENV",
        "AI_PROVIDER_OVERRIDE",
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "LOG_RETENTION_DAYS",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_PROFILE",
        "AI_PAID_CALLS_ENABLED",
    ]:
        monkeypatch.delenv(key, raising=False)
    for k, v in BASE_ENV.items():
        monkeypatch.setenv(k, v)


def test_TC_E0_16_01_defaults_are_safe(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _clear(monkeypatch)
    s = Settings(_env_file=None, _secrets_dir=tmp_path)
    assert s.app_env == "development"
    assert s.ai_paid_calls_enabled is False  # FR-019: mặc định TẮT
    assert s.log_retention_days == 90
    assert s.anthropic_api_key is None
    assert isinstance(s.database_url, SecretStr)


def test_TC_FR054_01_priority_secret_file_over_env_over_dotenv(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _clear(monkeypatch)
    dotenv = tmp_path / ".env"
    dotenv.write_text("ANTHROPIC_API_KEY=from-dotenv\nOPENAI_API_KEY=openai-from-dotenv\n")
    secrets = tmp_path / "secrets"
    secrets.mkdir()
    (secrets / "anthropic_api_key").write_text("from-secret-file")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "from-env")
    s = Settings(_env_file=dotenv, _secrets_dir=secrets)
    assert s.anthropic_api_key is not None
    assert s.anthropic_api_key.get_secret_value() == "from-secret-file"
    assert s.openai_api_key is not None
    assert s.openai_api_key.get_secret_value() == "openai-from-dotenv"
    # Secret không lộ qua repr
    assert "from-secret-file" not in repr(s)


def test_TC_FR018f_01_production_with_mock_override_fails_fast(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("AI_PROVIDER_OVERRIDE", "mock")
    with pytest.raises(ConfigError) as exc:
        Settings(_env_file=None, _secrets_dir=tmp_path)
    assert exc.value.code == "MOCK_NOT_ALLOWED"


def test_TC_FR018f_02_development_allows_mock_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER_OVERRIDE", "mock")
    s = Settings(_env_file=None, _secrets_dir=tmp_path)
    assert s.ai_provider_override == "mock"


def test_TC_FR054_02_empty_override_means_none(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("AI_PROVIDER_OVERRIDE", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    s = Settings(_env_file=None, _secrets_dir=tmp_path)
    assert s.ai_provider_override is None
    assert s.anthropic_api_key is None


def test_TC_FR057_01_log_retention_below_90_rejected(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("LOG_RETENTION_DAYS", "30")
    with pytest.raises(ConfigError) as exc:
        Settings(_env_file=None, _secrets_dir=tmp_path)
    assert exc.value.code == "VALIDATION_ERROR"


def test_TC_FR019b_01_oauth_style_credentials_are_ignored_with_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "oauth-token-should-be-ignored")
    monkeypatch.setenv("ANTHROPIC_PROFILE", "personal")
    warnings = detect_ignored_credentials()
    assert {"ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"} <= set(warnings)
    s = Settings(_env_file=None, _secrets_dir=tmp_path)
    assert s.anthropic_api_key is None  # không bao giờ dùng token OAuth thay cho API key
    assert "oauth-token-should-be-ignored" not in s.secret_values()


def test_TC_FR054_03_secret_values_lists_loaded_secrets(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _clear(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-value-123")
    s = Settings(_env_file=None, _secrets_dir=tmp_path)
    values = s.secret_values()
    assert "sk-ant-test-value-123" in values
    assert "p" not in values  # chỉ lấy secret đủ dài để tránh che nhầm
