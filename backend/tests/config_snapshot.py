"""Chụp và khôi phục bảng cấu hình (settings, projects, catalog model, giá, profile) giữa các test US6.

`clean_db` chỉ dọn bảng dữ liệu nghiệp vụ; các bảng cấu hình seed phải được trả về nguyên trạng sau test sửa đổi.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

# Thứ tự xóa theo khóa ngoại (con trước cha); khôi phục theo thứ tự ngược lại.
CONFIG_TABLES = ["model_task_profiles", "model_pricing", "ai_models", "settings", "projects"]


async def snapshot(engine: AsyncEngine) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    async with engine.connect() as conn:
        for t in CONFIG_TABLES:
            out[t] = list(
                (await conn.execute(text(f"SELECT COALESCE(jsonb_agg(to_jsonb(x)), '[]') FROM {t} x"))).scalar_one()  # noqa: S608
            )
    return out


async def restore(engine: AsyncEngine, snap: dict[str, list[dict[str, Any]]]) -> None:
    async with engine.begin() as conn:
        for t in CONFIG_TABLES:
            ids = [r["id"] for r in snap[t]]
            await conn.execute(
                text(f"DELETE FROM {t} WHERE NOT (id = ANY(CAST(:ids AS uuid[])))"),  # noqa: S608
                {"ids": ids},
            )
        for t in reversed(CONFIG_TABLES):
            cols = [
                r[0]
                for r in (
                    await conn.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns WHERE table_name = :t AND column_name <> 'id'"
                        ),
                        {"t": t},
                    )
                ).all()
            ]
            col_list = ", ".join(cols)
            for row in snap[t]:
                await conn.execute(
                    text(
                        f"UPDATE {t} SET ({col_list}) = (SELECT {col_list} FROM jsonb_populate_record(NULL::{t},"  # noqa: S608
                        " CAST(:r AS jsonb))) WHERE id = CAST(:id AS uuid)"
                    ),
                    {"r": json.dumps(row), "id": row["id"]},
                )
