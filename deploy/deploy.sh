#!/usr/bin/env bash
# ==============================================================
# deploy.sh — deploy امن، idempotent و قابل تکرار
# 1) fetch/build
# 2) backup قبل از migration
# 3) migration
# 4) rollout
# 5) health verification
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

# ---- اعتبارسنجی env (بدون چاپ secret)
source deploy/configure.sh

cd "$APP_DIR"

# ---- git pull
log "دریافت آخرین کد..."
git fetch origin
git reset --hard origin/main
COMMIT_SHA=$(git rev-parse --short HEAD)
log "Commit: $COMMIT_SHA"

# ---- backup قبل از migration
log "backup قبل از migration..."
bash "$APP_DIR/deploy/backup.sh" --pre-deploy

# ---- build image
log "Build image..."
$COMPOSE build --no-cache bot worker

# ---- تست image (smoke test ساده)
log "تست image..."
docker run --rm "$(docker compose -f docker-compose.yml images -q bot)" \
    python -c "import src.infrastructure.db.models" && log "Image OK"

# ---- migration
log "اجرای migration..."
$COMPOSE run --rm migrate

# ---- rollout
log "راه‌اندازی سرویس‌ها..."
$COMPOSE up -d --remove-orphans bot worker

# ---- health check
log "بررسی سلامت..."
sleep 15
MAX_TRIES=10
for i in $(seq 1 $MAX_TRIES); do
    if curl -sf http://localhost:9090/health | grep -q '"status":"ok"'; then
        log "✅ سرویس سالم است (تلاش $i/$MAX_TRIES)"
        break
    fi
    if [[ $i -eq $MAX_TRIES ]]; then
        error "سرویس بعد از $MAX_TRIES تلاش سالم نشد — rollback اجرا می‌شود"
        bash "$APP_DIR/deploy/rollback.sh"
    fi
    warn "تلاش $i/$MAX_TRIES — صبر ۱۰ ثانیه..."
    sleep 10
done

log "Deploy موفق: commit=$COMMIT_SHA"
