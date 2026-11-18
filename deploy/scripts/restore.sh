#!/bin/sh
# Khôi phục backup vào database (FR-073, SC-012): make restore FILE=backups/<file>.dump
# An toàn: từ chối khôi phục vào database đã có bảng (tránh ghi đè ngoài ý muốn).
# Quy trình khuyến nghị: dừng api/worker → tạo database trống → restore → khởi động lại (xem docs/operations).
set -eu

FILE="${1:?Dùng: restore.sh /backups/<file>.dump}"
[ -f "$FILE" ] || { echo "Không tìm thấy file backup: $FILE" >&2; exit 2; }
export PGHOST="${PGHOST:-postgres}"
export PGPORT="${PGPORT:-5432}"
export PGUSER="${PGUSER:-${POSTGRES_USER:?POSTGRES_USER chưa được đặt}}"
export PGPASSWORD="${PGPASSWORD:-${POSTGRES_PASSWORD:?POSTGRES_PASSWORD chưa được đặt}}"
export PGDATABASE="${PGDATABASE:-${POSTGRES_DB:?POSTGRES_DB chưa được đặt}}"

pg_restore --list "$FILE" > /dev/null
tables="$(psql -XAtq -c "SELECT count(*) FROM pg_tables WHERE schemaname NOT IN ('pg_catalog', 'information_schema')")"
if [ "$tables" != "0" ]; then
  echo "Database '$PGDATABASE' not empty ($tables bảng) – từ chối khôi phục. Hãy khôi phục vào database trống." >&2
  exit 3
fi
pg_restore --no-owner --no-privileges --exit-on-error --single-transaction --dbname="$PGDATABASE" "$FILE"
echo "Đã khôi phục $FILE vào database '$PGDATABASE'."
