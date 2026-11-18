#!/usr/bin/env python3
"""Kiểm tra secret bằng detect-secrets so với baseline đã rà soát (N1 – SC-008, FR-054).

- Quét bằng cùng plugin/bộ lọc của `.secrets.baseline` (detect-secrets 1.5.0, dev dependency của backend).
- Finding được so khớp theo (file, loại, hashed_secret) – không phụ thuộc số dòng, nên sửa file không làm CI dao động.
- Bất kỳ finding nào CHƯA có trong baseline → thoát mã 1 (secret mới bị chặn).
- Mục baseline phải có `is_secret: false` (đã rà soát); mục không còn xuất hiện chỉ được cảnh báo.

Dùng: `uv run python scripts/check_secrets.py [--root DIR] [--baseline FILE]` (mặc định: gốc repo, `.secrets.baseline`).
Cập nhật baseline: xem docs/operations/security.md – KHÔNG thêm mục chưa rà soát.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASELINE = ROOT / ".secrets.baseline"
# Lockfile: hash toàn vẹn gói (giữ như cấu hình CI trước đây). `.secrets.baseline`: chỉ chứa hashed_secret của các mục
# đã rà soát (detect-secrets cũng tự bỏ qua file baseline khi dùng `--baseline`).
EXCLUDE_FILES = r"(package-lock\.json|uv\.lock|\.secrets\.baseline)$"


def _scan(root: Path) -> dict[str, list[dict[str, Any]]]:
    cmd = [sys.executable, "-m", "detect_secrets", "scan", "--exclude-files", EXCLUDE_FILES]
    if not (root / ".git").exists():
        cmd.append("--all-files")  # thư mục không phải git (test canary) → quét mọi file
    out = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=True).stdout  # noqa: S603
    results: dict[str, list[dict[str, Any]]] = json.loads(out)["results"]
    return results


def _keys(results: dict[str, list[dict[str, Any]]]) -> set[tuple[str, str, str]]:
    return {(f, e["type"], e["hashed_secret"]) for f, items in results.items() for e in items}


def new_findings(root: Path, baseline: Path) -> list[dict[str, Any]]:
    data = json.loads(baseline.read_text(encoding="utf-8"))
    known = _keys(data["results"])
    found = _scan(root)
    return [
        {"filename": f, "type": e["type"], "line_number": e["line_number"]}
        for f, items in sorted(found.items())
        for e in items
        if (f, e["type"], e["hashed_secret"]) not in known
    ]


def unreviewed(baseline: Path) -> list[str]:
    data = json.loads(baseline.read_text(encoding="utf-8"))
    return [
        f"{f}:{e['line_number']}"
        for f, items in data["results"].items()
        for e in items
        if e.get("is_secret") is not False
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="detect-secrets so với baseline đã rà soát")
    ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    args = ap.parse_args(argv)
    pending = unreviewed(args.baseline)
    if pending:
        print("Baseline có mục chưa rà soát (is_secret khác false):", *pending, sep="\n  ")
        return 1
    new = new_findings(args.root, args.baseline)
    if new:
        print("PHÁT HIỆN SECRET MỚI chưa có trong baseline đã rà soát:")
        for n in new:
            print(f"  {n['filename']}:{n['line_number']} [{n['type']}]")
        print("Gỡ secret khỏi mã nguồn (dùng .env/Docker secrets).")
        print("Chỉ cập nhật baseline cho dương tính giả đã rà soát (docs/operations/security.md).")
        return 1
    print("detect-secrets: không có finding mới ngoài baseline đã rà soát.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
