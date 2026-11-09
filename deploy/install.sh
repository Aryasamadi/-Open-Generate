#!/usr/bin/env bash
# ==============================================================
# install.sh — آماده‌سازی VPS و راه‌اندازی اولیه
# - deploy user ایجاد می‌کند
# - Docker و Compose نصب می‌کند
# - دایرکتوری‌های لازم ایجاد می‌کند
# - secret در خروجی چاپ نمی‌شود
# ==============================================================
set -euo pipefail
IFS=$'\n\t'

DEPLOY_USER="ogdeploy"
APP_DIR="/opt/open-generate"
DATA_DIR="/data/open-generate"
LOG_FILE="/var/log/og-install.log"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

log()   { echo -e "${GREEN}[$(date '+%H:%M:%S')] ✅ $*${NC}" | tee -a "$LOG_FILE"; }
warn()  { echo -e "${YELLOW}[$(date '+%H:%M:%S')] ⚠️  $*${NC}" | tee -a "$LOG_FILE"; }
error() { echo -e "${RED}[$(date '+%H:%M:%S')] ❌ $*${NC}" | tee -a "$LOG_FILE" >&2; exit 1; }

[[ $EUID -ne 0 ]] && error "این script باید با root اجرا شود."

log "شروع نصب Open-Generate..."

# ---- پیش‌نیازها
apt-get update -qq
apt-get install -y -qq curl git ufw fail2ban

# ---- Docker
if ! command -v docker &>/dev/null; then
    log "نصب Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
else
    log "Docker از قبل نصب است."
fi

# ---- deploy user
if ! id "$DEPLOY_USER" &>/dev/null; then
    useradd -m -s /bin/bash "$DEPLOY_USER"
    usermod -aG docker "$DEPLOY_USER"
    log "کاربر $DEPLOY_USER ایجاد شد."
else
    warn "کاربر $DEPLOY_USER از قبل وجود دارد."
fi

# ---- دایرکتوری‌ها
mkdir -p "$APP_DIR" "$DATA_DIR/db" "$DATA_DIR/receipts" "$DATA_DIR/backups" "$DATA_DIR/logs"
chown -R "$DEPLOY_USER:$DEPLOY_USER" "$APP_DIR" "$DATA_DIR"
chmod 750 "$APP_DIR" "$DATA_DIR"

# ---- Firewall
read -r -p "⚠️  Firewall تنظیم شود؟ (y/N): " fw_confirm
if [[ "${fw_confirm,,}" == "y" ]]; then
    ufw default deny incoming
    ufw default allow outgoing
    ufw allow ssh
    ufw --force enable
    log "Firewall فعال شد."
fi

# ---- env template
if [[ ! -f "$APP_DIR/.env.secret" ]]; then
    cp -n .env.example "$APP_DIR/.env.secret" 2>/dev/null || true
    chmod 600 "$APP_DIR/.env.secret"
    warn "فایل .env.secret ایجاد شد — باید مقادیر را پر کنید: $APP_DIR/.env.secret"
fi

log "نصب کامل شد."
log "مرحله بعد: مقادیر .env.secret را تنظیم کنید، سپس deploy.sh را اجرا کنید."
