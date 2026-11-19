# Internal Interfaces – E1

Hợp đồng nội bộ giữa các thành phần E1 và với E0. Chữ ký Python mang tính hợp đồng (tên, đầu vào/ra, lỗi); chi tiết cài đặt thuộc
`/speckit-implement` (chưa được phép).

## 1. SearchAdapter (lớp `tools`, FR-006, FR-006c…f)

```python
class SearchAdapter(Protocol):
    data_origin: Literal["REAL", "MOCK"]
    async def search(self, query: str, *, market: str, language: str,
                     engines: Sequence[str], max_results: int) -> SearchResult: ...

@dataclass(frozen=True)
class SearchResult:
    hits: list[SearchHit]                 # url, title, snippet, engine
    engine_status: dict[str, EngineStatus] # OK | NO_RESULTS | UNAVAILABLE | RATE_LIMITED | CAPTCHA_DETECTED
```

- `SearxngSearchAdapter`: gọi `GET {SEARXNG_URL}/search?format=json&engines=...` trong mạng Compose nội bộ. `engines` luôn lấy từ
  `SearchSourcePolicyService.enabled_engines()` – adapter từ chối engine không có trong danh sách (phòng thủ 2 lớp).
- Engine trả CAPTCHA/chặn → `CAPTCHA_DETECTED`/`RATE_LIMITED`, không thử vượt (FR-006f); engine đó tạm ngưng trong lượt.
- `MockSearchAdapter`: kết quả cố định từ fixture, `data_origin = MOCK`; production từ chối khởi động nếu cấu hình mock (như E0).

## 2. PageFetcher (lớp `tools`, FR-005, FR-030a, FR-031)

```python
class PageFetcher(Protocol):
    data_origin: Literal["REAL", "MOCK"]
    async def fetch(self, url: str, *, deadline: datetime) -> FetchOutcome: ...

@dataclass(frozen=True)
class FetchOutcome:
    status: Literal["SUCCESS", "FAILED", "SKIPPED"]
    reason: str | None          # ROBOTS_DISALLOWED, RATE_LIMITED, ACCESS_RESTRICTED, HTTP_ERROR, TIMEOUT, NON_HTML, TOO_LARGE
    http_status: int | None
    text: str | None            # nội dung chính (CHƯA che PII) – chỉ tồn tại trong bộ nhớ, không log, không checkpoint
    published_at: datetime | None
    final_url: str | None
```

Thứ tự bắt buộc: robots.txt (cache 24 h trong `domain_access_state`) → khoảng cách tối thiểu
`max(per_domain_interval_s, Crawl-delay, Retry-After)` → HTTP GET (User-Agent nhận diện được, không giả trình duyệt; timeout 20 s;
≤ 3 MB; chỉ `text/html`) → trafilatura (bỏ `author`). 429/503 → thử lại tối đa 2 lần theo `Retry-After`, sau đó `SKIPPED`.
Trang yêu cầu đăng nhập/paywall/CAPTCHA → `SKIPPED ACCESS_RESTRICTED`. Crawl4AI (profile tùy chọn) cài đặt cùng interface.

## 3. PiiRedactor (lớp `modules/discovery/privacy`, FR-012a…c)

```python
def redact(text: str, *, language: str, country: str) -> RedactionResult: ...

@dataclass(frozen=True)
class RedactionResult:
    text: str                                # đã thay [EMAIL] [PHONE] [USER] [PERSON]
    counts: dict[str, int]
    status: Literal["REDACTED", "NEEDS_REVIEW", "UNSAFE"]
```

- `UNSAFE` (còn mẫu PII sau khi che) → đoạn bị bỏ, `page_fetch_log.reason = PII_UNSAFE`.
- Bắt buộc gọi trước: ghi `research_evidence`, tạo prompt AI, ghi log có nội dung, ghi checkpoint. Kiểm tra bằng test kiến trúc:
  hàm tạo prompt E1 chỉ nhận kiểu `RedactedText` (NewType) – không nhận `str` thô.

## 4. EvidenceErasureService (FR-013e, FR-013f)

```python
async def erase(target: EvidenceRef | SourceRef, *, reason: str, actor_id: UUID) -> ErasureResult
async def reapply_ledger() -> int   # gọi bởi restore.sh sau khi khôi phục và khi API khởi động
```

