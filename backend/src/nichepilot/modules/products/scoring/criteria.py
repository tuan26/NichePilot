"""Mức 5 tiêu chí sản phẩm (scoring-rubric §2; FR-027, FR-028a; Clarification Q2).

`affiliate`, `eligibility`, `quality` tính hoàn toàn từ thuộc tính có bằng chứng; `fit`, `price_fit` là mức AI đề xuất
(INFERRED) chỉ được
dùng khi điều kiện dữ liệu đạt. Không có dữ liệu → `level = None` (UNKNOWN) – KHÔNG gán điểm giả. Ngưỡng đọc từ
`rubric` của phiên bản
trọng số. Mã thuần, không I/O, không AI.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from nichepilot.modules.products.attributes import ResolvedAttribute
from nichepilot.modules.products.readiness import market_ok

LEVELS = (0, 25, 50, 75, 100)
CRITERIA_KEYS = ("fit", "affiliate", "eligibility", "quality", "price_fit")
DEFAULT_RUBRIC: dict[str, Any] = {
    "affiliate": {
        "rate_levels": [[30, 100], [20, 75], [10, 50], [5, 25]],
        "fixed_amount_levels": [[50, 75], [20, 50], [5, 25]],
        "up_to_penalty": 25,
        "recurring_bonus": 25,
        "recurring_min_months": 6,
        "short_cookie_days": 30,
        "short_cookie_penalty": 25,
    },
    "eligibility": {"max_restrictions_for_full": 1, "inferred_cap": 50},
    "quality": {"min_features": 3},
    "fit": {"no_match_cap": 25},
}


@dataclass(frozen=True)
class Criterion:
    level: int | None
    status: str  # VERIFIED | INFERRED | UNKNOWN
    reason: str = ""
    evidence_ids: tuple[str, ...] = ()
    inputs: dict[str, Any] = field(default_factory=dict)

    def as_json(self) -> dict[str, Any]:
        return {
            "level": self.level,
            "status": self.status,
            "reason": self.reason,
            "evidence_ids": list(self.evidence_ids),
            "inputs": self.inputs,
        }


UNKNOWN = Criterion(None, "UNKNOWN", "no evidence-backed data")


def _rubric(rubric: Mapping[str, Any] | None, key: str) -> dict[str, Any]:
    return {**DEFAULT_RUBRIC[key], **dict((rubric or {}).get(key) or {})}


def _clamp(level: float) -> int:
    snapped = max(0, min(100, round(level / 25.0) * 25))
    return snapped


def _ids(*attrs: ResolvedAttribute) -> tuple[str, ...]:
    return tuple(v.evidence_id for a in attrs for v in a.values)


def _ai_level(ai: Mapping[str, Any] | None, active_ids: set[str]) -> tuple[int | None, str, tuple[str, ...]]:
    if not ai:
        return None, "", ()
    level, reason = ai.get("level"), str(ai.get("reason") or "")
    ids = tuple(i for i in (ai.get("evidence_ids") or []) if i in active_ids)
    if level not in LEVELS or not reason.strip() or not ids:
        return None, reason, ids
    return int(level), reason, ids


def fit(
    ai: Mapping[str, Any] | None,
    *,
    has_pain_links: bool,
    persona_match: str,
    active_ids: set[str],
    rubric: Mapping[str, Any] | None = None,
) -> Criterion:
    level, reason, ids = _ai_level(ai, active_ids)
    if level is None or not has_pain_links:
        return Criterion(None, "UNKNOWN", reason or "fit not supported by evidence", ids)
    if persona_match == "NO_MATCH":
        level = min(level, int(_rubric(rubric, "fit")["no_match_cap"]))
    return Criterion(level, "INFERRED", reason, ids, {"persona_match": persona_match})


def price_fit(
    ai: Mapping[str, Any] | None,
    *,
    price_has_data: bool,
    ability_to_pay_known: bool,
    active_ids: set[str],
) -> Criterion:
    level, reason, ids = _ai_level(ai, active_ids)
    if level is None or not price_has_data or not ability_to_pay_known:
        return Criterion(None, "UNKNOWN", reason or "price or ability to pay unknown", ids)
    return Criterion(level, "INFERRED", reason, ids)


def _rate_level(rate: float, table: Sequence[Sequence[float]]) -> int:
    for threshold, lvl in table:
        if rate >= threshold:
            return int(lvl)
    return 0


def cheapest_price(price: ResolvedAttribute) -> float | None:
    if not price.has_data:
        return None
    amounts = [float(p["amount"]) for p in price.value or [] if isinstance(p, dict) and p.get("amount")]
    return min(amounts) if amounts else None


def affiliate(
    commission: ResolvedAttribute,
    cookie: ResolvedAttribute,
    *,
    cheapest: float | None,
    rubric: Mapping[str, Any] | None = None,
) -> Criterion:
    r = _rubric(rubric, "affiliate")
    if not commission.has_data:
        return Criterion(None, "UNKNOWN", "commission unknown")
    c: dict[str, Any] = dict(commission.value or {})
    kind = c.get("kind")
    base: float
    inputs: dict[str, Any] = {"kind": kind}
    if kind == "fixed":
        amount = c.get("value") if c.get("value") is not None else c.get("min")
        if amount is None:
            return Criterion(None, "UNKNOWN", "fixed commission without amount")
        if cheapest:
            rate = 100.0 * float(amount) / cheapest
            base = _rate_level(rate, r["rate_levels"])
            inputs["effective_rate"] = round(rate, 2)
        else:
            base = _rate_level(float(amount), r["fixed_amount_levels"])
            inputs["fixed_amount"] = amount
    else:
        rate_val = c.get("min") if c.get("min") is not None else c.get("value")
        if rate_val is None:
            rate_val = c.get("max")
        if rate_val is None:
            return Criterion(None, "UNKNOWN", "commission without rate")
        base = _rate_level(float(rate_val), r["rate_levels"])
        inputs["rate"] = rate_val
        if c.get("up_to"):
            base -= float(r["up_to_penalty"])
    months = c.get("recurring_months")
    if kind == "recurring" or (months is not None and int(months) >= int(r["recurring_min_months"])):
        base += float(r["recurring_bonus"])
        inputs["recurring"] = True
    if cookie.has_data:
        cv = dict(cookie.value or {})
        days = cv.get("days")
        if cv.get("session") or (days is not None and int(days) < int(r["short_cookie_days"])):
            base -= float(r["short_cookie_penalty"])
        inputs["cookie"] = cv
    status = "VERIFIED" if commission.verified else "INFERRED"
    return Criterion(_clamp(base), status, "computed from commission/cookie", _ids(commission, cookie), inputs)


def eligibility(
    vn: ResolvedAttribute,
    regions: ResolvedAttribute,
    restrictions: ResolvedAttribute,
    *,
    country: str,
    rubric: Mapping[str, Any] | None = None,
) -> Criterion:
    r = _rubric(rubric, "eligibility")
    vn_status = (vn.value or {}).get("status") if vn.has_data else None
    ok = market_ok(regions.value if regions.has_data else None, country)
    ids = _ids(vn, regions, restrictions)
    inputs = {"vn": vn_status, "market_ok": ok}
    if vn_status == "NOT_ALLOWED" or ok is False:
        return Criterion(
            0, "VERIFIED" if (vn.verified or regions.verified) else "INFERRED", "not eligible", ids, inputs
        )
    if vn_status is None and ok is None:
        return Criterion(None, "UNKNOWN", "eligibility unknown", ids, inputs)
    if vn_status == "ALLOWED" and ok is True:
        codes = (restrictions.value or {}).get("codes") or [] if restrictions.has_data else None
        if codes is not None and len(codes) <= int(r["max_restrictions_for_full"]):
            level = 100
        else:
            level = 75
        status = "VERIFIED" if vn.verified and regions.verified else "INFERRED"
        if status == "INFERRED":
            level = min(level, int(r["inferred_cap"]))
        return Criterion(level, status, "eligible", ids, {**inputs, "restrictions": codes})
    return Criterion(50, "INFERRED", "partially known eligibility", ids, inputs)


def quality(
    official: ResolvedAttribute,
    features: ResolvedAttribute,
    mentions: Iterable[tuple[str, str]],
    *,
    official_domain: str | None,
    rubric: Mapping[str, Any] | None = None,
) -> Criterion:
    """`mentions`: (registered_domain, sentiment) của bằng chứng `third_party_mention` ACTIVE."""
    r = _rubric(rubric, "quality")
    ments = [(d, s) for d, s in mentions if d and d != official_domain]
    n_features = len(features.value or []) if features.has_data else 0
    if not official.verified and n_features == 0 and not ments:
        return Criterion(None, "UNKNOWN", "no website, features or third-party mentions")
    t = 0
    t += 1 if official.verified else 0
    t += 1 if n_features >= int(r["min_features"]) else 0
    pos = {d for d, s in ments if s == "positive"}
    neg = {d for d, s in ments if s == "negative"}
    t += 2 if len(pos) >= 2 else (1 if len(pos) == 1 else 0)
    t -= 1 if len(neg) >= 2 else 0
    t = max(0, min(4, t))
    inputs = {
        "official_verified": official.verified,
        "features": n_features,
        "positive_groups": len(pos),
        "negative_groups": len(neg),
    }
    return Criterion(25 * t, "INFERRED", "computed from website/features/mentions", _ids(official, features), inputs)
