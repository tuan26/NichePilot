"""CLI áp dụng erasure ledger (X4; FR-013f; research R-09): `python -m nichepilot.jobs.erasure_ledger --strict`.

Chạy trong service `migrate` (sau `alembic upgrade head`, trước api/worker) và sau `make restore`. Thoát mã ≠ 0 khi
không áp dụng
đầy đủ được → api/worker không khởi động (Compose `service_completed_successfully`). Log không chứa nội dung bằng chứng.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from nichepilot.core.config import get_settings
from nichepilot.core.db import dispose_db, init_db
from nichepilot.core.discovery_config import get_discovery_settings
from nichepilot.core.logging import configure_logging, get_logger
from nichepilot.modules.discovery.erasure import Ledger, LedgerError, apply_erasure_ledger

log = get_logger(__name__)
EXIT_BLOCKED = 3


async def run(strict: bool) -> int:
    settings = get_settings()
    configure_logging(
        level=settings.log_level, fmt=settings.log_format, log_dir=None, secret_values=settings.secret_values()
    )
    sm = init_db(settings.database_url.get_secret_value())
    ledger = Ledger(get_discovery_settings().erasure_ledger_dir)
    try:
        res = await apply_erasure_ledger(sm, ledger, strict=strict)
        print(json.dumps({"status": "OK", "applied": res.applied, "tail_seq": res.tail_seq}))
        return 0
    except LedgerError as exc:
        print(json.dumps({"status": "BLOCKED", "code": exc.code}), file=sys.stderr)
        print(
            "Erasure ledger chưa được áp dụng – dữ liệu nghiên cứu E1 bị chặn. Xem"
            " docs/operations/discovery.md (Restore).",
            file=sys.stderr,
        )
        return EXIT_BLOCKED
    finally:
        await dispose_db()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--strict", action="store_true", default=True)
    args = ap.parse_args(argv)
    return asyncio.run(run(args.strict))


if __name__ == "__main__":
    sys.exit(main())