- Trong một transaction: đặt `excerpt = NULL`, `value = NULL`, `lifecycle_status = ERASED`, thay URL bằng `erased:<sha256>`,
  ghi `evidence_erasure_requests`, audit `evidence.erased` (chỉ ID + hash + lý do). Sau commit: append dòng JSON
  `{seq, target_type, content_hash, url_hash, erased_at}` vào ledger (fsync) rồi tạo job `discovery.recompute` cho ngách liên quan.
- `reapply_ledger` idempotent; ghi kết quả vào log vận hành. `content_hash`/`url_hash` cũng dùng để chặn thu thập lại.

## 5. Scoring (lớp `modules/discovery/scoring`, thuần, không I/O)

```python
def compute_opportunity(criteria: Mapping[Criterion, CriterionInput], weights: Weights,
                        coverage_threshold: Decimal) -> OpportunityResult   # score|None, coverage, normalized weights, status
def compute_confidence(evidence: Sequence[EvidenceFacts], criteria_status: Mapping[Criterion, Status],
                       coverage: Decimal, evidence_sufficient: bool, params: ConfidenceParams,
                       now: datetime) -> ConfidenceResult
def evaluate_threshold(links: Sequence[EvidenceLinkFacts], rules: EvidenceRules) -> ThresholdResult
def similarity(a: NicheKey, b: NicheKey, params: DedupParams) -> float
```

`compute_confidence` không có tham số Opportunity (FR-020) – kiểm tra bằng test chữ ký. Công thức chi tiết: [scoring-rubric.md](./scoring-rubric.md).

## 6. Agent và job (lớp `ai`/`jobs`)

| Job type | Agent | Giới hạn (định nghĩa agent E0) | Ghi chú |
|---|---|---|---|
| `discovery.run` | `NicheDiscoveryAgent` | max_steps 240, max_ai_calls 120, timeout 6000 s | Bước ở plan.md "Luồng xử lý" |
| `discovery.reevaluate` | `NicheReevaluationAgent` | max_steps 60, max_ai_calls 20 | Thu thập bổ sung + đánh giá lại 1 ngách |
| `discovery.recompute` | (không AI) | max_steps 10, max_ai_calls 0 | Sau đổi trọng số / xóa bằng chứng |

- Checkpoint chỉ chứa ID, hash, bộ đếm (trang, thời gian hoạt động), con trỏ hàng đợi URL – không chứa văn bản.
- Lớp `modules/discovery` không import `ai`/`tools`. Agent gọi `DiscoveryService` (modules) và tool qua Tool Registry; phù hợp
  hợp đồng import-linter E0.

## 7. Task type AI (Model Task Profile – seed)

| Task type | Đầu vào | Đầu ra (schema bắt buộc) | Model mặc định (chưa xác minh) |
|---|---|---|---|
| `discovery.candidates` | thị trường, ngôn ngữ, lĩnh vực gợi ý, ngách đã có (tên) | ≤ N ứng viên {name, customer_group, core_problem, queries[≤5]} | claude-sonnet-5-5 |
| `discovery.extract` | trích đoạn đã che PII (≤ 12) của 1 ngách | pain_points, persona, solutions, competitors, monetization_signals, channels – mỗi mục kèm evidence_ids | claude-haiku-5-5 |
| `discovery.assess` | tóm tắt bằng chứng + kết quả extract | per-evidence {relevance, quality, copy_suspected, reason}; per-criterion {level 0/25/50/75/100 \| null, status, reason}; recommendation | claude-sonnet-5-5 |
| `discovery.normalize` | tên/nhóm KH/vấn đề | dạng chuẩn hóa | claude-haiku-5-5 |

Nội dung ngoài luôn nằm trong khối `<untrusted_content id=…>`; system prompt nêu rõ không làm theo chỉ dẫn trong khối này (FR-012).
`evidence_ids` trong đầu ra phải thuộc tập đã cung cấp – ID lạ → đầu ra bị loại (chống bịa nguồn).

## 8. Audit action mới

`discovery.run_created`, `search_source.created`, `search_source.updated`, `scoring.weights_version_created`,
`niche.decision_recorded`, `niche.similarity_resolved`, `evidence.erased`, `erasure_ledger.reapplied`.
