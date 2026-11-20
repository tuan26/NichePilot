# Internal Interfaces – E1

Hợp đồng nội bộ giữa các thành phần E1 và với E0. Chữ ký Python mang tính hợp đồng (tên, đầu vào/ra, lỗi); chi tiết cài đặt thuộc
`/speckit-implement` (chưa được phép).

## 1. SourceAdapter (lớp `tools`, FR-006, FR-006c…g, research R-13)

```python
class SourceAdapter(Protocol):
    adapter_type: ClassVar[str]               # searxng_engine | http_json_api | open_dataset | licensed_data
    data_origin: Literal["REAL", "MOCK"]
    config_schema: ClassVar[type[BaseModel]]  # validate source_policies.config; từ chối khóa giống secret
    async def query(self, policy: UsableSourcePolicy, query: str, *, market: str, language: str,
                    max_results: int) -> SourceResult: ...

@dataclass(frozen=True)
class SourceResult:
    hits: list[SourceHit]          # url, title, snippet, published_at, source_policy_id
    source_status: SourceStatus    # OK | NO_RESULTS | UNAVAILABLE | RATE_LIMITED | ACCESS_RESTRICTED

class SourcePolicyService:          # modules/discovery/sources/policy.py
    def usable_for_run(self, *, trigger: Literal["MANUAL", "SCHEDULED"],
                       include_unverified: bool) -> list[UsableSourcePolicy]: ...
```

- `UsableSourcePolicy` chỉ tạo được qua `usable_for_run` (kiểu đóng): `SCHEDULED` → chỉ `enabled ∧ ALLOWED`; `MANUAL` +
  `include_unverified` → thêm `enabled ∧ UNVERIFIED ∧ warning_acknowledged`; `PROHIBITED` không bao giờ. Adapter không nhận
  `source_policies` thô → không có đường gọi nguồn chưa qua kiểm tra (test kiến trúc).
- Không có hàm nào trong service tự đổi `compliance_status`/`enabled`; chỉ `update_policy(actor_id, …)` do API chủ sở hữu gọi.
- `SearxngEngineAdapter`: `GET {SEARXNG_URL}/search?format=json&q=…&engines=<engine_name của các policy hợp lệ>` trong mạng nội bộ.
  `SearxngConfigWriter` sinh `settings.yml` (`keep_only` = engine của nguồn đang bật) khi policy thay đổi.
- `HttpJsonApiAdapter`: request theo `base_url` + `query_template`, ánh xạ kết quả bằng `result_mapping`; giới hạn tốc độ theo
  `rate_limit_per_minute` và `known_limits`; header xác thực lấy từ `os.environ[auth_env_var]` lúc gọi (không log, không lưu).
- `OpenDatasetAdapter`/`LicensedDataAdapter`: interface + bản mock trong E1.
- CAPTCHA/chặn → `ACCESS_RESTRICTED`/`RATE_LIMITED`, không thử vượt (FR-006f); nguồn đó tạm ngưng trong lượt.
- `MockSourceAdapter`: fixture cố định, `data_origin = MOCK`; production từ chối khởi động nếu cấu hình mock (như E0).

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
Trang yêu cầu đăng nhập/paywall/CAPTCHA → `SKIPPED ACCESS_RESTRICTED`. `PlaywrightPageFetcher` (profile `browser-fetcher`, tắt mặc định) cài đặt cùng interface; không dùng thành phần lẩn tránh
phát hiện bot (stealth). Crawl4AI không dùng (research R-03).

## 3. PiiEngine (lớp `modules/discovery/privacy`, FR-012a…c)

```python
class PiiEngine(Protocol):           # thay thế được (ví dụ Presidio sau này)
    name: ClassVar[str]
    def supports(self, language: str) -> bool: ...
    def redact(self, text: str, *, language: str, country: str) -> RedactionResult: ...

@dataclass(frozen=True)
class RedactionResult:
    text: RedactedText                       # NewType; đã thay [EMAIL] [PHONE] [USER] [PERSON]
    counts: dict[str, int]
    status: Literal["REDACTED", "NEEDS_REVIEW", "UNSAFE"]
```

- E1: `RegexSpacyPiiEngine` = regex + `phonenumbers` + spaCy `en_core_web_sm` (chỉ `ner`) cho tiếng Anh. Ngôn ngữ không `supports` →
  che regex/phonenumbers rồi `NEEDS_REVIEW`. Model không nạp được → `NEEDS_REVIEW` (không âm thầm bỏ qua NER).
