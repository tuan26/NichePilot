"""T009 – kiến trúc E3: AgentDefinition đủ, schema AI forbid, tool chỉ đọc, chấm điểm không AI (FR-003, FR-020, FR-029)."""

from __future__ import annotations

import inspect

import pytest
from pydantic import BaseModel

from nichepilot.jobs.agents import build_agents, keyword_research, serp_check
from nichepilot.modules.keywords import schemas

pytestmark = pytest.mark.keywords
E3_JOBS = ("keywords.run", "keywords.serp_check", "keywords.recompute")


def test_TC_E3_FR029_01_agent_definitions_complete() -> None:
    agents = build_agents()
    for job in E3_JOBS:
        d = agents[job].definition
        assert d.input_model is not None and d.output_model is not None and d.acceptance is not None
        assert d.timeout_s > 0 and d.max_steps > 0 and d.max_ai_calls >= 1 and d.token_budget >= 1
    run = agents["keywords.run"].definition
    assert (
        run.paid and run.max_ai_calls == 40 and set(run.extra_task_types) == {"keywords.analyze", "keywords.strategy"}
    )
    assert not agents["keywords.serp_check"].definition.paid and not agents["keywords.recompute"].definition.paid
    assert "call_ai" not in inspect.getsource(serp_check)  # serp_check và recompute không AI


def test_TC_E3_FR029_02_ai_output_schemas_forbid_extra_fields() -> None:
    for name in (
        "KeywordsGenerateOutput",
        "KeywordsAnalyzeOutput",
        "KeywordsStrategyOutput",
        "KeywordOut",
        "PageSummaryOut",
    ):
        model: type[BaseModel] = getattr(schemas, name)
        assert model.model_config.get("extra") == "forbid", name
    fields = set(schemas.KeywordOut.model_fields)
    assert not fields & {"search_volume", "cpc", "keyword_difficulty", "volume"}


def test_TC_E3_FR003_01_read_only_tools_and_registry_sources() -> None:
    agents = build_agents()
    for job in E3_JOBS:
        assert set(agents[job].definition.allowed_tools) <= {"source.query", "page.fetch", "robots.fetch"}
    src = inspect.getsource(keyword_research) + inspect.getsource(serp_check)
    for word in ("searxng_engine", "http_json_api", "MockSourceAdapter", "httpx", "publish", "submit_form"):
        assert word not in src


def test_TC_E3_FR020_02_scoring_modules_do_not_call_ai() -> None:
    from nichepilot.modules.keywords import analysis, clustering, evaluation, normalize, serp
    from nichepilot.modules.keywords.scoring import confidence, criteria, opportunity

    for mod in (evaluation, criteria, opportunity, confidence, clustering, normalize, serp, analysis):
        text_ = inspect.getsource(mod)
        assert "call_ai" not in text_ and "gateway" not in text_.lower()


def test_TC_E3_FR032_01_metrics_source_integration_not_implemented() -> None:
    """FR-032 (Later): chưa tích hợp Google Search Console/nguồn chỉ số keyword; chỉ có cột chỉ số + nguồn sẵn cho adapter tương lai."""
    import pathlib

    from nichepilot.modules.keywords.models import Keyword

    root = pathlib.Path(inspect.getfile(keyword_research)).parents[2]
    for path in root.rglob("*.py"):
        body = path.read_text(encoding="utf-8").lower()
        for word in ("searchconsole", "webmasters", "dataforseo", "keywordplanner", "semrush", "ahrefs"):
            assert word not in body, (path, word)
    cols = set(Keyword.__table__.columns.keys())
    assert {
        "search_volume",
        "cpc",
        "keyword_difficulty",
        "metrics_source",
        "metrics_collected_at",
        "metrics_market",
    } <= cols
    names = {str(c.name) for c in Keyword.__table__.constraints if c.name}
    for col in ("search_volume", "cpc", "keyword_difficulty"):
        assert any(n.endswith(f"{col}_sourced") for n in names), col  # có giá trị ⇒ bắt buộc nguồn (CHECK DB)
