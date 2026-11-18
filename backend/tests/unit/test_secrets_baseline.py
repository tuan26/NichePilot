"""N1 – Baseline detect-secrets có kiểm soát (SC-008, FR-054).

- Mọi mục trong `.secrets.baseline` đã được rà soát (`is_secret: false`) và thuộc nhóm dương tính giả đã xác minh.
- Repository hiện tại không có finding mới ngoài baseline.
- Secret MỚI (canary sinh lúc chạy, không commit) vẫn bị phát hiện → kiểm tra thất bại.
"""

from __future__ import annotations

import importlib.util
import json
import secrets
import string
import sys
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[3]
BASELINE = ROOT / ".secrets.baseline"
SCRIPT = ROOT / "backend" / "scripts" / "check_secrets.py"
# Nhóm dương tính giả đã rà soát (xem docs/operations/security.md). Không thêm file mới vào đây khi chưa rà soát.
REVIEWED_FILES = {
    ".specify/integrations/claude.manifest.json",
    ".specify/integrations/speckit.manifest.json",
    ".specify/memory/.constitution-template.json",
    "backend/tests/api_helpers.py",
    "backend/tests/contract/test_auth_session.py",
    "backend/tests/contract/test_auth_setup.py",
    "backend/tests/integration/test_auth_lockout.py",
    "backend/tests/integration/test_job_logs.py",
    "backend/tests/integration/test_no_secret_leak.py",
    "backend/tests/unit/core/test_config.py",
    "backend/tests/unit/core/test_logging.py",
    "deploy/env/.env.example",
    "frontend/src/i18n/locales/en.json",
    "frontend/src/i18n/locales/vi.json",
    "frontend/tests/e2e/us1-auth-i18n.spec.ts",
    "specs/001-foundation-ai-infrastructure/contracts/configuration.md",
}


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_secrets", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_secrets"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_TC_SC008_10_baseline_only_reviewed_false_positives() -> None:
    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    entries = [(f, e) for f, items in data["results"].items() for e in items]
    assert entries, "baseline rỗng – không khớp kết quả rà soát"
    assert {f for f, _ in entries} <= REVIEWED_FILES, "baseline chứa file chưa được rà soát"
    assert all(e.get("is_secret") is False for _, e in entries), (
        "mọi mục phải được đánh dấu đã rà soát (is_secret=false)"
    )
    assert all("hashed_secret" in e and "line_number" in e for _, e in entries)
    # baseline chỉ lưu hash, không lưu giá trị bí mật dạng rõ
    raw = BASELINE.read_text(encoding="utf-8")
    assert "sk-ant-api03" not in raw and "change-me-local-only" not in raw


def test_TC_SC008_11_repository_has_no_new_findings() -> None:
    mod = _load()
    new = mod.new_findings(ROOT, BASELINE)
    assert new == [], new


def test_TC_SC008_12_new_secret_is_detected(tmp_path: Path) -> None:
    """Canary: khóa dạng AWS và chuỗi entropy cao sinh lúc chạy → phải bị phát hiện, kiểm tra trả mã lỗi."""
    mod = _load()
    alphabet = string.ascii_uppercase + string.digits
    aws_like = "AKIA" + "".join(secrets.choice(alphabet) for _ in range(16))
    high_entropy = secrets.token_hex(24)
    (tmp_path / "leak.py").write_text(f'AWS_ACCESS_KEY_ID = "{aws_like}"\napi_token = "{high_entropy}"\n')
    new = mod.new_findings(tmp_path, BASELINE)
    types = {f["type"] for f in new}
    assert "AWS Access Key" in types, new
    assert mod.main(["--root", str(tmp_path), "--baseline", str(BASELINE)]) == 1
