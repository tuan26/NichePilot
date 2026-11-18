#!/bin/sh
# Entrypoint service `backup` (profile ops): chạy backup.sh theo BACKUP_CRON bằng crond của BusyBox.
set -eu
CRON="${BACKUP_CRON:-0 3 * * *}"
export TZ="${BACKUP_TZ:-${TZ:-Asia/Ho_Chi_Minh}}"  # BACKUP_CRON tính theo múi giờ này
# crond không truyền biến môi trường cho job → ghi các biến cần thiết vào file chỉ root đọc được.
umask 077
env | grep -E '^(PG[A-Z]*|POSTGRES_(USER|PASSWORD|DB)|BACKUP_[A-Z]*|TZ)=' | sed "s/'/'\\\\''/g; s/=\(.*\)/='\1'/; s/^/export /" > /run/backup.env
mkdir -p /etc/crontabs
echo "$CRON . /run/backup.env && /scripts/backup.sh >> /proc/1/fd/1 2>> /proc/1/fd/2" > /etc/crontabs/root
echo "Lịch backup: '$CRON' (TZ=${TZ:-UTC}), giữ ${BACKUP_RETENTION:-7} bản."
exec crond -f -l 8
