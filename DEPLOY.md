# راهنمای Push و Deploy

## ۱. Push به GitHub

```bash
# روی ماشین محلی یا VPS:
git clone https://github.com/Aryasamadi/-Open-Generate.git
cd -Open-Generate

# کپی فایل‌های ساخته‌شده (از خروجی Claude):
# تمام فایل‌ها را در همین ریپو قرار دهید

git add -A
git commit -m "feat: initial complete implementation"
git push origin main
```

## ۲. Deploy روی VPS (Ubuntu 22+)

```bash
# --- روی VPS ---
git clone https://github.com/Aryasamadi/-Open-Generate.git /opt/open-generate
cd /opt/open-generate

# نصب Docker
curl -fsSL https://get.docker.com | sh
systemctl enable --now docker

# تنظیم env
cp .env.example .env.secret
nano .env.secret
# مقادیر الزامی را پر کنید

# بررسی تنظیمات
bash deploy/configure.sh .env.secret

# راه‌اندازی
docker compose up -d

# بررسی سلامت
docker compose ps
curl http://localhost:9090/health
```

## ۳. بررسی logs

```bash
docker compose logs -f bot
docker compose logs -f worker
```

## ۴. تنظیم ربات (اولین بار)

۱. `/start` در تلگرام بزنید
۲. پنل ادمین → AI عمومی → افزودن مدل
۳. API key مدل AI خود را وارد کنید
۴. برگشت → کانال‌ها → افزودن کانال
۵. ربات را ادمین کانال کنید
۶. منابع RSS اضافه کنید
۷. تنظیمات → حالت → خودکار

## ۵. Backup خودکار

```bash
# اضافه به crontab
crontab -e

# هر شب ۳ صبح
0 3 * * * /opt/open-generate/deploy/backup.sh >> /var/log/og-backup.log 2>&1
```

## ۶. Restore (بازیابی از backup)

```bash
bash deploy/restore.sh /data/open-generate/backups/og_backup_YYYYMMDD_HHMMSS.sql.gz[.enc]
```

- checksum فایل (در صورت وجود `.sha256`) بررسی می‌شود
- اگر فایل با پسوند `.enc` باشد، با `BACKUP_ENCRYPTION_KEY` رمزگشایی می‌شود
- قبل از overwrite یک safety-backup از وضعیت فعلی گرفته می‌شود
- نیاز به تایپ صریح `RESTORE` برای تأیید نهایی دارد
- سرویس‌های `bot` و `worker` به‌طور موقت متوقف و پس از اتمام دوباره راه‌اندازی می‌شوند

## ۷. به‌روزرسانی

```bash
cd /opt/open-generate
bash deploy/deploy.sh
```
