"""Cấu hình E1 – Autonomous Niche Discovery (specs/002-niche-discovery; research R-02, R-05, R-09).

Tách khỏi `core/config.py` của E0 (không đổi cấu hình E0 đã nghiệm thu). Fail-closed ở production:
- PII engine phải nằm trong danh sách phê duyệt (quyết định I2).
- Nguồn giả lập (mock) bị cấm (như MockAIProvider của E0).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from nichepilot.core.config import AppEnv, ConfigError

KNOWN_PII_ENGINES = ("regex-phone", "spacy-en-sm")
SourceMode = Literal["real", "mock"]


class DiscoverySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=False)

    app_env: AppEnv = "development"
    searxng_url: str = "http://searxng:8080"
    pii_engine: str = "regex-phone"
    pii_approved_engines: str = "regex-phone"
    discovery_source_mode: SourceMode = "real"
    erasure_ledger_dir: Path = Path("/var/lib/nichepilot/erasure-ledger")
    searxng_config_dir: Path = Path("/var/lib/nichepilot/searxng")
    searxng_base_settings: Path = Path("/opt/nichepilot/searxng/settings.base.yml")
    discovery_user_agent: str = "NichePilotResearchBot/0.1 (+self-hosted research; contact: site owner)"
    fetch_timeout_s: float = Field(default=20.0, gt=0, le=60)
    fetch_max_bytes: int = Field(default=3 * 1024 * 1024, gt=0)
    ledger_health_cache_s: float = Field(default=60.0, ge=0)
    # T128: profile tùy chọn browser-fetcher (TẮT mặc định – quyết định I1)
    page_fetcher: Literal["http", "browser"] = "http"
    browser_ws_endpoint: str | None = None
    browser_executable_path: str | None = None

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    def approved_engines(self) -> set[str]:
        return {e.strip() for e in self.pii_approved_engines.split(",") if e.strip()}


def validate_discovery_settings(settings: DiscoverySettings) -> None:
    """Kiểm tra lúc khởi động (api + worker). Lỗi → ConfigError, tiến trình dừng."""
    if settings.pii_engine not in KNOWN_PII_ENGINES:
        raise ConfigError("PII_ENGINE_NOT_APPROVED", f"PII engine không xác định: {settings.pii_engine}")
    if settings.is_production and settings.pii_engine not in settings.approved_engines():
        raise ConfigError(
            "PII_ENGINE_NOT_APPROVED",
            f"PII engine '{settings.pii_engine}' chưa được phê duyệt cho production (PII_APPROVED_ENGINES)",
        )
    if settings.is_production and settings.discovery_source_mode == "mock":
        raise ConfigError("MOCK_NOT_ALLOWED", "Nguồn giả lập bị cấm khi APP_ENV=production")


@lru_cache(maxsize=1)
def get_discovery_settings() -> DiscoverySettings:
    return DiscoverySettings()
