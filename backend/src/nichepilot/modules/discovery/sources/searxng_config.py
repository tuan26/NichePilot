"""Sinh `settings.yml` của SearXNG từ nguồn ALLOWED đang bật (FR-006g, FR-006d; research R-02).

`keep_only` = engine của nguồn `searxng_engine` đang bật và ALLOWED; rỗng → SearXNG không truy vấn engine nào.
`plugins: {}` luôn giữ nguyên (plugin tracker_url_remover tự tải dữ liệu từ Internet). Không cần sửa code để thêm nguồn.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterable
from pathlib import Path

import yaml


def render_settings(base_yaml: str, engine_names: Iterable[str]) -> str:
    cfg = yaml.safe_load(base_yaml) or {}
    cfg.setdefault("use_default_settings", {}).setdefault("engines", {})["keep_only"] = sorted(set(engine_names))
    cfg["plugins"] = {}
    server = cfg.setdefault("server", {})
    server["limiter"] = False
    server["public_instance"] = False
    server["image_proxy"] = False
    server.pop("secret_key", None)  # secret chỉ qua SEARXNG_SECRET
    header = "# Sinh tự động bởi NichePilot từ source_policies (chỉ nguồn ALLOWED đang bật). KHÔNG sửa tay.\n"
    return header + str(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))


def write_settings(config_dir: Path, base_path: Path, engine_names: Iterable[str]) -> bool:
    """Ghi nguyên tử; trả True nếu nội dung đổi (cần khởi động lại service `searxng`)."""
    content = render_settings(base_path.read_text(encoding="utf-8"), engine_names)
    target = config_dir / "settings.yml"
    if target.is_file() and target.read_text(encoding="utf-8") == content:
        return False
    config_dir.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=config_dir, prefix=".settings.", suffix=".yml")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, target)
    return True
