# Quickstart – kiểm chứng E3 Keyword & Audience Research

Mọi kịch bản dùng AI giả lập theo kịch bản và nguồn giả lập (`data_origin = MOCK`). Không gọi API có phí, không truy cập mạng ngoài. Kết quả
MOCK **không** phải nghiên cứu keyword thật; SC-008 giữ `BLOCKED`.

## 1. Kiểm thử tự động

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports && uv run pytest -m keywords
```

```bash
cd frontend && npm run lint && npm run typecheck && npm test
```

```bash
uv run --no-project python scripts/traceability_report.py --strict
```

## 2. Kịch bản tích hợp chính (`tests/integration/keywords/`)

| # | Kịch bản | Kỳ vọng | Yêu cầu |
|---|---|---|---|
| 1 | Ngách MOCK + 2 sản phẩm E2, nguồn mock `ALLOWED`, SERP + trang đối thủ fixture | Keyword có origin; ≥ 50% LONG_TAIL; mỗi sản phẩm có keyword commercial; cluster xếp hạng | FR-005…FR-008, SC-001, SC-003 |
| 2 | AI trả keyword không có origin / origin ngách khác | Keyword bị loại, ghi `rejected` | FR-005 |
| 3 | AI trả thêm trường `search_volume` | Toàn bộ đầu ra bị loại (schema) ; mọi chỉ số `UNKNOWN` | FR-009, SC-002 |
| 4 | Không có nguồn `ALLOWED` | Lượt `PARTIAL_COMPLETED / NO_COMPLIANT_SEARCH_SOURCE`; keyword nội bộ vẫn có, SERP/gap `UNKNOWN` | Clarification (b) |
| 5 | Chạy lại lượt / tiếp tục sau sự cố | 0 keyword/cluster/SERP/bằng chứng trùng | FR-004, SC-004 |
| 6 | Ngách `INSUFFICIENT_EVIDENCE` | 409 `NICHE_NOT_ELIGIBLE` | FR-001 |
| 7 | Chiến lược AI có câu "we tested" không bằng chứng | Câu bị loại, `rejected_claims` +1 | BR-11 |
| 8 | Đổi trọng số | Phiên bản mới, tính lại không AI, điểm cũ tái lập được | FR-017, SC-004 |
| 9 | serp_check với kết quả đổi | Phiên bản 2 + `changes`; lỗi → giữ phiên bản cũ | FR-031 |

## 3. Xem thử giao diện bằng MOCK (development)

```bash
docker compose -f deploy/docker-compose.yml --env-file deploy/env/.env exec -T api python -m nichepilot.jobs.discovery_demo_seed
```

```bash
docker compose -f deploy/docker-compose.yml --env-file deploy/env/.env exec -T api python -m nichepilot.jobs.products_demo_seed
```

```bash
docker compose -f deploy/docker-compose.yml --env-file deploy/env/.env exec -T api python -m nichepilot.jobs.keywords_demo_seed
```

Bảng xếp hạng → bật MOCK → ngách `[MOCK DEMO]` → **Keyword** → cluster xếp hạng; chi tiết cluster hiển thị keyword (Search Volume/CPC/KD =
`UNKNOWN`), intent, SERP, gap, strategy, chú thích "không phải dự báo traffic/doanh thu". Chuyển EN.

## 4. E2E (Playwright, `E2E_SUITE=discovery`)

Sau 3 lệnh seed: mở cluster MOCK → thấy `UNKNOWN` cho chỉ số → ghi quyết định "Theo dõi" kèm lý do → EN.
