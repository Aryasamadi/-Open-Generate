"""
مدل‌های SQLAlchemy — نگاشت کامل جداول دیتابیس.
همه زمان‌ها UTC ذخیره می‌شوند.
Secretها رمزنگاری‌شده ذخیره می‌شوند.
"""
from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Index,
    Integer, Numeric, String, Text, UniqueConstraint,
    func, text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator, VARCHAR


# ------------------------------------------------------------------ Base
class Base(DeclarativeBase):
    pass


# ------------------------------------------------------------------ Custom Types

class JSONType(TypeDecorator):
    """JSON portable بین PostgreSQL (JSONB) و SQLite (Text)"""
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value, ensure_ascii=False)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return value


# ------------------------------------------------------------------ Users

class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(64))
    first_name: Mapped[str] = mapped_column(String(256), nullable=False)
    last_name: Mapped[str | None] = mapped_column(String(256))
    language: Mapped[str] = mapped_column(String(8), default="fa", server_default="fa")
    role: Mapped[str] = mapped_column(String(32), default="user", server_default="user")
    plan_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("plans.id"), nullable=True)
    plan_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    next_plan_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("plans.id"), nullable=True)
    next_plan_starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    ban_reason: Mapped[str | None] = mapped_column(Text)
    free_quota_used: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now()
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )

    channels: Mapped[list["ChannelModel"]] = relationship(back_populates="owner")
    wallets: Mapped[list["WalletModel"]] = relationship(back_populates="user")


# ------------------------------------------------------------------ Plans

class PlanModel(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    name_en: Mapped[str] = mapped_column(String(128), nullable=False)
    days: Mapped[int] = mapped_column(Integer, nullable=False)
    daily_posts: Mapped[int] = mapped_column(Integer, nullable=False)
    max_sources: Mapped[int] = mapped_column(Integer, nullable=False)
    max_channels: Mapped[int] = mapped_column(Integer, nullable=False)
    daily_tests: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[str] = mapped_column(String(64), nullable=False)
    price_en: Mapped[str] = mapped_column(String(64), nullable=False)
    price_num: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    price_num_fa: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    description_en: Mapped[str] = mapped_column(Text, default="", server_default="")
    is_free: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    sort: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


# ------------------------------------------------------------------ Channels

class ChannelModel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.telegram_id"), nullable=False, index=True
    )
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    bot_is_admin: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    settings_json: Mapped[dict] = mapped_column(JSONType, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now()
    )

    owner: Mapped["UserModel"] = relationship(back_populates="channels")
    sources: Mapped[list["SourceModel"]] = relationship(back_populates="channel")
    articles: Mapped[list["ArticleModel"]] = relationship(back_populates="channel")


# ------------------------------------------------------------------ Sources

class SourceModel(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    feed_url: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(32), default="rss")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # API اختصاصی
    api_url: Mapped[str | None] = mapped_column(Text)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text)  # رمزنگاری‌شده
    api_note: Mapped[str | None] = mapped_column(Text)
    # وضعیت
    etag: Mapped[str | None] = mapped_column(String(256))
    last_modified: Mapped[str | None] = mapped_column(String(128))
    last_fetch: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    fail_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    found_total: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
    next_try_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now()
    )

    channel: Mapped["ChannelModel"] = relationship(back_populates="sources")


# ------------------------------------------------------------------ Articles

class ArticleModel(Base):
    __tablename__ = "articles"
    __table_args__ = (
        UniqueConstraint("channel_id", "content_hash", name="uq_article_channel_hash"),
        UniqueConstraint("channel_id", "url_hash", name="uq_article_channel_url"),
        Index("ix_article_status_channel", "channel_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    canonical_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    url_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="fetched", server_default="fetched", index=True
    )
    raw_text: Mapped[str | None] = mapped_column(Text)
    full_text: Mapped[str | None] = mapped_column(Text)
    post_html: Mapped[str | None] = mapped_column(Text)
    media_url: Mapped[str | None] = mapped_column(Text)
    media_type: Mapped[str | None] = mapped_column(String(32))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now()
    )
    score: Mapped[float] = mapped_column(Numeric(5, 4), default=0.0, server_default="0")
    category: Mapped[str | None] = mapped_column(String(128))
    scoring_detail: Mapped[dict | None] = mapped_column(JSONType)
    ai_model_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ai_models.id", ondelete="SET NULL"), nullable=True
    )
    ai_prompt_hash: Mapped[str | None] = mapped_column(String(64))
    ai_retries: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    ai_error: Mapped[str | None] = mapped_column(Text)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger)
    publish_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_publish_error: Mapped[str | None] = mapped_column(Text)
    published_at_actual: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    reason: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[int | None] = mapped_column(BigInteger)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )

    channel: Mapped["ChannelModel"] = relationship(back_populates="articles")


# ------------------------------------------------------------------ AI Models

class AIModelModel(Base):
    __tablename__ = "ai_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(256), nullable=False)
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    model_id: Mapped[str] = mapped_column(String(256), nullable=False)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text)  # رمزنگاری‌شده
    is_global: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    owner_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    temperature: Mapped[float] = mapped_column(Numeric(4, 2), default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, default=1024)
    priority: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    fail_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_error: Mapped[str | None] = mapped_column(Text)
    last_ok: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    last_fail: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    next_try_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    circuit_open: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now()
    )


