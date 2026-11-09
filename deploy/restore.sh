#!/usr/bin/env bash
# ==============================================================
# restore.sh — بازیابی دیتابیس از فایل backup ساخته‌شده توسط backup.sh
#
# این اسکریپت همتای backup.sh است. قبل از این فایل، پروژه راهی برای
# برگرداندن یک backup نداشت — فقط می‌شد backup گرفت، نه restore کرد.
#
# استفاده:
#   bash deploy/restore.sh /data/open-generate/backups/og_backup_YYYYMMDD_HHMMSS.sql.gz[.enc]
#
# این اسکریپت:
# 1) checksum فایل را در صورت وجود تأیید می‌کند
# 2) در صورت رمزنگاری‌شده بودن (.enc)، رمزگشایی می‌کند
# 3) قبل از overwrite، یک safety-backup از وضعیت فعلی DB می‌گیرد
# 4) با تأیید صریح کاربر، restore را روی سرویس db اجرا می‌کند
# ==============================================================
set -euo pipefail
IFS=$'\n\t'

APP_DIR="/opt/open-generate"
DATA_DIR="/data/open-generate"
COMPOSE="docker compose -f $APP_DIR/docker-compose.yml --env-file $APP_DIR/.env.secret"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()   { echo -e "${GREEN}[$(date '+%H:%M:%S')] ✅ $*${NC}"; }
warn()  { echo -e "${YELLOW}[$(date '+%H:%M:%S')] ⚠️  $*${NC}"; }
error() { echo -e "${RED}[$(date '+%H:%M:%S')] ❌ $*${NC}" >&2; exit 1; }

BACKUP_FILE_ARG="${1:-}"
[[ -z "$BACKUP_FILE_ARG" ]] && error "استفاده: bash deploy/restore.sh <path-to-backup-file>"
[[ ! -f "$BACKUP_FILE_ARG" ]] && error "فایل یافت نشد: $BACKUP_FILE_ARG"

source "$APP_DIR/.env.secret" 2>/dev/null || true

WORK_DIR=$(mktemp -d)
trap 'rm -rf "$WORK_DIR"' EXIT

RESTORE_FILE="$BACKUP_FILE_ARG"

# ---- بررسی checksum در صورت وجود
if [[ -f "${BACKUP_FILE_ARG}.sha256" ]]; then
    log "بررسی checksum..."
    (cd "$(dirname "$BACKUP_FILE_ARG")" && sha256sum -c "$(basename "$BACKUP_FILE_ARG").sha256") \
        || error "checksum نامعتبر است — فایل ممکن است خراب یا دستکاری‌شده باشد"
else
    warn "فایل .sha256 یافت نشد — checksum بررسی نمی‌شود"
fi

# ---- رمزگشایی در صورت نیاز
if [[ "$BACKUP_FILE_ARG" == *.enc ]]; then
    [[ -z "${BACKUP_ENCRYPTION_KEY:-}" ]] && error "فایل رمزنگاری‌شده است اما BACKUP_ENCRYPTION_KEY تنظیم نشده"
    log "رمزگشایی backup..."
    DECRYPTED="$WORK_DIR/restore.sql.gz"
    openssl enc -d -aes-256-cbc -salt -pbkdf2 \
        -pass "pass:${BACKUP_ENCRYPTION_KEY}" \
        -in "$BACKUP_FILE_ARG" -out "$DECRYPTED" \
        || error "رمزگشایی ناموفق بود — کلید اشتباه است یا فایل خراب است"
    RESTORE_FILE="$DECRYPTED"
fi

# ---- safety backup از وضعیت فعلی قبل از overwrite
log "ساخت safety-backup از وضعیت فعلی DB قبل از restore..."
if ! bash "$APP_DIR/deploy/backup.sh" --pre-restore; then
    warn "safety-backup ناموفق بود!"
    echo ""
    echo -e "${RED}⚠️  هشدار بحرانی: safety-backup از وضعیت فعلی گرفته نشد."
    echo -e "   اگر restore ادامه پیدا کند و با مشکل مواجه شود،"
    echo -e "   هیچ نقطه‌ای برای بازگشت وجود ندارد و ممکن است داده از دست برود.${NC}"
    echo ""
    read -r -p "آیا می‌خواهید بدون safety-backup ادامه دهید؟ (برای تأیید UNSAFE را تایپ کنید): " unsafe_confirm
    if [[ "$unsafe_confirm" != "UNSAFE" ]]; then
        echo "لغو شد — ابتدا مشکل backup را بررسی کنید."
        exit 1
    fi
    warn "کاربر با آگاهی از خطر ادامه را تأیید کرد."
fi

# ---- تأیید صریح کاربر
echo ""
echo -e "${RED}⚠️  هشدار: این عملیات تمام داده‌های فعلی دیتابیس را با محتوای"
echo -e "   فایل backup جایگزین می‌کند. این عمل برگشت‌ناپذیر است مگر از"
echo -e "   safety-backup بالا استفاده کنید.${NC}"
echo ""
read -r -p "برای تأیید عبارت RESTORE را دقیقاً تایپ کنید: " confirm
[[ "$confirm" != "RESTORE" ]] && { echo "لغو شد."; exit 0; }

# ---- توقف سرویس‌های مصرف‌کننده DB تا از نوشتن هم‌زمان جلوگیری شود
log "توقف موقت bot و worker..."
$COMPOSE stop bot worker

# ---- اجرای restore
log "اجرای restore روی دیتابیس..."
gunzip -c "$RESTORE_FILE" | $COMPOSE exec -T db \
    psql -U "${DB_USER:-og_user}" -d "${DB_NAME:-opengenerate}" \
    || error "Restore ناموفق بود — bot/worker دستی راه‌اندازی نشدند، ابتدا وضعیت DB را بررسی کنید"

# ---- راه‌اندازی مجدد
log "راه‌اندازی مجدد bot و worker..."
$COMPOSE up -d bot worker

log "✅ Restore با موفقیت کامل شد."
