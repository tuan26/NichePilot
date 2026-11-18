"""Đăng ký agent. E0 chỉ có `system.diagnostic`; agent nghiên cứu thuộc E1–E3."""

from __future__ import annotations

from nichepilot.jobs.agents.diagnostic import DiagnosticAgent
from nichepilot.jobs.runtime import Agent


def build_agents() -> dict[str, Agent]:
    agents: list[Agent] = [DiagnosticAgent()]
    return {a.definition.job_type: a for a in agents}
