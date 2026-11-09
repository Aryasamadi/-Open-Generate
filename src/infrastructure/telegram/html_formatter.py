"""
HTML Formatter — تبدیل محتوا به HTML معتبر Telegram Bot API.

تگ‌های پشتیبانی‌شده در Bot API (HTML mode):
  <b> <strong>              — bold
  <i> <em>                  — italic
  <u> <ins>                 — underline
  <s> <strike> <del>        — strikethrough
  <span class="tg-spoiler"> — spoiler
  <tg-spoiler>              — spoiler (shorthand)
  <a href="URL">            — hyperlink
  <code>                    — inline code
  <pre>                     — preformatted / code block
  <pre><code class="lang">  — code block with language
  <blockquote>              — blockquote
  <blockquote expandable>   — expandable blockquote (Bot API 7.4+)
  <tg-emoji emoji-id="..."> — custom emoji

تگ‌های HTML استاندارد که تلگرام پشتیبانی نمی‌کند:
  <h1>…<h6>  <p>  <br>  <table>  <ul>  <li>  <div>  <span> (بجز tg-spoiler)
  <img>  <hr>  و هر چیز دیگری

محدودیت‌های سخت:
  متن پیام: 4096 کاراکتر
  کپشن عکس: 1024 کاراکتر
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass, field
from typing import Optional


# ——————————————————————————————————————————————————————————
#  تگ‌های مجاز — به‌صورت regex دقیق برای whitelist
# ——————————————————————————————————————————————————————————
_ALLOWED_OPEN = re.compile(
    r"""
    <(
      b|strong|i|em|u|ins|s|strike|del|code|pre|tg-spoiler
      |blockquote(?:\s+expandable)?
      |a\s+href="[^"<>]{0,2048}"
      |span\s+class="tg-spoiler"
      |tg-emoji\s+emoji-id="\d+"
      |pre><code(?:\s+class="[a-zA-Z0-9_+-]{1,32}")?
    )>
    """,
    re.VERBOSE | re.IGNORECASE,
)
_ALLOWED_CLOSE = re.compile(
    r"</(b|strong|i|em|u|ins|s|strike|del|code|pre|tg-spoiler"
    r"|blockquote|a|span|tg-emoji)>",
    re.IGNORECASE,
)
_MAX_TEXT   = 4096
_MAX_CAPTION = 1024

# ——————————————————————————————————————————————————————————
#  تبدیل Markdown-table به متن خوانا
# ——————————————————————————————————————————————————————————
_MD_TABLE_ROW = re.compile(r"^\|(.+)\|$", re.MULTILINE)
_MD_TABLE_SEP = re.compile(r"^\|[\s\-\|:]+\|$", re.MULTILINE)


def convert_markdown_table(text: str) -> str:
    """
    جدول Markdown را به فرمت متنی خوانا در تلگرام تبدیل می‌کند.
    مثال ورودی:
      | نام | مقدار |
      |-----|-------|
      | الف | ۱۰۰   |
    خروجی:
      📊 جدول:
      • نام: الف → مقدار: ۱۰۰
    """
    lines = text.split("\n")
    result_lines: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # پیدا کردن شروع جدول: خط با pipe
        if _MD_TABLE_ROW.match(line.strip()):
            table_lines = []
            while i < len(lines) and (
                _MD_TABLE_ROW.match(lines[i].strip())
                or _MD_TABLE_SEP.match(lines[i].strip())
            ):
                table_lines.append(lines[i])
                i += 1
            converted = _table_to_text(table_lines)
            result_lines.extend(converted)
        else:
            result_lines.append(line)
            i += 1
    return "\n".join(result_lines)


def _table_to_text(table_lines: list[str]) -> list[str]:
    rows: list[list[str]] = []
    for line in table_lines:
        if _MD_TABLE_SEP.match(line.strip()):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        rows.append(cells)

    if not rows:
        return []

    headers = rows[0]
    data_rows = rows[1:]
    output = ["<b>📊 جدول:</b>"]
    for row in data_rows:
        parts = []
        for h, v in zip(headers, row):
            if h and v:
                parts.append(f"<b>{html.escape(h)}</b>: {html.escape(v)}")
        if parts:
            output.append("• " + " | ".join(parts))
    return output


# ——————————————————————————————————————————————————————————
#  تبدیل H1-H6 به bold با emoji
# ——————————————————————————————————————————————————————————
_H_PATTERN = re.compile(r"<h[1-6][^>]*>(.*?)</h[1-6]>", re.IGNORECASE | re.DOTALL)
_H_MD_PATTERN = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)


def convert_headings(text: str) -> str:
    """تبدیل <h1>…<h6> و # Markdown headings به bold"""
    text = _H_PATTERN.sub(lambda m: f"\n<b>📌 {m.group(1).strip()}</b>\n", text)
    text = _H_MD_PATTERN.sub(lambda m: f"\n<b>{'📌' if len(m.group(1))==1 else '▪️'} {m.group(2).strip()}</b>", text)
    return text


