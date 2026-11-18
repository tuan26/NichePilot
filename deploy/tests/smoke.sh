#!/usr/bin/env bash
# Smoke test Docker Compose (FR-070, FR-074, SC-001, SC-002).
# Test case: TC-FR070-02 TC-SC001-01 TC-SC002-01 (prod), TC-FR074-02 (dev). Chỉ chạy trong CI/thủ công (cần Docker).
#   deploy/tests/smoke.sh prod  – make up → mọi service healthy ≤ 5 phút; RAM nghỉ (docker stats) ≤ 3 GB
#   SMOKE_NO_BUILD=1 dùng image đã build sẵn (máy cần build với CA/proxy riêng)
#   deploy/tests/smoke.sh dev   – make dev → sửa file backend/frontend → api, worker, Vite tự nạp lại
# Ghi báo cáo vào ${SMOKE_REPORT:-smoke-report.txt}. Chạy với MockAIProvider, AI_PAID_CALLS_ENABLED=false.
set -euo pipefail

MODE="${1:-prod}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
REPORT="${SMOKE_REPORT:-$ROOT/smoke-report.txt}"
ENV_FILE="deploy/env/.env"
TIMEOUT_S="${SMOKE_TIMEOUT_S:-300}"
MAX_IDLE_MB="${SMOKE_MAX_IDLE_MB:-3072}"
COMPOSE=(docker compose -f deploy/docker-compose.yml --env-file "$ENV_FILE")
COMPOSE_DEV=(docker compose -f deploy/docker-compose.yml -f deploy/docker-compose.dev.yml)
# SMOKE_EXTRA_COMPOSE: file override chỉ dùng cho máy cần proxy/CA riêng (không commit), ví dụ mạng host cho Vite.
[ -n "${SMOKE_EXTRA_COMPOSE:-}" ] && COMPOSE_DEV+=(-f "$SMOKE_EXTRA_COMPOSE")
COMPOSE_DEV+=(--env-file "$ENV_FILE")

[ -f "$ENV_FILE" ] || cp deploy/env/.env.example "$ENV_FILE"
grep -q '^AI_PAID_CALLS_ENABLED=false$' "$ENV_FILE" || { echo "Smoke test chỉ chạy khi AI_PAID_CALLS_ENABLED=false" >&2; exit 2; }

log() { echo "$*" | tee -a "$REPORT"; }
dump_dev_logs() {  # chẩn đoán khi thất bại: vài dòng cuối của từng service vào báo cáo
  for svc in web api worker; do
    log "--- $svc (tail 25) ---"
    "${COMPOSE_DEV[@]}" logs --no-color --tail 25 "$svc" 2>&1 | cut -c1-300 | tee -a "$REPORT"
  done
}
: > "$REPORT"
log "mode=$MODE date=$(date -u +%FT%TZ)"

wait_http() {  # url, timeout
  local url="$1" limit="$2" start=$SECONDS
  until curl -fsS -o /dev/null "$url"; do
    (( SECONDS - start > limit )) && return 1
    sleep 3
  done
}

to_mb() {  # "512.3MiB" | "1.2GiB" | "800kB" → MB (số nguyên)
  awk -v v="$1" 'BEGIN{n=v+0; u=v; gsub(/[0-9.]/,"",u);
    if(u~/^GiB|^GB/) n*=1024; else if(u~/^KiB|^kB/) n/=1024; else if(u~/^B$/) n/=1048576; printf "%d", n}'
}

if [ "$MODE" = "prod" ]; then
  start=$SECONDS
  if [ "${SMOKE_NO_BUILD:-0}" = "1" ]; then "${COMPOSE[@]}" up -d; else "${COMPOSE[@]}" up -d --build; fi
  wait_http "http://localhost:8080/health" "$TIMEOUT_S" || { log "FAIL: không healthy sau ${TIMEOUT_S}s"; "${COMPOSE[@]}" ps | tee -a "$REPORT"; exit 1; }
  log "startup_seconds=$(( SECONDS - start )) (giới hạn ${TIMEOUT_S})"
  sleep "${SMOKE_IDLE_WAIT_S:-60}"   # để hệ thống về trạng thái nghỉ
  total=0
  while read -r name mem; do
    mb=$(to_mb "$mem"); total=$(( total + mb )); log "mem $name ${mb}MB"
  done < <(docker stats --no-stream --format '{{.Name}} {{.MemUsage}}' | awk '{print $1, $2}')
  log "idle_total_mb=$total (giới hạn ${MAX_IDLE_MB})"
  (( total <= MAX_IDLE_MB )) || { log "FAIL: RAM nghỉ vượt giới hạn"; exit 1; }
  log "PASS prod"
elif [ "$MODE" = "dev" ]; then
  if [ "${SMOKE_NO_BUILD:-0}" = "1" ]; then "${COMPOSE_DEV[@]}" up -d; else "${COMPOSE_DEV[@]}" up -d --build; fi
  wait_http "http://localhost:8000/health" "$TIMEOUT_S" || { log "FAIL: api dev không lên"; dump_dev_logs; exit 1; }
  wait_http "http://localhost:8080/" "$TIMEOUT_S" || { log "FAIL: Vite dev không lên"; dump_dev_logs; exit 1; }
  backend_file="backend/src/nichepilot/__init__.py"
  frontend_file="frontend/src/main.tsx"
  cp "$backend_file" /tmp/smoke_backend.bak; cp "$frontend_file" /tmp/smoke_frontend.bak
  trap 'cp /tmp/smoke_backend.bak "$backend_file"; cp /tmp/smoke_frontend.bak "$frontend_file"' EXIT
  # Vite chỉ phát HMR/log cho module đã có trong module graph (đã có client tải) → tải trước module sẽ sửa.
  curl -fsS -o /dev/null "http://localhost:8080/src/main.tsx" || { log "FAIL: Vite không phục vụ src/main.tsx"; exit 1; }
  since="$(date -u +%FT%TZ)"
  echo "# smoke-reload $(date +%s)" >> "$backend_file"
  echo "// smoke-reload $(date +%s)" >> "$frontend_file"
  ok_api=0 ok_worker=0 ok_web=0
  for _ in $(seq 1 30); do
    sleep 2
    "${COMPOSE_DEV[@]}" logs --since "$since" api 2>&1 | grep -qiE "reloading|detected change" && ok_api=1
    "${COMPOSE_DEV[@]}" logs --since "$since" worker 2>&1 | grep -qiE "restarting|changes detected|worker started" && ok_worker=1
    "${COMPOSE_DEV[@]}" logs --since "$since" web 2>&1 | grep -qiE "hmr update|page reload" && ok_web=1
    (( ok_api && ok_worker && ok_web )) && break
  done
  log "reload api=$ok_api worker=$ok_worker web=$ok_web"
  wait_http "http://localhost:8000/health" 60 || { log "FAIL: api không lên lại sau reload"; exit 1; }
  (( ok_api && ok_worker && ok_web )) || { log "FAIL dev hot reload"; dump_dev_logs; exit 1; }
  log "PASS dev"
else
  echo "Dùng: $0 prod|dev" >&2; exit 2
fi
