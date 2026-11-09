"""
Seed داده‌های اولیه — پلن‌های پیش‌فرض.
ایمن در برابر اجرای مجدد (upsert با ON CONFLICT).
"""
from __future__ import annotations

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DEFAULT_PLANS = [
    {
        "name": "رایگان",
        "name_en": "Free",
        "days": 0,          # بدون انقضا
        "daily_posts": 3,
        "max_sources": 2,
        "max_channels": 1,
        "daily_tests": 2,
        "price": "رایگان",
        "price_en": "Free",
        "price_num": "0",
        "price_num_fa": "۰",
        "description": "برای آشنایی با سیستم",
        "description_en": "For getting started",
        "is_free": True,
        "sort": 0,
    },
    {
        "name": "برنزی",
        "name_en": "Bronze",
        "days": 30,
        "daily_posts": 10,
        "max_sources": 5,
        "max_channels": 2,
        "daily_tests": 5,
        "price": "۱۵۰,۰۰۰ تومان / ماه",
        "price_en": "$5 / month",
        "price_num": "1500000",
        "price_num_fa": "۱,۵۰۰,۰۰۰ ریال",
        "description": "مناسب برای کانال‌های کوچک",
        "description_en": "For small channels",
        "is_free": False,
        "sort": 1,
    },
    {
        "name": "نقره‌ای",
        "name_en": "Silver",
        "days": 30,
        "daily_posts": 30,
        "max_sources": 15,
        "max_channels": 5,
        "daily_tests": 20,
        "price": "۳۵۰,۰۰۰ تومان / ماه",
        "price_en": "$12 / month",
        "price_num": "3500000",
        "price_num_fa": "۳,۵۰۰,۰۰۰ ریال",
        "description": "مناسب برای کانال‌های متوسط",
        "description_en": "For growing channels",
        "is_free": False,
        "sort": 2,
    },
    {
        "name": "طلایی",
        "name_en": "Gold",
        "days": 30,
        "daily_posts": 100,
        "max_sources": 50,
        "max_channels": 20,
        "daily_tests": 50,
        "price": "۷۵۰,۰۰۰ تومان / ماه",
        "price_en": "$25 / month",
        "price_num": "7500000",
        "price_num_fa": "۷,۵۰۰,۰۰۰ ریال",
        "description": "برای خبرگزاری‌ها و تیم‌های بزرگ",
        "description_en": "For agencies and large teams",
        "is_free": False,
        "sort": 3,
    },
]


async def seed() -> None:
    from decimal import Decimal
    from sqlalchemy import select, insert
    from src.infrastructure.db.session import get_session, get_engine
    from src.infrastructure.db.models import PlanModel, MetaModel

    # اطمینان از وجود جداول
    from src.infrastructure.db.models import Base
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with get_session() as session:
        for plan_data in DEFAULT_PLANS:
            existing = (await session.execute(
                select(PlanModel).where(PlanModel.name == plan_data["name"])
            )).scalar_one_or_none()

            if existing:
                print(f"⏭️  پلن «{plan_data['name']}» از قبل وجود دارد.")
                continue

            plan = PlanModel(
                name=plan_data["name"],
                name_en=plan_data["name_en"],
                days=plan_data["days"],
                daily_posts=plan_data["daily_posts"],
                max_sources=plan_data["max_sources"],
                max_channels=plan_data["max_channels"],
                daily_tests=plan_data["daily_tests"],
                price=plan_data["price"],
                price_en=plan_data["price_en"],
                price_num=Decimal(plan_data["price_num"]),
                price_num_fa=plan_data["price_num_fa"],
                description=plan_data["description"],
                description_en=plan_data["description_en"],
                is_free=plan_data["is_free"],
                is_active=True,
                sort=plan_data["sort"],
            )
            session.add(plan)
            print(f"✅ پلن «{plan_data['name']}» اضافه شد.")

        # ثبت نسخه seed
        existing_meta = (await session.execute(
            select(MetaModel).where(MetaModel.key == "seed_version")
        )).scalar_one_or_none()
        if not existing_meta:
            session.add(MetaModel(key="seed_version", value="1.0.0"))

    print("\n✅ Seed کامل شد.")


if __name__ == "__main__":
    os.environ.setdefault("APP_ENV", "production")
    asyncio.run(seed())
