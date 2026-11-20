"""T018 – SourcePolicyService (FR-006d, SC-017; quyết định A1).

- usable_for_run() chỉ trả nguồn enabled ∧ ALLOWED cho MỌI loại lượt; không có tham số đưa nguồn khác vào.
- Test kiến trúc: chỉ `update_policy` được ghi compliance_status/enabled (không có đường tự bật/tự nâng trạng thái).
"""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path

import pytest

from nichepilot.modules.discovery.sources import policy as policy_mod
from nichepilot.modules.discovery.sources.policy import SourcePolicyService, UsableSourcePolicy

pytestmark = pytest.mark.discovery
SRC = Path(__file__).resolve().parents[3] / "src" / "nichepilot"


def test_TC_E1_FR006d_02_usable_for_run_has_no_bypass_parameter() -> None:
    params = list(inspect.signature(SourcePolicyService.usable_for_run).parameters)
    assert params == ["self"]
    with pytest.raises(TypeError):
        UsableSourcePolicy(object(), None)  # type: ignore[arg-type]  # chỉ service tạo được (kiểu đóng)


WRITE_SQL = re.compile(r"\b(UPDATE\s+source_policies|INSERT\s+INTO\s+source_policies)\b", re.I)
SCAN = [SRC / "modules" / "discovery", SRC / "jobs" / "agents", SRC / "api" / "v1" / "discovery.py"]


def _writers() -> set[tuple[str, str]]:
    """(file, function) có câu SQL ghi source_policies hoặc gán thuộc tính compliance_status/enabled."""
    found: set[tuple[str, str]] = set()
    files = [p for root in SCAN if root.exists() for p in ([root] if root.is_file() else root.rglob("*.py"))]
    for path in files:
        if path.name == "models.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            for node in ast.walk(fn):
                hit = (
                    isinstance(node, ast.Constant) and isinstance(node.value, str) and WRITE_SQL.search(node.value)
                ) or (
                    isinstance(node, ast.Assign | ast.AugAssign)
                    and any(
                        isinstance(t, ast.Attribute) and t.attr in {"compliance_status", "enabled"}
                        for t in (node.targets if isinstance(node, ast.Assign) else [node.target])
                    )
                )
                if hit:
                    found.add((path.name, fn.name))
    return found


def test_TC_E1_SC017_01_only_update_policy_writes_status_or_enabled() -> None:
    assert _writers() <= {("policy.py", "update_policy"), ("policy.py", "create_policy")}
    create_src = inspect.getsource(policy_mod.SourcePolicyService.create_policy)
    assert "'UNVERIFIED'" in create_src and "false" in create_src  # nguồn mới luôn UNVERIFIED, tắt
    for name in ("enable", "auto_enable", "promote", "bypass", "acknowledge_warning", "include_unverified"):
        assert not hasattr(SourcePolicyService, name)