- `NEEDS_REVIEW`: lưu bản đã che, không tính ngưỡng, không gửi AI. `UNSAFE` (còn mẫu PII sau khi che) → bỏ đoạn,
  `page_fetch_log.reason = PII_UNSAFE`.
- Hàm tạo prompt E1 chỉ nhận `RedactedText` có `status = REDACTED` – không nhận `str` thô (test kiến trúc + mypy).

## 4. EvidenceErasureService và erasure ledger (FR-013e, FR-013f, X4)

```python
async def erase(target: EvidenceRef | SourceRef, *, reason: str, actor_id: UUID) -> ErasureResult
def apply_erasure_ledger(*, strict: bool = True) -> LedgerApplyResult   # CLI: python -m nichepilot.ops.apply_erasure_ledger --strict
async def ledger_health() -> LedgerHealth                              # dùng cho API gate + /system/status
```

- `erase`: (1) append dòng vào ledger (hash chain, fsync) → (2) transaction DB (xóa nội dung, `ERASED`, `evidence_erasure_requests`,
  audit `evidence.erased`, cập nhật `erasure_ledger_state`) → (3) tạo job `discovery.recompute`. Lỗi ở (2) → trả lỗi; dòng sổ được áp
  dụng ở lần kiểm tra kế tiếp (idempotent).
- `apply_erasure_ledger --strict`: xác minh genesis/`ledger_id`, chuỗi hash, `applied_seq ≤ tail_seq`; áp dụng các dòng
  `seq > applied_seq` trong **một** transaction; thành công → `status = OK`. Bất kỳ lỗi nào → rollback, `status = BLOCKED`, thoát mã ≠ 0.
  Gọi trong service `migrate` (sau `alembic upgrade`) và trong `restore.sh` sau `pg_restore`.
- Gate: API middleware cho router E1 + worker trước khi nhận job E1 gọi `ledger_health()` (cache 60 s); không `OK`/lệch → 503
  `ERASURE_LEDGER_NOT_APPLIED` (API) / không nhận job (worker). `/api/v1/system/status` có thành phần `erasure_ledger`.
- Sổ không chứa nội dung/PII: chỉ ID, hash, thời điểm.

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

| Task type | Đầu vào | Đầu ra (schema bắt buộc) | Model seed trong Model Task Profile (chưa xác minh) |
|---|---|---|---|
| `discovery.candidates` | thị trường, ngôn ngữ, lĩnh vực gợi ý, ngách đã có (tên) | ≤ N ứng viên {name, customer_group, core_problem, queries[≤5]} | claude-sonnet-5-5 |
| `discovery.extract` | trích đoạn đã che PII (≤ 12) của 1 ngách | pain_points, persona, solutions, competitors, monetization_signals, channels – mỗi mục kèm evidence_ids | claude-haiku-5-5 |
| `discovery.assess` | tóm tắt bằng chứng + kết quả extract | per-evidence {relevance, quality, copy_suspected, reason}; per-criterion {level 0/25/50/75/100 \| null, status, reason}; recommendation | claude-sonnet-5-5 |
| `discovery.normalize` | tên/nhóm KH/vấn đề | dạng chuẩn hóa | claude-haiku-5-5 |

Model chỉ được chọn qua Model Task Profile của E0 (dữ liệu cấu hình, đổi được qua API) – business logic chỉ nêu task type, không
nêu model ID. Tác vụ đơn giản (`extract`, `normalize`) seed model tiết kiệm; tác vụ phân tích (`candidates`, `assess`) seed model mạnh
hơn. Gọi có phí chỉ khi model đã `verified` và có giá đã xác minh (E0 FR-019c, FR-041) và `AI_PAID_CALLS_ENABLED=true` do chủ sở
hữu bật.

Nội dung ngoài luôn nằm trong khối `<untrusted_content id=…>`; system prompt nêu rõ không làm theo chỉ dẫn trong khối này (FR-012).
`evidence_ids` trong đầu ra phải thuộc tập đã cung cấp – ID lạ → đầu ra bị loại (chống bịa nguồn).

## 8. Audit action mới

`discovery.run_created`, `source.created`, `source.updated`, `scoring.weights_version_created`,
`niche.decision_recorded`, `niche.similarity_resolved`, `evidence.erased`, `erasure_ledger.reapplied`, `erasure_ledger.blocked`,
`erasure_ledger.reinitialized`.
