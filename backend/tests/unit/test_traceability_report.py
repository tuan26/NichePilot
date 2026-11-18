"""T127 – Test cho script báo cáo truy vết (SC-011)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "traceability_report.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("traceability_report", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["traceability_report"] = mod
    spec.loader.exec_module(mod)
    return mod


P = "T" + "C"  # ghép lúc chạy để script truy vết không đếm chuỗi mẫu trong file này là test thật

SPEC = """# Spec
- **FR-001**: Hệ thống MUST làm A.
- **FR-002**: Hệ thống MUST làm B,
  tiếp dòng.
- **FR-019c**: Hệ thống MUST chặn gọi có phí.
- **FR-073**: Hệ thống SHOULD backup.
- **SC-003**: Job thật thành công.
"""


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    spec = tmp_path / "spec.md"
    spec.write_text(SPEC, encoding="utf-8")
    tests = tmp_path / "tests"
    (tests / "unit").mkdir(parents=True)
    (tests / "live").mkdir()
    (tests / "unit" / "test_a.py").write_text(f"def test_{P}_FR001_01(): ...\ndef test_{P}_FR019c_02(): ...\n")
    (tests / "unit" / "b.spec.ts").write_text(f"test('{P}-FR073-01 backup', () => {{}})\n// {P}-FR999-01\n")
    (tests / "live" / "test_live.py").write_text(f"def test_{P}_SC003_L1(): ...\ndef test_{P}_FR002_L1(): ...\n")
    return spec, tests


def test_TC_SC011_01_parse_and_classify(tmp_path: Path) -> None:
    mod = _load()
    spec, tests = _fixture(tmp_path)
    reqs, unknown = mod.build(spec, [tests])
    assert {k for k, r in reqs.items() if r.must} == {"FR-001", "FR-002", "FR-019c"}  # SHOULD và SC không là Must
    assert len(reqs["FR-001"].auto_tests) == 1 and len(reqs["FR-019c"].auto_tests) == 1
    assert len(reqs["FR-002"].auto_tests) == 0 and len(reqs["FR-002"].live_tests) == 1  # live tách riêng
    assert len(reqs["SC-003"].live_tests) == 1 and len(reqs["FR-073"].auto_tests) == 1
    assert unknown == {"FR-999"}
    report = mod.render(reqs, unknown)
    assert "| FR-002 | Có | 0 | 1 | LIVE_ONLY |" in report


def test_TC_SC011_02_strict_fails_when_must_missing_auto_test(tmp_path: Path) -> None:
    mod = _load()
    spec, tests = _fixture(tmp_path)
    out = tmp_path / "r.md"
    assert mod.main(["--spec", str(spec), "--tests", str(tests), "--strict", "--out", str(out)]) == 1
    assert "FR-002" in out.read_text(encoding="utf-8").split("chưa có test tự động", 1)[1]
    (tests / "unit" / "test_c.py").write_text(f"def test_{P}_FR002_01(): ...\n")
    assert mod.main(["--spec", str(spec), "--tests", str(tests), "--strict"]) == 0


def test_TC_SC011_03_clause_ids_map_to_parent_requirement(tmp_path: Path) -> None:
    """Mã có hậu tố chữ (mục f của FR-018) là mục của FR-018 (không phải yêu cầu riêng) → tính cho FR-018."""
    mod = _load()
    spec = tmp_path / "spec.md"
    spec.write_text("- **FR-018**: Mock MUST: (f) kiểm tra cấu hình; (g) mặc định REAL.\n- **FR-019c**: MUST chặn.\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_x.py").write_text(
        f"def test_{P}_FR018f_01(): ...\ndef test_{P}_FR018g_02(): ...\ndef test_{P}_FR019c_01(): ...\n"
    )
    reqs, unknown = mod.build(spec, [tests])
    assert unknown == set()
    assert len(reqs["FR-018"].auto_tests) == 2
    assert any("FR-018(f)" in t for t in reqs["FR-018"].auto_tests)
    assert len(reqs["FR-019c"].auto_tests) == 1  # FR-019c là bullet thật, không gộp vào FR-019
