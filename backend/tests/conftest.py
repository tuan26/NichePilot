"""Hạ tầng test dùng chung (T023).

- PostgreSQL 17 thật qua testcontainers (hoặc `NICHEPILOT_TEST_DATABASE_URL` nếu đã có sẵn DB).
- Chặn mọi kết nối mạng ra ngoài ở tầng socket Python: test tự động KHÔNG được gọi provider thật (SC-003b).
- Dữ liệu giả lập chỉ nằm trong thư mục tests/ và được đánh dấu rõ (Constitution I).
"""

from __future__ import annotations

import ipaddress
import os
import socket
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

BACKEND_DIR = Path(__file__).resolve().parents[1]
SEED_SOURCE_KEYS = [
    "searxng:wikipedia",
    "api:stackexchange",
    "api:hn-algolia",
    "searxng:mojeek",
    "searxng:marginalia",
    "searxng:mwmbl",
    "searxng:duckduckgo",
    "searxng:brave",
    "searxng:startpage",
    "searxng:google",
    "searxng:bing",
]
REPO_DIR = BACKEND_DIR.parent
SPEC_DIR = REPO_DIR / "specs" / "001-foundation-ai-infrastructure"

os.environ.setdefault("TESTCONTAINERS_RYUK_DISABLED", "true")

# ---------------------------------------------------------------------------
# Chặn mạng ra ngoài (chỉ cho phép loopback và mạng nội bộ Docker)
# ---------------------------------------------------------------------------
_real_connect = socket.socket.connect


def _is_allowed(address: object) -> bool:
    if isinstance(address, str):  # AF_UNIX (docker.sock)
        return True
    if not isinstance(address, tuple) or not address:
        return True
    host = str(address[0])
    if host in {"localhost", "host.docker.internal"}:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_loopback or ip.is_private


class OutboundNetworkBlockedError(RuntimeError):
    pass


def _guarded_connect(self: socket.socket, address: object) -> None:
    if not _is_allowed(address):
        raise OutboundNetworkBlockedError(f"Test tự động không được kết nối ra ngoài: {address!r}")
    _real_connect(self, address)  # type: ignore[arg-type]


@pytest.fixture(autouse=True, scope="session")
def _block_outbound_network() -> Iterator[None]:
    socket.socket.connect = _guarded_connect  # type: ignore[method-assign]
    yield
    socket.socket.connect = _real_connect  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# PostgreSQL
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def pg_url() -> Iterator[str]:
    """URL dạng SQLAlchemy `postgresql+psycopg://` tới một PostgreSQL 17 trống."""
    preset = os.environ.get("NICHEPILOT_TEST_DATABASE_URL")
    if preset:
        yield preset
        return
    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer("postgres:17-alpine", driver="psycopg") as pg:
        yield pg.get_connection_url()


@pytest.fixture(scope="session")
def migrated_db(pg_url: str) -> str:
    """Áp dụng toàn bộ migration lên DB test một lần cho cả phiên."""
    from alembic import command

    from tests.helpers import alembic_config

    command.upgrade(alembic_config(pg_url), "head")
    return pg_url


@pytest.fixture(scope="session")
async def engine(migrated_db: str) -> AsyncIterator[AsyncEngine]:
    eng = create_async_engine(migrated_db, pool_pre_ping=True)
    yield eng
    await eng.dispose()


# E1 – bảng nghiệp vụ theo thứ tự khóa ngoại (con trước cha). niche_evaluations bất biến (trigger) → dọn riêng.
E1_TABLES = [
    "niche_run_links",
    "niche_similarity",
    "niche_evidence_links",
    "niche_findings",
    "pain_points",
    "buyer_personas",
    "competitors",
    "page_fetch_log",
    "evidence_erasure_requests",
    "domain_access_state",
]
MUTABLE_TABLES = [
    "research_evidence",
    "research_sources",
    "budget_reservations",
    "ai_usage_logs",
    "tool_executions",
    "job_steps",
    "agent_jobs",
    "job_schedules",
    "auth_sessions",
    "users",
    "audit_logs",
]


