"""0010_discovery_seed – dữ liệu khởi tạo E1 (T037; data-model §2; source-verification.md; research R-10).

- Phiên bản trọng số v1 = BR-03 (25/20/20/15/10/10), Coverage 60%, tham số bằng chứng/Confidence/dedup mặc định.
- Nguồn S1–S11: TẤT CẢ `UNVERIFIED`, `enabled = false` (quyết định A1 – không nguồn nào được dùng tới khi chủ sở hữu xác minh).
- Model Task Profile cho 4 task type E1: model seed `verified = false` từ 0005 – gọi có phí vẫn bị chặn.
- Dòng `erasure_ledger_state` (sổ chưa khởi tạo).

Revision ID: 0010_discovery_seed
Revises: 0009_discovery
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "0010_discovery_seed"
down_revision = "0009_discovery"
branch_labels = None
depends_on = None

WEIGHTS_V1 = {
    "problem_severity": 25,
    "monetization": 20,
    "market_gap": 20,
    "reachability": 15,
    "competition_opportunity": 10,
    "demand_stability": 10,
}
EVIDENCE_RULES = {
    "min_items": 2,
    "min_independent_groups": 2,
    "min_relevance": 0.6,
    "min_quality": 0.5,
    "simhash_max_distance": 3,
}
CONFIDENCE_PARAMS = {
    "weights": {"N": 0.25, "Q": 0.20, "D": 0.15, "F": 0.15, "K": 0.15, "V": 0.10},
    "freshness_days": 730,
    "insufficient_cap": 30,
    "formula_version": 1,
}
DEDUP_PARAMS = {"duplicate": 0.85, "possible": 0.60, "w_problem": 0.6, "w_customer": 0.4}

SEARX = "searxng_engine"
API = "http_json_api"
SEED_SOURCES = [
    # source_key, display_name, adapter_type, tos_url, config
    (
        "searxng:wikipedia",
        "Wikipedia (MediaWiki)",
        SEARX,
        "https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use",
        {"engine_name": "wikipedia"},
    ),
    (
        "api:stackexchange",
        "Stack Exchange API",
        API,
        "https://stackoverflow.com/legal/api-terms-of-use",
        {
            "base_url": "https://api.stackexchange.com/2.3/search/advanced",
            "query_template": "q={query}&site=stackoverflow&order=desc&sort=relevance",
            "result_mapping": {"items": "items", "url": "link", "title": "title"},
        },
    ),
    (
        "api:hn-algolia",
        "Hacker News (Algolia API)",
        API,
        "https://hn.algolia.com/api",
        {
            "base_url": "https://hn.algolia.com/api/v1/search",
            "query_template": "query={query}&tags=story",
            "result_mapping": {"items": "hits", "url": "url", "title": "title"},
        },
    ),
    ("searxng:mojeek", "Mojeek", SEARX, "https://www.mojeek.com/about/terms", {"engine_name": "mojeek"}),
    (
        "searxng:marginalia",
        "Marginalia Search",
        SEARX,
        "https://about.marginalia-search.com/article/api/",
        {"engine_name": "marginalia"},
    ),
    ("searxng:mwmbl", "Mwmbl", SEARX, "https://mwmbl.org", {"engine_name": "mwmbl"}),
    ("searxng:duckduckgo", "DuckDuckGo", SEARX, "https://duckduckgo.com/terms", {"engine_name": "duckduckgo"}),
    (
        "searxng:brave",
        "Brave Search",
        SEARX,
        "https://search.brave.com/help/terms-of-service",
        {"engine_name": "brave"},
    ),
    (
        "searxng:startpage",
        "Startpage",
        SEARX,
        "https://www.startpage.com/en/terms-of-service/",
        {"engine_name": "startpage"},
    ),
    ("searxng:google", "Google", SEARX, "https://policies.google.com/terms", {"engine_name": "google"}),
    (
        "searxng:bing",
        "Bing (Microsoft)",
        SEARX,
        "https://www.microsoft.com/en-us/servicesagreement",
        {"engine_name": "bing"},
    ),
]
SEED_SOURCE_KEYS = [s[0] for s in SEED_SOURCES]

PROFILES = [
    # task_type, model, effort, max_output_tokens – model chỉ là dữ liệu cấu hình (không hard-code trong nghiệp vụ)
    ("discovery.candidates", "claude-sonnet-5-5", "medium", 8000),
    ("discovery.extract", "claude-haiku-5-5", "low", 4096),
    ("discovery.assess", "claude-sonnet-5-5", "medium", 8000),
    ("discovery.normalize", "claude-haiku-5-5", "low", 2048),
]


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "INSERT INTO scoring_weights_versions (version, weights, coverage_threshold, evidence_rules,"
            " confidence_params, dedup_params, is_active) VALUES (1, CAST(:w AS jsonb), 60, CAST(:e AS jsonb),"
            " CAST(:c AS jsonb), CAST(:d AS jsonb), true)"
        ),
        {
            "w": json.dumps(WEIGHTS_V1),
            "e": json.dumps(EVIDENCE_RULES),
            "c": json.dumps(CONFIDENCE_PARAMS),
            "d": json.dumps(DEDUP_PARAMS),
        },
    )
    for key, name, adapter, tos, config in SEED_SOURCES:
        bind.execute(
            sa.text(
                "INSERT INTO source_policies (source_key, display_name, adapter_type, config, tos_url,"
                " compliance_status, enabled) VALUES (:k, :n, :a, CAST(:c AS jsonb), :t, 'UNVERIFIED', false)"
            ),
            {"k": key, "n": name, "a": adapter, "c": json.dumps(config), "t": tos},
        )
    for task_type, model, effort, max_out in PROFILES:
        bind.execute(
            sa.text(
                "INSERT INTO model_task_profiles (task_type, provider, model, effort, max_output_tokens) "
                "VALUES (:t, 'anthropic', :m, :e, :x)"
            ),
            {"t": task_type, "m": model, "e": effort, "x": max_out},
        )
    bind.execute(sa.text("INSERT INTO erasure_ledger_state (id, applied_seq, status) VALUES (1, 0, 'OK')"))


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM erasure_ledger_state"))
    bind.execute(sa.text("DELETE FROM model_task_profiles WHERE task_type = ANY(:t)"), {"t": [p[0] for p in PROFILES]})
    bind.execute(sa.text("DELETE FROM source_policies WHERE source_key = ANY(:k)"), {"k": SEED_SOURCE_KEYS})
    bind.execute(sa.text("DELETE FROM scoring_weights_versions WHERE version = 1"))
