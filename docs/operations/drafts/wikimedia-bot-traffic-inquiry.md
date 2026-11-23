# Bản nháp email hỏi Wikimedia về truy cập Action API (CHƯA GỬI)

> Trạng thái: **bản nháp – chưa gửi**. Chủ sở hữu tự gửi từ địa chỉ liên hệ do chủ sở hữu chọn (không dùng email cá nhân khi chưa
> quyết định). Các chỗ trong `[[ … ]]` do chủ sở hữu điền trước khi gửi; agent không điền thông tin cá nhân hay thông tin giả.
> Lý do: robots.txt của en.wikipedia.org (`User-agent: *` → `Disallow: /w/`, `Disallow: /api/`) mâu thuẫn với mục "Action API rules"
> của Robot Policy – chủ sở hữu chọn hỏi Wikimedia (phương án b, 2026-11-23). Liên quan: `specs/002-niche-discovery/source-verification.md` S1.

---

**To:** bot-traffic@wikimedia.org
**Subject:** Clarification: small research bot using the Action API search vs. robots.txt Disallow /w/ and /api/

Hello Wikimedia team,

I operate a small, self-hosted research tool and would like to confirm that its planned use of English Wikipedia is acceptable
before enabling it. I have read the Terms of Use, the User-Agent Policy, the API Usage Guidelines, API:Etiquette and the Robot policy
on Wikitech.

Planned use:
- Search only, via the Action API: `https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch=<query>&format=json&srlimit=10&maxlag=5`.
  We would not use the Action API to retrieve page HTML.
- For a small number of matching articles, fetch the article page once via the canonical `/wiki/Article_name` URL (no query
  parameters, no cookies, no JavaScript) and store a short excerpt (at most 1,000 characters) with a link back to the article for
  attribution under CC BY-SA 4.0. Content is used for internal research only and is not redistributed in bulk.
- Volume: at most a few hundred requests per run, a few runs per week. Requests are strictly serial (concurrency 1), at most about
  0.5 requests per second, with gzip, `maxlag=5`, exponential backoff on `maxlag`/`ratelimited` errors, honouring `Retry-After` on 429,
  and a 5-second pause after any response that takes more than 1 second.
- Not run on Wikimedia Cloud Services; requests are unauthenticated.

Questions:
1. robots.txt for en.wikipedia.org contains `User-agent: *` with `Disallow: /w/` and `Disallow: /api/`, while the Robot policy also
   contains "Action API rules". For a small research bot as described, is it permitted to call `/w/api.php` for `list=search` only
   (no HTML retrieval), despite those robots.txt directives?
2. If it is permitted, are there additional conditions we should follow (for example authentication, a different rate, or the
   `/api/rest_v1/` or `/w/rest.php` search endpoints instead)? If it is not permitted, which endpoint or method do you recommend for
   small-scale search?
3. For the User-Agent, is the following format acceptable, and is a dedicated contact email or a project website sufficient as the
   contact information?
   `NichePilotResearchBot/0.1 ([[website or contact email chosen by the operator]]) python-httpx/0.28`

We will keep the source disabled until we receive your guidance.

Thank you for your time,
[[Name or team name chosen by the operator]]
[[Contact email or website chosen by the operator – the same contact that will appear in the User-Agent]]