@pytest.fixture
async def clean_db(engine: AsyncEngine) -> AsyncIterator[AsyncEngine]:
    """Làm sạch dữ liệu vận hành sau mỗi test, GIỮ NGUYÊN seed (projects, settings, ai_models…). Chỉ dùng trong test.

    Xóa bằng DELETE theo thứ tự khóa ngoại để hành động FK (ví dụ settings.updated_by SET NULL) chạy đúng;
    không dùng TRUNCATE … CASCADE vì sẽ lan sang bảng seed.
    """
    yield engine
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
        existing = set(result.scalars())  # đọc trọn một lần
        if "niches" in existing:
            for table in E1_TABLES:
                await conn.execute(text(f"DELETE FROM {table}"))  # noqa: S608 – tên bảng là hằng số
            await conn.execute(text("UPDATE niches SET latest_evaluation_id = NULL"))
            await conn.execute(text("ALTER TABLE niche_evaluations DISABLE TRIGGER trg_niche_evaluations_immutable"))
            await conn.execute(text("DELETE FROM niche_evaluations"))
            await conn.execute(text("ALTER TABLE niche_evaluations ENABLE TRIGGER trg_niche_evaluations_immutable"))
            await conn.execute(text("DELETE FROM niches WHERE merged_into_id IS NOT NULL"))
            await conn.execute(text("DELETE FROM niches"))
            await conn.execute(text("DELETE FROM discovery_runs"))
            await conn.execute(text("DELETE FROM research_evidence"))
            await conn.execute(text("DELETE FROM research_sources"))
            # giữ seed: nguồn S1–S11 về UNVERIFIED/tắt, xóa nguồn do test tạo; trọng số về v1; sổ xóa về trạng thái đầu
            await conn.execute(
                text(
                    "UPDATE source_policies SET compliance_status = 'UNVERIFIED', enabled = false, verified_at = NULL,"
                    " verified_by = NULL, verification_note = NULL, allowed_access_methods = '{}',"
                    " permitted_use_scope = NULL, updated_by = NULL WHERE source_key = ANY(:k)"
                ),
                {"k": SEED_SOURCE_KEYS},
            )
            await conn.execute(
                text("DELETE FROM source_policies WHERE NOT (source_key = ANY(:k))"), {"k": SEED_SOURCE_KEYS}
            )
            await conn.execute(text("DELETE FROM scoring_weights_versions WHERE version > 1"))
            await conn.execute(text("UPDATE scoring_weights_versions SET is_active = true, created_by = NULL"))
            await conn.execute(
                text(
                    "UPDATE erasure_ledger_state SET ledger_id = NULL, applied_seq = 0, applied_hash = NULL,"
                    " status = 'OK', last_error = NULL, checked_at = NULL"
                )
            )
        for table in MUTABLE_TABLES:
            if table in existing and table != "audit_logs":
                await conn.execute(text(f"DELETE FROM {table}"))  # noqa: S608 – tên bảng là hằng số
        # audit_logs append-only: chỉ test được phép tắt trigger để dọn dữ liệu.
        await conn.execute(text("SET LOCAL session_replication_role = replica"))
        await conn.execute(text("TRUNCATE audit_logs"))
        await conn.execute(text("TRUNCATE procrastinate_jobs CASCADE"))


# ---------------------------------------------------------------------------
# E1 – marker chạy riêng (T007). Test bị bỏ qua có lý do bắt đầu "BLOCKED:" được báo cáo là BLOCKED, KHÔNG PASS.
# ---------------------------------------------------------------------------
OPT_IN_MARKERS = {
    "live_sources": "NICHEPILOT_RUN_LIVE_SOURCES",
    "perf": "NICHEPILOT_RUN_PERF",
    "pii_ner": "NICHEPILOT_RUN_PII_NER",
    "browser": "NICHEPILOT_RUN_BROWSER",
}
BLOCKED_PREFIX = "BLOCKED:"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    for item in items:
        for marker, env in OPT_IN_MARKERS.items():
            if item.get_closest_marker(marker) and os.environ.get(env) != "1":
                reason = (
                    f"{BLOCKED_PREFIX} test nguồn thật chỉ chạy thủ công ({env}=1) và cần nguồn ALLOWED"
                    if marker == "live_sources"
                    else f"chạy riêng: đặt {env}=1"
                )
                item.add_marker(pytest.mark.skip(reason=reason))


def pytest_terminal_summary(terminalreporter: object, exitstatus: int, config: pytest.Config) -> None:
    stats = getattr(terminalreporter, "stats", {})
    blocked = [r for r in stats.get("skipped", []) if BLOCKED_PREFIX in str(getattr(r, "longrepr", ""))]
    if blocked:
        terminalreporter.write_line(  # type: ignore[attr-defined]
            f"BLOCKED (không phải PASS): {len(blocked)} test – xem lý do 'BLOCKED:' trong báo cáo skip"
        )
