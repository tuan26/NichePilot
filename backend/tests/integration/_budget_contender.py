"""Tiến trình con cho test tranh chấp ngân sách (T021). Chạy 10 coroutine reserve() đồng thời."""

from __future__ import annotations

import asyncio
import sys
import uuid
from decimal import Decimal


async def _main(db_url: str, job_id: str, amount: str, n: int) -> None:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from nichepilot.ai.budget import BudgetExceededError, BudgetService

    engine = create_async_engine(db_url, pool_size=n, max_overflow=0)
    svc = BudgetService(async_sessionmaker(engine, expire_on_commit=False))

    async def one() -> str:
        try:
            await svc.reserve(uuid.UUID(job_id), Decimal(amount), "MOCK", call_timeout_s=60)
            return "OK"
        except BudgetExceededError as e:
            return e.scope

    results = await asyncio.gather(*(one() for _ in range(n)))
    await engine.dispose()
    print(",".join(results))


if __name__ == "__main__":
    asyncio.run(_main(sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])))
