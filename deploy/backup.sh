#!/usr/bin/env bash
# Daily backup of the MySQL database + uploaded photos. Keeps the last 14 days.
# Setup:  chmod +x backup.sh && sudo crontab -e   →   30 2 * * *  /var/www/vihea/deploy/backup.sh
# Credentials: create /root/.my.cnf  with   [client]\nuser=att\npassword=YOUR_DB_PASSWORD   (chmod 600)
set -euo pipefail
DB="moeys_attendance"
APP="/var/www/vihea"
OUT="/var/backups/vihea"
KEEP_DAYS=14
STAMP=$(date +%F_%H%M)

mkdir -p "$OUT"
mysqldump --single-transaction --routines "$DB" | gzip > "$OUT/db_$STAMP.sql.gz"
tar -czf "$OUT/uploads_$STAMP.tar.gz" -C "$APP/backend" uploads
cp "$APP/backend/.env" "$OUT/env_$STAMP.bak" && chmod 600 "$OUT/env_$STAMP.bak"
find "$OUT" -type f -mtime +$KEEP_DAYS -delete
echo "Backup OK: $OUT ($STAMP)"
# Recommended: also copy $OUT off the server (rclone to Google Drive / another machine), because a backup on the same disk is lost if the disk fails.
