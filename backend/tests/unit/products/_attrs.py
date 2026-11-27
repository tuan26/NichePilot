"""Tiện ích dựng thuộc tính cho unit test E2 (dữ liệu tự soạn – không phải dữ liệu thật)."""

from __future__ import annotations

from typing import Any

from nichepilot.modules.products.attributes import AttrEvidence, ResolvedAttribute, resolve

_n = 0


def ev(key: str, value: dict[str, Any], status: str = "VERIFIED", domain: str = "vendor.example") -> AttrEvidence:
    global _n
    _n += 1
    return AttrEvidence(f"e{_n}", key, value, status, f"https://{domain}/p{_n}", domain, "[MOCK] excerpt")


def attr(
    key: str, value: dict[str, Any] | None, status: str = "VERIFIED", domain: str = "vendor.example"
) -> ResolvedAttribute:
    if value is None:
        return ResolvedAttribute(key, "UNKNOWN", None)
    return resolve(key, [ev(key, value, status, domain)])
