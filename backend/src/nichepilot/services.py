"""Lắp ráp dịch vụ dùng chung cho tiến trình api và worker (AI Gateway, Tool Registry, agent, runtime, hàng đợi)."""

from __future__ import annotations

from dataclasses import dataclass

import procrastinate
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from nichepilot.ai.gateway import AIGateway
from nichepilot.core.config import Settings
from nichepilot.core.discovery_config import DiscoverySettings
from nichepilot.discovery_wiring import DiscoveryServices, build_discovery
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
    discovery: DiscoveryServices | None = None  # E1 (specs/002-niche-discovery)


def build_services(
    settings: Settings,
    sessionmaker: async_sessionmaker[AsyncSession],
    *,
    discovery_settings: DiscoverySettings | None = None,
) -> Services:
    gateway = AIGateway.from_settings(settings, sessionmaker)
    tools = build_tool_registry()
    discovery = build_discovery(sessionmaker, tools, discovery_settings)  # E1: kiểm tra cấu hình + đăng ký tool
    agents = build_agents()
    runtime = JobRuntime(sessionmaker, gateway, tools, agents, settings)
    proc_app = build_procrastinate_app(settings.database_url.get_secret_value(), runtime.run)
    queue = ProcrastinateJobQueue(proc_app)
    runtime.requeue = queue.enqueue_run
    register_maintenance(
        proc_app,
        gateway.budget,
        sessionmaker,
        queue,
        settings.job_stalled_after_s,
        settings.ai_provider_override,
        settings.log_dir,
    )
    return Services(settings, gateway, tools, agents, runtime, proc_app, queue, discovery)
