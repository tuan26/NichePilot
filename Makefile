# NichePilot – lệnh vận hành và phát triển. Xem specs/001-foundation-ai-infrastructure/quickstart.md
COMPOSE := docker compose -f deploy/docker-compose.yml --env-file deploy/env/.env
COMPOSE_DEV := docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml --env-file deploy/env/.env

.PHONY: up down dev logs migrate test test-backend test-frontend test-e2e test-live lint backup restore

up:
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

dev:
	$(COMPOSE_DEV) up --build

logs:
	$(COMPOSE) logs -f api worker

migrate:
	$(COMPOSE) run --rm migrate

lint:
	cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run lint-imports
	cd frontend && npm run lint && npm run typecheck

test: lint test-backend test-frontend

test-backend:
	cd backend && uv run pytest

test-frontend:
	cd frontend && npm test

test-e2e:
	cd frontend && npm run test:e2e

# Gọi API THẬT có phí – chỉ chạy khi chủ sở hữu cho phép (AI_PAID_CALLS_ENABLED=true + API key + NICHEPILOT_LIVE_MAX_USD)
test-live:
	cd backend && uv run pytest -m live

backup:
	$(COMPOSE) --profile ops run --rm --entrypoint /scripts/backup.sh backup

restore:
	@test -n "$(FILE)" || (echo "Dùng: make restore FILE=backups/<file>.dump" && exit 1)
	$(COMPOSE) --profile ops run --rm --entrypoint /scripts/restore.sh backup /backups/$(notdir $(FILE))
	# E1 (X4): áp dụng lại erasure ledger trước khi dữ liệu được dùng; lỗi → make thất bại, dữ liệu vẫn bị chặn
	$(COMPOSE) run --rm --no-deps migrate python -m nichepilot.jobs.erasure_ledger --strict
