"""ScriptedDiscoveryAI – TEST DOUBLE thay provider `mock` cho test E1 (data_origin = MOCK, không gọi mạng).

Trả kết quả có cấu trúc theo kịch bản cho từng task type E1 và ghi lại request để test kiểm tra prompt (không PII, nội dung
ngoài được bọc trong <untrusted_content>). KHÔNG phải dữ liệu nghiên cứu thật; KHÔNG chứng minh tích hợp provider thật.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
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


Script = dict[str, Any] | Callable[[LLMRequest], dict[str, Any]]
UNTRUSTED_RE = re.compile(r"<untrusted_content[^>]*>\n(.*?)\n</untrusted_content>", re.S)


def excerpts_in(req: LLMRequest) -> list[dict[str, str]]:
    """Trích danh sách {evidence_id, excerpt} agent đã gửi (trong khối <untrusted_content>)."""
    out: list[dict[str, str]] = []
    for m in req.messages:
        for body in UNTRUSTED_RE.findall(str(m.content)):
            out.extend(json.loads(body))
    return out


def default_extract(req: LLMRequest) -> dict[str, Any]:
    """[MOCK] Một pain point dẫn MỌI bằng chứng được cung cấp; persona/khoảng trống có trạng thái; monetization UNKNOWN."""
    ids = [e["evidence_id"] for e in excerpts_in(req)]
    if not ids:
        return {"pain_points": []}
    return {
        "pain_points": [
            {
                "title": "[MOCK] Running out of ingredients without warning",
                "description": "[MOCK] Owners discover missing stock too late and count by hand.",
                "severity": 4,
                "severity_reason": "[MOCK] repeated weekly losses described",
                "status": "VERIFIED",
                "evidence_ids": ids,
            }
        ],
        "persona": {
            "segment": {
                "value": "[MOCK] owners of very small food businesses",
                "status": "VERIFIED",
                "evidence_ids": ids[:1],
            },
            "context": {
                "value": "[MOCK] busy mornings, manual counting",
                "status": "INFERRED",
                "evidence_ids": ids[:1],
            },
            "goals": {"value": "[MOCK] be warned before stock runs out", "status": "VERIFIED", "evidence_ids": ids[:1]},
            "obstacles": {"value": "[MOCK] existing apps too complex", "status": "INFERRED", "evidence_ids": []},
            "ability_to_pay": {"status": "UNKNOWN"},
        },
        "findings": {
            "CURRENT_SOLUTIONS": {
                "value": ["[MOCK] spreadsheets", "[MOCK] paper"],
                "status": "VERIFIED",
                "evidence_ids": ids[:1],
            },
            "MARKET_GAPS": {
                "value": "[MOCK] simple phone-first stock alerts",
                "status": "INFERRED",
                "evidence_ids": ids,
            },
            "MONETIZATION": {"status": "UNKNOWN"},
        },
        "competitors": [
            {
                "name": "[MOCK] Spreadsheet",
                "kind": "MANUAL_WORKAROUND",
                "weaknesses": ["[MOCK] slow"],
                "evidence_ids": ids[:1],
            }
        ],
    }


def default_criteria(ids: list[str]) -> dict[str, Any]:
    """[MOCK] mức tiêu chí giống ví dụ tính tay scoring-rubric §3 (Opportunity 60,71 khi đủ bằng chứng)."""
    first = ids[:1]
    return {
        "problem_severity": {
            "level": 75,
            "status": "VERIFIED",
            "reason": "[MOCK] weekly losses",
            "evidence_ids": first,
        },
        "monetization": {"level": None, "status": "UNKNOWN", "reason": "[MOCK] no affiliate evidence"},
        "market_gap": {"level": 50, "status": "INFERRED", "reason": "[MOCK] apps too complex", "evidence_ids": first},
        "reachability": {"level": 75, "status": "INFERRED", "reason": "[MOCK] active forums", "evidence_ids": first},
        "competition_opportunity": {
            "level": 25,
            "status": "INFERRED",
            "reason": "[MOCK] several apps",
            "evidence_ids": first,
        },
        "demand_stability": {"level": None, "status": "UNKNOWN", "reason": "[MOCK] no trend data"},
    }


def default_assess(req: LLMRequest) -> dict[str, Any]:
    ex = excerpts_in(req)
    return {
        "evidence": [
            {
                "evidence_id": e["evidence_id"],
                "relevance": 0.9,
                "quality": 0.8,
                "copy_suspected": False,
                "reason": "[MOCK] describes the pain point directly",
            }
            for e in ex
        ],
        "criteria": default_criteria([e["evidence_id"] for e in ex]),
        "recommendation": {"decision": "PURSUE", "reason": "[MOCK] clear repeated pain"},
    }


class ScriptedDiscoveryAI:
    name = "mock"
    data_origin = "MOCK"
    paid = False

    def __init__(self, scripts: dict[str, Script] | None = None) -> None:
        self.scripts: dict[str, Script] = {
            "discovery.candidates": CANDIDATES,
            "discovery.extract": default_extract,
            "discovery.assess": default_assess,
            **(scripts or {}),
        }
        self.requests: list[LLMRequest] = []
        self.before_generate: Callable[[LLMRequest], Any] | None = None  # hook test (vd. xóa bằng chứng giữa lượt)

    async def count_input_tokens(self, req: LLMRequest) -> int:
        return 500

    async def generate(self, req: LLMRequest) -> LLMResponse:
        if self.before_generate is not None:
            hooked = self.before_generate(req)
            if hasattr(hooked, "__await__"):
                await hooked
        self.requests.append(req)
        script = self.scripts.get(req.task_type, {})
        parsed = script(req) if callable(script) else script
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

    def requests_for(self, task_type: str) -> list[LLMRequest]:
        return [r for r in self.requests if r.task_type == task_type]

    def prompt_text(self) -> str:
        return "\n".join(f"{r.system}\n" + "\n".join(str(m.content) for m in r.messages) for r in self.requests)
