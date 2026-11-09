"""initial schema — all 25 tables

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("plans",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("name_en", sa.String(128), nullable=False),
        sa.Column("days", sa.Integer, nullable=False),
        sa.Column("daily_posts", sa.Integer, nullable=False),
        sa.Column("max_sources", sa.Integer, nullable=False),
        sa.Column("max_channels", sa.Integer, nullable=False),
        sa.Column("daily_tests", sa.Integer, nullable=False),
        sa.Column("price", sa.String(64), nullable=False),
        sa.Column("price_en", sa.String(64), nullable=False),
        sa.Column("price_num", sa.Numeric(18, 4), nullable=False),
        sa.Column("price_num_fa", sa.String(64), nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("description_en", sa.Text, server_default=""),
        sa.Column("is_free", sa.Boolean, server_default="false"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("sort", sa.Integer, server_default="0"),
    )

    op.create_table("users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("telegram_id", sa.BigInteger, nullable=False),
        sa.Column("username", sa.String(64)),
        sa.Column("first_name", sa.String(256), nullable=False),
        sa.Column("last_name", sa.String(256)),
        sa.Column("language", sa.String(8), server_default="fa"),
        sa.Column("role", sa.String(32), server_default="user"),
        sa.Column("plan_id", sa.Integer, sa.ForeignKey("plans.id"), nullable=True),
        sa.Column("plan_expires_at", sa.DateTime),
        sa.Column("next_plan_id", sa.Integer, sa.ForeignKey("plans.id"), nullable=True),
        sa.Column("next_plan_starts_at", sa.DateTime),
        sa.Column("is_banned", sa.Boolean, server_default="false"),
        sa.Column("ban_reason", sa.Text),
        sa.Column("free_quota_used", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("last_active_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"], unique=True)

    op.create_table("channels",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("owner_id", sa.BigInteger, sa.ForeignKey("users.telegram_id"), nullable=False),
        sa.Column("telegram_id", sa.BigInteger, nullable=False),
        sa.Column("username", sa.String(128)),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("bot_is_admin", sa.Boolean, server_default="false"),
        sa.Column("verified_at", sa.DateTime),
        sa.Column("settings_json", sa.Text, server_default="{}"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_channels_owner_id", "channels", ["owner_id"])
    op.create_index("ix_channels_telegram_id", "channels", ["telegram_id"], unique=True)

    op.create_table("ai_models",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(256), nullable=False),
        sa.Column("base_url", sa.Text, nullable=False),
        sa.Column("model_id", sa.String(256), nullable=False),
        sa.Column("api_key_encrypted", sa.Text),
        sa.Column("is_global", sa.Boolean, server_default="false"),
        sa.Column("owner_id", sa.BigInteger),
        sa.Column("temperature", sa.Numeric(4, 2), server_default="0.7"),
        sa.Column("max_tokens", sa.Integer, server_default="1024"),
        sa.Column("priority", sa.Integer, server_default="0"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("fail_count", sa.Integer, server_default="0"),
        sa.Column("last_error", sa.Text),
        sa.Column("last_ok", sa.DateTime),
        sa.Column("last_fail", sa.DateTime),
        sa.Column("next_try_after", sa.DateTime),
        sa.Column("circuit_open", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table("sources",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("owner_id", sa.BigInteger, nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("feed_url", sa.Text),
        sa.Column("source_type", sa.String(32), server_default="rss"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("api_url", sa.Text),
        sa.Column("api_key_encrypted", sa.Text),
        sa.Column("api_note", sa.Text),
        sa.Column("etag", sa.String(256)),
        sa.Column("last_modified", sa.String(128)),
        sa.Column("last_fetch", sa.DateTime),
        sa.Column("fail_count", sa.Integer, server_default="0"),
        sa.Column("found_total", sa.Integer, server_default="0"),
        sa.Column("last_error", sa.Text),
        sa.Column("next_try_after", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_sources_channel_id", "sources", ["channel_id"])

    op.create_table("articles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("sources.id", ondelete="SET NULL"), nullable=True),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("canonical_url", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("url_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), server_default="fetched"),
        sa.Column("raw_text", sa.Text),
        sa.Column("full_text", sa.Text),
        sa.Column("post_html", sa.Text),
        sa.Column("media_url", sa.Text),
        sa.Column("media_type", sa.String(32)),
        sa.Column("published_at", sa.DateTime),
        sa.Column("fetched_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("score", sa.Numeric(5, 4), server_default="0"),
        sa.Column("category", sa.String(128)),
        sa.Column("scoring_detail", sa.Text),
        sa.Column("ai_model_id", sa.Integer, sa.ForeignKey("ai_models.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ai_prompt_hash", sa.String(64)),
        sa.Column("ai_retries", sa.Integer, server_default="0"),
        sa.Column("ai_error", sa.Text),
        sa.Column("telegram_message_id", sa.BigInteger),
        sa.Column("publish_attempts", sa.Integer, server_default="0"),
        sa.Column("last_publish_error", sa.Text),
        sa.Column("published_at_actual", sa.DateTime),
        sa.Column("reason", sa.Text),
        sa.Column("reviewed_by", sa.BigInteger),
        sa.Column("reviewed_at", sa.DateTime),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_articles_channel_id", "articles", ["channel_id"])
    op.create_index("ix_articles_status", "articles", ["status"])
    op.create_unique_constraint("uq_article_channel_hash", "articles", ["channel_id", "content_hash"])
    op.create_unique_constraint("uq_article_channel_url", "articles", ["channel_id", "url_hash"])

    for tbl_def in _remaining_tables():
        op.create_table(*tbl_def[0], *tbl_def[1])
        for idx in tbl_def[2]:
            if idx[0] == "unique":
                op.create_unique_constraint(idx[1], tbl_def[0], idx[2])
            else:
                op.create_index(idx[1], tbl_def[0], idx[2], unique=idx[0] == "unique_idx")


def _remaining_tables():
    return [
        ("pay_requests", [
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.telegram_id"), nullable=False),
            sa.Column("plan_id", sa.Integer, sa.ForeignKey("plans.id"), nullable=False),
            sa.Column("amount", sa.Numeric(18, 4), nullable=False),
            sa.Column("currency", sa.String(16), nullable=False),
            sa.Column("status", sa.String(32), server_default="pending"),
            sa.Column("receipt_path", sa.Text), sa.Column("receipt_mime", sa.String(64)),
            sa.Column("receipt_size", sa.Integer), sa.Column("discount_code", sa.String(64)),
            sa.Column("discount_applied", sa.Numeric(18, 4), server_default="0"),
            sa.Column("note", sa.Text), sa.Column("decided_by", sa.BigInteger),
            sa.Column("decision_note", sa.Text), sa.Column("claimed_at", sa.DateTime),
            sa.Column("applied_at", sa.DateTime), sa.Column("decided_at", sa.DateTime),
            sa.Column("notified_at", sa.DateTime),
            sa.Column("idempotency_key", sa.String(128), unique=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        ], [("idx", "ix_pay_requests_user_id", ["user_id"]), ("idx", "ix_pay_requests_status", ["status"])]),

        ("wallet", [
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger, sa.ForeignKey("users.telegram_id"), nullable=False),
            sa.Column("currency", sa.String(16), nullable=False),
            sa.Column("balance", sa.Numeric(18, 4), server_default="0"),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        ], [("unique", "uq_wallet_user_currency", ["user_id", "currency"])]),

        ("credit_log", [
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger, nullable=False),
            sa.Column("currency", sa.String(16), nullable=False),
            sa.Column("delta", sa.Numeric(18, 4), nullable=False),
            sa.Column("balance_after", sa.Numeric(18, 4), nullable=False),
            sa.Column("reason", sa.String(128), nullable=False),
            sa.Column("ref", sa.String(256)), sa.Column("note", sa.Text),
            sa.Column("idempotency_key", sa.String(128), unique=True),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        ], [("idx", "ix_credit_log_user_id", ["user_id"])]),

        ("discounts", [
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("code", sa.String(64), unique=True, nullable=False),
            sa.Column("percent", sa.Numeric(5, 2), nullable=False),
            sa.Column("expires_at", sa.DateTime), sa.Column("max_uses", sa.Integer, nullable=False),
            sa.Column("used", sa.Integer, server_default="0"),
            sa.Column("is_active", sa.Boolean, server_default="true"),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        ], []),

        ("referrals", [
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("referrer_id", sa.BigInteger, nullable=False),
            sa.Column("referred_id", sa.BigInteger, nullable=False),
            sa.Column("credit_amount", sa.Numeric(18, 4), nullable=False),
            sa.Column("currency", sa.String(16), nullable=False),
            sa.Column("credited", sa.Boolean, server_default="false"),
            sa.Column("credited_at", sa.DateTime), sa.Column("note", sa.Text),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        ], [("unique", "uq_referral_referred", ["referred_id"]), ("idx", "ix_referrals_referrer_id", ["referrer_id"])]),

        ("notifications", [
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger, nullable=False),
            sa.Column("notification_type", sa.String(64), nullable=False),
            sa.Column("payload", sa.Text, nullable=False),
            sa.Column("attempts", sa.Integer, server_default="0"),
            sa.Column("max_attempts", sa.Integer, server_default="5"),
            sa.Column("next_attempt_at", sa.DateTime, nullable=False),
            sa.Column("delivered_at", sa.DateTime),
            sa.Column("is_dead", sa.Boolean, server_default="false"),
            sa.Column("last_error", sa.Text),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        ], [("idx", "ix_notifications_user_id", ["user_id"])]),

        ("usage", [
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger, nullable=False),
            sa.Column("date", sa.String(10), nullable=False),
            sa.Column("posts_count", sa.Integer, server_default="0"),
            sa.Column("tests_count", sa.Integer, server_default="0"),
            sa.Column("ai_calls", sa.Integer, server_default="0"),
            sa.Column("ai_tokens_in", sa.Integer, server_default="0"),
            sa.Column("ai_tokens_out", sa.Integer, server_default="0"),
        ], [("unique", "uq_usage_user_date", ["user_id", "date"])]),

        ("dedup", [
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("channel_id", sa.Integer, nullable=False),
            sa.Column("hash", sa.String(64), nullable=False),
            sa.Column("seen_at", sa.DateTime, server_default=sa.func.now()),
        ], [("unique", "uq_dedup_channel_hash", ["channel_id", "hash"]), ("idx", "ix_dedup_channel_id", ["channel_id"])]),

        ("support", [
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger, nullable=False),
            sa.Column("status", sa.String(32), server_default="open"),
            sa.Column("subject", sa.Text),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("closed_at", sa.DateTime),
        ], [("idx", "ix_support_user_id", ["user_id"])]),

        ("support_map", [
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("ticket_id", sa.Integer, sa.ForeignKey("support.id", ondelete="CASCADE"), nullable=False),
            sa.Column("sender_id", sa.BigInteger, nullable=False),
            sa.Column("is_admin", sa.Boolean, server_default="false"),
            sa.Column("text", sa.Text), sa.Column("file_id", sa.String(256)),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        ], [("idx", "ix_support_map_ticket_id", ["ticket_id"])]),

        ("scheduler_heartbeat", [
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("beat_at", sa.DateTime, server_default=sa.func.now()),
            sa.Column("worker_id", sa.String(128), nullable=False),
        ], []),

        ("pub_journal", [
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("article_id", sa.Integer, sa.ForeignKey("articles.id", ondelete="CASCADE"), nullable=False),
            sa.Column("channel_id", sa.Integer, nullable=False),
            sa.Column("attempt", sa.Integer, nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("telegram_message_id", sa.BigInteger),
            sa.Column("error", sa.Text),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        ], [("idx", "ix_pub_journal_article_id", ["article_id"])]),

        ("meta", [
            sa.Column("key", sa.String(128), primary_key=True),
            sa.Column("value", sa.Text, nullable=False),
            sa.Column("updated_at", sa.DateTime, server_default=sa.func.now()),
        ], []),

        ("kv_cache", [
            sa.Column("key", sa.String(256), primary_key=True),
            sa.Column("value", sa.Text, nullable=False),
            sa.Column("expires_at", sa.DateTime),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        ], []),

        ("plan_changes", [
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.BigInteger, nullable=False),
            sa.Column("old_plan_id", sa.Integer),
            sa.Column("new_plan_id", sa.Integer, nullable=False),
            sa.Column("changed_by", sa.BigInteger, nullable=False),
            sa.Column("reason", sa.Text), sa.Column("pay_request_id", sa.Integer),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        ], [("idx", "ix_plan_changes_user_id", ["user_id"])]),

        ("deeplinks", [
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("token", sa.String(128), unique=True, nullable=False),
            sa.Column("action", sa.String(64), nullable=False),
            sa.Column("payload", sa.Text, nullable=False),
            sa.Column("created_by", sa.BigInteger, nullable=False),
            sa.Column("used_by", sa.BigInteger),
            sa.Column("expires_at", sa.DateTime, nullable=False),
            sa.Column("used_at", sa.DateTime),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        ], []),

        ("ai_usage", [
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("model_id", sa.Integer, sa.ForeignKey("ai_models.id", ondelete="CASCADE"), nullable=False),
            sa.Column("date", sa.String(10), nullable=False),
            sa.Column("calls", sa.Integer, server_default="0"),
            sa.Column("tokens_in", sa.Integer, server_default="0"),
            sa.Column("tokens_out", sa.Integer, server_default="0"),
        ], [("unique", "uq_ai_usage_model_date", ["model_id", "date"])]),

        ("ch_tokens", [
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("channel_id", sa.Integer, sa.ForeignKey("channels.id", ondelete="CASCADE"), nullable=False),
            sa.Column("token", sa.String(128), unique=True, nullable=False),
            sa.Column("created_by", sa.BigInteger, nullable=False),
            sa.Column("claimed_by", sa.BigInteger),
            sa.Column("expires_at", sa.DateTime, nullable=False),
            sa.Column("used", sa.Boolean, server_default="false"),
            sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        ], []),
    ]


def downgrade() -> None:
    for t in reversed([
        "ch_tokens","ai_usage","deeplinks","plan_changes","kv_cache","meta",
        "pub_journal","scheduler_heartbeat","support_map","support","dedup",
        "usage","notifications","referrals","discounts","credit_log","wallet",
        "pay_requests","articles","sources","ai_models","channels","users","plans",
    ]):
        op.drop_table(t)
