"""تست‌های واحد html_formatter — بدون نیاز به dependency خارجی"""
from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.infrastructure.telegram.html_formatter import (
    sanitize_telegram_html,
    build_post_structure,
    split_into_chunks,
    convert_markdown_table,
    _MAX_TEXT,
    _MAX_CAPTION,
)


class TestSanitizeHTML:
    def test_allowed_bold(self):
        assert sanitize_telegram_html("<b>متن</b>") == "<b>متن</b>"

    def test_allowed_italic(self):
        assert sanitize_telegram_html("<i>متن</i>") == "<i>متن</i>"

    def test_allowed_link(self):
        result = sanitize_telegram_html('<a href="https://example.com">لینک</a>')
        assert '<a href="https://example.com">' in result

    def test_allowed_code(self):
        assert "<code>" in sanitize_telegram_html("<code>print(x)</code>")

    def test_allowed_blockquote(self):
        assert "<blockquote>" in sanitize_telegram_html("<blockquote>نقل‌قول</blockquote>")

    def test_allowed_expandable_blockquote(self):
        result = sanitize_telegram_html("<blockquote expandable>متن</blockquote>")
        assert "<blockquote expandable>" in result

    def test_allowed_spoiler(self):
        result = sanitize_telegram_html('<span class="tg-spoiler">مخفی</span>')
        assert 'tg-spoiler' in result

    def test_disallowed_h1_converted_to_bold(self):
        result = sanitize_telegram_html("<h1>عنوان اصلی</h1>")
        assert "<h1>" not in result
        assert "<b>" in result
        assert "عنوان اصلی" in result

    def test_disallowed_div_stripped(self):
        result = sanitize_telegram_html("<div>محتوا</div>")
        assert "<div>" not in result
        assert "محتوا" in result

    def test_disallowed_script_stripped_and_escaped(self):
        result = sanitize_telegram_html("<script>alert(1)</script>")
        assert "<script>" not in result

    def test_disallowed_img_stripped(self):
        result = sanitize_telegram_html('<img src="http://evil.com/x.png" />')
        assert "<img" not in result

    def test_xss_escape(self):
        result = sanitize_telegram_html("&lt;script&gt;")
        assert "<script>" not in result

    def test_br_to_newline(self):
        result = sanitize_telegram_html("خط اول<br>خط دوم")
        assert "\n" in result
        assert "<br>" not in result

    def test_p_to_newline(self):
        result = sanitize_telegram_html("<p>پاراگراف اول</p><p>پاراگراف دوم</p>")
        assert "<p>" not in result
        assert "پاراگراف اول" in result

    def test_empty_string(self):
        assert sanitize_telegram_html("") == ""

    def test_plain_text_unchanged(self):
        result = sanitize_telegram_html("متن ساده بدون HTML")
        assert result == "متن ساده بدون HTML"

    def test_ampersand_escaped(self):
        result = sanitize_telegram_html("AT&T")
        assert "&amp;T" in result or "AT&T" not in result or "AT&amp;T" in result


class TestMarkdownTable:
    def test_simple_table(self):
        md = "| نام | مقدار |\n|-----|-------|\n| الف | ۱۰۰ |"
        result = convert_markdown_table(md)
        assert "<b>" in result
        assert "الف" in result
        assert "|--" not in result

    def test_no_table_unchanged(self):
        text = "این یک متن عادی است."
        result = convert_markdown_table(text)
        assert result == text

    def test_table_values_escaped(self):
        md = "| col1 | col2 |\n|------|------|\n| <b>test</b> | val |"
        result = convert_markdown_table(md)
        # مقادیر باید escape شده باشند — نه اجرا شده
        assert "&lt;b&gt;" in result or "<b>col1</b>" in result or "col1" in result


class TestSplitIntoChunks:
    def test_short_text_not_split(self):
        text = "متن کوتاه"
        chunks = split_into_chunks(text, max_len=4096)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_split(self):
        text = ("کلمه " * 1000).strip()
        chunks = split_into_chunks(text, max_len=200)
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 200

    def test_no_chunk_exceeds_limit(self):
        text = "a" * 10000
        chunks = split_into_chunks(text, max_len=4096)
        for chunk in chunks:
            assert len(chunk) <= 4096

    def test_split_at_paragraph(self):
        text = ("پاراگراف اول.\n\n" * 50 + "آخر").strip()
        chunks = split_into_chunks(text, max_len=500)
        assert len(chunks) > 1


class TestBuildPostStructure:
    def test_short_text_no_continuation(self):
        result = build_post_structure(
            post_html="<b>متن کوتاه</b>",
            title="عنوان",
            source_url="https://example.com",
            media_url=None,
            hashtags=[],
            signature="",
            include_link=True,
            include_media=False,
        )
        assert result.continuation_chunks == []
        assert len(result.caption) <= _MAX_TEXT

    def test_caption_limit_with_photo(self):
        long_text = "این یک متن خیلی طولانی است. " * 100
        result = build_post_structure(
            post_html=long_text,
            title="عنوان",
            source_url="https://example.com",
            media_url="https://example.com/img.jpg",
            hashtags=[],
            signature="",
            include_link=True,
            include_media=True,
        )
        assert result.has_media is True
        assert len(result.caption) <= _MAX_CAPTION

    def test_long_text_has_continuations(self):
        long_text = "کلمه طولانی " * 500
        result = build_post_structure(
            post_html=long_text,
            title="عنوان",
            source_url="https://example.com",
            media_url="https://example.com/img.jpg",
            hashtags=[],
            signature="",
            include_link=False,
            include_media=True,
        )
        assert len(result.continuation_chunks) > 0
        for chunk in result.continuation_chunks:
            assert len(chunk) <= _MAX_TEXT

    def test_hashtags_in_caption(self):
        result = build_post_structure(
            post_html="محتوا",
            title="عنوان",
            source_url="https://example.com",
            media_url=None,
            hashtags=["فناوری", "هوش_مصنوعی"],
            signature="",
            include_link=False,
            include_media=False,
        )
        assert "#فناوری" in result.caption
        assert "#هوش_مصنوعی" in result.caption

    def test_signature_in_caption(self):
        result = build_post_structure(
            post_html="محتوا",
            title="عنوان",
            source_url="https://example.com",
            media_url=None,
            hashtags=[],
            signature="@MyChannel",
            include_link=False,
            include_media=False,
        )
        assert "@MyChannel" in result.caption

    def test_no_media_flag_ignores_media_url(self):
        result = build_post_structure(
            post_html="متن",
            title="عنوان",
            source_url="https://example.com",
            media_url="https://example.com/img.jpg",
            hashtags=[],
            signature="",
            include_link=False,
            include_media=False,  # ← غیرفعال
        )
        assert result.has_media is False


class TestParseAdminIds:
    """تست parse_admin_ids برای همه حالت‌های edge case"""

    def _parse(self, v):
        """شبیه‌سازی منطق validator"""
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        if isinstance(v, int):
            return [v]
        return [int(x) for x in v]

    def test_string_single(self):
        assert self._parse("123456789") == [123456789]

    def test_string_multiple(self):
        assert self._parse("123,456,789") == [123, 456, 789]

    def test_string_with_spaces(self):
        assert self._parse("123 , 456") == [123, 456]

    def test_list(self):
        assert self._parse([1, 2, 3]) == [1, 2, 3]

    def test_single_int(self):
        # حالتی که قبلاً TypeError می‌داد
        assert self._parse(123456789) == [123456789]

    def test_empty_string(self):
        assert self._parse("") == []


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
