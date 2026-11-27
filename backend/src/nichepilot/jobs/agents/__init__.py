"""Đăng ký agent. E0: `system.diagnostic`; E1: `discovery.run`, `discovery.recompute`, `discovery.reevaluate`
(specs/002-niche-discovery); E2: `products.run`, `products.terms_check`, `products.recompute`; E3: `keywords.run`,
`keywords.serp_check`, `keywords.recompute`."""

from __future__ import annotations

from nichepilot.jobs.agents.diagnostic import DiagnosticAgent
from nichepilot.jobs.agents.keyword_research import KeywordResearchAgent
from nichepilot.jobs.agents.niche_discovery import NicheDiscoveryAgent
from nichepilot.jobs.agents.niche_reevaluate import NicheRecomputeAgent, NicheReevaluationAgent
from nichepilot.jobs.agents.product_discovery import ProductDiscoveryAgent
from nichepilot.jobs.agents.program_terms_check import ProductRecomputeAgent, ProgramTermsCheckAgent
from nichepilot.jobs.agents.serp_check import KeywordRecomputeAgent, SerpCheckAgent
from nichepilot.jobs.runtime import Agent


def build_agents() -> dict[str, Agent]:
    agents: list[Agent] = [
        DiagnosticAgent(),
        NicheDiscoveryAgent(),
        NicheRecomputeAgent(),
        NicheReevaluationAgent(),
        # E2 (specs/003-product-affiliate-discovery, Y1)
        ProductDiscoveryAgent(),
        ProgramTermsCheckAgent(),
        ProductRecomputeAgent(),
        # E3 (specs/004-keyword-audience-research, Z1)
        KeywordResearchAgent(),
        SerpCheckAgent(),
        KeywordRecomputeAgent(),
    ]
    return {a.definition.job_type: a for a in agents}
