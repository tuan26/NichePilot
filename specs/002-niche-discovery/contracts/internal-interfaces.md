# Internal Interfaces – E1

Hợp đồng nội bộ giữa các thành phần E1 và với E0. Chữ ký Python mang tính hợp đồng (tên, đầu vào/ra, lỗi); chi tiết cài đặt thuộc
`/speckit-implement` (chưa được phép).

## 0. Phân lớp (khớp `backend/.importlinter` của E0)

- `tools/` (adapter nguồn, fetcher, `PiiEngine`, tool `source.query`/`page.fetch`/`robots.fetch`) không import `modules/`.
- `modules/discovery` (policy, truy cập tên miền, chấm điểm, xóa) không import `tools/`/`ai/`.
- `jobs/agents/niche_discovery.py` điều phối: lấy policy hợp lệ + kiểm tra robots/khoảng cách (modules) → gọi tool qua Tool Registry →
  lưu kết quả đã che (modules) → gọi AI Gateway.
- Tool Registry E0 lưu input/output tool vào `tool_calls` → **mọi văn bản bên ngoài phải được che PII trong handler trước khi trả**;
  văn bản thô không bao giờ là output của tool.

## 1. SourceAdapter (lớp `tools`, FR-006, FR-006c…g, research R-13)

```python
class SourceAdapter(Protocol):
    adapter_type: ClassVar[str]               # searxng_engine | http_json_api | open_dataset | licensed_data
    data_origin: Literal["REAL", "MOCK"]
    config_schema: ClassVar[type[BaseModel]]  # validate source_policies.config; từ chối khóa bị cấm (§1.1)
    async def query(self, policy: UsableSourcePolicy, query: str, *, market: str, language: str,
                    max_results: int) -> SourceResult: ...

@dataclass(frozen=True)
class SourceResult:
    hits: list[SourceHit]          # url, title, snippet, published_at, source_policy_id
    source_status: SourceStatus    # OK | NO_RESULTS | UNAVAILABLE | RATE_LIMITED | ACCESS_RESTRICTED

class SourcePolicyService:          # modules/discovery/sources/policy.py (agent chuyển kết quả thành input của tool `source.query`)
    def usable_for_run(self) -> list[UsableSourcePolicy]: ...   # chỉ enabled ∧ ALLOWED – mọi loại lượt
```

- `UsableSourcePolicy` chỉ tạo được qua `usable_for_run` (kiểu đóng) và chỉ chứa nguồn `enabled ∧ ALLOWED`. Không có tham số, cờ hay
  xác nhận cảnh báo nào làm nguồn `UNVERIFIED`/`PROHIBITED` lọt vào (quyết định A1). Adapter không nhận `source_policies` thô.
- Tool `source.query` nhận snapshot policy (`source_key`, `adapter_type`, `config`, `compliance_status`, `verified_at`) và **từ chối mọi
  trạng thái khác `ALLOWED`** (lớp 2). Snippet kết quả được che PII trong handler.
- Không có hàm nào trong service tự đổi `compliance_status`/`enabled`; chỉ `update_policy(actor_id, …)` do API chủ sở hữu gọi; đổi khỏi
  `ALLOWED` đặt `enabled = false` cùng transaction. Test kiến trúc quét mã: chỉ `update_policy` ghi hai cột này.
- Chính sách truy cập riêng mỗi nguồn (FR-006): `config.rate_limit_per_minute`, `config.max_retries` (0–5), `config.timeout_s` (1–60) –
  adapter tôn trọng; lỗi xác thực (401/403 của API chính thức) → `UNAVAILABLE` lý do `AUTH_FAILED`, không thử lại.
- `SearxngEngineAdapter`: `GET {SEARXNG_URL}/search?format=json&q=…&engines=<engine_name của các policy hợp lệ>` trong mạng nội bộ.
  `SearxngConfigWriter` sinh `settings.yml` (`keep_only` = engine của nguồn đang bật) khi policy thay đổi.
- `HttpJsonApiAdapter`: request theo `base_url` + `query_template`, ánh xạ kết quả bằng `result_mapping`; giới hạn tốc độ theo
  `rate_limit_per_minute` và `known_limits`; header xác thực lấy từ `os.environ[auth_env_var]` lúc gọi (không log, không lưu).
