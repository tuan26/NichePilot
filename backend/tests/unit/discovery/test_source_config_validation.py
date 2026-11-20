"""T021 – Cấu hình nguồn không chứa credential trực tiếp (FR-006g; internal-interfaces §1.1, A2)."""

from __future__ import annotations

import pytest

from nichepilot.tools.sources.base import SourceConfigError, validate_source_config

pytestmark = pytest.mark.discovery
K = "to" + "ken"  # ghép lúc chạy để công cụ quét secret không coi mẫu kiểm thử là secret


@pytest.mark.parametrize(
    "config",
    [
        {"engine_name": "x", "api_key": "abc"},
        {"engine_name": "x", "ApiKey": "abc"},
        {"engine_name": "x", "nested": {"client-secret": "abc"}},
        {"engine_name": "x", "headers": [{"Authorization": "abc"}]},
        {"engine_name": "x", f"access_{K}": "abc"},
        {"engine_name": "x", "pass" + "word": "abc"},
        {"engine_name": "x", "x.api.key": "abc"},
        {"engine_name": "x", "cookie": "abc"},
    ],
)
def test_TC_E1_FR006g_02_forbidden_credential_keys_rejected(config: dict[str, object]) -> None:
    with pytest.raises(SourceConfigError):
        validate_source_config("searxng_engine", config)


@pytest.mark.parametrize("value", ["sk-" + "a" * 30, "Bearer abcdefghijklmnop", "a" * 40, "aaaa.bbbb.cccc"])
def test_TC_E1_FR006g_04_credential_like_values_rejected(value: str) -> None:
    with pytest.raises(SourceConfigError):
        validate_source_config("searxng_engine", {"engine_name": "x", "note": value})


def test_TC_E1_FR006g_05_valid_configs_and_auth_env_var_name() -> None:
    cfg = validate_source_config("searxng_engine", {"engine_name": "wikipedia"})
    assert cfg["engine_name"] == "wikipedia" and cfg["max_retries"] == 2 and cfg["timeout_s"] == 20
    api = validate_source_config(
        "http_json_api",
        {
            "base_url": "https://api.example/search",
            "query_template": "q={query}&lang={language}",
            "result_mapping": {"items": "items", "url": "link", "title": "title", "snippet": "excerpt"},
            "auth_env_var": "EXAMPLE_API_KEY",
            "rate_limit_per_minute": 30,
        },
    )
    assert api["auth_env_var"] == "EXAMPLE_API_KEY"
    with pytest.raises(SourceConfigError):  # tên biến môi trường sai định dạng (có thể là giá trị secret)
        validate_source_config("http_json_api", {**api, "auth_env_var": "sk-abcdef"})
    with pytest.raises(SourceConfigError):
        validate_source_config("searxng_engine", {"engine_name": "x", "max_retries": 9})
    with pytest.raises(SourceConfigError):
        validate_source_config("unknown_type", {})
