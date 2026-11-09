#!/usr/bin/env bash
# اعتبارسنجی env بدون چاپ secret
set -euo pipefail

ENV_FILE="${1:-.env.secret}"
[[ ! -f "$ENV_FILE" ]] && { echo "❌ فایل $ENV_FILE یافت نشد." >&2; exit 1; }

REQUIRED_VARS=(
    "TELEGRAM_BOT_TOKEN"
    "ENCRYPTION_KEY"
    "DB_PASSWORD"
    "SUPER_ADMIN_IDS"
)

source "$ENV_FILE"
MISSING=()
for var in "${REQUIRED_VARS[@]}"; do
    [[ -z "${!var:-}" ]] && MISSING+=("$var")
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
    echo "❌ متغیرهای الزامی تنظیم نشده‌اند: ${MISSING[*]}" >&2
    exit 1
fi

# بررسی طول ENCRYPTION_KEY (بدون چاپ مقدار)
KEY_LEN=${#ENCRYPTION_KEY}
if [[ $KEY_LEN -lt 32 ]]; then
    echo "❌ ENCRYPTION_KEY باید حداقل ۳۲ کاراکتر باشد." >&2
    exit 1
fi

echo "✅ تنظیمات معتبر است."
