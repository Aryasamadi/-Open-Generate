# ------------------------------------------------------------------ Stage 1: builder
FROM python:3.11-slim AS builder

WORKDIR /build

# system deps برای کتابخانه‌های native
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# ترتیب مهم است: hatchling برای resolve کردن پکیج به pyproject.toml *و*
# دایرکتوری src/ نیاز دارد (packages = ["src"]). اگر src/ کپی نشود،
# build wheel شکست می‌خورد و بدون "|| true" این خطا دیده نمی‌شد —
# نتیجه‌اش یک image بدون هیچ dependency نصب‌شده اما build "موفق" بود.
# اینجا عمداً fallback خاموش نداریم: شکست نصب باید build را متوقف کند.
COPY pyproject.toml .
COPY src/ ./src/
RUN pip install --no-cache-dir --prefix=/install ".[dev]"

# ------------------------------------------------------------------ Stage 2: runtime
FROM python:3.11-slim AS runtime

# security: non-root user
RUN groupadd -r ogapp && useradd -r -g ogapp -d /app -s /bin/false ogapp

# runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# کپی packages از builder
COPY --from=builder /install /usr/local

WORKDIR /app

# کپی کد
COPY --chown=ogapp:ogapp src/ ./src/
COPY --chown=ogapp:ogapp config/ ./config/
COPY --chown=ogapp:ogapp pyproject.toml .
COPY --chown=ogapp:ogapp alembic.ini .

# دایرکتوری‌های data (volume پایدار)
RUN mkdir -p /data/db /data/receipts /data/backups /data/logs \
    && chown -R ogapp:ogapp /data /app

USER ogapp

# متغیر محیطی پیش‌فرض
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

EXPOSE 9090 9091

# healthcheck واقعی
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:9090/health || exit 1

# پیش‌فرض: راه‌اندازی ربات
CMD ["python", "-m", "src.runtime.bot"]
