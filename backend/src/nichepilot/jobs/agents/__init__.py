"""Đăng ký agent. E0: `system.diagnostic`; E1: `discovery.run`, `discovery.recompute`, `discovery.reevaluate`
(specs/002-niche-discovery)."""

from __future__ import annotations

from nichepilot.jobs.agents.diagnostic import DiagnosticAgent
from nichepilot.jobs.agents.niche_discovery import NicheDiscoveryAgent
from nichepilot.jobs.agents.niche_reevaluate import NicheRecomputeAgent, NicheReevaluationAgent
from nichepilot.jobs.runtime import Agent


def build_agents() -> dict[str, Agent]:
    agents: list[Agent] = [DiagnosticAgent(), NicheDiscoveryAgent(), NicheRecomputeAgent(), NicheReevaluationAgent()]
    return {a.definition.job_type: a for a in agents}
