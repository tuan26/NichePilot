"""Lắp ráp dịch vụ dùng chung cho tiến trình api và worker (AI Gateway, Tool Registry, agent, runtime, hàng đợi)."""

from __future__ import annotations

from dataclasses import dataclass

import procrastinate
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nichepilot.ai.gateway import AIGateway
from nichepilot.core.config import Settings
from nichepilot.jobs.agents import build_agents
from nichepilot.jobs.maintenance import register_maintenance
from nichepilot.jobs.queue import ProcrastinateJobQueue, build_procrastinate_app
from nichepilot.jobs.runtime import Agent, JobRuntime
from nichepilot.tools.builtin.system_runtime_info import build_tool_registry
from nichepilot.tools.registry import ToolRegistry


@dataclass
class Services:
    settings: Settings
    gateway: AIGateway
    tools: ToolRegistry
    agents: dict[str, Agent]
    runtime: JobRuntime
    procrastinate_app: procrastinate.App
    job_queue: ProcrastinateJobQueue


def build_services(settings: Settings, sessionmaker: async_sessionmaker[AsyncSession]) -> Services:
    gateway = AIGateway.from_settings(settings, sessionmaker)
    tools = build_tool_registry()
    agents = build_agents()
    runtime = JobRuntime(sessionmaker, gateway, tools, agents, settings)
    proc_app = build_procrastinate_app(settings.database_url.get_secret_value(), runtime.run)
    register_maintenance(proc_app, gateway.budget)
    return Services(settings, gateway, tools, agents, runtime, proc_app, ProcrastinateJobQueue(proc_app))