- `OpenDatasetAdapter`/`LicensedDataAdapter`: interface + bản mock trong E1.
- CAPTCHA/chặn → `ACCESS_RESTRICTED`/`RATE_LIMITED`, không thử vượt (FR-006f); nguồn đó tạm ngưng trong lượt.
- Lỗi mạng (DNS, kết nối, timeout) → `UNAVAILABLE` lý do `NETWORK_ERROR`; mọi nguồn của lượt `UNAVAILABLE` → lượt kết thúc
  `PARTIAL_COMPLETED` / `SOURCES_UNAVAILABLE`, không tạo dữ liệu thay thế.
- `MockSourceAdapter`: fixture cố định, `data_origin = MOCK`; production từ chối khởi động nếu cấu hình mock (như E0).

### 1.1 Khóa cấu hình bị cấm chứa credential trực tiếp (A2)

`source_policies.config` được validate đệ quy (mọi cấp lồng nhau, mọi phần tử mảng). Một khóa bị từ chối (`SOURCE_CONFIG_INVALID`) nếu
tên khóa, sau khi chuyển chữ thường và bỏ `-`, `_`, `.`, khớp hoặc chứa một trong các chuỗi sau:

| Nhóm | Chuỗi bị cấm (đã chuẩn hóa) |
|---|---|
| Khóa API | `apikey`, `accesskey`, `secretkey`, `privatekey`, `clientsecret`, `consumersecret` |
| Mật khẩu | `password`, `passwd`, `pwd`, `passphrase` |
| Token / phiên | `token`, `bearer`, `cookie`, `session`, `sessionid`, `jwt` |
| Header xác thực | `authorization`, `authheader`, `xapikey` |
| Khác | `secret`, `credential`, `credentials`, `signature`, `privatekeyid` |

Ngoại lệ duy nhất: khóa đúng bằng `auth_env_var` (giá trị phải khớp `^[A-Z][A-Z0-9_]{2,63}$` – tên biến môi trường, không phải giá
trị). Ngoài ra, mọi **giá trị** chuỗi khớp mẫu thường gặp của credential (tiền tố `sk-`, `Bearer `, chuỗi base64/hex ≥ 32 ký tự liền,
JWT `xxx.yyy.zzz`) cũng bị từ chối. Danh sách là cấu hình mã có test; mở rộng danh sách không cần đổi schema.

## 2. PageFetcher (lớp `tools`, FR-005, FR-030a, FR-031)

```python
class PageFetcher(Protocol):
    data_origin: Literal["REAL", "MOCK"]
    async def fetch(self, url: str, *, deadline: datetime) -> FetchOutcome: ...

@dataclass(frozen=True)
class FetchOutcome:
    status: Literal["SUCCESS", "FAILED", "SKIPPED"]
    reason: str | None          # ROBOTS_DISALLOWED, RATE_LIMITED, ACCESS_RESTRICTED, HTTP_ERROR, TIMEOUT, NETWORK_ERROR, NON_HTML, TOO_LARGE, PII_UNSAFE
    http_status: int | None
    text: RedactedText | None   # nội dung chính ĐÃ che PII (che trong handler); văn bản thô chỉ là biến cục bộ của handler
    redaction: RedactionResult | None
    published_at: datetime | None
    final_url: str | None
```

Agent gọi `DomainAccessService.permit(url)` (modules) trước mỗi lần gọi tool `page.fetch`; thứ tự bắt buộc: robots.txt (tool
`robots.fetch`, cache 24 h trong `domain_access_state`) → khoảng cách tối thiểu
`max(per_domain_interval_s, Crawl-delay, Retry-After)` → HTTP GET (User-Agent nhận diện được, không giả trình duyệt; timeout 20 s;
≤ 3 MB; chỉ `text/html`) → trafilatura (bỏ `author`). 429/503 → thử lại tối đa 2 lần theo `Retry-After`, sau đó `SKIPPED`.
Trang yêu cầu đăng nhập/paywall/CAPTCHA → `SKIPPED ACCESS_RESTRICTED`. `Retry-After` dài hơn thời gian còn lại của lượt → bỏ tên miền
(`RATE_LIMITED`), không chờ vượt giới hạn. `PlaywrightPageFetcher` (profile `browser-fetcher`, tắt mặc định) cài đặt cùng interface; không
dùng stealth, vượt CAPTCHA hay chống phát hiện bot (quyết định I1).

