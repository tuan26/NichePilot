"""Kiểm chứng đầu ra AI trước khi lưu (research R-03; FR-009, FR-024; Constitution I).

1. Mọi `evidence_id` phải thuộc tập trích đoạn đã đưa vào prompt – một id lạ → loại TOÀN BỘ mục chứa nó (sản
phẩm/chương trình).
2. Giá trị số (giá, % hoa hồng, ngày cookie, ngưỡng thanh toán) phải xuất hiện trong ít nhất một trích đoạn được dẫn –
không thấy →
   bỏ giá trị đó (thành UNKNOWN) và đếm vào `rejected_values`.
3. Mã quốc gia phải là ISO-3166 alpha-2 (2 chữ hoa); mã giới hạn quảng cáo đã được schema ràng buộc.
Mã thuần, không I/O.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from nichepilot.modules.products.schemas import (
    CommissionOut,
    ProductAttrsOut,
    ProductOut,
    ProductsExtractOutput,
    ProgramExtractOutput,
    ProgramOut,
)

NUM_RE = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")
ISO2_RE = re.compile(r"^[A-Z]{2}$")


@dataclass
class Validation:
    rejected_values: int = 0
    rejected_items: int = 0


def numbers_in(text: str) -> set[Decimal]:
    out: set[Decimal] = set()
    for raw in NUM_RE.findall(text or ""):
        try:
            out.add(Decimal(raw.replace(",", "")).normalize())
        except InvalidOperation:
            continue
    return out


def supported(number: float | int | None, evidence_ids: Iterable[str], excerpts: Mapping[str, str]) -> bool:
    """Số `number` có xuất hiện trong ít nhất một trích đoạn được dẫn không (so sánh giá trị đã chuẩn hóa)."""
    if number is None:
        return True
    target = Decimal(str(number)).normalize()
    return any(target in numbers_in(excerpts.get(eid, "")) for eid in evidence_ids)


def _ids_ok(ids: Iterable[str], allowed: Mapping[str, str]) -> bool:
    return all(i in allowed for i in ids)


def _product_ids(p: ProductOut) -> list[str]:
    ids: list[str] = []
    for link in p.pain_point_links:
        ids += link.evidence_ids
    for pr in p.prices:
        ids += pr.evidence_ids
    for f in p.features:
        ids += f.evidence_ids
    if p.target_customer:
        ids += p.target_customer.evidence_ids
    return ids


def validate_products(
    out: ProductsExtractOutput, excerpts: Mapping[str, str], pain_point_ids: set[str], v: Validation | None = None
) -> tuple[list[ProductOut], Validation]:
    v = v or Validation()
    kept: list[ProductOut] = []
    for p in out.products:
        if not _ids_ok(_product_ids(p), excerpts):
            v.rejected_items += 1  # evidence_id lạ → chống bịa nguồn: loại cả sản phẩm
            continue
        links = [link for link in p.pain_point_links if link.pain_point_id in pain_point_ids]
        prices = []
        for pr in p.prices:
            if supported(pr.amount, pr.evidence_ids, excerpts):
                prices.append(pr)
            else:
                v.rejected_values += 1
        kept.append(p.model_copy(update={"pain_point_links": links, "prices": prices}))
    return kept, v


def _commission_ok(c: CommissionOut, excerpts: Mapping[str, str]) -> bool:
    nums = [c.value, c.min, c.max]
    if c.kind in ("percent", "recurring", "fixed") and c.value is None and c.min is None and c.max is None:
        return False  # không có con số nào → không dùng được (UNKNOWN)
    return all(supported(n, c.evidence_ids, excerpts) for n in nums) and supported(
        c.recurring_months, c.evidence_ids, excerpts
    )


def _validate_program(p: ProgramOut, excerpts: Mapping[str, str], v: Validation) -> ProgramOut | None:
    parts = [
        p.commission,
        p.cookie,
        p.payment,
        p.vn_eligibility,
        p.promotion_regions,
        p.ad_restrictions,
        p.program_status,
    ]
    ids = [i for part in parts if part is not None for i in part.evidence_ids]
    if not _ids_ok(ids, excerpts):
        v.rejected_items += 1
        return None
    upd: dict[str, object] = {}
    if p.commission is not None and not _commission_ok(p.commission, excerpts):
        upd["commission"] = None
        v.rejected_values += 1
    if p.cookie is not None and not p.cookie.session and not supported(p.cookie.days, p.cookie.evidence_ids, excerpts):
        upd["cookie"] = None
        v.rejected_values += 1
    if p.cookie is not None and not p.cookie.session and p.cookie.days is None:
        upd["cookie"] = None
    if p.payment is not None and not supported(p.payment.min_payout, p.payment.evidence_ids, excerpts):
        upd["payment"] = p.payment.model_copy(update={"min_payout": None})
        v.rejected_values += 1
    if p.promotion_regions is not None:
        codes = [*p.promotion_regions.include, *p.promotion_regions.exclude]
        if any(not ISO2_RE.match(c) for c in codes) or (not p.promotion_regions.is_global and not codes):
            upd["promotion_regions"] = None
            v.rejected_values += 1
    return p.model_copy(update=upd)


def validate_program_extract(
    out: ProgramExtractOutput, excerpts: Mapping[str, str], v: Validation | None = None
) -> tuple[ProductAttrsOut | None, list[ProgramOut], Validation]:
    v = v or Validation()
    product = out.product
    if product is not None:
        ids: list[str] = []
        if product.official_website:
            ids += product.official_website.evidence_ids
        for pr in product.prices:
            ids += pr.evidence_ids
        for f in product.features:
            ids += f.evidence_ids
        if product.target_customer:
            ids += product.target_customer.evidence_ids
        if not _ids_ok(ids, excerpts):
            v.rejected_items += 1
            product = None
        else:
            prices = [pr for pr in product.prices if supported(pr.amount, pr.evidence_ids, excerpts)]
            v.rejected_values += len(product.prices) - len(prices)
            product = product.model_copy(update={"prices": prices})
    programs = [q for p in out.programs if (q := _validate_program(p, excerpts, v)) is not None]
    return product, programs, v
