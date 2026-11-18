"""T019 – Ranh giới module bằng import-linter (FR-001, FR-025)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]


def test_TC_FR001_01_import_contracts_hold() -> None:
    lint_imports = Path(sys.executable).parent / "lint-imports"
    proc = subprocess.run(  # noqa: S603 – lệnh cố định, không có input ngoài
        [str(lint_imports), "--config", str(BACKEND_DIR / ".importlinter")],
        cwd=BACKEND_DIR,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Contracts: " in proc.stdout
    assert " broken" not in proc.stdout.split("Contracts:")[-1].replace("0 broken", "")


def test_TC_FR025_01_contract_file_declares_required_contracts() -> None:
    cfg = (BACKEND_DIR / ".importlinter").read_text()
    assert "nichepilot.jobs.agents" in cfg
    assert "nichepilot.ai.providers" in cfg
    assert "layers" in cfg
