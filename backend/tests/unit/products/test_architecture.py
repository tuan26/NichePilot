"""T011 – kiến trúc E2: không công cụ có tác động bên ngoài, khai báo agent đủ, nguồn qua registry (FR-025, FR-030, FR-039, FR-041)."""

from __future__ import annotations

import inspect

import pytest

from nichepilot.jobs.agents import build_agents, product_discovery
from nichepilot.jobs.agents import program_terms_check as ptc

pytestmark = pytest.mark.products
E2_JOBS = ("products.run", "products.terms_check", "products.recompute")


def test_TC_E2_FR025_01_no_external_effect_tools() -> None:
    agents = build_agents()
    for job in E2_JOBS:
        tools = set(agents[job].definition.allowed_tools)
        assert tools <= {"source.query", "page.fetch", "robots.fetch"}, (job, tools)
    src = inspect.getsource(product_discovery) + inspect.getsource(ptc)
    for word in ("signup", "sign_up", "register(", "submit_form", "accept_terms", "login("):
        assert word not in src.lower()


def test_TC_E2_FR039_01_agent_definitions_complete() -> None:
    agents = build_agents()
    for job in E2_JOBS:
        d = agents[job].definition
        assert d.input_model is not None and d.output_model is not None and d.acceptance is not None
        assert d.timeout_s > 0 and d.max_steps > 0 and d.max_ai_calls >= 0 and d.token_budget >= 0
    run = agents["products.run"].definition
    assert (
        run.paid
        and run.max_ai_calls == 60
        and set(run.extra_task_types) == {"products.program_extract", "products.assess"}
    )
    assert not agents["products.recompute"].definition.paid
    src = inspect.getsource(ptc.ProductRecomputeAgent)
    assert "call_ai" not in src  # tính lại không AI


def test_TC_E2_FR041_01_sources_only_through_registry_tools() -> None:
    src = inspect.getsource(product_discovery) + inspect.getsource(ptc)
    for adapter in ("searxng_engine", "http_json_api", "MockSourceAdapter", "httpx"):
        assert adapter not in src


def test_TC_E2_FR030_01_scoring_modules_do_not_call_ai() -> None:
    from nichepilot.modules.products import evaluation, readiness
    from nichepilot.modules.products.scoring import criteria

    for mod in (evaluation, readiness, criteria):
        text_ = inspect.getsource(mod)
        assert "call_ai" not in text_ and "gateway" not in text_.lower()
