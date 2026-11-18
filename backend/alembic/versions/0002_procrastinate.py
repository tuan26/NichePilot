"""0002_procrastinate – schema hàng đợi Procrastinate 3.11.0 (R-01).

Dùng bản SQL đã vendor (`sql/procrastinate_3_11_0_schema.sql`, SHA-256
d1f91ba563f92376c631a7d88cb54a5fdc849d5ff104fcc6d157a8a1227f779f) để migration không phụ thuộc phiên bản gói
đang cài. Nâng cấp Procrastinate = thêm revision mới áp dụng file migration SQL tương ứng của gói.

Revision ID: 0002_procrastinate
Revises: 0001_core
"""

from __future__ import annotations

from pathlib import Path

from alembic import op

revision = "0002_procrastinate"
down_revision = "0001_core"
branch_labels = None
depends_on = None

SCHEMA_SQL = Path(__file__).with_name("sql") / "procrastinate_3_11_0_schema.sql"


def _raw_execute(sql: str) -> None:
    # Thực thi trực tiếp qua psycopg (không qua tham số hóa) vì SQL chứa `%`, `::` và khối DO $$.
    dbapi_conn = op.get_bind().connection.driver_connection
    dbapi_conn.execute(sql)  # type: ignore[union-attr]


def upgrade() -> None:
    _raw_execute(SCHEMA_SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    _raw_execute(
        """
        DROP TABLE IF EXISTS procrastinate_events, procrastinate_periodic_defers,
            procrastinate_jobs, procrastinate_workers CASCADE;
        DO $$
        DECLARE fn record;
        BEGIN
            FOR fn IN
                SELECT p.oid::regprocedure AS sig FROM pg_proc p
                JOIN pg_namespace n ON n.oid = p.pronamespace
                WHERE n.nspname = 'public' AND p.proname LIKE 'procrastinate\\_%'
            LOOP
                EXECUTE 'DROP FUNCTION IF EXISTS ' || fn.sig || ' CASCADE';
            END LOOP;
        END $$;
        DROP TYPE IF EXISTS procrastinate_job_to_defer_v1, procrastinate_job_event_type,
            procrastinate_job_status CASCADE;
        """
    )
