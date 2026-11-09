#!/usr/bin/env bash
# backup امن — رمزنگاری قبل از خروج از VPS
set -euo pipefail
IFS=$'\n\t'

APP_DIR="/opt/open-generate"
DATA_DIR="/data/open-generate"
BACKUP_DIR="$DATA_DIR/backups"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
BACKUP_FILE="$BACKUP_DIR/og_backup_${TIMESTAMP}.sql.gz"
ENCRYPTED_FILE="${BACKUP_FILE}.enc"

source "$APP_DIR/.env.secret" 2>/dev/null || true

log()   { echo "[$(date '+%H:%M:%S')] $*"; }
warn()  { echo "⚠️  $*" >&2; }
error() { echo "❌ $*" >&2; exit 1; }

mkdir -p "$BACKUP_DIR"

# ---- dump PostgreSQL
log "Dump PostgreSQL..."
docker compose -f "$APP_DIR/docker-compose.yml" exec -T db \
    pg_dump -U "${DB_USER:-og_user}" "${DB_NAME:-opengenerate}" \
    | gzip > "$BACKUP_FILE" \
    || error "Dump ناموفق بود"

# ---- رمزنگاری
if [[ -n "${BACKUP_ENCRYPTION_KEY:-}" ]]; then
    log "رمزنگاری backup..."
    openssl enc -aes-256-cbc -salt -pbkdf2 \
        -pass "pass:${BACKUP_ENCRYPTION_KEY}" \
        -in "$BACKUP_FILE" -out "$ENCRYPTED_FILE"
    rm "$BACKUP_FILE"
    FINAL_FILE="$ENCRYPTED_FILE"
else
    warn "BACKUP_ENCRYPTION_KEY تنظیم نشده — backup رمزنگاری نمی‌شود"
    FINAL_FILE="$BACKUP_FILE"
fi

# checksum
sha256sum "$FINAL_FILE" > "${FINAL_FILE}.sha256"
log "Backup: $FINAL_FILE"

# ---- offsite (اختیاری)
if [[ "${BACKUP_OFFSITE_ENABLED:-false}" == "true" ]]; then
    log "انتقال به offsite..."
    # S3 upload — نیاز به awscli
    aws s3 cp "$FINAL_FILE" "s3://${BACKUP_OFFSITE_S3_BUCKET}/$(basename $FINAL_FILE)" \
        --endpoint-url "${BACKUP_OFFSITE_S3_ENDPOINT:-}" \
        || log "⚠️ Offsite upload ناموفق — backup محلی موجود است"
fi

# ---- نگهداری — حذف قدیمی‌ها
find "$BACKUP_DIR" -name "og_backup_*.sql.gz*" -mtime +7 -delete 2>/dev/null || true

log "✅ Backup کامل شد."