## 3. PiiEngine (lớp `tools/privacy`, FR-012a…c)

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

- Engine production mặc định: `RegexPhonePiiEngine` (`regex-phone/1`) = regex + `phonenumbers` + `PersonNameRiskDetector` (heuristic, research
  R-05). Phát hiện nguy cơ tên người → `NEEDS_REVIEW`. Regex không bao giờ được coi là đủ: đoạn chỉ `REDACTED` khi detector không phát hiện gì.
- Engine tùy chọn dev/test: `SpacyEnPiiEngine` (`spacy-en-sm/1`) – chỉ nạp khi `PII_ENGINE=spacy-en-sm` **và** engine có trong
  `PII_APPROVED_ENGINES`; nhóm dependency `pii-ner` không cài trong image production (quyết định I2).
- `select_pii_engine(settings) -> PiiEngine`: fail-closed – production từ chối khởi động nếu `PII_ENGINE` ∉ `PII_APPROVED_ENGINES` (mặc định
  chỉ `regex-phone`) hoặc engine cần model không có sẵn; không bao giờ tải model lúc chạy.
- `NEEDS_REVIEW`: lưu bản đã che, không tính ngưỡng, không gửi AI. `UNSAFE` (còn mẫu PII sau khi che) → bỏ đoạn,
  `page_fetch_log.reason = PII_UNSAFE`.
- Hàm tạo prompt E1 chỉ nhận `RedactedText` có `status = REDACTED` – không nhận `str` thô (test kiến trúc + mypy).

## 4. EvidenceErasureService và erasure ledger (FR-013e, FR-013f, X4)

```python
async def erase(target: EvidenceRef | SourceRef, *, reason: str, actor_id: UUID) -> ErasureResult
def apply_erasure_ledger(*, strict: bool = True) -> LedgerApplyResult   # CLI: python -m nichepilot.jobs.erasure_ledger --strict
async def ledger_health() -> LedgerHealth                              # dùng cho API gate + GET /api/v1/discovery/status
```

- `erase`: khóa `erasure_ledger_state` (FOR UPDATE – tuần tự hóa xóa/áp dụng sổ) → sổ phải đồng bộ với DB (`tail_seq = applied_seq`,
  nếu không → `ERASURE_LEDGER_NOT_APPLIED`) → (1) append dòng vào ledger (hash chain, fsync; lỗi I/O → 503 `ERASURE_LEDGER_WRITE_FAILED`,
  DB không đổi) → (2) CÙNG transaction DB: xóa nội dung, `ERASED`, `evidence_erasure_requests`, audit `evidence.erased` (định danh + lý do,
  không nội dung/URL), cập nhật `erasure_ledger_state`, **tính lại đồng bộ** ngưỡng bằng chứng của các ngách liên quan → (3) API tạo job
  `discovery.recompute` (qua đường tạo job E0). Lỗi ở (2) → rollback, trả lỗi; cache sức khỏe sổ bị xóa nên cổng 503 bật ngay; dòng sổ
  được áp dụng (kèm tính lại ngách) ở lần `apply_erasure_ledger` kế tiếp (idempotent).
- `apply_erasure_ledger` tính lại các ngách bị ảnh hưởng trong cùng transaction áp dụng sổ (sau restore, ngách không giữ trạng thái cũ).
- `apply_erasure_ledger --strict`: xác minh genesis/`ledger_id`, chuỗi hash, `applied_seq ≤ tail_seq`; áp dụng các dòng
  `seq > applied_seq` trong **một** transaction; thành công → `status = OK`. Bất kỳ lỗi nào → rollback, `status = BLOCKED`, thoát mã ≠ 0.
  Gọi trong service `migrate` (sau `alembic upgrade`) và trong `restore.sh` sau `pg_restore`.
