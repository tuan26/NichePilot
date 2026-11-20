"""Cấu hình nguồn dùng chung cho `modules/discovery` và `tools/sources` (FR-006, FR-006g; internal-interfaces §1.1, A2).

Đặt ở `core` vì hai lớp `modules` và `tools` không được import lẫn nhau (backend/.importlinter). Cấu hình KHÔNG chứa credential:
khóa bị cấm ở mọi cấp lồng nhau, giá trị có dạng credential bị từ chối; xác thực chỉ qua `auth_env_var` = TÊN biến môi trường.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

# internal-interfaces §1.1 – chuỗi bị cấm trong TÊN khóa (sau khi chữ thường và bỏ `-`, `_`, `.`)
FORBIDDEN_KEY_PARTS = (
    "apikey",
    "accesskey",
    "secretkey",
    "privatekey",
    "clientsecret",
    "consumersecret",
    "password",
    "passwd",
    "pwd",
    "passphrase",
    "token",
    "bearer",
    "cookie",
    "session",
    "jwt",
    "authorization",
    "authheader",
    "xapikey",
    "secret",
    "credential",
    "signature",
)
ALLOWED_KEYS = frozenset({"auth_env_var"})
CREDENTIAL_VALUE_RE = re.compile(
    r"^(?:sk-[A-Za-z0-9_-]{8,}|Bearer\s+\S{8,}|[A-Za-z0-9+/=_-]{32,}|[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]{4,})$"
)
ENV_VAR_RE = re.compile(r"^[A-Z][A-Z0-9_]{2,63}$")
URL_LIKE_RE = re.compile(r"^https?://")


class SourceConfigError(ValueError):
    pass


def _normalize_key(key: str) -> str:
    return re.sub(r"[-_.\s]", "", key.lower())


def _check_tree(node: Any, path: str = "config") -> None:
    if isinstance(node, dict):
        for key, value in node.items():
            k = str(key)
            if k not in ALLOWED_KEYS and any(part in _normalize_key(k) for part in FORBIDDEN_KEY_PARTS):
                raise SourceConfigError(f"{path}.{k}: khóa không được chứa credential (internal-interfaces §1.1)")
            _check_tree(value, f"{path}.{k}")
    elif isinstance(node, list):
        for i, item in enumerate(node):
            _check_tree(item, f"{path}[{i}]")
    elif isinstance(node, str) and not URL_LIKE_RE.match(node) and CREDENTIAL_VALUE_RE.match(node.strip()):
        raise SourceConfigError(f"{path}: giá trị có dạng credential")


class _AccessPolicy(BaseModel):
    """FR-006: chính sách truy cập riêng của từng nguồn."""

    model_config = ConfigDict(extra="forbid")
    rate_limit_per_minute: int = Field(default=30, ge=1, le=600)
    max_retries: int = Field(default=2, ge=0, le=5)
    timeout_s: int = Field(default=20, ge=1, le=60)


class SearxngEngineConfig(_AccessPolicy):
    engine_name: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9 _.-]+$")
    categories: list[str] = Field(default_factory=list)


class HttpJsonApiConfig(_AccessPolicy):
    base_url: str = Field(pattern=r"^https://")
    query_template: str = Field(min_length=1, max_length=500)
    result_mapping: dict[str, str]
    auth_env_var: str | None = None
    auth_header_name: str = Field(default="Authorization", max_length=64)

    @field_validator("auth_env_var")
    @classmethod
    def _env_name(cls, v: str | None) -> str | None:
        if v is not None and not ENV_VAR_RE.match(v):
            raise ValueError("auth_env_var phải là TÊN biến môi trường (^[A-Z][A-Z0-9_]{2,63}$)")
        return v

    @field_validator("result_mapping")
    @classmethod
    def _mapping(cls, v: dict[str, str]) -> dict[str, str]:
        if "url" not in v:
            raise ValueError("result_mapping phải có 'url'")
        return v


class DatasetConfig(_AccessPolicy):
    path: str = Field(min_length=1, max_length=500)
    license_url: str = Field(pattern=r"^https://")
    field_mapping: dict[str, str] = Field(default_factory=dict)


class LicensedDataConfig(DatasetConfig):
    license_reference: str = Field(min_length=3, max_length=200)


ADAPTER_CONFIG_MODELS: dict[str, type[_AccessPolicy]] = {
    "searxng_engine": SearxngEngineConfig,
    "http_json_api": HttpJsonApiConfig,
    "open_dataset": DatasetConfig,
    "licensed_data": LicensedDataConfig,
}


def validate_source_config(adapter_type: str, config: dict[str, Any]) -> dict[str, Any]:
    """Validate `source_policies.config` theo `adapter_type`; trả cấu hình đã chuẩn hóa (có mặc định)."""
    model = ADAPTER_CONFIG_MODELS.get(adapter_type)
    if model is None:
        raise SourceConfigError(f"adapter_type không hỗ trợ: {adapter_type}")
    if not isinstance(config, dict):
        raise SourceConfigError("config phải là object")
    _check_tree(config)
    try:
        return model.model_validate(config).model_dump()
    except ValidationError as exc:
        raise SourceConfigError("; ".join(f"{'.'.join(map(str, e['loc']))}: {e['type']}" for e in exc.errors())) from None


