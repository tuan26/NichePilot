"""0014_keywords_seed – dữ liệu khởi tạo E3 (T011; scoring-rubric; Clarification Q1 = A 2026-11-27).

- Trọng số keyword v1: fit 30, intent_value 20, competition 20, content_gap 15, demand 15; Coverage 60%; ngưỡng mức (rubric §2);
  tham số Confidence (rubric §3); mẫu keyword commercial và từ khóa tuyên bố trải nghiệm (research R-03, R-08).
- Model Task Profile cho 3 task type E3: model seed `verified = false` từ 0005 – gọi có phí vẫn bị chặn.

Revision ID: 0014_keywords_seed
Revises: 0013_keywords
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "0014_keywords_seed"
down_revision = "0013_keywords"
branch_labels = None
depends_on = None

WEIGHTS_V1 = {"fit": 30, "intent_value": 20, "competition": 20, "content_gap": 15, "demand": 15}
RUBRIC_V1 = {
    "formula_version": 1,
    # Không mặc định ý định mua cao luôn tốt hơn keyword giải quyết vấn đề (Q1): PROBLEM/SOLUTION informational = transactional.
    "intent_value": {
        "COMMERCIAL_INVESTIGATION": 100,
        "INFORMATIONAL_PROBLEM": 75,
        "TRANSACTIONAL": 75,
        "INFORMATIONAL": 25,
        "NAVIGATIONAL": 0,
    },
    "competition_levels": [[0.5, 100], [0.3, 75], [0.2, 50], [0.0001, 25]],
    "content_gap_levels": [[0.75, 100], [0.5, 75], [0.25, 50], [0.0001, 25]],
    "demand_levels": [[6, 100], [4, 75], [3, 50], [1, 25]],
    "weak_page_types": ["forum", "qa"],
}
CONFIDENCE_PARAMS = {
    "weights": {"S": 0.25, "D": 0.20, "F": 0.15, "O": 0.20, "V": 0.20},
    "domain_target": 4,
    "freshness_days": 180,
    "formula_version": 1,
}
TEMPLATES = {
    "commercial": [
        "best {product} alternatives",
        "{product} review",
        "{product} pricing",
        "{product} vs {other}",
        "is {product} worth it for {segment}",
    ],
    "experience_claim_terms": [
        "we tested",
        "i tested",
        "we tried",
        "i tried",
        "hands-on",
        "tested it",
        "đã dùng thử",
        "đã test",
    ],
    "max_strategy_clusters": 5,
}
PROFILES = [
    # task_type, model, effort, max_output_tokens – model chỉ là dữ liệu cấu hình (không hard-code trong nghiệp vụ)
    ("keywords.generate", "claude-haiku-5-5", "low", 6000),
    ("keywords.analyze", "claude-haiku-5-5", "low", 6000),
    ("keywords.strategy", "claude-sonnet-5-5", "medium", 6000),
]


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO keyword_scoring_weights (version, weights, rubric, coverage_min, confidence_params, templates,"
            " is_active) VALUES (1, CAST(:w AS jsonb), CAST(:r AS jsonb), 60, CAST(:c AS jsonb), CAST(:t AS jsonb), true)"
        ),
        {
            "w": json.dumps(WEIGHTS_V1),
            "r": json.dumps(RUBRIC_V1),
            "c": json.dumps(CONFIDENCE_PARAMS),
            "t": json.dumps(TEMPLATES, ensure_ascii=False),
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
    bind.execute(sa.text("DELETE FROM keyword_scoring_weights"))
