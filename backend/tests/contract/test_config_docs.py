"""T124 – Tài liệu/cấu hình đồng bộ (FR-071): biến môi trường mẫu ↔ hợp đồng cấu hình; tài liệu vận hành tồn tại."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
ENV_EXAMPLE = ROOT / "deploy" / "env" / ".env.example"
CONFIG_DOC = ROOT / "specs" / "001-foundation-ai-infrastructure" / "contracts" / "configuration.md"
OPS_DOCS = ["README.md", "windows-setup.md", "troubleshooting.md", "backup-restore.md", "enable-real-api.md"]


def _env_vars() -> set[str]:
    names = set()
    for line in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^([A-Z][A-Z0-9_]*)=", line)
        if m:
            names.add(m.group(1))
    return names


def _documented_vars() -> set[str]:
    text = CONFIG_DOC.read_text(encoding="utf-8")
    section = text.split("## Biến môi trường", 1)[1].split("\n## ", 1)[0]
    return set(re.findall(r"^\| `([A-Z][A-Z0-9_]*)` \|", section, flags=re.M))


def test_TC_FR071_01_env_example_matches_configuration_contract() -> None:
    env, documented = _env_vars(), _documented_vars()
    assert env, "không đọc được .env.example"
    assert sorted(env - documented) == [], "biến có trong .env.example nhưng thiếu trong configuration.md"
    assert sorted(documented - env) == [], "biến có trong configuration.md nhưng thiếu trong .env.example"


def test_TC_FR054_20_env_example_has_no_real_secrets() -> None:
    text = ENV_EXAMPLE.read_text(encoding="utf-8")
    assert re.search(r"^ANTHROPIC_API_KEY=$", text, flags=re.M)
    assert re.search(r"^OPENAI_API_KEY=$", text, flags=re.M)
    assert re.search(r"^AI_PAID_CALLS_ENABLED=false$", text, flags=re.M)
    assert not re.search(r"sk-(ant|proj)-[A-Za-z0-9]", text)


@pytest.mark.parametrize("name", OPS_DOCS)
def test_TC_FR071_02_operations_docs_exist(name: str) -> None:
    path = ROOT / "docs" / "operations" / name
    assert path.is_file(), f"thiếu {path}"
    assert len(path.read_text(encoding="utf-8").strip()) > 200, f"{name} gần như rỗng"
