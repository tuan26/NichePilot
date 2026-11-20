"""ScriptedDiscoveryAI – TEST DOUBLE thay provider `mock` cho test E1 (data_origin = MOCK, không gọi mạng).

Trả kết quả có cấu trúc theo kịch bản cho từng task type E1 và ghi lại request để test kiểm tra prompt (không PII, nội dung
ngoài được bọc trong <untrusted_content>). KHÔNG phải dữ liệu nghiên cứu thật; KHÔNG chứng minh tích hợp provider thật.
"""

from __future__ import annotations

import json
from typing import Any

from nichepilot.ai.providers.base import ConnectionCheckResult, LLMRequest, LLMResponse, TokenUsage

CANDIDATES = {
    "candidates": [
        {
            "name": "[MOCK] Small bakery inventory",
            "micro_niche": "[MOCK] Flour and dairy stock alerts for micro bakeries",
            "domain": "food & beverage",
            "customer_group": "owners of one- to three-person bakeries",
            "core_problem": "running out of ingredients without warning",
            "queries": ["bakery inventory"],
        },
        {
            "name": "[MOCK] Grooming salon scheduling",
            "micro_niche": "[MOCK] Saturday double-booking for dog groomers",
            "domain": "pet services",
            "customer_group": "independent dog grooming salons",
            "core_problem": "double-booked appointments",
            "queries": ["grooming scheduling"],
        },
        {
            "name": "[MOCK] Tutoring rescheduling",
            "micro_niche": "[MOCK] Lesson rescheduling for small tutoring centres",
            "domain": "education",
            "customer_group": "small tutoring centres",
            "core_problem": "rescheduling lessons takes days of messages",
            "queries": ["tutoring scheduling"],
        },
    ]
}


class ScriptedDiscoveryAI:
    name = "mock"
    data_origin = "MOCK"
    paid = False

    def __init__(self, scripts: dict[str, dict[str, Any]] | None = None) -> None:
        self.scripts = {"discovery.candidates": CANDIDATES, "discovery.extract": {"pain_points": []}, **(scripts or {})}
        self.requests: list[LLMRequest] = []

    async def count_input_tokens(self, req: LLMRequest) -> int:
        return 500

    async def generate(self, req: LLMRequest) -> LLMResponse:
        self.requests.append(req)
        parsed = self.scripts.get(req.task_type, {})
        return LLMResponse(
            outcome="SUCCESS",
            content_text="[MOCK] " + json.dumps(parsed, ensure_ascii=False),
            parsed_output=parsed,
            usage=TokenUsage(input_tokens=500, output_tokens=200),
            raw_model="mock-model",
            data_origin="MOCK",
        )

    async def check_connection(self) -> ConnectionCheckResult:
        return ConnectionCheckResult(provider="mock", result="MOCK")

    def prompt_text(self) -> str:
        return "\n".join(f"{r.system}\n" + "\n".join(str(m.content) for m in r.messages) for r in self.requests)
