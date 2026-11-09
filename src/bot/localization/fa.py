"""متون رابط کاربری — فارسی"""

TEXTS = {
    # ------------------------------------------------------------------ عمومی
    "welcome": "👋 سلام {name}!\nبه ربات مدیریت کانال خوش آمدید.",
    "choose_action": "یک گزینه انتخاب کنید:",
    "back": "🔙 بازگشت",
    "cancel": "❌ لغو",
    "done": "✅ انجام شد",
    "error_generic": "⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید.",
    "not_authorized": "⛔ شما مجوز این عملیات را ندارید.",
    "banned": "⛔ حساب شما مسدود شده است.\nدلیل: {reason}",
    "operation_in_progress": "⏳ عملیات در حال انجام است، لطفاً صبر کنید...",
    "confirm_action": "⚠️ آیا مطمئنید؟\n{detail}",
    "yes_confirm": "✅ بله، تأیید می‌کنم",
    "no_cancel": "❌ خیر، لغو",

    # ------------------------------------------------------------------ کانال
    "channel_menu": "📢 مدیریت کانال‌ها",
    "channel_add": "➕ افزودن کانال",
    "channel_list": "📋 لیست کانال‌ها",
    "channel_settings": "⚙️ تنظیمات کانال",
    "channel_status": "📊 وضعیت کانال",
    "channel_delete": "🗑️ حذف کانال",
    "channel_enter_id": "🔗 لطفاً username یا شناسه عددی کانال را وارد کنید:\n(مثال: @mychannel یا -1001234567890)",
    "channel_checking": "🔍 در حال بررسی کانال...",
    "channel_added": "✅ کانال {title} با موفقیت اضافه شد.",
    "channel_not_admin": "❌ ربات در این کانال ادمین نیست یا مجوز ارسال ندارد.",
    "channel_already_exists": "⚠️ این کانال قبلاً اضافه شده است.",
    "channel_limit_reached": "⛔ به سقف کانال‌های مجاز در پلن شما رسیده‌اید ({max}).",
    "channel_deleted": "🗑️ کانال با موفقیت حذف شد.",
    "channel_enabled": "✅ کانال فعال شد.",
    "channel_disabled": "⏸️ کانال غیرفعال شد.",
    "no_channels": "❌ هنوز کانالی اضافه نکرده‌اید.",

    # ------------------------------------------------------------------ منابع
    "source_menu": "📰 مدیریت منابع",
    "source_add": "➕ افزودن منبع",
    "source_list": "📋 لیست منابع",
    "source_enter_url": "🔗 آدرس منبع (URL یا RSS feed) را وارد کنید:",
    "source_enter_title": "✏️ عنوان نمایشی منبع را وارد کنید:",
    "source_added": "✅ منبع {title} اضافه شد.",
    "source_deleted": "🗑️ منبع حذف شد.",
    "source_limit_reached": "⛔ به سقف منابع مجاز در پلن شما رسیده‌اید ({max}).",
    "source_invalid_url": "❌ آدرس وارد‌شده معتبر نیست.",
    "source_ssrf_blocked": "⛔ این آدرس مجاز نیست.",
    "no_sources": "❌ هنوز منبعی تعریف نکرده‌اید.",

    # ------------------------------------------------------------------ هوش مصنوعی
    "ai_menu": "🤖 مدیریت مدل‌های AI",
    "ai_add": "➕ افزودن مدل",
    "ai_list": "📋 لیست مدل‌ها",
    "ai_test": "🧪 تست مدل",
    "ai_enter_provider": "انتخاب provider:",
    "ai_enter_base_url": "🔗 آدرس پایه API را وارد کنید:",
    "ai_enter_api_key": "🔑 API key را وارد کنید (در پیام بعدی پاک خواهد شد):",
    "ai_enter_model_id": "🤖 شناسه مدل را وارد کنید:",
    "ai_enter_display_name": "✏️ نام نمایشی مدل:",
    "ai_testing": "🧪 در حال تست اتصال...",
    "ai_test_ok": "✅ اتصال موفق بود.",
    "ai_test_failed": "❌ تست ناموفق: {error}",
    "ai_added": "✅ مدل {name} اضافه شد.",
    "ai_deleted": "🗑️ مدل حذف شد.",
    "ai_key_masked": "🔑 API key ذخیره شد (نمایش: {masked})",
    "ai_discover_models": "🔍 کشف مدل‌های موجود...",

    # ------------------------------------------------------------------ پلن و پرداخت
    "plan_menu": "💎 پلن اشتراک",
    "plan_current": "📋 پلن فعلی شما: {name}\nانقضا: {expires}\nروزانه: {daily} پست",
    "plan_expired": "⚠️ پلن شما منقضی شده است.",
    "plan_buy": "🛒 خرید اشتراک",
    "plan_list": "لطفاً پلن مورد نظر را انتخاب کنید:",
    "plan_selected": "پلن {name} انتخاب شد.\nمبلغ: {price}",
    "payment_enter_receipt": "📎 لطفاً تصویر یا PDF رسید پرداخت را ارسال کنید:",
    "payment_submitted": "✅ درخواست پرداخت ثبت شد.\nکد پیگیری: #{id}\nپس از تأیید، پلن فعال می‌شود.",
    "payment_pending": "⏳ درخواست پرداخت #{id} در حال بررسی است.",
    "payment_approved": "✅ پرداخت تأیید شد! پلن {plan} فعال شد.",
    "payment_rejected": "❌ پرداخت رد شد.\nدلیل: {reason}",
    "payment_duplicate": "⚠️ یک درخواست پرداخت در حال بررسی دارید.",
    "discount_enter_code": "🏷️ کد تخفیف را وارد کنید (یا رد کنید):",
    "discount_applied": "✅ کد تخفیف اعمال شد: {percent}٪ تخفیف",
    "discount_invalid": "❌ کد تخفیف نامعتبر یا منقضی شده است.",

    # ------------------------------------------------------------------ کیف پول
    "wallet_menu": "💰 کیف پول",
    "wallet_balance": "موجودی: {balance} {currency}",

    # ------------------------------------------------------------------ پشتیبانی
    "support_menu": "🆘 پشتیبانی",
    "support_new": "✉️ تیکت جدید",
    "support_enter_message": "پیام خود را بنویسید:",
    "support_submitted": "✅ تیکت #{id} ثبت شد.",
    "support_reply": "💬 پاسخ تیکت #{id}:\n{message}",

    # ------------------------------------------------------------------ تنظیمات موتور
    "settings_menu": "⚙️ تنظیمات موتور",
    "settings_mode": "حالت انتشار: {mode}",
    "settings_mode_auto": "🤖 خودکار",
    "settings_mode_review": "👁️ بازبینی",
    "settings_prompt": "✏️ Prompt سفارشی",
    "settings_topic": "🎯 موضوع",
    "settings_language": "🌐 زبان خروجی",
    "settings_timezone": "🕐 منطقه زمانی",
    "settings_schedule": "📅 زمان‌بندی",
    "settings_categories": "🏷️ دسته‌بندی‌ها",
    "settings_criteria": "⚖️ معیارها و وزن‌ها",
    "settings_min_score": "🎯 حداقل امتیاز",
    "settings_saved": "✅ تنظیمات ذخیره شد.",
    "settings_enter_prompt": "✏️ prompt سفارشی را وارد کنید (یا /skip):",
    "settings_enter_topic": "🎯 موضوع کانال را بنویسید:",
    "settings_enter_timezone": "🕐 نام منطقه زمانی را وارد کنید (مثال: Asia/Tehran):",
    "settings_enter_min_score": "🎯 حداقل امتیاز را وارد کنید (۰ تا ۱، مثال: ۰.۵):",
    "settings_invalid_timezone": "❌ منطقه زمانی نامعتبر است.",
    "settings_invalid_score": "❌ امتیاز باید بین ۰ و ۱ باشد.",

    # ------------------------------------------------------------------ بازبینی
    "review_queue": "📋 صف بازبینی ({count} مقاله)",
    "review_article": "📄 مقاله:\n<b>{title}</b>\n\nامتیاز: {score} | دسته: {category}\nمنبع: {source}",
    "review_approve": "✅ تأیید",
    "review_reject": "❌ رد",
    "review_edit": "✏️ ویرایش",
    "review_approved": "✅ مقاله تأیید و در صف انتشار قرار گرفت.",
    "review_rejected": "❌ مقاله رد شد.",
    "review_empty": "✅ صف بازبینی خالی است.",

    # ------------------------------------------------------------------ آمار
    "stats_menu": "📊 آمار و مصرف",
    "stats_today": "امروز: {posts} پست | {tests} تست | {ai_calls} AI call",
    "stats_tokens": "توکن‌ها: {tokens_in} ورودی / {tokens_out} خروجی",

    # ------------------------------------------------------------------ سوپرادمین
    "admin_menu": "👑 پنل سوپرادمین",
    "admin_users": "👥 مدیریت کاربران",
    "admin_channels": "📢 مدیریت کانال‌ها",
    "admin_plans": "💎 مدیریت پلن‌ها",
    "admin_payments": "💳 پرداخت‌ها",
    "admin_ai_models": "🤖 مدل‌های عمومی AI",
    "admin_broadcast": "📣 ارسال همگانی",
    "admin_health": "💊 وضعیت سیستم",
    "admin_user_search": "🔍 جستجوی کاربر (ID یا username):",
    "admin_ban_user": "🚫 مسدود کردن کاربر",
    "admin_unban_user": "✅ رفع مسدودیت",
    "admin_ban_reason": "دلیل مسدودیت را بنویسید:",
    "admin_banned": "🚫 کاربر {id} مسدود شد.",
    "admin_unbanned": "✅ کاربر {id} از مسدودیت خارج شد.",
    "admin_broadcast_message": "✉️ متن پیام همگانی را بنویسید:",
    "admin_broadcast_preview": "👁️ پیش‌نمایش:\n{text}\n\nارسال به {count} کاربر؟",
    "admin_broadcast_confirm": "📣 تأیید ارسال همگانی",
    "admin_broadcast_sent": "✅ ارسال کامل شد.\nموفق: {ok} | ناموفق: {fail}",

    # ------------------------------------------------------------------ معرفی
    "referral_menu": "🎁 معرفی دوستان",
    "referral_link": "🔗 لینک معرفی شما:\n{link}",
    "referral_count": "تعداد معرفی‌شدگان: {count}",
    "referral_earned": "💰 اعتبار کسب‌شده: {amount} {currency}",

    # ------------------------------------------------------------------ زبان
    "language_menu": "🌐 انتخاب زبان",
    "language_set": "✅ زبان تغییر کرد.",
}


def t(key: str, lang: str = "fa", **kwargs: object) -> str:
    """ترجمه با جایگزینی پارامترها"""
    if lang == "en":
        from src.bot.localization.en import TEXTS as EN
        text = EN.get(key, TEXTS.get(key, key))
    else:
        text = TEXTS.get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text
