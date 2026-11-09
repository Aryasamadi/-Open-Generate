"""
ساختار Prompt برای AI — تلگرام HTML ساختاریافته و دقیق.

مشکل قبلی: prompt فقط می‌گفت "HTML معتبر باشد" — بدون مثال یا قالب دقیق.
نتیجه: مدل‌های مختلف خروجی‌های متفاوت و ناسازگار می‌دادند.

الگوی صحیح: system prompt صریح درباره تگ‌های مجاز + ساختار مورد انتظار + مثال.
"""
from __future__ import annotations


# تگ‌های مجاز telegram bot api
_TG_HTML_REFERENCE = """
تگ‌های HTML مجاز در Telegram Bot API:
  <b>text</b>                          — bold
  <i>text</i>                          — italic
  <u>text</u>                          — underline
  <s>text</s>                          — strikethrough
  <code>text</code>                    — inline code
  <pre>text</pre>                      — code block
  <blockquote>text</blockquote>        — blockquote
  <blockquote expandable>text</blockquote>  — expandable blockquote
  <span class="tg-spoiler">text</span> — spoiler
  <a href="URL">text</a>               — hyperlink

تگ‌های HTML که تلگرام پشتیبانی نمی‌کند (از آن‌ها استفاده نکن):
  <h1>…<h6>  <p>  <br>  <div>  <ul>  <li>  <table>  <img>  <span> (غیر از tg-spoiler)
  هیچ attribute دیگری روی تگ‌های مجاز (مثلاً style= یا class= روی b یا i)
"""

_STRUCTURE_TEMPLATE_FA = """
ساختار خروجی مورد انتظار (فارسی):

<b>📌 [عنوان خلاصه‌شده]</b>

[یک یا دو پاراگراف اصلی — روان، خوانا، بدون اغراق]

اگر نقل‌قول مستقیم دارد:
<blockquote>[نقل‌قول]</blockquote>

اگر جدول دارد، آن را به این شکل نمایش بده:
• <b>[ستون ۱]</b>: [مقدار] | <b>[ستون ۲]</b>: [مقدار]

اگر کد یا دستور فنی دارد:
<code>[کد کوتاه]</code> یا:
<pre><code class="python">[کد چندخطی]</code></pre>

محدودیت: خروجی نهایی باید زیر 3800 کاراکتر باشد.
"""

_STRUCTURE_TEMPLATE_EN = """
Expected output structure (English):

<b>📌 [Summarized title]</b>

[One or two main paragraphs — clear, readable, no exaggeration]

If there's a direct quote:
<blockquote>[quote]</blockquote>

If there's a table, render it as:
• <b>[col1]</b>: [value] | <b>[col2]</b>: [value]

If there's code:
<code>[short code]</code> or:
<pre><code class="python">[multiline code]</code></pre>

Constraint: Final output must be under 3800 characters.
"""


def build_system_prompt(
    language: str,
    custom_prompt: str = "",
    topic: str = "",
    max_words: int = 400,
) -> str:
    """
    ساخت system prompt کامل برای تولید محتوای تلگرام.
    custom_prompt کاربر جایگزین رفتار پیش‌فرض می‌شود، نه append.
    """
    if custom_prompt.strip():
        # اگر کاربر prompt سفارشی داده، اضافه‌کردن ضوابط فنی HTML کافی است
        return (
            custom_prompt.strip()
            + "\n\n"
            + "--- ضوابط فنی اجباری ---\n"
            + _TG_HTML_REFERENCE
            + "\nخروجی باید HTML معتبر تلگرام باشد و زیر 3800 کاراکتر."
        )

    if language == "fa":
        base = (
            "تو یک ویراستار خبری حرفه‌ای هستی که محتوا را برای کانال تلگرام آماده می‌کنی.\n\n"
            "وظیفه: مقاله داده‌شده را به فارسی روان، دقیق و جذاب بازنویسی کن.\n\n"
            "قوانین سخت:\n"
            "1. فقط از محتوای موجود استفاده کن — واقعیت، آمار یا لینک بی‌منبع اضافه نکن\n"
            "2. اغراق، اظهارنظر و ادعای بدون مدرک ممنوع\n"
            f"3. حداکثر {max_words} کلمه\n"
            "4. فقط تگ‌های HTML مجاز تلگرام استفاده کن\n"
        )
        if topic:
            base += f"5. محتوا باید مرتبط با موضوع «{topic}» باشد\n"
        return base + "\n" + _TG_HTML_REFERENCE + "\n" + _STRUCTURE_TEMPLATE_FA
    else:
        base = (
            "You are a professional news editor preparing content for a Telegram channel.\n\n"
            "Task: Rewrite the provided article in fluent, accurate, and engaging English.\n\n"
            "Hard rules:\n"
            "1. Only use existing content — do not fabricate facts, statistics, or links\n"
            "2. No exaggeration, opinion, or unsupported claims\n"
            f"3. Maximum {max_words} words\n"
            "4. Only use Telegram-supported HTML tags\n"
        )
        if topic:
            base += f"5. Content must be relevant to the topic: '{topic}'\n"
        return base + "\n" + _TG_HTML_REFERENCE + "\n" + _STRUCTURE_TEMPLATE_EN