# ——————————————————————————————————————————————————————————
#  HTML Sanitizer اصلی
# ——————————————————————————————————————————————————————————
def sanitize_telegram_html(raw: str) -> str:
    """
    ورودی: متن خام که ممکن است HTML ناخالص، Markdown یا plain text باشد.
    خروجی: HTML معتبر تلگرام — فقط تگ‌های whitelist‌شده باقی می‌مانند.

    الگوریتم:
    1. تبدیل جداول Markdown پیش از هر چیز
    2. تبدیل heading‌ها
    3. تبدیل <br> و <p> به newline
    4. escape همه کاراکترهای HTML
    5. بازگرداندن تگ‌های مجاز از روی نسخه اصلی (قبل از escape)
    """
    if not raw:
        return ""

    # 1. جدول Markdown
    text = convert_markdown_table(raw)
    # 2. heading‌ها
    text = convert_headings(text)
    # 3. فاصله‌گذاری
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</p>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<p[^>]*>", "", text, flags=re.IGNORECASE)

    # 4+5. escape + بازگرداندن تگ‌های مجاز
    # نکته: به‌جای parse درخت، از روش token-based استفاده می‌کنیم:
    # هر تگ را موقتاً با placeholder جایگزین، escape می‌کنیم، برمی‌گردانیم.
    tokens: dict[str, str] = {}
    counter = [0]

    def stash(m: re.Match) -> str:
        key = f"\x00TG{counter[0]}\x00"
        counter[0] += 1
        tokens[key] = m.group(0)
        return key

    # stash تگ‌های مجاز
    combined = re.compile(
        r"""
        <(?:
          /?(?:b|strong|i|em|u|ins|s|strike|del|code|tg-spoiler|blockquote
              |pre|a|span|tg-emoji)
          (?:\s[^<>]{0,512})?
        )>
        """,
        re.VERBOSE | re.IGNORECASE,
    )
    text = combined.sub(stash, text)

    # escape همه باقی‌مانده
    text = html.escape(text, quote=False)

    # بازگرداندن تگ‌های stash‌شده — اما فقط مجاز
    for key, original_tag in tokens.items():
        if _ALLOWED_OPEN.match(original_tag) or _ALLOWED_CLOSE.match(original_tag):
            text = text.replace(html.escape(key, quote=False), original_tag)
            text = text.replace(key, original_tag)
        else:
            # تگ غیرمجاز — محتوا را نگه می‌داریم ولی تگ را حذف
            text = text.replace(html.escape(key, quote=False), "")
            text = text.replace(key, "")

    # پاکسازی چندین newline پشت‌سرهم
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ——————————————————————————————————————————————————————————
#  تقسیم محتوای بلند به چند chunk
# ——————————————————————————————————————————————————————————
@dataclass
class MessageChunk:
    text: str
    is_first: bool = False
    is_last: bool = False


def split_into_chunks(text: str, max_len: int = _MAX_TEXT) -> list[str]:
    """
    محتوا را به chunks حداکثر max_len کاراکتر تقسیم می‌کند.
    در مرزهای پاراگراف یا جمله می‌شکند — نه وسط یک تگ HTML.
    """
    if len(text) <= max_len:
        return [text]

    chunks: list[str] = []
    remaining = text

    while len(remaining) > max_len:
        # تلاش برای شکستن در \n\n (پاراگراف)
        cut = remaining.rfind("\n\n", 0, max_len)
        if cut < max_len // 2:
            # تلاش برای شکستن در \n
            cut = remaining.rfind("\n", 0, max_len)
        if cut < max_len // 2:
            # تلاش برای شکستن در ". "
            cut = remaining.rfind(". ", 0, max_len)
        if cut < max_len // 2:
            # آخرین چاره: برش سخت
            cut = max_len - 1

        # اطمینان از نبود تگ باز ناقص در انتهای chunk
        chunk = remaining[:cut].rstrip()
        # بستن تگ‌های باز (ساده)
        chunk = _close_open_tags(chunk)
        chunks.append(chunk)
        remaining = remaining[cut:].lstrip()

    if remaining:
        chunks.append(remaining)

    return chunks


