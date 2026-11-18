"""FR-070, FR-074 – Cấu hình Docker Compose (kiểm tra tĩnh). Kiểm tra động: deploy/tests/smoke.sh trong CI
(TC-FR070-02, TC-FR074-02, TC-SC001-01, TC-SC002-01)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

DEPLOY = Path(__file__).resolve().parents[3] / "deploy"
REQUIRED = ["postgres", "migrate", "api", "worker", "web"]


def _load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = yaml.safe_load((DEPLOY / name).read_text(encoding="utf-8"))
    return data


def test_TC_FR070_01_single_compose_with_limits_and_profiles() -> None:
    services = _load("docker-compose.yml")["services"]
    assert set(REQUIRED) <= services.keys()
    for name, svc in services.items():
        assert svc.get("mem_limit"), f"{name} thiếu mem_limit"
        if name in REQUIRED:
            assert "profiles" not in svc, f"{name} là thành phần bắt buộc, không được nằm trong profile"
    assert services["backup"]["profiles"] == ["ops"]  # thành phần tùy chọn tách theo profile
    for name in ("api", "worker"):
        assert services[name]["depends_on"]["migrate"]["condition"] == "service_completed_successfully"
    assert services["postgres"]["image"].startswith("postgres:17")
    assert "127.0.0.1:5432:5432" in services["postgres"]["ports"]  # DB không mở ra mạng ngoài


def test_TC_FR074_01_dev_override_hot_reload() -> None:
    dev = _load("docker-compose.dev.yml")["services"]
    assert "--reload" in dev["api"]["command"]
    assert dev["worker"]["command"][0] == "watchfiles"
    assert "npm run dev" in " ".join(dev["web"]["command"])
    for name in ("api", "worker"):
        assert any(v.startswith("../backend/src:") for v in dev[name]["volumes"])
    assert any(v.startswith("../frontend:") for v in dev["web"]["volumes"])


def _mb(v: str) -> int:
    n, unit = int(v[:-1]), v[-1].lower()
    return n * 1024 if unit == "g" else n


def test_TC_FR074_03_dev_web_has_memory_for_npm_and_vite() -> None:
    """Dev override chạy `npm ci` + Vite trong container `web` – không được kế thừa giới hạn 128m của Caddy production
    (bị OOM-kill: phát hiện khi chạy smoke dev 2026-11-18)."""
    prod_web = _load("docker-compose.yml")["services"]["web"]
    dev_web = _load("docker-compose.dev.yml")["services"]["web"]
    limit = dev_web.get("mem_limit", prod_web["mem_limit"])
    assert _mb(limit) >= 1024, limit
