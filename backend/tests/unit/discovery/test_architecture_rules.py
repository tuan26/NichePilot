"""T125 – Quy tắc kiến trúc E1 (FR-028, FR-012b, FR-006d, FR-006f) – kiểm tra tĩnh trên mã nguồn.

- Không model ID hard-code trong `modules/discovery` và `jobs/agents/niche_*` (chỉ task type – Model Task Profile E0).
- Văn bản ngoài chỉ vào prompt qua cổng `ensure_ai_safe` (RedactedText REDACTED) trong agent.
- Không import `crawl4ai`, `playwright_stealth`, `patchright` ở bất kỳ đâu (quyết định I1).
- Chỉ `SourcePolicyService.update_policy` được ghi `compliance_status`/`enabled` của `source_policies`.
- Không có định danh `include_unverified`/`acknowledge_warning`/`confirm_warning` trong mã E1 (quyết định A1).
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.discovery
SRC = Path(__file__).resolve().parents[3] / "src" / "nichepilot"
FRONT = Path(__file__).resolve().parents[4] / "frontend" / "src"
E1_FILES = [
    *sorted((SRC / "modules" / "discovery").rglob("*.py")),
    *sorted((SRC / "jobs" / "agents").glob("niche_*.py")),
    SRC / "api" / "v1" / "discovery.py",
    SRC / "discovery_wiring.py",
    *sorted((SRC / "tools").rglob("*.py")),
]
MODEL_RE = re.compile(r"""["'](claude-[a-z0-9.-]+|gpt-[a-z0-9.-]+|o[134]-[a-z0-9-]+|gemini-[a-z0-9.-]+)["']""")


def _code_strings(path: Path) -> list[str]:
    """Chuỗi trong mã (bỏ docstring/comment)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {
        id(n.body[0].value)
        for n in ast.walk(tree)
        if isinstance(n, ast.Module | ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
        and n.body
        and isinstance(n.body[0], ast.Expr)
        and isinstance(n.body[0].value, ast.Constant)
    }
    return [
        n.value
        for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings
    ]


def test_TC_E1_FR028_02_no_hardcoded_model_ids_in_e1_business_logic() -> None:
    offenders = [f"{p.relative_to(SRC)}: {s}" for p in E1_FILES for s in _code_strings(p) if MODEL_RE.search(f'"{s}"')]
    assert offenders == []


def test_TC_E1_FR012b_04_prompt_text_only_through_redacted_gate() -> None:
    src = (SRC / "jobs" / "agents" / "niche_discovery.py").read_text(encoding="utf-8")
    assert "ensure_ai_safe(" in src and "wrap_untrusted(" in src
    tree = ast.parse(src)
    for fn in ast.walk(tree):
        if isinstance(fn, ast.AsyncFunctionDef) and fn.name in ("_extract", "_assess"):
            body = ast.unparse(fn)
            assert "_active_excerpts" in body, fn.name  # chỉ trích đoạn đã qua cổng REDACTED
            assert "page[" not in body and "segments" not in body, fn.name  # không đưa nội dung trang thô vào prompt


def test_TC_E1_FR006f_02_no_stealth_or_crawl4ai_imports() -> None:
    banned = ("crawl4ai", "playwright_stealth", "patchright")
    offenders: list[str] = []
    for p in sorted(SRC.rglob("*.py")):
        for node in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else []
            )
            offenders += [f"{p.relative_to(SRC)}: {n}" for n in names if n.split(".")[0] in banned]
    assert offenders == []
    lock = (SRC.parents[1] / "uv.lock").read_text(encoding="utf-8")
    assert not any(f'name = "{b}"' in lock or f'name = "{b.replace("_", "-")}"' in lock for b in banned)


def test_TC_E1_FR006d_04_only_update_policy_writes_compliance_and_enabled() -> None:
    write_re = re.compile(r"UPDATE\s+source_policies\s+SET[^\"']*\b(compliance_status|enabled)\s*=", re.I)
    offenders = []
    for p in sorted(SRC.rglob("*.py")):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if write_re.search(line) and "write-ok: update_policy" not in line:
                offenders.append(f"{p.relative_to(SRC)}:{i}")
    assert offenders == []


def test_TC_E1_FR006d_05_no_unverified_or_warning_bypass_identifiers() -> None:
    banned = re.compile(r"include_unverified|acknowledge_warning|confirm_warning|allow_unverified")
    files = [*E1_FILES, *sorted(FRONT.rglob("*.ts")), *sorted(FRONT.rglob("*.tsx"))]
    offenders = [str(p) for p in files if banned.search(p.read_text(encoding="utf-8"))]
    assert offenders == []
