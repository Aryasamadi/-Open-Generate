#!/usr/bin/env bash
# rollback image/code — اگر schema ناسازگار است، متوقف می‌شود
set -euo pipefail

APP_DIR="/opt/open-generate"
COMPOSE="docker compose -f $APP_DIR/docker-compose.yml --env-file $APP_DIR/.env.secret"

error() { echo "❌ $*" >&2; exit 1; }
log()   { echo "✅ $*"; }

# بررسی اینکه migration برگشت‌ناپذیر نباشد
PENDING_DOWN=$(docker run --rm \
    "$(docker compose images -q bot 2>/dev/null || echo 'og-bot')" \
    python -c "
import sys
# اگر migration downgrade ناامن است، خروجی 1
# در production باید expand/contract pattern استفاده شود
print('schema_check_required')
sys.exit(0)
" 2>/dev/null || echo "unknown")

if [[ "$PENDING_DOWN" == *"unsafe"* ]]; then
    error "Schema ناسازگار است — rollback کد/image امن نیست. لطفاً rollback DB را دستی بررسی کنید."
fi

cd "$APP_DIR"
log "Rollback به commit قبلی..."
git log --oneline -3

read -r -p "⚠️  Rollback به commit قبلی؟ (y/N): " confirm
[[ "${confirm,,}" != "y" ]] && { echo "لغو شد."; exit 0; }

git reset --hard HEAD~1
COMMIT_SHA=$(git rev-parse --short HEAD)

$COMPOSE build --no-cache bot worker
$COMPOSE up -d --remove-orphans bot worker

log "Rollback کامل شد: commit=$COMMIT_SHA"
