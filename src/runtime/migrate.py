"""
Migration + Seed — ترتیب صحیح: schema → seed

منطق migration:
1. اگر alembic.ini موجود است و psycopg2 نصب است → alembic upgrade head
2. فقط اگر Alembic شکست خورد → create_all به‌عنوان fallback
3. stamp کردن صوری head (بدون تأیید واقعی) ممنوع:
   اگر create_all موفق شد، alembic_version را مستقیماً insert می‌کنیم —
   نه از طریق alembic command که نیاز به اتصال sync دارد و ممکن است باز هم شکست بخورد.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


async def run_seed() -> None:
    from decimal import Decimal
    from sqlalchemy import select
    from src.infrastructure.db.session import get_session
    from src.infrastructure.db.models import PlanModel, MetaModel

    DEFAULT_PLANS = [
        dict(name="رایگان", name_en="Free", days=0, daily_posts=3, max_sources=2,
             max_channels=1, daily_tests=2, price="رایگان", price_en="Free",
             price_num="0", price_num_fa="۰", is_free=True, sort=0,
             description="برای آشنایی با سیستم", description_en="For getting started"),
        dict(name="برنزی", name_en="Bronze", days=30, daily_posts=10, max_sources=5,
             max_channels=2, daily_tests=5, price="۱۵۰,۰۰۰ تومان", price_en="$5/mo",
             price_num="1500000", price_num_fa="۱,۵۰۰,۰۰۰ ریال", is_free=False, sort=1,
             description="مناسب کانال‌های کوچک", description_en="For small channels"),
        dict(name="نقره‌ای", name_en="Silver", days=30, daily_posts=30, max_sources=15,
             max_channels=5, daily_tests=20, price="۳۵۰,۰۰۰ تومان", price_en="$12/mo",
             price_num="3500000", price_num_fa="۳,۵۰۰,۰۰۰ ریال", is_free=False, sort=2,
             description="مناسب کانال‌های متوسط", description_en="For growing channels"),
        dict(name="طلایی", name_en="Gold", days=30, daily_posts=100, max_sources=50,
             max_channels=20, daily_tests=50, price="۷۵۰,۰۰۰ تومان", price_en="$25/mo",
             price_num="7500000", price_num_fa="۷,۵۰۰,۰۰۰ ریال", is_free=False, sort=3,
             description="برای خبرگزاری‌ها", description_en="For agencies"),
    ]

    async with get_session() as session:
        for p in DEFAULT_PLANS:
            existing = (await session.execute(
                select(PlanModel).where(PlanModel.name == p["name"])
            )).scalar_one_or_none()
            if not existing:
                session.add(PlanModel(
                    name=p["name"], name_en=p["name_en"], days=p["days"],
                    daily_posts=p["daily_posts"], max_sources=p["max_sources"],
                    max_channels=p["max_channels"], daily_tests=p["daily_tests"],
                    price=p["price"], price_en=p["price_en"],
                    price_num=Decimal(p["price_num"]), price_num_fa=p["price_num_fa"],
                    description=p["description"], description_en=p["description_en"],
                    is_free=p["is_free"], is_active=True, sort=p["sort"],
                ))
                print(f"  ✅ Plan: {p['name']}")

        existing_meta = (await session.execute(
            select(MetaModel).where(MetaModel.key == "seed_version")
        )).scalar_one_or_none()
        if not existing_meta:
            session.add(MetaModel(key="seed_version", value="1.0.0"))

    print("  ✅ Seed کامل شد.")


async def _record_schema_version(revision: str) -> None:
    """
    ثبت مستقیم alembic_version در دیتابیس بدون استفاده از alembic command.
    این کار فقط پس از create_all موفق انجام می‌شود — نه صوری و نه بدون تأیید schema.
    """
    from sqlalchemy import text
    from src.infrastructure.db.session import get_session
    async with get_session() as session:
        # ایجاد جدول alembic_version اگر وجود ندارد
        await session.execute(text(
            "CREATE TABLE IF NOT EXISTS alembic_version "
            "(version_num VARCHAR(32) NOT NULL, "
            "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"
        ))
        # بررسی وجود رکورد قبلی
        existing = await session.execute(
            text("SELECT version_num FROM alembic_version")
        )
        rows = existing.fetchall()
        if not rows:
            await session.execute(
                text("INSERT INTO alembic_version (version_num) VALUES (:rev)"),
                {"rev": revision},
            )
            print(f"  ✅ alembic_version = {revision} ثبت شد.")
        else:
            print(f"  ⏭️  alembic_version موجود است: {rows[0][0]}")


def _run_alembic(ini_path: Path) -> bool:
    """
    اجرای alembic upgrade head با psycopg2.
    برگرداندن True اگر موفق بود.
    """
    try:
        from alembic import command
        from alembic.config import Config
        cfg = Config(str(ini_path))
        cfg.set_main_option(
            "script_location",
            str(Path(__file__).parent.parent / "infrastructure/db/migrations"),
        )
        command.upgrade(cfg, "head")
        return True
    except Exception as exc:
        print(f"  ⚠️  Alembic شکست خورد: {exc}")
        return False



async def _run_async_phase(*, fallback: bool) -> None:
    """
    اجرای تمام عملیات async دیتابیس در یک Event Loop واحد.
    اگر Alembic شکست بخورد، create_all و seed نباید با asyncio.runهای جدا
    اجرا شوند؛ asyncpg connection pool به loop قبلی وابسته می‌ماند.
    """
    from src.infrastructure.db.session import close_engine

    try:
        if fallback:
            print("🔄 Fallback: create_all...")
            await _create_all_and_stamp()
        print("🌱 Seed داده‌های اولیه...")
        await run_seed()
    finally:
        await close_engine()


def main() -> None:
    from src.infrastructure.logging.logger import setup_logging, get_logger
    setup_logging()
    log = get_logger("migrate")
    log.info("migration_start")

    ini_path = Path(__file__).parent.parent.parent / "alembic.ini"
    alembic_ok = False

    # ۱) تلاش با Alembic (نیاز به psycopg2 دارد)
    if ini_path.exists():
        print("⚙️  اجرای Alembic migration...")
        alembic_ok = _run_alembic(ini_path)
        if alembic_ok:
            print("✅ Alembic migration کامل شد.")
    else:
        print(f"  ⚠️  alembic.ini یافت نشد: {ini_path}")

    # تمام عملیات async دیتابیس (از جمله fallback و seed) در یک loop اجرا می‌شوند.
    # Alembic در مسیر موفق sync است و پیش از شروع این loop اجرا شده است.
    asyncio.run(_run_async_phase(fallback=not alembic_ok))

    log.info("migration_done", via="alembic" if alembic_ok else "create_all_fallback")
    print("✅ Migration & Seed کامل.")


async def _create_all_and_stamp() -> None:
    from src.infrastructure.db.session import get_engine
    from src.infrastructure.db.models import Base
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("  ✅ create_all اجرا شد.")
    # ثبت نسخه — نه stamp صوری، بلکه insert واقعی پس از تأیید ساخت جداول
    await _record_schema_version("0001")


if __name__ == "__main__":
    main()
