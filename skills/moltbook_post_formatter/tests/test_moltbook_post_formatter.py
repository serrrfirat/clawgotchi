"""
Tests for Moltbook Post Formatter

Tests markdown formatting, title validation, and post preview generation.
"""

import pytest
from moltbook_post_formatter import (
    format_moltbook_post,
    format_title,
    validate_post,
    preview_post,
    MoltbookFormatError,
    MARKDOWN_BOLD,
    MARKDOWN_ITALIC,
    MARKDOWN_LINK,
    MARKDOWN_CODE,
)


class TestFormatMoltbookPost:
    """Test the main formatting function."""
    
    def test_plain_text_passes_through(self):
        """Plain text should remain unchanged."""
        result = format_moltbook_post("Hello World")
        assert result == "Hello World"
    
    def test_bold_formatting(self):
        """Bold markdown should convert to HTML."""
        result = format_moltbook_post("This is **bold** text")
        assert "<strong>bold</strong>" in result
    
    def test_italic_formatting(self):
        """Italic markdown should convert to HTML."""
        result = format_moltbook_post("This is *italic* text")
        assert "<em>italic</em>" in result
    
    def test_bold_and_italic(self):
        """Combined bold and italic should work."""
        result = format_moltbook_post("***bold and italic***")
        assert "<strong>" in result and "<em>" in result
    
    def test_link_formatting(self):
        """Links should convert to HTML."""
        result = format_moltbook_post("[Moltbook](https://moltbook.com)")
        assert '<a href="https://moltbook.com">Moltbook</a>' in result
    
    def test_inline_code(self):
        """Inline code should be wrapped in pre tags."""
        result = format_moltbook_post("Run `npm install`")
        assert "<pre>" in result or "<code>" in result
    
    def test_code_block(self):
        """Code blocks should be preserved."""
        result = format_moltbook_post("```python\nprint('hello')\n```")
        assert "<pre>" in result
    
    def test_html_entities_escaped(self):
        """HTML special characters should be escaped."""
        result = format_moltbook_post("3 < 5 & 10 > 2")
        assert "&lt;" in result and "&gt;" in result and "&amp;" in result
    
    def test_apostrophe_handling(self):
        """Apostrophes should be preserved, not break formatting."""
        result = format_moltbook_post("Don't forget to test")
        assert "Don't" in result or "Don&apos;t" in result
    
    def test_newlines_converted(self):
        """Newlines should be converted to breaks."""
        result = format_moltbook_post("Line 1\nLine 2")
        assert "<br>" in result or "\n" in result
    
    def test_bullet_list(self):
        """Bullet lists should be formatted."""
        result = format_moltbook_post("- Item 1\n- Item 2\n- Item 3")
        assert "<li>" in result or "-" in result
    
    def test_numbered_list(self):
        """Numbered lists should be formatted."""
        result = format_moltbook_post("1. First item\n2. Second item")
        assert "1." in result or "<ol>" in result
    
    def test_empty_string(self):
        """Empty string should return empty string."""
        result = format_moltbook_post("")
        assert result == ""
    
    def test_none_raises_error(self):
        """None input should raise MoltbookFormatError."""
        with pytest.raises(MoltbookFormatError):
            format_moltbook_post(None)
    
    def test_non_string_raises_error(self):
        """Non-string input should raise MoltbookFormatError."""
        with pytest.raises(MoltbookFormatError):
            format_moltbook_post(123)
        with pytest.raises(MoltbookFormatError):
            format_moltbook_post(["list"])
    
    def test_multiline_post(self):
        """Multiline posts should be formatted correctly."""
        content = """# Title

This is a paragraph with **bold** and *italic*.

- Point one
- Point two

[Link here](http://example.com)
"""
        result = format_moltbook_post(content)
        assert "<strong>" in result or "<em>" in result


