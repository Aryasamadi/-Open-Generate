"""موجودیت کاربر"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional


class UserRole(str, Enum):
    USER = "user"
    ADMIN = "admin"          # channel admin
    SUPER_ADMIN = "super_admin"


class User:
    """
    کاربر سیستم — شناسه اصلی Telegram user_id است.
    مجوزها در backend کنترل می‌شوند؛ مخفی کردن دکمه کافی نیست.
    """

    def __init__(
        self,
        telegram_id: int,
        username: Optional[str],
        first_name: str,
        last_name: Optional[str],
        language: str = "fa",
        role: UserRole = UserRole.USER,
        plan_id: Optional[int] = None,
        plan_expires_at: Optional[datetime] = None,
        next_plan_id: Optional[int] = None,
        next_plan_starts_at: Optional[datetime] = None,
        is_banned: bool = False,
        ban_reason: Optional[str] = None,
        free_quota_used: int = 0,
        created_at: Optional[datetime] = None,
        last_active_at: Optional[datetime] = None,
        id: Optional[int] = None,
    ) -> None:
        self.id = id
        self.telegram_id = telegram_id
        self.username = username
        self.first_name = first_name
        self.last_name = last_name
        self.language = language
        self.role = role
        self.plan_id = plan_id
        self.plan_expires_at = plan_expires_at
        self.next_plan_id = next_plan_id
        self.next_plan_starts_at = next_plan_starts_at
        self.is_banned = is_banned
        self.ban_reason = ban_reason
        self.free_quota_used = free_quota_used
        self.created_at = created_at or datetime.utcnow()
        self.last_active_at = last_active_at or datetime.utcnow()

    # ------------------------------------------------------------------ Helpers

    @property
    def full_name(self) -> str:
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name

    @property
    def is_super_admin(self) -> bool:
        return self.role == UserRole.SUPER_ADMIN

    @property
    def is_admin(self) -> bool:
        return self.role in (UserRole.ADMIN, UserRole.SUPER_ADMIN)

    @property
    def has_active_plan(self) -> bool:
        if self.plan_expires_at is None:
            return True  # پلن رایگان بدون انقضا
        return datetime.utcnow() < self.plan_expires_at

    @property
    def plan_is_expired(self) -> bool:
        return not self.has_active_plan

    def can_access(self, required_role: UserRole) -> bool:
        """بررسی سطح دسترسی — RBAC اصلی"""
        if self.is_banned:
            return False
        role_order = {
            UserRole.USER: 0,
            UserRole.ADMIN: 1,
            UserRole.SUPER_ADMIN: 2,
        }
        return role_order[self.role] >= role_order[required_role]

    def __repr__(self) -> str:
        return (
            f"User(id={self.id}, telegram_id={self.telegram_id}, "
            f"username={self.username!r}, role={self.role})"
        )
