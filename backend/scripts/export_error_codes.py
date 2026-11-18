"""Xuất danh mục mã lỗi cho frontend (T040 – FR-061). Chạy: uv run python scripts/export_error_codes.py"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from nichepilot.core.errors import ERROR_CATALOG  # noqa: E402


def main() -> None:
    out = ROOT / "frontend" / "src" / "api" / "error-codes.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    data = {code: {"status": spec.status, "title": spec.title} for code, spec in sorted(ERROR_CATALOG.items())}
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Đã ghi {len(data)} mã lỗi vào {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
