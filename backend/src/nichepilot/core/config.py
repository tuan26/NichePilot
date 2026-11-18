"""Cấu hình khởi động (T024 – FR-018(f), FR-019b, FR-054, FR-057).

Thứ tự ưu tiên: Docker secret file (`/run/secrets/<tên>`) > biến môi trường > file `.env` > mặc định.
Secret dùng `SecretStr`; không bao giờ đọc hồ sơ OAuth/CLI của người dùng (chỉ API key chính thức).
"""

from __future__ import annotations

import os
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

AppEnv = Literal["development", "test", "production"]
ProviderName = Literal["anthropic", "openai", "mock"]

DEFAULT_SECRETS_DIR = Path("/run/secrets")
IGNORED_CREDENTIAL_VARS = ("ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE", "ANTHROPIC_CONFIG_DIR")
MIN_SECRET_LEN_FOR_REDACTION = 6
MIN_LOG_RETENTION_DAYS = 90


class ConfigError(Exception):
    """Lỗi cấu hình khởi động – ứng dụng phải dừng (fail-fast)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=None,
        extra="ignore",
        case_sensitive=False,
        secrets_dir=str(DEFAULT_SECRETS_DIR) if DEFAULT_SECRETS_DIR.is_dir() else None,
    )

    app_env: AppEnv = "development"
    app_version: str = "0.1.0"

    database_url: SecretStr

    session_idle_timeout_hours: int = Field(default=12, ge=1)
    auth_lockout_threshold: int = Field(default=5, ge=1)
    auth_lockout_minutes: int = Field(default=15, ge=1)
    cookie_secure: bool = False

    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    ai_provider_override: ProviderName | None = None
    ai_paid_calls_enabled: bool = False
    mock_ai_default_scenario: str = "success"

    worker_concurrency: int = Field(default=1, ge=1, le=8)
    job_retry_delay_s: int = Field(default=30, ge=0)
    job_stalled_after_s: int = Field(default=120, ge=30)

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["json", "console"] = "json"
    log_dir: Path | None = None
    log_retention_days: int = MIN_LOG_RETENTION_DAYS
    log_disk_warn_gb: float = Field(default=2.0, gt=0)

    backup_retention: int = Field(default=7, ge=1)
    backup_cron: str = "0 3 * * *"
    nichepilot_live_max_usd: Decimal = Decimal("0.05")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return init_settings, file_secret_settings, env_settings, dotenv_settings

    @field_validator("anthropic_api_key", "openai_api_key", "ai_provider_override", "log_dir", mode="before")
    @classmethod
    def _empty_is_none(cls, v: Any) -> Any:
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("database_url")
    @classmethod
    def _postgres_only(cls, v: SecretStr) -> SecretStr:
        # FR-003: toàn bộ dữ liệu vận hành nằm trong PostgreSQL, driver psycopg 3 (không SQLite/MySQL/asyncpg).
        if not v.get_secret_value().startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL phải có dạng postgresql+psycopg://…")
        return v

    @field_validator("log_retention_days")
    @classmethod
    def _retention_at_least_90(cls, v: int) -> int:
        if v < MIN_LOG_RETENTION_DAYS:
            raise ValueError(f"log_retention_days phải >= {MIN_LOG_RETENTION_DAYS}")
        return v

    @model_validator(mode="after")
    def _mock_forbidden_in_production(self) -> Settings:
        if self.app_env == "production" and self.ai_provider_override == "mock":
            raise ValueError("MOCK_NOT_ALLOWED")
        return self

    def __init__(self, **values: Any) -> None:
        try:
            super().__init__(**values)
        except ValidationError as exc:
            if any("MOCK_NOT_ALLOWED" in str(e.get("msg", "")) for e in exc.errors()):
                raise ConfigError("MOCK_NOT_ALLOWED", "MockAIProvider bị cấm khi APP_ENV=production") from None
            fields = ", ".join(".".join(str(p) for p in e["loc"]) for e in exc.errors())
            raise ConfigError("VALIDATION_ERROR", f"Cấu hình không hợp lệ: {fields}") from None

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def secret_values(self) -> list[str]:
        """Giá trị secret đã nạp – dùng để che trong log và prompt gửi LLM."""
        values: list[str] = []
        for field in ("database_url", "anthropic_api_key", "openai_api_key"):
            secret = getattr(self, field)
            if secret is None:
                continue
            raw = secret.get_secret_value()
            if len(raw) >= MIN_SECRET_LEN_FOR_REDACTION:
                values.append(raw)
            if field == "database_url" and "@" in raw and ":" in raw.split("@", 1)[0]:
                password = raw.split("@", 1)[0].rsplit(":", 1)[-1]
                if len(password) >= MIN_SECRET_LEN_FOR_REDACTION:
                    values.append(password)
        return values


def detect_ignored_credentials() -> list[str]:
    """Biến xác thực kiểu OAuth/CLI bị bỏ qua có chủ đích (FR-019b) – trả về để ghi cảnh báo."""
    return [name for name in IGNORED_CREDENTIAL_VARS if os.environ.get(name)]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    env_file = os.environ.get("NICHEPILOT_ENV_FILE")
    return Settings(_env_file=env_file) if env_file else Settings()
