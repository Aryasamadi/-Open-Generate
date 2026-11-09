#!/usr/bin/env bash
# doctor — بررسی کامل سیستم قبل از deploy
set -euo pipefail

APP_DIR="/opt/open-generate"
ENV_FILE="$APP_DIR/.env.secret"

OK=0; WARN=0; FAIL=0

check() {
    local label="$1"; shift
    if "$@" &>/dev/null; then
        echo "✅ $label"; ((OK++)) || true
    else
        echo "❌ $label"; ((FAIL++)) || true
    fi
}

warn_check() {
    local label="$1"; shift
    if "$@" &>/dev/null; then
        echo "✅ $label"; ((OK++)) || true
    else
        echo "⚠️  $label"; ((WARN++)) || true
    fi
}

echo "=== Disk ==="
df -h / | awk 'NR==2{print "استفاده:", $5, "— آزاد:", $4}'
DISK_PCT=$(df / | awk 'NR==2{print $5}' | tr -d '%')
[[ $DISK_PCT -lt 80 ]] && echo "✅ فضا کافی" && ((OK++)) || { echo "❌ فضا کم است ($DISK_PCT%)"; ((FAIL++)) || true; }

echo ""
echo "=== Docker ==="
check "Docker daemon"       systemctl is-active docker
check "Docker Compose"      docker compose version
check "Image build context" [[ -f "$APP_DIR/Dockerfile" ]]

echo ""
echo "=== Network ==="
check "DNS resolution"      nslookup api.telegram.org
check "Telegram reachable"  curl -sf --max-time 5 https://api.telegram.org

echo ""
echo "=== Config ==="
check ".env.secret موجود"   [[ -f "$ENV_FILE" ]]
check ".env.secret permissions" [[ "$(stat -c %a $ENV_FILE 2>/dev/null)" == "600" ]]
warn_check "ENCRYPTION_KEY تنظیم" bash -c "source $ENV_FILE 2>/dev/null && [[ -n \"\${ENCRYPTION_KEY:-}\" ]]"
warn_check "TELEGRAM_BOT_TOKEN"   bash -c "source $ENV_FILE 2>/dev/null && [[ -n \"\${TELEGRAM_BOT_TOKEN:-}\" ]]"

echo ""
echo "=== Ports ==="
check "Port 9090 (health) آزاد" bash -c "! ss -tlnp | grep ':9090 '"

echo ""
echo "============================================"
echo "✅ OK: $OK | ⚠️  WARN: $WARN | ❌ FAIL: $FAIL"
[[ $FAIL -gt 0 ]] && exit 1 || exit 0
