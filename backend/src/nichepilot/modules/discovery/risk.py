"""Cờ rủi ro ngách (T095; FR-010, FR-035; data-model `niches.risk_flags`) – xác định, chỉ GẮN CỜ, không tự loại ngách.

`COMPLIANCE_SENSITIVE`: lĩnh vực nhạy cảm/hạn chế theo danh sách từ khóa (sức khỏe/thuốc, tài chính vay/đầu
tư/crypto, cờ bạc,
người lớn, vũ khí, chất kích thích, thực phẩm chức năng giảm cân, pháp lý). Danh sách là heuristic tiếng Anh – có thể
sót/nhầm, chủ
sở hữu luôn xem lại. `LOW_EVIDENCE_FRESHNESS`: độ mới F < 0,25. `MONETIZATION_RISK`: chưa có tín hiệu affiliate có
bằng chứng.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

SENSITIVE_PATTERNS = (
    r"\b(weight[- ]loss|diet pills?|supplements?|nutraceuticals?)\b",
    r"\b(prescription|medication|medicines?|drugs?|pharma\w*|dosage|clinic|diagnos\w+|therapy|treatment)\b",
    r"\b(payday|loans?|credit (repair|card)|debt relief|mortgage|insurance|forex|trading signals?|crypto\w*|bitcoin|"
    r"invest(ing|ment)s?)\b",
    r"\b(casino|gambling|betting|sportsbook|poker|lottery)\b",
    r"\b(adult|porn\w*|escort|dating)\b",
    r"\b(firearms?|guns?|ammo|ammunition|weapons?)\b",
    r"\b(cbd|cannabis|marijuana|vape|vaping|tobacco|nicotine|alcohol|kratom)\b",
    r"\b(legal advice|lawsuit|immigration|visa)\b",
)
SENSITIVE_RE = re.compile("|".join(SENSITIVE_PATTERNS), re.IGNORECASE)
LOW_FRESHNESS = 0.25


def compliance_sensitive(text: str) -> bool:
    return bool(SENSITIVE_RE.search(text or ""))


def risk_flags(*, texts: Iterable[str], monetization_status: str, freshness: float, has_evidence: bool) -> list[str]:
    flags: set[str] = set()
    if any(compliance_sensitive(t) for t in texts):
        flags.add("COMPLIANCE_SENSITIVE")
    if has_evidence and freshness < LOW_FRESHNESS:
        flags.add("LOW_EVIDENCE_FRESHNESS")
    if monetization_status != "SIGNALS_FOUND":
        flags.add("MONETIZATION_RISK")
    return sorted(flags)
