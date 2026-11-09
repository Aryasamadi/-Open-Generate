"""موجودیت پلن اشتراک"""
from __future__ import annotations
from decimal import Decimal
from typing import Optional


class Plan:
    """
    پلن اشتراک — همه محدودیت‌ها در backend enforce می‌شوند.
    پس از انقضا داده‌ها حذف نمی‌شوند.
    """

    def __init__(
        self,
        name: str,
        name_en: str,
        days: int,
        daily_posts: int,
        max_sources: int,
        max_channels: int,
        daily_tests: int,
        price: str,                   # قیمت نمایشی فارسی
        price_en: str,                # قیمت نمایشی انگلیسی
        price_num: Decimal,           # مقدار عددی دقیق
        price_num_fa: str,            # نمایش فارسی عدد
        description: str = "",
        description_en: str = "",
        is_free: bool = False,
        is_active: bool = True,
        sort: int = 0,
        id: Optional[int] = None,
    ) -> None:
        self.id = id
        self.name = name
        self.name_en = name_en
        self.days = days
        self.daily_posts = daily_posts
        self.max_sources = max_sources
        self.max_channels = max_channels
        self.daily_tests = daily_tests
        self.price = price
        self.price_en = price_en
        self.price_num = price_num
        self.price_num_fa = price_num_fa
        self.description = description
        self.description_en = description_en
        self.is_free = is_free
        self.is_active = is_active
        self.sort = sort

    def __repr__(self) -> str:
        return f"Plan(id={self.id}, name={self.name!r}, days={self.days})"
