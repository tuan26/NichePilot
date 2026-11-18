"""0005_seed_ai – catalog model, bảng giá tham khảo, Model Task Profile mặc định (R-04, FR-019c).

QUAN TRỌNG: mọi model và giá của provider thật được seed với `verified = false`. Chúng phải được xác minh từ nguồn
chính thức (Models API / trang giá) trước khi hệ thống cho phép bất kỳ lời gọi có phí nào. Model `mock` chỉ dùng ở
development/test và có bảng giá giả lập riêng – không phải chi phí thật.

Revision ID: 0005_seed_ai
Revises: 0004_ai_jobs
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_seed_ai"
down_revision = "0004_ai_jobs"
branch_labels = None
depends_on = None

REFERENCE_NOTE = (
    "Giá tham khảo từ tài liệu Claude API (bản cache 2026-11-03) – CHƯA xác minh với trang giá chính thức; "
    "phải xác minh trước khi bật gọi có phí."
)
MOCK_NOTE = "Giá GIẢ LẬP nội bộ cho MockAIProvider (bằng giá tham khảo Haiku 5.5) – KHÔNG phải chi phí thật."

MODELS = [
    # provider, model_id, display_name, verified, source
    ("anthropic", "claude-haiku-5-5", "Claude Haiku 5.5", False, None),
    ("anthropic", "claude-sonnet-5-5", "Claude Sonnet 5.5", False, None),
    ("anthropic", "claude-opus-5-5", "Claude Opus 5.5", False, None),
    ("mock", "mock-model", "Mock model (dev/test)", True, "internal mock – không phải model thật"),
]

PRICING = [
    # provider, model, in, out, cache_read, cache_write, long_threshold, long_in, long_out, note, verified
    ("anthropic", "claude-haiku-5-5", "0.10", "0.50", None, None, 100000, "0.50", "2.50", REFERENCE_NOTE, False),
    ("anthropic", "claude-sonnet-5-5", "2.00", "10.00", "0.10", None, None, None, None, REFERENCE_NOTE, False),
    ("anthropic", "claude-opus-5-5", "4.00", "20.00", "0.20", None, None, None, None, REFERENCE_NOTE, False),
    ("mock", "mock-model", "0.10", "0.50", "0.01", "0.125", None, None, None, MOCK_NOTE, True),
]

PROFILES = [
    # task_type, model, effort, max_output_tokens
    ("system.diagnostic", "claude-haiku-5-5", "low", 1024),
    ("extract.simple", "claude-haiku-5-5", "low", 4096),
    ("analyze.standard", "claude-sonnet-5-5", "medium", 16000),
    ("reason.complex", "claude-opus-5-5", "medium", 32000),
]


def upgrade() -> None:
    bind = op.get_bind()
    for provider, model_id, name, verified, source in MODELS:
        bind.execute(
            sa.text(
                "INSERT INTO ai_models (provider, model_id, display_name, verified, verification_source, "
                "verified_at, verified_by, supports_structured_output, supports_tools, supports_effort) "
                "VALUES (:p, :m, :n, :v, :s, CASE WHEN :v THEN now() END, CASE WHEN :v THEN 'SYSTEM:seed' END, "
                "CASE WHEN :v THEN true END, CASE WHEN :v THEN true END, CASE WHEN :v THEN true END)"
            ),
            {"p": provider, "m": model_id, "n": name, "v": verified, "s": source},
        )
    for p, m, i, o, cr, cw, lt, li, lo, note, verified in PRICING:
        bind.execute(
            sa.text(
                "INSERT INTO model_pricing (provider, model, version, input_per_mtok, output_per_mtok, "
                "cache_read_per_mtok, cache_write_per_mtok, long_context_threshold_tokens, long_input_per_mtok, "
                "long_output_per_mtok, source_note, verified) "
                "VALUES (:p, :m, 1, :i, :o, :cr, :cw, :lt, :li, :lo, :n, :v)"
            ),
            {
                "p": p,
                "m": m,
                "i": i,
                "o": o,
                "cr": cr,
                "cw": cw,
                "lt": lt,
                "li": li,
                "lo": lo,
                "n": note,
                "v": verified,
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
    op.execute("DELETE FROM model_task_profiles")
    op.execute("DELETE FROM model_pricing")
    op.execute("DELETE FROM ai_models")
