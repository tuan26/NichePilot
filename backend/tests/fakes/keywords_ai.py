"""ScriptedKeywordsAI – TEST DOUBLE thay provider `mock` cho test E3 (data_origin = MOCK, không gọi mạng).

Đọc CHÍNH prompt agent gửi (id pain point/persona/sản phẩm, trích đoạn trong `<untrusted_content>`) và trả đầu ra theo kịch bản cố định
dẫn đúng id. Kịch bản ghi đè cho phép mô phỏng AI bịa chỉ số, origin lạ, tuyên bố "đã test"… KHÔNG phải dữ liệu nghiên cứu thật; KHÔNG
chứng minh tích hợp provider thật.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from nichepilot.ai.providers.base import ConnectionCheckResult, LLMRequest, LLMResponse, TokenUsage
from tests.fakes.products_ai import excerpts_in

Script = dict[str, Any] | Callable[[LLMRequest], dict[str, Any]]
LINE_RE = re.compile(r"^- ([^:]+): (.*?) \| (.*)$")
PAIN_RE = re.compile(r"^- ([0-9a-f-]{36}): ", re.M)


def _prompt(req: LLMRequest) -> str:
    return "\n".join(str(m.content) for m in req.messages)


def sections(req: LLMRequest) -> dict[str, list[tuple[str, str, list[str]]]]:
    """Tách các mục `Pain points`, `Buyer persona attributes`, `Products` của prompt keywords.generate."""
    out: dict[str, list[tuple[str, str, list[str]]]] = {"pain": [], "persona": [], "product": []}
    current = None
    for line in _prompt(req).splitlines():
        if line.startswith("Pain points"):
            current = "pain"
        elif line.startswith("Buyer persona"):
            current = "persona"
        elif line.startswith("Products"):
            current = "product"
        elif current and (m := LINE_RE.match(line)):
            out[current].append((m.group(1).strip(), m.group(2).strip(), [x for x in m.group(3).split(", ") if x]))
    return out


LONG_TAIL_PROBLEMS = [
    ("how to stop running out of ingredients in a micro bakery", "PROBLEM", "INFORMATIONAL"),
    ("low stock alert app for small bakeries", "SOLUTION", "COMMERCIAL_INVESTIGATION"),
    ("why does my bakery keep running out of flour", "PROBLEM", "INFORMATIONAL"),
    ("track ingredient stock without a spreadsheet", "SOLUTION", "INFORMATIONAL"),
    ("weekly ingredient count checklist for bakeries", "SOLUTION", "INFORMATIONAL"),
    ("reorder point for flour in a small bakery", "PROBLEM", "INFORMATIONAL"),
]


def default_generate(req: LLMRequest) -> dict[str, Any]:
    s = sections(req)
    kws: list[dict[str, Any]] = []
    if s["pain"]:
        pid, _title, ev = s["pain"][0]
        for text, kt, intent in LONG_TAIL_PROBLEMS:
            kws.append(
                {
                    "text": text,
                    "keyword_type": kt,
                    "intent": intent,
                    "intent_reason": "[MOCK] problem-solving query",
                    "origins": [{"origin_type": "PAIN_POINT", "pain_point_id": pid, "reason": "[MOCK] same pain"}],
                    "fit": {"level": 75, "reason": "[MOCK] matches the stock-out pain", "evidence_ids": ev[:1]},
                }
            )
    if s["persona"]:
        attr, _v, ev = s["persona"][0]
        kws.append(
            {
                "text": "inventory tips for micro bakery owners on a budget",
                "keyword_type": "INFORMATIONAL",
                "intent": "INFORMATIONAL",
                "origins": [{"origin_type": "PERSONA", "persona_attribute": attr}],
                "fit": {"level": 50, "reason": "[MOCK] persona segment", "evidence_ids": ev[:1]},
            }
        )
    for prod_id, name, ev in s["product"][:1]:
        kws.append(
            {
                "text": f"{name} expiry tracking for home bakers",
                "keyword_type": "PRODUCT",
                "intent": "COMMERCIAL_INVESTIGATION",
                "origins": [{"origin_type": "PRODUCT", "product_id": prod_id}],
                "fit": {"level": 75, "reason": "[MOCK] product feature", "evidence_ids": ev[:1]},
            }
        )
    return {"keywords": kws}


def default_analyze(req: LLMRequest) -> dict[str, Any]:
    pains = PAIN_RE.findall(_prompt(req))
    pages: dict[str, dict[str, Any]] = {}
    for e in excerpts_in(req):
        url, text = e["url"], e["excerpt"]
        page = pages.setdefault(
            url,
            {
                "url": url,
                "headings": ["[MOCK] heading"],
                "topics": [],
                "has_comparison": False,
                "has_pricing": False,
                "has_experience_evidence": False,
                "covered_pain_point_ids": [],
                "evidence_ids": [],
            },
        )
        page["evidence_ids"].append(e["evidence_id"])
        if "[COVERS]" in text and pains:
            page["covered_pain_point_ids"] = pains[:1]
        page["has_comparison"] = page["has_comparison"] or "[COMPARISON]" in text
        page["has_pricing"] = page["has_pricing"] or "[PRICING]" in text or "pric" in text.lower()
    for p in pages.values():
        p["evidence_ids"] = p["evidence_ids"][:6]
    return {"pages": list(pages.values())}


def clusters_in(req: LLMRequest) -> list[dict[str, Any]]:
    text = _prompt(req)
    body = text.split("Clusters:\n", 1)[1].split("\n<untrusted_content", 1)[0]
    return list(json.loads(body))


def default_strategy(req: LLMRequest) -> dict[str, Any]:
    out = []
    for c in clusters_in(req):
        ev = c["evidence_ids"]
        kws = list(c["keywords"])
        out.append(
            {
                "cluster_id": c["cluster_id"],
                "persona": {
                    "goals": {"value": "[MOCK] never run out of key ingredients", "evidence_ids": ev[:1]},
                    "barriers": {"value": "[MOCK] no time after the morning rush", "evidence_ids": ["not-an-evidence"]},
                },
                "strategy": {
                    "content_type": "GUIDE",
                    "angle": "[MOCK] Show a simple low-stock routine step by step. We tested every app hands-on.",
                    "pain_point_ids": c["pain_point_ids"],
                    "product_ids": c["product_ids"],
                    "primary_keyword_id": kws[0] if kws else None,
                    "secondary_keyword_ids": kws[1:3],
                    "gap_refs": c["gap_pain_point_ids"],
                },
            }
        )
    return {"clusters": out}


class ScriptedKeywordsAI:
    name = "mock"
    data_origin = "MOCK"
    paid = False

    def __init__(self, scripts: dict[str, Script] | None = None) -> None:
        self.scripts: dict[str, Script] = {
            "keywords.generate": default_generate,
            "keywords.analyze": default_analyze,
            "keywords.strategy": default_strategy,
            **(scripts or {}),
        }
        self.requests: list[LLMRequest] = []

    async def count_input_tokens(self, req: LLMRequest) -> int:
        return 500

    async def generate(self, req: LLMRequest) -> LLMResponse:
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
