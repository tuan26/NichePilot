"""FakePaidProvider – TEST DOUBLE đóng vai provider có phí. Không gọi mạng; KHÔNG chứng minh tích hợp API thật."""

from __future__ import annotations

from nichepilot.ai.providers.base import (
    ConnectionCheckResult,
    LLMRequest,
    LLMResponse,
    ProviderName,
    ProviderRateLimitedError,
    ProviderUnavailableError,
    TokenUsage,
)


class FakePaidProvider:
    data_origin = "REAL"
    paid = True

    def __init__(self, *, name: ProviderName = "anthropic", fail_with: str | None = None) -> None:
        self.name = name
        self.fail_with = fail_with
        self.calls = 0

    async def count_input_tokens(self, req: LLMRequest) -> int:
        return 100

    async def generate(self, req: LLMRequest) -> LLMResponse:
        self.calls += 1
        if self.fail_with == "rate_limit":
            raise ProviderRateLimitedError("fake 429", sent=True, retry_after_s=0)
        if self.fail_with == "provider_error":
            raise ProviderUnavailableError("fake 503", sent=True)
        return LLMResponse(
            outcome="SUCCESS",
            content_text="fake",
            parsed_output=None,
            usage=TokenUsage(input_tokens=100, output_tokens=10),
            raw_model=req.model,
            data_origin="REAL",
        )

    async def check_connection(self) -> ConnectionCheckResult:
        return ConnectionCheckResult(provider=self.name, result="OK")
