"""Khóa chống trùng sản phẩm/chương trình (research R-08; FR-015).

- Sản phẩm: `domain:<official_domain>` khi có website chính thức; ngược lại `name:<vendor chuẩn hóa>|<tên chuẩn hóa>`.
- Chương trình: `<operator_domain hoặc tên chuẩn hóa>|<terms_url chuẩn hóa hoặc tên chuẩn hóa>`.
Chuẩn hóa: chữ thường, bỏ dấu, bỏ hậu tố pháp lý (inc, llc, ltd, gmbh, co, corp), chỉ giữ chữ-số. Mã thuần.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit

LEGAL_SUFFIXES = {"inc", "llc", "ltd", "gmbh", "co", "corp", "corporation", "limited", "plc", "sa", "srl"}
_TOKEN = re.compile(r"[a-z0-9]+")


def normalize_name(text: str | None) -> str:
    if not text:
        return ""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    ascii_text = ascii_text.replace("[mock demo]", " ").replace("[mock]", " ")
    tokens = [t for t in _TOKEN.findall(ascii_text) if t not in LEGAL_SUFFIXES]
    return " ".join(tokens)


def normalize_url(url: str | None) -> str:
    if not url:
        return ""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower().removeprefix("www.")
    path = parts.path.rstrip("/").lower()
    return f"{host}{path}"


def product_dedup_key(name: str, vendor: str | None, official_domain: str | None) -> str:
    if official_domain:
        return f"domain:{official_domain.lower()}"
    return f"name:{normalize_name(vendor)}|{normalize_name(name)}"


def program_dedup_key(name: str, operator_domain: str | None, terms_url: str | None) -> str:
    left = operator_domain.lower() if operator_domain else normalize_name(name)
    right = normalize_url(terms_url) or normalize_name(name)
    return f"{left}|{right}"