- Gate (không sửa Job Runtime/Scheduler/system status của E0 – H1):
  - API: dependency FastAPI chỉ trên router E1 (endpoint dữ liệu nghiên cứu) gọi `ledger_health()` (cache 60 s); không `OK` → 503
    `ERASURE_LEDGER_NOT_APPLIED`. Trạng thái hiển thị ở `GET /api/v1/discovery/status` (endpoint mới của E1).
  - Agent: bước đầu `preflight` của mọi job `discovery.*` gọi `ledger_health()`; không `OK` → bước thất bại với mã
    `ERASURE_LEDGER_NOT_APPLIED` theo cơ chế lỗi bước sẵn có của E0 (không nhận dữ liệu, không gọi AI).
- Xóa khi lượt đang chạy: agent đọc lại bằng chứng qua `EvidenceService.query` (lọc `ACTIVE`) ngay trước `extract`/`assess`/`evaluate`;
  checkpoint chỉ chứa ID → bằng chứng bị xóa giữa chừng không được dùng ở bước kế tiếp; nội dung trùng `content_hash` đã xóa bị bỏ khi
  thu thập (`page_fetch_log.reason = ERASED_CONTENT`).
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

## 6. Agent và job (lớp `jobs`, `jobs/agents/` như DiagnosticAgent E0)

| Job type | Agent | Giới hạn (định nghĩa agent E0) | Ghi chú |
|---|---|---|---|
| `discovery.run` | `NicheDiscoveryAgent` | max_steps 240, max_ai_calls 120, timeout 6000 s | Bước ở plan.md "Luồng xử lý" |
| `discovery.reevaluate` | `NicheReevaluationAgent` (kế thừa pipeline `discovery.run`) | max_steps 60, max_ai_calls 20 | Thu thập bổ sung + đánh giá lại 1 ngách; truy vấn sinh xác định từ nhóm KH + vấn đề (không AI đề xuất ứng viên); kết quả job có `comparison` before/after |
| `discovery.recompute` | `NicheRecomputeAgent` (không AI) | max_steps 10, max_ai_calls 1 (ràng buộc E0 `≥ 1`; agent không gọi AI – test kiểm tra 0 `ai_usage_logs`) | Sau đổi trọng số / xóa bằng chứng |

- Bước `preflight` (đầu tiên, idempotent): kiểm tra ledger; `ensure_run` tạo hoặc lấy `discovery_runs` theo `job_id` (UNIQUE –
  `INSERT … ON CONFLICT (job_id) DO NOTHING`) với `trigger` và `schedule_id` đọc từ `agent_jobs` của E0. Nhờ đó lượt theo lịch (scheduler E0
  tạo job `discovery.run` bình thường) có bản ghi lượt mà **không** sửa Scheduler/Job Runtime (H1, U1).
- Giới hạn/thu thập (US4, triển khai 2026-11-21):
  - Phân bổ trang: mỗi ứng viên tối đa `ceil(page_limit / số ứng viên)` lượt thử trước; phần dư dành cho ứng viên còn URL; tổng ≤ `page_limit`.
  - Dừng sớm: ứng viên "đủ tạm thời" khi có ≥ `min_items + 1` trích đoạn từ ≥ `min_independent_groups + 1` tên miền (dư 1 vì `assess`
    có thể loại); ứng viên không còn URL coi như đã quyết. Mọi ứng viên đủ/đã quyết → bỏ hàng đợi còn lại; `stop_reason =
    ALL_CANDIDATES_SUFFICIENT` chỉ khi đánh giá xác định cuối cùng xác nhận mọi ứng viên đủ.
  - Chạm `page_limit`: dừng thu thập nhưng vẫn `extract`/`assess` dữ liệu đã có → `PARTIAL_COMPLETED/PAGE_LIMIT_REACHED`. Hết thời gian:
    không gửi lời gọi AI mới, đánh giá xác định → `PARTIAL_COMPLETED/TIME_LIMIT_REACHED`.
  - 429/503: thử lại tối đa 2 lần theo `Retry-After` (mặc định 30 s nếu thiếu); `Retry-After` > thời gian còn lại → bỏ tên miền ngay
    (mọi URL của tên miền ghi `RATE_LIMITED`), lưu `domain_access_state.blocked_until/block_reason`.
  - Job E0 bị hủy giữa chừng: API lượt trả `outcome = PARTIAL_COMPLETED`, `stop_reason = CANCELLED` (suy ra, không sửa runtime E0).