# ------------------------------------------------------------------ Payments

class PayRequestModel(Base):
    __tablename__ = "pay_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.telegram_id"), nullable=False, index=True
    )
    plan_id: Mapped[int] = mapped_column(Integer, ForeignKey("plans.id"), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="pending", server_default="pending", index=True
    )
    receipt_path: Mapped[str | None] = mapped_column(Text)
    receipt_mime: Mapped[str | None] = mapped_column(String(64))
    receipt_size: Mapped[int | None] = mapped_column(Integer)
    discount_code: Mapped[str | None] = mapped_column(String(64))
    discount_applied: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default="0"
    )
    note: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[int | None] = mapped_column(BigInteger)
    decision_note: Mapped[str | None] = mapped_column(Text)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now()
    )


# ------------------------------------------------------------------ Wallet / Ledger

class WalletModel(Base):
    __tablename__ = "wallet"
    __table_args__ = (
        UniqueConstraint("user_id", "currency", name="uq_wallet_user_currency"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.telegram_id"), nullable=False, index=True
    )
    currency: Mapped[str] = mapped_column(String(16), nullable=False)
    balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), default=Decimal("0"), server_default="0"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["UserModel"] = relationship(back_populates="wallets")


class LedgerModel(Base):
    __tablename__ = "credit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(16), nullable=False)
    delta: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reason: Mapped[str] = mapped_column(String(128), nullable=False)
    ref: Mapped[str | None] = mapped_column(String(256))
    note: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now()
    )


# ------------------------------------------------------------------ Discounts

class DiscountModel(Base):
    __tablename__ = "discounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    max_uses: Mapped[int] = mapped_column(Integer, nullable=False)
    used: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now()
    )


# ------------------------------------------------------------------ Referrals

class ReferralModel(Base):
    __tablename__ = "referrals"
    __table_args__ = (
        UniqueConstraint("referred_id", name="uq_referral_referred"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    referrer_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    referred_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    credit_amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(16), nullable=False)
    credited: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    credited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now()
    )


# ------------------------------------------------------------------ Notifications

class NotificationModel(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    notification_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONType, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, server_default="5")
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    is_dead: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now()
    )


# ------------------------------------------------------------------ Usage

class UsageModel(Base):
    __tablename__ = "usage"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_usage_user_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD UTC
    posts_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    tests_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    ai_calls: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    ai_tokens_in: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    ai_tokens_out: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


# ------------------------------------------------------------------ Publication Journal

class PubJournalModel(Base):
    """ثبت تلاش‌های انتشار — برای recovery و idempotency"""
    __tablename__ = "pub_journal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    article_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("articles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    telegram_message_id: Mapped[int | None] = mapped_column(BigInteger)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now()
    )


# ------------------------------------------------------------------ Support

class SupportTicketModel(Base):
    __tablename__ = "support"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(32), default="open", server_default="open"
    )
    subject: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))


class SupportMessageModel(Base):
    __tablename__ = "support_map"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("support.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    text: Mapped[str | None] = mapped_column(Text)
    file_id: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now()
    )


# ------------------------------------------------------------------ Channel Tokens (claim)

class ChannelTokenModel(Base):
    __tablename__ = "ch_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )
    token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    claimed_by: Mapped[int | None] = mapped_column(BigInteger)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now()
    )


# ------------------------------------------------------------------ AI Usage

class AIUsageModel(Base):
    __tablename__ = "ai_usage"
    __table_args__ = (
        UniqueConstraint("model_id", "date", name="uq_ai_usage_model_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ai_models.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[str] = mapped_column(String(10), nullable=False)
    calls: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    tokens_in: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    tokens_out: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


# ------------------------------------------------------------------ KV Cache

class KVCacheModel(Base):
    __tablename__ = "kv_cache"

    key: Mapped[str] = mapped_column(String(256), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now()
    )


# ------------------------------------------------------------------ Dedup

class DedupModel(Base):
    """جدول تکراریابی — hash → channel_id"""
    __tablename__ = "dedup"
    __table_args__ = (
        UniqueConstraint("channel_id", "hash", name="uq_dedup_channel_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now()
    )


# ------------------------------------------------------------------ Scheduler Heartbeat

class SchedulerHeartbeatModel(Base):
    __tablename__ = "scheduler_heartbeat"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    beat_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now()
    )
    worker_id: Mapped[str] = mapped_column(String(128), nullable=False)


# ------------------------------------------------------------------ Meta / Schema Version

class MetaModel(Base):
    __tablename__ = "meta"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now(), onupdate=func.now()
    )


# ------------------------------------------------------------------ Deeplinks

class DeeplinkModel(Base):
    __tablename__ = "deeplinks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONType, nullable=False)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    used_by: Mapped[int | None] = mapped_column(BigInteger)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now()
    )


# ------------------------------------------------------------------ Plan Changes (audit)

class PlanChangeModel(Base):
    __tablename__ = "plan_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    old_plan_id: Mapped[int | None] = mapped_column(Integer)
    new_plan_id: Mapped[int] = mapped_column(Integer, nullable=False)
    changed_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    pay_request_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=False), server_default=func.now()
    )
