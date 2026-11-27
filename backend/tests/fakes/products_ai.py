"""ScriptedProductsAI – TEST DOUBLE thay provider `mock` cho test E2 (data_origin = MOCK, không gọi mạng).

Trích xuất "giả lập" bằng regex trên CHÍNH các trích đoạn agent gửi (fixture tự soạn `tests/fixtures/products`), dẫn đúng
`evidence_id`. Kịch bản ghi đè cho phép mô phỏng AI bịa số liệu, sai schema… KHÔNG phải dữ liệu nghiên cứu thật; KHÔNG chứng minh
tích hợp provider thật.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any
from urllib.parse import urlsplit

from nichepilot.ai.providers.base import ConnectionCheckResult, LLMRequest, LLMResponse, TokenUsage

UNTRUSTED_RE = re.compile(r"<untrusted_content[^>]*>\n(.*?)\n</untrusted_content>", re.S)
PAIN_RE = re.compile(r"^- ([0-9a-f-]{36}): ", re.M)
PRODUCTS = {"stockpal": "StockPal", "doughtrack": "DoughTrack"}
Script = dict[str, Any] | Callable[[LLMRequest], dict[str, Any]]


def excerpts_in(req: LLMRequest) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in req.messages:
        for body in UNTRUSTED_RE.findall(str(m.content)):
            out.extend(json.loads(body))
    return out


def _prompt(req: LLMRequest) -> str:
    return "\n".join(str(m.content) for m in req.messages)


def default_extract(req: LLMRequest) -> dict[str, Any]:
    pains = PAIN_RE.findall(_prompt(req))
    out = []
    for key, name in PRODUCTS.items():
        ids = [e["evidence_id"] for e in excerpts_in(req) if name in e["excerpt"]]
        if not ids or not pains:
            continue
        out.append(
            {
                "name": name,
                "official_url": f"https://{key}.example",
                "category": "SOFTWARE",
                "pain_point_links": [{"pain_point_id": pains[0], "evidence_ids": ids[:1]}],
            }
        )
    return {"products": out}


def _num(pattern: str, text: str) -> float | None:
    m = re.search(pattern, text)
    return float(m.group(1)) if m else None


def default_program_extract(req: LLMRequest) -> dict[str, Any]:
    name = re.search(r"^Product: (.+)$", _prompt(req), re.M)
    product = name.group(1).strip() if name else ""
    key = product.lower()
    attrs: dict[str, Any] = {"prices": [], "features": []}
    program: dict[str, Any] = {
        "name": f"{product} Partner Program",
        "operator_type": "VENDOR",
        "terms_url": None,
    }
    found_program = False
    for e in excerpts_in(req):
        eid, text, url = e["evidence_id"], e["excerpt"], e.get("url", "")
        host = urlsplit(url).hostname or ""
        if host == f"{key}.example" and "official_website" not in attrs:
            attrs["official_website"] = {"url": f"https://{key}.example", "evidence_ids": [eid]}
        price = _num(r"\$(\d+) per month", text)
        if price is not None and "commission" not in text:
            attrs["prices"].append(
                {"plan": "Starter", "amount": price, "currency": "USD", "period": "month", "evidence_ids": [eid]}
            )
        if "Features included" in text:
            for f in ("low-stock alerts", "phone app", "supplier reorder lists", "expiry tracking"):
                if f in text:
                    attrs["features"].append({"text": f, "evidence_ids": [eid]})
        if "built for" in text.lower():
            attrs["target_customer"] = {"text": "small bakeries and cafés", "evidence_ids": [eid]}
        rate = _num(r"(\d+)% (?:recurring )?commission", text)
        if rate is not None:
            found_program = True
            if host == f"{key}.example":
                program["terms_url"] = url
            recurring = "recurring" in text
            com: dict[str, Any] = {
                "kind": "recurring" if recurring else "percent",
                "value": rate,
                "evidence_ids": [eid],
            }
            months = _num(r"for (\d+) months", text)
            if months is not None:
                com["recurring_months"] = int(months)
            program.setdefault("_commissions", []).append(com)
        days = _num(r"(\d+)-day cookie", text)
        if days is not None:
            program["cookie"] = {"days": int(days), "evidence_ids": [eid]}
        if "PayPal" in text or "bank transfer" in text:
            pay: dict[str, Any] = {
                "methods": ["PayPal"] if "PayPal" in text else ["bank transfer"],
                "evidence_ids": [eid],
            }
            mp = _num(r"minimum payout of \$(\d+)", text)
            if mp is not None:
                pay.update(min_payout=mp, currency="USD")
            program["payment"] = pay
            found_program = True
        if "Vietnam" in text:
            program["vn_eligibility"] = {"status": "ALLOWED", "evidence_ids": [eid]}
        if "worldwide" in text:
            program["promotion_regions"] = {"is_global": True, "evidence_ids": [eid]}
        if "brand keywords" in text:
            program["ad_restrictions"] = {"codes": ["NO_BRAND_BIDDING"], "evidence_ids": [eid]}
    coms = program.pop("_commissions", [])
    programs = []
    if found_program:
        # trang chính thức và trang bên thứ ba đều được trả về – mã quyết định VERIFIED/INFERRED/CONFLICTING
        for com in coms or [None]:
            p = dict(program)
            if com is not None:
                p["commission"] = com
            programs.append(p)
    return {"product": attrs, "programs": programs}


def default_assess(req: LLMRequest) -> dict[str, Any]:
    ex = excerpts_in(req)
    ids = [e["evidence_id"] for e in ex]
    third = [
        {"evidence_id": e["evidence_id"], "sentiment": "positive"}
        for e in ex
        if any(w in e["excerpt"] for w in ("love", "great"))
    ]
    return {
        "fit": {"level": 75, "reason": "[MOCK] addresses running out of ingredients", "evidence_ids": ids[:1]},
        "price_fit": {"level": 50, "reason": "[MOCK] monthly plan", "evidence_ids": ids[:1]},
        "persona_match": "MATCH",
        "third_party_mentions": third,
        "recommendation": {"decision": "SELECT", "reason": "[MOCK] solves the main pain point"},
    }


class ScriptedProductsAI:
    name = "mock"
    data_origin = "MOCK"
    paid = False

    def __init__(self, scripts: dict[str, Script] | None = None) -> None:
        self.scripts: dict[str, Script] = {
            "products.extract": default_extract,
            "products.program_extract": default_program_extract,
            "products.assess": default_assess,
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