def _close_open_tags(text: str) -> str:
    """تگ‌های HTML باز را می‌بندد تا chunk معتبر باشد"""
    # ساده‌ترین پیاده‌سازی برای تگ‌های مجاز
    closeable = ["b", "i", "u", "s", "code", "pre", "blockquote", "a", "span", "tg-spoiler"]
    stack: list[str] = []
    for m in re.finditer(r"<(/?)(\w[\w-]*)(?:\s[^>]*)?>", text):
        is_close, tag = m.group(1), m.group(2).lower()
        if tag in closeable:
            if is_close:
                if stack and stack[-1] == tag:
                    stack.pop()
            else:
                stack.append(tag)
    # بستن معکوس
    for tag in reversed(stack):
        text += f"</{tag}>"
    return text


# ——————————————————————————————————————————————————————————
#  ساختار پست نهایی
# ——————————————————————————————————————————————————————————
@dataclass
class PostStructure:
    """ساختار کامل یک پست تلگرام برای یک مقاله"""
    caption: str                   # برای send_photo — حداکثر 1024 کاراکتر
    continuation_chunks: list[str] # پیام‌های متنی بعدی اگر محتوا بلند بود
    has_media: bool = False
    media_url: Optional[str] = None


def build_post_structure(
    post_html: str,
    title: str,
    source_url: str,
    media_url: Optional[str],
    hashtags: list[str],
    signature: str,
    include_link: bool,
    include_media: bool,
    language: str = "fa",
) -> PostStructure:
    """
    ساخت ساختار کامل پست با رعایت تمام محدودیت‌های تلگرام.

    منطق:
    - اگر media_url داریم: اولین پیام send_photo با caption ≤1024
    - محتوای بیشتر → پیام‌های متنی ادامه‌دار
    - اگر media_url نداریم: پیام متنی ≤4096
    """
    # sanitize و آماده‌سازی محتوا
    clean_body = sanitize_telegram_html(post_html or title)
    clean_title = sanitize_telegram_html(title)

    # ساختار: تیتر + بدنه + هشتگ + لینک + امضا
    parts: list[str] = []

    if clean_body and clean_body != clean_title:
        # تیتر به‌عنوان bold در ابتدا
        parts.append(f"<b>{clean_title}</b>")
        parts.append(clean_body)
    else:
        parts.append(clean_body or clean_title)

    if hashtags:
        tag_line = " ".join(
            f"#{t.lstrip('#')}" for t in hashtags[:10]
        )
        parts.append(tag_line)

    footer_parts: list[str] = []
    if include_link and source_url:
        safe_url = html.escape(source_url)
        footer_parts.append(f'<a href="{safe_url}">🔗 منبع</a>')
    if signature:
        footer_parts.append(sanitize_telegram_html(signature))
    if footer_parts:
        parts.append(" | ".join(footer_parts))

    full_text = "\n\n".join(p for p in parts if p)

    has_media = include_media and bool(media_url)

    if has_media:
        # caption: حداکثر 1024
        if len(full_text) <= _MAX_CAPTION:
            return PostStructure(
                caption=full_text,
                continuation_chunks=[],
                has_media=True,
                media_url=media_url,
            )
        else:
            # caption: تیتر + لینک (فشرده)
            short_caption_parts = [f"<b>{clean_title}</b>"]
            if include_link and source_url:
                safe_url = html.escape(source_url)
                short_caption_parts.append(f'<a href="{safe_url}">🔗 منبع</a>')
            short_caption = "\n".join(short_caption_parts)
            if len(short_caption) > _MAX_CAPTION:
                short_caption = short_caption[:_MAX_CAPTION]

            # محتوای اصلی در پیام‌های ادامه‌دار
            # متن کامل را تقسیم می‌کنیم
            chunks = split_into_chunks(full_text, _MAX_TEXT)
            return PostStructure(
                caption=short_caption,
                continuation_chunks=chunks,
                has_media=True,
                media_url=media_url,
            )
    else:
        # بدون عکس: متن خالص
        if len(full_text) <= _MAX_TEXT:
            return PostStructure(
                caption=full_text,
                continuation_chunks=[],
                has_media=False,
            )
        else:
            chunks = split_into_chunks(full_text, _MAX_TEXT)
            return PostStructure(
                caption=chunks[0],
                continuation_chunks=chunks[1:],
                has_media=False,
            )
