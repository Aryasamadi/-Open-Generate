# Open-Generate ⚡

**سامانه چندکاربره مدیریت کانال تلگرام با انتشار خودکار محتوای خبری و هوش مصنوعی**

---

## ویژگی‌ها

| ویژگی | توضیح |
|---|---|
| 🤖 چند AI Provider | Anthropic، OpenAI، Gemini، Groq، DeepSeek، Mistral، Ollama، هر endpoint سفارشی |
| 📰 RSS/Atom/API | دریافت خودکار از هر منبع خبری |
| 🔄 Pipeline کامل | Fetch → Dedup → Score → AI → Review → Publish |
| 👁️ حالت بازبینی | تأیید/رد/ویرایش پست قبل از انتشار |
| 💎 مدیریت پلن | رایگان، برنزی، نقره‌ای، طلایی با محدودیت‌های enforce‌شده |
| 🛡️ امنیت | SSRF protection، رمزنگاری API key، RBAC، rate limit |
| 🌐 دو زبانه | فارسی و انگلیسی |
| 📣 Notification | اعلان دائمی با retry/backoff/dead-letter |

---

## راه‌اندازی سریع (Docker)

### ۱. پیش‌نیازها
```bash
# نصب Docker
curl -fsSL https://get.docker.com | sh
```

### ۲. دریافت پروژه
```bash
git clone https://github.com/Aryasamadi/-Open-Generate.git
cd Open-Generate
```

### ۳. تنظیم محیط
```bash
cp .env.example .env.secret
nano .env.secret
```

**مقادیر الزامی:**
```env
TELEGRAM_BOT_TOKEN=توکن_ربات_از_BotFather
SUPER_ADMIN_IDS=شناسه_عددی_تلگرام_شما
ENCRYPTION_KEY=یک_رشته_تصادفی_۳۲_کاراکتری
DB_PASSWORD=رمزعبور_قوی_برای_دیتابیس
```

**ساخت ENCRYPTION_KEY:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### ۴. راه‌اندازی
```bash
docker compose up -d
```

**همین! ربات در ۳۰ ثانیه آماده است.**

---

## راه‌اندازی دستی (بدون Docker)

### پیش‌نیازها
- Python 3.11+
- PostgreSQL 14+ (یا SQLite برای توسعه)

### نصب
```bash
pip install -e ".[dev]"
```

### Migration و Seed
```bash
python -m src.runtime.migrate
```

### اجرا
```bash
# ترمینال ۱ — ربات
python -m src.runtime.bot

# ترمینال ۲ — worker (scheduler + publish + notification)
python -m src.runtime.worker
```

---

## ساختار پروژه

```
src/
├── bot/
│   ├── handlers/        # ConversationHandler wizards
│   ├── middleware/       # auth، rate limit
│   └── localization/    # fa.py، en.py
├── application/         # use caseها و serviceها
├── domain/              # entities، value objects، rules
├── infrastructure/
│   ├── ai/              # adapters (Anthropic، OpenAI-compat)
│   ├── db/              # SQLAlchemy، migrations، repositories
│   ├── fetcher/         # HTTP fetcher امن (SSRF protection)
│   ├── scheduler/       # APScheduler، jobs، publish worker
│   └── telegram/        # publisher
└── runtime/             # bot.py، worker.py، migrate.py، health.py
```

---

## تنظیمات پیشرفته

### حالت Webhook (production)
```env
BOT_MODE=webhook
WEBHOOK_URL=https://yourdomain.com
WEBHOOK_SECRET=random-secret-string
WEBHOOK_PORT=8443
```

### SQLite (توسعه)
```env
DB_DRIVER=sqlite+aiosqlite
SQLITE_PATH=/data/db/opengenerate.db
```

### Backup خودکار
```bash
# در crontab
0 3 * * * /opt/open-generate/deploy/backup.sh
```

### Restore
```bash
bash deploy/restore.sh /data/open-generate/backups/og_backup_YYYYMMDD_HHMMSS.sql.gz[.enc]
```
قبل از جایگزینی، از وضعیت فعلی دیتابیس یک safety-backup گرفته می‌شود و اجرا
نیازمند تایپ صریح عبارت `RESTORE` است.

---

## اولین ورود به ربات

۱. `/start` را بزنید
۲. شناسه تلگرام شما باید در `SUPER_ADMIN_IDS` باشد تا پنل ادمین نمایش داده شود
۳. از پنل ادمین → AI عمومی، اولین مدل را اضافه کنید
۴. کانال را اضافه کرده، منابع RSS را وارد کنید
۵. تنظیمات موتور را انجام دهید و حالت را روشن کنید

---

## Health Check

فقط سرویس `bot` پورت ۹۰۹۰ را روی `127.0.0.1` میزبان منتشر می‌کند (برای امنیت،
نه روی اینترنت). همین یک endpoint کافی است چون وضعیت `scheduler` را هم از
طریق جدول مشترک `scheduler_heartbeat` که worker می‌نویسد گزارش می‌دهد —
یعنی سلامت هر دو سرویس bot و worker را نشان می‌دهد.

```bash
curl http://localhost:9090/health
```

```json
{
  "status": "ok",
  "checks": {
    "db": {"status": "ok"},
    "scheduler": {"status": "ok", "age_seconds": 15}
  }
}
```

---

## امنیت

- **API key‌ها** با Fernet (AES-256) رمزنگاری می‌شوند
- **SSRF** — همه IP private/loopback/metadata مسدود است
- **RBAC** — هر callback مجدداً authorize می‌شود، callback_data مجوز نیست
- **Rate limit** — ۳۰ درخواست/دقیقه per-user
- **Secrets** — هرگز در log یا Git ثبت نمی‌شوند
- **Dockerfile** — non-root user، multi-stage

---

## لایسنس

MIT