- `preflight`: không có nguồn ALLOWED (lượt theo lịch/đánh giá lại) → `PARTIAL_COMPLETED/NO_COMPLIANT_SEARCH_SOURCE` ngay, 0 lời gọi AI.
- Checkpoint chỉ chứa ID, hash, bộ đếm (trang, thời gian hoạt động), con trỏ hàng đợi URL – không chứa văn bản.
- Hết thời gian khi đang chờ lời gọi AI: lời gọi đang dở xử lý theo quy tắc E0 (giữ chỗ/đối soát), không gửi lời gọi mới, chuyển sang
  `evaluate`/`finalize` → `PARTIAL_COMPLETED` / `TIME_LIMIT_REACHED`.
- Mất kết nối DB giữa bước: theo cơ chế E0 (worker thoát, khởi động lại, tiếp tục từ checkpoint – E0 SC-006); bước E1 idempotent theo
  `seq` và UNIQUE (`page_fetch_log.url_hash`, `niches.dedup_key`) nên không tạo trùng.
- Agent (lớp `jobs`) gọi `modules/discovery`, AI Gateway và tool qua Tool Registry; `allowed_tools` = {`source.query`, `page.fetch`,
  `robots.fetch`}, mọi tool `external_effect = false`.

## 7. Task type AI (Model Task Profile – seed)

| Task type | Đầu vào | Đầu ra (schema bắt buộc) | Model seed trong Model Task Profile (chưa xác minh) |
|---|---|---|---|
| `discovery.candidates` | thị trường, ngôn ngữ, lĩnh vực gợi ý, ngách đã có (tên) | ≤ N ứng viên {name, customer_group, core_problem, queries[≤5]} | claude-sonnet-5-5 |
| `discovery.extract` | trích đoạn đã che PII (≤ 12) của 1 ngách | pain_points, persona, solutions, competitors, monetization_signals, channels – mỗi mục kèm evidence_ids | claude-haiku-5-5 |
| `discovery.assess` | tóm tắt bằng chứng + kết quả extract | per-evidence {relevance, quality, copy_suspected, reason}; per-criterion {level 0/25/50/75/100 \| null, status, reason}; recommendation | claude-sonnet-5-5 |
| `discovery.normalize` | tên/nhóm KH/vấn đề | dạng chuẩn hóa | claude-haiku-5-5 |

Gọi task type phụ: `NicheDiscoveryAgent.definition.task_type = "discovery.candidates"`,
`extra_task_types = ("discovery.extract", "discovery.assess", "discovery.normalize")`; bước gọi `ctx.call_ai(..., task_type="discovery.extract")`.
`JobContext.call_ai` (E0, bổ sung tham số tùy chọn được duyệt 2026-11-20) từ chối task type chưa đăng ký với `TASK_TYPE_NOT_ALLOWED`; mọi lời
gọi vẫn qua `AIGateway` (profile, giá đã xác minh, ngân sách, giới hạn lời gọi/token của job). Không truyền `task_type` → hành vi E0 giữ nguyên.

Model chỉ được chọn qua Model Task Profile của E0 (dữ liệu cấu hình, đổi được qua API) – business logic chỉ nêu task type, không
nêu model ID. Tác vụ đơn giản (`extract`, `normalize`) seed model tiết kiệm; tác vụ phân tích (`candidates`, `assess`) seed model mạnh
hơn. Gọi có phí chỉ khi model đã `verified` và có giá đã xác minh (E0 FR-019c, FR-041) và `AI_PAID_CALLS_ENABLED=true` do chủ sở
hữu bật.

Nội dung ngoài luôn nằm trong khối `<untrusted_content id=…>`; system prompt nêu rõ không làm theo chỉ dẫn trong khối này (FR-012).
`evidence_ids` trong đầu ra phải thuộc tập đã cung cấp – ID lạ → đầu ra bị loại (chống bịa nguồn).

## 8. Audit action mới

`discovery.run_created`, `source.created`, `source.updated` (trước/sau, gồm `compliance_status`, `enabled`), `scoring.weights_version_created`,
`niche.decision_recorded`, `niche.similarity_resolved`, `evidence.erased`, `erasure_ledger.reapplied`, `erasure_ledger.blocked`,
`erasure_ledger.reinitialized`.
