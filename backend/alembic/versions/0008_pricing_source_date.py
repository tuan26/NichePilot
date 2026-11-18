"""0008_pricing_source_date – giá đã xác minh phải có nguồn chính thức và ngày xác minh (C3, FR-041, FR-019c).

Revision ID: 0008_pricing_source_date
Revises: 0007_evidence
"""

from __future__ import annotations

from alembic import op

revision = "0008_pricing_source_date"
down_revision = "0007_evidence"
branch_labels = None
depends_on = None

CONDITION = (
    "provider = 'mock' OR NOT verified OR "
    "(source_note ~ 'https?://[^[:space:]]+' AND source_note ~ '[0-9]{4}-[0-9]{2}-[0-9]{2}')"
)


def upgrade() -> None:
    op.create_check_constraint(op.f("ck_model_pricing_verified_source_date"), "model_pricing", CONDITION)


def downgrade() -> None:
    op.drop_constraint(op.f("ck_model_pricing_verified_source_date"), "model_pricing", type_="check")
