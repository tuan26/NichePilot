#!/usr/bin/env python3
"""Báo cáo truy vết yêu cầu → test (T127, SC-011, Constitution IX).

- Đọc FR/SC từ spec.md (FR có từ "MUST" = mức Must).
- Quét test case dạng `TC_<REQ>_<nn>` / `TC-<REQ>-<nn>` (ví dụ `TC_FR033_01` → FR-033)
  trong backend/frontend/deploy tests.
- Tách test tự động (mock / không gọi API thật) và test live (gọi API thật, chỉ chạy thủ công).
- `--strict`: thoát mã 1 nếu có FR mức Must chưa có test tự động nào.

Chỉ dùng thư viện chuẩn: `python scripts/traceability_report.py [--strict] [--out report.md]`.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SPEC = ROOT / "specs" / "001-foundation-ai-infrastructure" / "spec.md"
DEFAULT_TEST_DIRS = [ROOT / "backend" / "tests", ROOT / "frontend" / "tests", ROOT / "deploy" / "tests"]
REQ_LINE = re.compile(r"^- \*\*((?:FR|SC)-\d+[a-z]?)\*\*:\s*(.*)$")
TC_RE = re.compile(r"TC[_-](FR|SC)-?(\d{3}[a-z]?)[_-]([0-9A-Za-z]+)")
TEST_SUFFIXES = {".py", ".ts", ".tsx", ".sh"}


@dataclass
class Requirement:
    req_id: str
    text: str
    must: bool
    auto_tests: set[str] = field(default_factory=set)
    live_tests: set[str] = field(default_factory=set)


def parse_spec(spec: Path) -> dict[str, Requirement]:
    reqs: dict[str, Requirement] = {}
    current: Requirement | None = None
    for line in spec.read_text(encoding="utf-8").splitlines():
        m = REQ_LINE.match(line)
        if m:
            current = Requirement(m.group(1), m.group(2), must=False)
            reqs[current.req_id] = current
        elif current is not None and line.startswith("  ") and line.strip():
            current.text += " " + line.strip()
        else:
            current = None
    for r in reqs.values():
        r.must = r.req_id.startswith("FR-") and "MUST" in r.text
    return reqs


def scan_tests(dirs: list[Path]) -> list[tuple[str, str, bool]]:
    """Trả về (req_id, test_case_id, is_live)."""
    found: list[tuple[str, str, bool]] = []
    for d in dirs:
        if not d.is_dir():
            continue
        for path in sorted(d.rglob("*")):
            if path.suffix not in TEST_SUFFIXES or "node_modules" in path.parts or "__pycache__" in path.parts:
                continue
            is_live = "live" in path.relative_to(d).parts
            for m in TC_RE.finditer(path.read_text(encoding="utf-8", errors="ignore")):
                req = f"{m.group(1)}-{m.group(2)}"
                found.append(
                    (req, f"{m.group(0)} ({path.relative_to(ROOT) if path.is_relative_to(ROOT) else path})", is_live)
                )
    return found


def build(spec: Path, dirs: list[Path]) -> tuple[dict[str, Requirement], set[str]]:
    reqs = parse_spec(spec)
    unknown: set[str] = set()
    for req, tc, is_live in scan_tests(dirs):
        r = reqs.get(req)
        if r is None:
            unknown.add(req)
            continue
        (r.live_tests if is_live else r.auto_tests).add(tc)
    return reqs, unknown


def render(reqs: dict[str, Requirement], unknown: set[str]) -> str:
    must = [r for r in reqs.values() if r.must]
    covered = [r for r in must if r.auto_tests]
    lines = [
        "# Báo cáo truy vết yêu cầu → test (E0)",
        "",
        f"- FR mức Must: {len(must)}; có test tự động: {len(covered)}; thiếu: {len(must) - len(covered)}",
        "- Test tự động chạy với MockAIProvider/transport giả lập – KHÔNG chứng minh tích hợp provider thật.",
        "- Cột *Live* chỉ liệt kê test live đã viết; kết quả live nằm trong live-results.jsonl"
        " (nếu đã được phép chạy).",
        "",
        "| Yêu cầu | Must | Test tự động | Test live | Trạng thái |",
        "|---|---|---|---|---|",
    ]
    for r in sorted(reqs.values(), key=lambda x: (x.req_id[:2], x.req_id)):
        status = "COVERED" if r.auto_tests else ("LIVE_ONLY" if r.live_tests else "MISSING")
        lines.append(
            f"| {r.req_id} | {'Có' if r.must else ''} | {len(r.auto_tests)} | {len(r.live_tests)} | {status} |"
        )
    if unknown:
        lines += ["", f"Mã test tham chiếu yêu cầu không có trong spec: {', '.join(sorted(unknown))}"]
    missing = [r.req_id for r in must if not r.auto_tests]
    lines += ["", "## FR mức Must chưa có test tự động", "", ", ".join(missing) if missing else "Không có."]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    ap.add_argument("--tests", type=Path, action="append", help="thư mục test (lặp lại được)")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--strict", action="store_true", help="thoát 1 nếu FR Must thiếu test tự động")
    args = ap.parse_args(argv)
    reqs, unknown = build(args.spec, args.tests or DEFAULT_TEST_DIRS)
    report = render(reqs, unknown)
    if args.out:
        args.out.write_text(report, encoding="utf-8")
    print(report)
    missing = [r for r in reqs.values() if r.must and not r.auto_tests]
    return 1 if args.strict and missing else 0


if __name__ == "__main__":
    sys.exit(main())
