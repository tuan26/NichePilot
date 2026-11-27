"""0012_products_seed – dữ liệu khởi tạo E2 (T013; data-model §2; scoring-rubric; Clarification Q2 2026-11-27).

- Phiên bản trọng số sản phẩm v1: fit 25, affiliate 25, eligibility 20, quality 15, price_fit 15; Coverage 60%; rubric ngưỡng mức;
  tham số Confidence; mẫu truy vấn xác định (research R-02); tên miền không phải website chính thức (research R-04).
- Model Task Profile cho 3 task type E2: model seed `verified = false` từ 0005 – gọi có phí vẫn bị chặn.

Revision ID: 0012_products_seed
Revises: 0011_products
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "0012_products_seed"
down_revision = "0011_products"
branch_labels = None
depends_on = None

WEIGHTS_V1 = {"fit": 25, "affiliate": 25, "eligibility": 20, "quality": 15, "price_fit": 15}
RUBRIC_V1 = {
    "formula_version": 1,
    "affiliate": {
        "rate_levels": [[30, 100], [20, 75], [10, 50], [5, 25]],
        "fixed_amount_levels": [[50, 75], [20, 50], [5, 25]],
        "up_to_penalty": 25,
        "recurring_bonus": 25,
        "recurring_min_months": 6,
        "short_cookie_days": 30,
        "short_cookie_penalty": 25,
    },
    "eligibility": {"max_restrictions_for_full": 1, "inferred_cap": 50},
    "quality": {"min_features": 3},
    "fit": {"no_match_cap": 25},
}
CONFIDENCE_PARAMS = {
    "weights": {"A": 0.30, "D": 0.20, "F": 0.15, "K": 0.15, "V": 0.20},
    "domain_target": 4,
    "freshness_days": 365,
    "formula_version": 1,
}
QUERY_TEMPLATES = {
    "max_pain_points": 3,
    "niche": ["{pain_point} {segment} tool", "best {kind} for {segment}"],
    "product": ["{product} pricing", "{product} affiliate program"],
}
NON_OFFICIAL_DOMAINS = [
    "amazon.com",
    "ebay.com",
    "walmart.com",
    "etsy.com",
    "g2.com",
    "capterra.com",
    "trustpilot.com",
    "reddit.com",
    "youtube.com",
    "medium.com",
    "producthunt.com",
    "wikipedia.org",
]
PROFILES = [
    # task_type, model, effort, max_output_tokens – model chỉ là dữ liệu cấu hình (không hard-code trong nghiệp vụ)
    ("products.extract", "claude-haiku-5-5", "low", 6000),
    ("products.program_extract", "claude-haiku-5-5", "low", 6000),
    ("products.assess", "claude-sonnet-5-5", "medium", 4096),
]


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO product_scoring_weights (version, weights, rubric, coverage_min, confidence_params,"
            " query_templates, non_official_domains, is_active) VALUES (1, CAST(:w AS jsonb), CAST(:r AS jsonb), 60,"
            " CAST(:c AS jsonb), CAST(:q AS jsonb), :n, true)"
        ),
        {
            "w": json.dumps(WEIGHTS_V1),
            "r": json.dumps(RUBRIC_V1),
            "c": json.dumps(CONFIDENCE_PARAMS),
            "q": json.dumps(QUERY_TEMPLATES),
            "n": NON_OFFICIAL_DOMAINS,
        },
    )
    for task_type, model, effort, max_out in PROFILES:
        bind.execute(
            sa.text(
                "INSERT INTO model_task_profiles (task_type, provider, model, effort, max_output_tokens) "
                "VALUES (:t, 'anthropic', :m, :e, :x)"
            ),
            {"t": task_type, "m": model, "e": effort, "x": max_out},
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM model_task_profiles WHERE task_type = ANY(:t)"), {"t": [p[0] for p in PROFILES]})
    bind.execute(sa.text("DELETE FROM product_scoring_weights"))
