#!/bin/sh
# Backup PostgreSQL của NichePilot (FR-073): pg_dump -Fc, xoay vòng giữ BACKUP_RETENTION bản mới nhất.
# Chạy trong service `backup` (image postgres:17-alpine): make backup
# File backup chứa dữ liệu nhạy cảm (hash mật khẩu, audit log) → quyền 0600, thư mục backups/ bị loại khỏi git.
# Database KHÔNG chứa API key (chỉ nằm trong .env/Docker secrets).
set -eu
umask 077

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION="${BACKUP_RETENTION:-7}"
export PGHOST="${PGHOST:-postgres}"
export PGPORT="${PGPORT:-5432}"
export PGUSER="${PGUSER:-${POSTGRES_USER:?POSTGRES_USER chưa được đặt}}"
export PGPASSWORD="${PGPASSWORD:-${POSTGRES_PASSWORD:?POSTGRES_PASSWORD chưa được đặt}}"
export PGDATABASE="${PGDATABASE:-${POSTGRES_DB:?POSTGRES_DB chưa được đặt}}"

case "$RETENTION" in
  ''|*[!0-9]*) echo "BACKUP_RETENTION phải là số nguyên dương" >&2; exit 2 ;;
esac
[ "$RETENTION" -ge 1 ] || { echo "BACKUP_RETENTION phải >= 1" >&2; exit 2; }

mkdir -p "$BACKUP_DIR"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
name="nichepilot-${stamp}"
n=1
while [ -e "$BACKUP_DIR/${name}.dump" ]; do
  name="nichepilot-${stamp}-${n}"
  n=$((n + 1))
done
partial="$BACKUP_DIR/.${name}.dump.partial"
trap 'rm -f "$partial"' EXIT

pg_dump --format=custom --no-owner --no-privileges --file="$partial"
pg_restore --list "$partial" > /dev/null   # xác nhận file đọc được trước khi công bố
chmod 600 "$partial"
mv "$partial" "$BACKUP_DIR/${name}.dump"
trap - EXIT
echo "Đã tạo backup: $BACKUP_DIR/${name}.dump"
# E1 (X4): sao kèm erasure ledger (chỉ ID/hash, không nội dung). Bản sổ sống trong volume vẫn là nguồn chuẩn khi restore.
if [ -f "${LEDGER_DIR:-/ledger}/ledger.jsonl" ]; then
  cp "${LEDGER_DIR:-/ledger}/ledger.jsonl" "$BACKUP_DIR/${name}.ledger.jsonl"
  chmod 600 "$BACKUP_DIR/${name}.ledger.jsonl"
  echo "Đã sao erasure ledger: $BACKUP_DIR/${name}.ledger.jsonl"
fi

# Xoay vòng: tên chứa timestamp UTC nên sắp xếp theo tên = theo thời gian.
ls -1 "$BACKUP_DIR" | grep -E '^nichepilot-[0-9TZ-]+\.dump$' | sort -r | tail -n +"$((RETENTION + 1))" | while read -r old; do
  rm -f "$BACKUP_DIR/$old"
  echo "Đã xóa backup cũ: $old"
done
