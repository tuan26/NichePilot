"""Schema E2 – đầu ra AI (bắt buộc, `extra="forbid"` – Constitution V, FR-039) và tham số/kết quả lượt.

AI chỉ TRÍCH XUẤT có dẫn `evidence_ids`; trạng thái xác minh, điểm số và trạng thái sẵn sàng do mã quyết định
(research R-03, R-04).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Level = Literal[0, 25, 50, 75, 100]
AD_RESTRICTION_CODES = ("NO_BRAND_BIDDING", "NO_COUPON_SITES", "NO_PPC", "NO_EMAIL", "NO_SOCIAL_ADS", "OTHER")
AdCode = Literal["NO_BRAND_BIDDING", "NO_COUPON_SITES", "NO_PPC", "NO_EMAIL", "NO_SOCIAL_ADS", "OTHER"]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Cited(_Strict):
    evidence_ids: list[str] = Field(min_length=1, max_length=12)


class PriceOut(Cited):
    plan: str = Field(min_length=1, max_length=120)
    amount: float = Field(ge=0)
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$")
    period: Literal["one_time", "month", "year", "other"] = "other"
    promo: bool = False


class TextOut(Cited):
    text: str = Field(min_length=1, max_length=300)


class PainLinkOut(Cited):
    pain_point_id: str


class OfficialSiteOut(Cited):
    url: str = Field(min_length=8, max_length=500)


class ProductOut(_Strict):
    name: str = Field(min_length=1, max_length=200)
    vendor: str | None = Field(default=None, max_length=200)
    official_url: str | None = Field(default=None, max_length=500)
    category: Literal["PHYSICAL", "SOFTWARE", "DIGITAL", "UNKNOWN"] = "UNKNOWN"
    pain_point_links: list[PainLinkOut] = Field(default_factory=list, max_length=10)
    prices: list[PriceOut] = Field(default_factory=list, max_length=10)
    features: list[TextOut] = Field(default_factory=list, max_length=15)
    target_customer: TextOut | None = None


class ProductsExtractOutput(_Strict):
    products: list[ProductOut] = Field(default_factory=list, max_length=20)


class CommissionOut(Cited):
    kind: Literal["percent", "fixed", "tiered", "per_category", "recurring"]
    value: float | None = Field(default=None, ge=0)
    min: float | None = Field(default=None, ge=0)
    max: float | None = Field(default=None, ge=0)
    up_to: bool = False
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    recurring_months: int | None = Field(default=None, ge=1, le=120)
    conditions: str | None = Field(default=None, max_length=300)


class CookieOut(Cited):
    days: int | None = Field(default=None, ge=0, le=3650)
    session: bool = False


class PaymentOut(Cited):
    methods: list[str] = Field(default_factory=list, max_length=10)
    min_payout: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    schedule: str | None = Field(default=None, max_length=60)


class VnEligibilityOut(Cited):
    status: Literal["ALLOWED", "NOT_ALLOWED"]


class RegionsOut(Cited):
    is_global: bool = False
    include: list[str] = Field(default_factory=list, max_length=250)
    exclude: list[str] = Field(default_factory=list, max_length=250)


class RestrictionsOut(Cited):
    codes: list[AdCode] = Field(min_length=1, max_length=6)
    other: str | None = Field(default=None, max_length=300)


class ProgramStatusOut(Cited):
    status: Literal["OPEN", "CLOSED"]


class ProgramOut(_Strict):
    name: str = Field(min_length=1, max_length=200)
    operator_type: Literal["VENDOR", "NETWORK", "UNKNOWN"] = "UNKNOWN"
    operator_name: str | None = Field(default=None, max_length=200)
    terms_url: str | None = Field(default=None, max_length=500)
    commission: CommissionOut | None = None
    cookie: CookieOut | None = None
    payment: PaymentOut | None = None
    vn_eligibility: VnEligibilityOut | None = None
    promotion_regions: RegionsOut | None = None
    ad_restrictions: RestrictionsOut | None = None
    program_status: ProgramStatusOut | None = None


class ProductAttrsOut(_Strict):
    official_website: OfficialSiteOut | None = None
    prices: list[PriceOut] = Field(default_factory=list, max_length=10)
    features: list[TextOut] = Field(default_factory=list, max_length=15)
    target_customer: TextOut | None = None


class ProgramExtractOutput(_Strict):
    product: ProductAttrsOut | None = None
    programs: list[ProgramOut] = Field(default_factory=list, max_length=5)


class LevelOut(_Strict):
    level: Level | None = None
    reason: str = Field(default="", max_length=600)
    evidence_ids: list[str] = Field(default_factory=list, max_length=12)


class MentionOut(_Strict):
    evidence_id: str
    sentiment: Literal["positive", "neutral", "negative"]


class RecommendationOut(_Strict):
    decision: Literal["SELECT", "REJECT", "UNKNOWN"] = "UNKNOWN"
    reason: str = Field(default="", max_length=1000)


class ProductAssessOutput(_Strict):
    fit: LevelOut = Field(default_factory=LevelOut)
    price_fit: LevelOut = Field(default_factory=LevelOut)
    persona_match: Literal["MATCH", "PARTIAL", "NO_MATCH", "UNKNOWN"] = "UNKNOWN"
    third_party_mentions: list[MentionOut] = Field(default_factory=list, max_length=20)
    recommendation: RecommendationOut = Field(default_factory=RecommendationOut)


class ProductRunParams(_Strict):
    """`data-model.md product_runs.params`."""

    niche_id: str
    max_products: int = Field(default=10, ge=1, le=20)
    page_limit: int = Field(default=60, ge=5, le=200)
    time_limit_s: int = Field(default=1800, ge=60, le=5400)
    per_domain_interval_s: float = Field(default=2.0, ge=2.0, le=60.0)
    mock_scenario: str | None = None


class ProductRunResult(_Strict):
    run_id: str
    outcome: Literal["COMPLETED", "PARTIAL_COMPLETED"]
    stop_reason: str
    products_found: int = 0


class TermsCheckParams(_Strict):
    program_id: str
    mock_scenario: str | None = None


class TermsCheckResult(_Strict):
    run_id: str
    outcome: Literal["COMPLETED", "PARTIAL_COMPLETED"]
    stop_reason: str
    new_version: int | None = None


class RecomputeParams(_Strict):
    niche_id: str | None = None
    mock_scenario: str | None = None


class RecomputeResult(_Strict):
    run_id: str
    outcome: Literal["COMPLETED", "PARTIAL_COMPLETED"]
    stop_reason: str
    recomputed: int = 0
