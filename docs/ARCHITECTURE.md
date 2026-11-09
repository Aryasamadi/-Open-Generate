# معماری سیستم — Open-Generate

## ساختار کلی: Modular Monolith

```
┌─────────────────────────────────────────────────────┐
│                    Telegram Bot                      │
│  (PTB v21 — polling یا webhook)                     │
├─────────┬───────────┬──────────────┬───────────────-┤
│  Bot    │ Application│   Domain     │ Infrastructure │
│  Layer  │   Layer   │   Layer      │    Layer       │
│         │           │              │                │
│ handlers│ use cases │ entities     │ DB (SQLAlchemy)│
│ wizards │ services  │ rules        │ AI adapters    │
│ keyboards│          │ value objects│ Fetcher (safe) │
│ localize│           │ errors       │ Scheduler      │
│         │           │              │ Crypto         │
│         │           │              │ Logging        │
└─────────┴───────────┴──────────────┴────────────────┘
                           │
                    ┌──────▼──────┐
                    │  PostgreSQL │
                    │  (primary)  │
                    └─────────────┘
```

## لایه‌ها

### A) Telegram Interface
- `src/bot/handlers/` — command و callback handlers
- `src/bot/keyboards/` — inline keyboards
- `src/bot/wizards/` — ConversationHandler wizards
- `src/bot/middleware/` — auth، rate limit
- `src/bot/localization/` — فارسی و انگلیسی

### B) Application
- `src/application/` — use caseها (channel، source، content، payment، ...)

### C) Domain
- `src/domain/entities/` — business objects
- `src/domain/rules/` — business rules
- `src/domain/errors/` — domain errors

### D) Infrastructure
- `src/infrastructure/db/` — SQLAlchemy، migrations، repositories
- `src/infrastructure/ai/` — AI adapters (Anthropic، OpenAI-compat)
- `src/infrastructure/fetcher/` — HTTP fetcher امن (SSRF protection)
- `src/infrastructure/scheduler/` — APScheduler با heartbeat
- `src/infrastructure/crypto/` — Fernet encryption
- `src/infrastructure/logging/` — structlog ساختاریافته

### E) Runtime
- `src/runtime/bot.py` — نقطه ورود ربات
- `src/runtime/worker.py` — scheduler + notification worker
- `src/runtime/migrate.py` — اجرای migration
- `src/runtime/health.py` — health server

## تصمیمات معماری (ADR)

### ADR-001: PostgreSQL vs SQLite
**تصمیم:** PostgreSQL پیش‌فرض
**دلیل:** چند worker، رشد آتی، concurrency واقعی
**SQLite:** فقط برای توسعه محلی (DB_DRIVER=sqlite+aiosqlite)

### ADR-002: Modular Monolith
**تصمیم:** یک process منفرد با ماژول‌های مجزا
**دلیل:** overhead microservice بدون نیاز واقعی

### ADR-003: APScheduler vs Celery
**تصمیم:** APScheduler داخلی
**دلیل:** dependency کمتر، کافی برای VPS منفرد

### ADR-004: Fernet Encryption
**تصمیم:** cryptography.fernet برای API key‌ها
**دلیل:** امن، مستند، پشتیبانی rotation

## Flow انتشار (Pipeline)
```
منابع → Fetch → Parse → Normalize → Dedup →
بازه زمانی → پالایش → Scoring → min_score →
AI → Validate → صف → انتشار → Journal
```

## امنیت
- SSRF: تمام IP privateها blocked
- RBAC: هر callback مجدداً authorize می‌شود
- Secrets: Fernet encrypted در DB، key خارج DB
- Rate limit: per-user و global
- Logs: mask تمام secrets
