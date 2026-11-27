"""Chuẩn hóa, khóa gộp trùng và độ dài keyword (research R-03, R-04; FR-006, FR-008) – mã thuần, xác định."""

from __future__ import annotations

import re
import unicodedata

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_ES_ENDINGS = ("ses", "xes", "zes", "ches", "shes")


def normalize(text: str) -> str:
    """Chữ thường, bỏ dấu (kể cả `đ`), thay ký tự không chữ-số bằng khoảng trắng, gộp khoảng trắng."""
    s = text.replace("đ", "d").replace("Đ", "D")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch)).lower()
    return " ".join(_NON_ALNUM.sub(" ", s).split())


def singular(token: str) -> str:
    """Số ít đơn giản cho từ ≥ 4 ký tự (chỉ dùng cho khóa gộp trùng, không hiển thị)."""
    if len(token) < 4:
        return token
    if token.endswith("ies"):
        return token[:-3] + "y"
    if token.endswith(_ES_ENDINGS):
        return token[:-2]
    if token.endswith("s") and not token.endswith(("ss", "us", "is")):
        return token[:-1]
    return token


def dedup_key(text: str) -> str:
    """Khóa gộp trùng: chuẩn hóa → số ít → sắp xếp token (không phụ thuộc hoa/thường, dấu, số nhiều, thứ tự từ)."""
    return " ".join(sorted(singular(t) for t in normalize(text).split()))


def length_class(text: str) -> str:
    """`HEAD` 1–2 từ, `MID` 3 từ, `LONG_TAIL` ≥ 4 từ (theo số từ sau chuẩn hóa)."""
    n = len(normalize(text).split())
    if n <= 2:
        return "HEAD"
    if n == 3:
        return "MID"
    return "LONG_TAIL"