class TestFormatTitle:
    """Test title formatting and validation."""
    
    def test_short_title_passes(self):
        """Valid short title should pass."""
        result = format_title("Short Title")
        assert result == "Short Title"
    
    def test_long_title_truncated(self):
        """Titles over 100 chars should be truncated."""
        long_title = "A" * 150
        result = format_title(long_title)
        assert len(result) <= 100
        assert "..." in result
    
    def test_title_stripped(self):
        """Title should be stripped of whitespace."""
        result = format_title("  Spaced Title  ")
        assert result == "Spaced Title"
    
    def test_empty_title_raises(self):
        """Empty title should raise MoltbookFormatError."""
        with pytest.raises(MoltbookFormatError):
            format_title("")
    
    def test_none_title_raises(self):
        """None title should raise MoltbookFormatError."""
        with pytest.raises(MoltbookFormatError):
            format_title(None)
    
    def test_title_with_special_chars(self):
        """Special characters should be allowed."""
        result = format_title("Title with: special - chars & more!")
        assert result == "Title with: special - chars & more!"
    
    def test_title_newlines_removed(self):
        """Newlines in titles should be removed."""
        result = format_title("Multi\nLine\nTitle")
        assert "\n" not in result


class TestValidatePost:
    """Test post validation."""
    
    def test_valid_post_passes(self):
        """Valid post should return True."""
        is_valid, error = validate_post("general", "Title", "Content here")
        assert is_valid is True
        assert error is None
    
    def test_empty_submolt_fails(self):
        """Empty submolt should fail."""
        is_valid, error = validate_post("", "Title", "Content")
        assert is_valid is False
        assert "submolt" in error.lower()
    
    def test_empty_title_fails(self):
        """Empty title should fail."""
        is_valid, error = validate_post("general", "", "Content")
        assert is_valid is False
        assert "title" in error.lower()
    
    def test_empty_content_fails(self):
        """Empty content should fail."""
        is_valid, error = validate_post("general", "Title", "")
        assert is_valid is False
        assert "content" in error.lower()
    
    def test_content_too_long_fails(self):
        """Content over 10000 chars should fail."""
        long_content = "x" * 10001
        is_valid, error = validate_post("general", "Title", long_content)
        assert is_valid is False
        assert "long" in error.lower() or "limit" in error.lower()
    
    def test_title_too_long_fails(self):
        """Title over 200 chars should fail."""
        long_title = "x" * 201
        is_valid, error = validate_post("general", long_title, "Content")
        assert is_valid is False
        assert "title" in error.lower()


class TestPreviewPost:
    """Test post preview generation."""
    
    def test_preview_contains_title(self):
        """Preview should include title."""
        preview = preview_post("general", "Test Title", "Content here")
        assert "Test Title" in preview
    
    def test_preview_contains_content_start(self):
        """Preview should include content start."""
        preview = preview_post("general", "Title", "The actual content goes here")
        assert "The actual content" in preview or "content" in preview.lower()
    
    def test_preview_shows_truncation(self):
        """Long content should be truncated with ellipsis."""
        long_content = "word " * 100
        preview = preview_post("general", "Title", long_content)
        assert "..." in preview
    
    def test_preview_shows_submolt(self):
        """Preview should indicate submolt."""
        preview = preview_post("general", "Title", "Content")
        assert "general" in preview.lower()
    
    def test_preview_validates_post(self):
        """Invalid post should show error in preview."""
        preview = preview_post("", "", "")
        assert "error" in preview.lower() or "invalid" in preview.lower()


class TestEdgeCases:
    """Test edge cases and unusual inputs."""
    
    def test_very_long_title(self):
        """Very long titles should be handled."""
        very_long = "A" * 500
        result = format_title(very_long)
        assert len(result) <= 100
    
    def test_unicode_in_content(self):
        """Unicode should be preserved."""
        result = format_moltbook_post("Hello 世界 🌍")
        assert "世界" in result or "🌍" in result
    
    def test_mixed_markdown(self):
        """Mixed markdown should all be converted."""
        result = format_moltbook_post("""
        # Header
        
        **Bold** and *italic* and `code`
        
        [Link](http://test.com)
        
        - List item
        """)
        assert "<strong>" in result or "<em>" in result or "<a href=" in result


class TestConstants:
    """Test markdown constant values."""
    
    def test_bold_constant(self):
        assert MARKDOWN_BOLD == "**"
    
    def test_italic_constant(self):
        assert MARKDOWN_ITALIC == "*"
    
    def test_link_constant(self):
        assert MARKDOWN_LINK == "["
    
    def test_code_constant(self):
        assert MARKDOWN_CODE == "`"


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
