#!/usr/bin/env python3
"""Báo cáo truy vết yêu cầu → test (T127, SC-011, Constitution IX).

- Đọc FR/SC từ spec.md (FR có từ "MUST" = mức Must).
- Quét test case dạng `TC_<REQ>_<nn>` / `TC-<REQ>-<nn>` (ví dụ `TC_FR033_01` → FR-033)
  trong backend/frontend/deploy tests.
- Tách test tự động (mock / không gọi API thật) và test live (gọi API thật, chỉ chạy thủ công).
- Mã có hậu tố chữ không phải bullet riêng (ví dụ `TC_FR018f_04`) được tính cho mục (f) của FR-018.
- `--strict`: thoát mã 1 nếu có FR mức Must chưa có test tự động nào.
- Nhiều spec (E1, T006): spec 001 dùng `TC_FR…/TC_SC…`, spec 002 dùng `TC_E1_FR…/TC_E1_SC…`
  (không lẫn mã giữa các spec).
  Yêu cầu chỉ được tham chiếu bởi task chưa hoàn thành trong tasks.md cạnh spec → `PENDING` (chưa bắt buộc có test);
  khi một task tham chiếu yêu cầu được đánh dấu [X], yêu cầu đó phải có test tự động.
- Test trong thư mục `live/` hoặc `live_sources/` là test thủ công (không tính là tự động; `live_sources` báo BLOCKED
  khi chưa có nguồn ALLOWED).

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
E1_SPEC = ROOT / "specs" / "002-niche-discovery" / "spec.md"
DEFAULT_TEST_DIRS = [ROOT / "backend" / "tests", ROOT / "frontend" / "tests", ROOT / "deploy" / "tests"]
REQ_LINE = re.compile(r"^- \*\*((?:FR|SC)-\d+[a-z]?)\*\*:\s*(.*)$")
TC_RE = re.compile(r"TC[_-](FR|SC)-?(\d{3}[a-z]?)[_-]([0-9A-Za-z]+)")
LIVE_DIRS = {"live", "live_sources"}
TASK_LINE = re.compile(r"^- \[( |x|X)\] T\d{3}")
REQ_REF = re.compile(r"\b((?:FR|SC)-\d{3}[a-z]?)\b")


def tc_pattern(prefix: str) -> re.Pattern[str]:
    """Mẫu mã test của một spec: rỗng = spec 001 (`TC_FR001_01`), `E1` = spec 002 (`TC_E1_FR001_01`)."""
    if not prefix:
        return TC_RE
    return re.compile(rf"TC[_-]{re.escape(prefix)}[_-](FR|SC)-?(\d{{3}}[a-z]?)[_-]([0-9A-Za-z]+)")


@dataclass(frozen=True)
class Profile:
    spec: Path
    prefix: str
    title: str


TEST_SUFFIXES = {".py", ".ts", ".tsx", ".sh"}
CLAUSE_RE = re.compile(r"^((?:FR|SC)-\d{3})([a-z])$")


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


def pending_requirements(tasks: Path) -> set[str]:
    """Yêu cầu PENDING: được tham chiếu trong tasks.md nhưng chưa bắt buộc có test.

    Bắt buộc có test khi (a) một task đã [X] chứa mã test `TC_…` của yêu cầu, hoặc (b) mọi task tham chiếu yêu cầu đã [X].
    Không có tasks.md → rỗng (mọi yêu cầu bắt buộc).
    """
    if not tasks.is_file():
        return set()
    refs_done: set[str] = set()
    refs_open: set[str] = set()
    tested_done: set[str] = set()
    current_done: bool | None = None
    for line in tasks.read_text(encoding="utf-8").splitlines():
        m = TASK_LINE.match(line)
        if m:
            current_done = m.group(1) in "xX"
        elif current_done is None or not (line.startswith("  ") and line.strip()):
            current_done = None
            continue
        target = refs_done if current_done else refs_open
        target.update(REQ_REF.findall(line))
        for kind, num in re.findall(r"TC[_-]\w*?(FR|SC)(\d{3}[a-z]?)[_-]", line):
            target.add(f"{kind}-{num}")
            if current_done:
                tested_done.add(f"{kind}-{num}")
    required = tested_done | (refs_done - refs_open)
    return (refs_done | refs_open) - required


def scan_tests(dirs: list[Path], prefix: str = "") -> list[tuple[str, str, bool]]:
    """Trả về (req_id, test_case_id, is_live)."""
    pattern = tc_pattern(prefix)
    found: list[tuple[str, str, bool]] = []
    for d in dirs:
        if not d.is_dir():
            continue
        for path in sorted(d.rglob("*")):
            if path.suffix not in TEST_SUFFIXES or "node_modules" in path.parts or "__pycache__" in path.parts:
                continue
            is_live = bool(LIVE_DIRS & set(path.relative_to(d).parts))
            for m in pattern.finditer(path.read_text(encoding="utf-8", errors="ignore")):
                req = f"{m.group(1)}-{m.group(2)}"
                found.append(
                    (req, f"{m.group(0)} ({path.relative_to(ROOT) if path.is_relative_to(ROOT) else path})", is_live)
                )
    return found


def build(spec: Path, dirs: list[Path], prefix: str = "") -> tuple[dict[str, Requirement], set[str]]:
    reqs = parse_spec(spec)
    unknown: set[str] = set()
    for req, tc, is_live in scan_tests(dirs, prefix):
        r = reqs.get(req)
        clause = CLAUSE_RE.match(req)
        if r is None and clause and clause.group(1) in reqs:
            # `FR-018(f)` = mục (f) của FR-018 (quy ước ghi trong spec: FR-018(f)), không phải yêu cầu riêng.
            r = reqs[clause.group(1)]
            tc = f"{tc} [{clause.group(1)}({clause.group(2)})]"
        if r is None:
            unknown.add(req)
            continue
        (r.live_tests if is_live else r.auto_tests).add(tc)
    return reqs, unknown


def _missing(reqs: dict[str, Requirement], pending: set[str]) -> list[str]:
    return [r.req_id for r in reqs.values() if r.must and not r.auto_tests and r.req_id not in pending]


def render(
    reqs: dict[str, Requirement], unknown: set[str], *, pending: set[str] | None = None, title: str = "E0"
) -> str:
    pending = pending or set()
    must = [r for r in reqs.values() if r.must]
    covered = [r for r in must if r.auto_tests]
    pend = [r for r in must if not r.auto_tests and r.req_id in pending]
    lines = [
        f"# Báo cáo truy vết yêu cầu → test ({title})",
        "",
        f"- FR mức Must: {len(must)}; có test tự động: {len(covered)}; PENDING (task chưa làm): {len(pend)};"
        f" thiếu: {len(must) - len(covered) - len(pend)}",
        "- Test tự động chạy với MockAIProvider/transport giả lập – KHÔNG chứng minh tích hợp provider thật.",
        "- Cột *Live* chỉ liệt kê test live đã viết; kết quả live nằm trong live-results.jsonl"
        " (nếu đã được phép chạy).",
        "",
        "| Yêu cầu | Must | Test tự động | Test live | Trạng thái |",
        "|---|---|---|---|---|",
    ]
    for r in sorted(reqs.values(), key=lambda x: (x.req_id[:2], x.req_id)):
        if r.auto_tests:
            status = "COVERED"
        elif r.req_id in pending:
            status = "PENDING"
        else:
            status = "LIVE_ONLY" if r.live_tests else "MISSING"
        lines.append(
            f"| {r.req_id} | {'Có' if r.must else ''} | {len(r.auto_tests)} | {len(r.live_tests)} | {status} |"
        )
    if unknown:
        lines += ["", f"Mã test tham chiếu yêu cầu không có trong spec: {', '.join(sorted(unknown))}"]
    missing = _missing(reqs, pending)
    lines += ["", "## FR mức Must chưa có test tự động", "", ", ".join(missing) if missing else "Không có."]
    return "\n".join(lines) + "\n"


DEFAULT_PROFILES = [Profile(DEFAULT_SPEC, "", "E0"), Profile(E1_SPEC, "E1", "E1")]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--spec", type=Path, help="chỉ một spec (mặc định: mọi spec trong DEFAULT_PROFILES)")
    ap.add_argument("--prefix", default="", help="tiền tố mã test của spec (rỗng cho spec 001, E1 cho spec 002)")
    ap.add_argument("--tests", type=Path, action="append", help="thư mục test (lặp lại được)")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--strict", action="store_true", help="thoát 1 nếu FR Must (không PENDING) thiếu test tự động")
    args = ap.parse_args(argv)
    profiles = (
        [Profile(args.spec, args.prefix, args.prefix or args.spec.parent.name)] if args.spec else DEFAULT_PROFILES
    )
    parts: list[str] = []
    failed = False
    for prof in profiles:
        if not prof.spec.is_file():
            continue
        reqs, unknown = build(prof.spec, args.tests or DEFAULT_TEST_DIRS, prof.prefix)
        pending = pending_requirements(prof.spec.parent / "tasks.md")
        parts.append(render(reqs, unknown, pending=pending, title=prof.title))
        failed = failed or bool(_missing(reqs, pending))
    report = "\n".join(parts)
    if args.out:
        args.out.write_text(report, encoding="utf-8")
    print(report)
    return 1 if args.strict and failed else 0


if __name__ == "__main__":
    sys.exit(main())
