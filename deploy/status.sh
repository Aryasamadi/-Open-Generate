#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/open-generate"
COMPOSE="docker compose -f $APP_DIR/docker-compose.yml"

echo "=== وضعیت سرویس‌ها ==="
$COMPOSE ps

echo ""
echo "=== Commit/Image ==="
cd "$APP_DIR" && git log --oneline -1

echo ""
echo "=== Health Check ==="
curl -sf http://localhost:9090/health | python3 -m json.tool || echo "❌ health endpoint پاسخ نداد"

echo ""
echo "=== DB ==="
$COMPOSE exec db pg_isready -U "${DB_USER:-og_user}" && echo "✅ DB OK" || echo "❌ DB مشکل دارد"
