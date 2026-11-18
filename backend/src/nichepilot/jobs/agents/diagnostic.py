"""Agent `system.diagnostic` (T079 – FR-026): job chẩn đoán AI của E0.

3 bước: (1) AI chọn tool → (2) chạy tool `system.runtime_info` → (3) AI trả kết quả có cấu trúc.
Với MockAIProvider mọi kết quả AI mang nhãn [MOCK]; với provider thật chỉ chạy khi chủ sở hữu cho phép gọi có phí.
Agent KHÔNG import provider – chỉ dùng JobContext (AI Gateway, Tool Registry dùng chung).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from nichepilot.ai.gateway import LLMMessage
from nichepilot.ai.sanitize import wrap_untrusted
from nichepilot.jobs.runtime import AgentDefinition, JobContext, StepOutcome

TOOL = "system.runtime_info"
SYSTEM = "You are the NichePilot diagnostic agent. Verify that tool calling and structured output work."
PROMPT = "Call the tool system.runtime_info once, then report the diagnostic result."


class DiagnosticInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mock_scenario: str | None = Field(default=None, description="Chỉ hợp lệ khi provider là MockAIProvider (dev/test)")


class DiagnosticOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ok"]
    note: str


def _acceptance(result: dict[str, Any]) -> list[str]:
    problems = []
    if result.get("status") != "ok":
        problems.append("status phải là 'ok'")
    if not isinstance(result.get("runtime"), dict) or "server_time_utc" not in result["runtime"]:
        problems.append("thiếu kết quả tool system.runtime_info")
    return problems


DEFINITION = AgentDefinition(
    job_type="system.diagnostic",
    description="Job chẩn đoán AI: một lời gọi tool + một kết quả có cấu trúc",
    task_type="system.diagnostic",
    input_model=DiagnosticInput,
    output_model=DiagnosticOutput,
    allowed_tools=[TOOL],
    max_steps=5,
    max_ai_calls=4,
    timeout_s=300,
    token_budget=200_000,
    paid=True,
    acceptance=_acceptance,
)


class DiagnosticAgent:
    definition = DEFINITION

    async def run_step(self, seq: int, state: dict[str, Any], ctx: JobContext) -> StepOutcome:
        if seq == 1:
            res = await ctx.call_ai(
                system=SYSTEM, messages=[LLMMessage(role="user", content=PROMPT)], tools=ctx.tool_specs()
            )
            first = res.response.tool_calls[0] if res.response.tool_calls else None
            tool_call = {"id": first.id, "name": first.name, "input": first.input} if first else None
            return StepOutcome(
                name="ask_model_for_tool",
                step_type="AI_CALL",
                output={"tool_call": tool_call, "provider": res.provider, "model": res.model},
                state={**state, "tool_call": tool_call, "provider": res.provider, "model": res.model},
            )
        if seq == 2:
            call: dict[str, Any] = state.get("tool_call") or {"id": "agent-default", "name": TOOL, "input": {}}
            # Quyền tool được Tool Registry kiểm tra – model không thể gọi tool ngoài danh sách cho phép.
            output = await ctx.call_tool(str(call["name"]), dict(call.get("input") or {}))
            return StepOutcome(
                name="run_tool", step_type="TOOL_CALL", output=output, state={**state, "runtime": output}
            )
        final_call: dict[str, Any] = state.get("tool_call") or {"id": "agent-default", "name": TOOL, "input": {}}
        messages = [
            LLMMessage(role="user", content=PROMPT),
            LLMMessage(role="assistant", content=[{"type": "tool_use", **final_call}]),
            LLMMessage(
                role="user",
                content=[
                    {
                        "type": "tool_result",
                        "tool_use_id": final_call["id"],
                        "content": wrap_untrusted(state["runtime"], source=TOOL),
                    }
                ],
            ),
        ]
        res = await ctx.call_ai(system=SYSTEM, messages=messages, output_model=DiagnosticOutput)
        result = {
            **(res.parsed or {}),
            "provider": res.provider,
            "model": res.model,
            "runtime": state["runtime"],
            "data_origin": res.data_origin,
        }
        return StepOutcome(name="summarize", step_type="AI_CALL", output=result, state=state, done=True, result=result)
