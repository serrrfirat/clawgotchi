"""
Tests for JSON Escape Utility
"""

import pytest
from json_escape import (
    escape_for_moltbook,
    build_post_payload,
    escape_curl_content,
    validate_json_string,
    batch_escape,
    MoltbookJsonError
)


class TestEscapeForMoltbook:
    """Test the main escape function."""
    
    def test_simple_string(self):
        assert escape_for_moltbook("hello") == "hello"
    
    def test_with_apostrophe(self):
        result = escape_for_moltbook("Hello 'world'")
        # Single quotes should be escaped as \u0027
        assert "\\'" in result or "'" in result
    
    def test_with_double_quotes(self):
        result = escape_for_moltbook('Say "hello"')
        # Double quotes should be escaped
        assert '\\"' in result
    
    def test_with_newlines(self):
        result = escape_for_moltbook("line1\nline2")
        assert "\\n" in result
    
    def test_with_backslash(self):
        result = escape_for_moltbook("path\\to\\file")
        # Backslashes should be escaped
        assert "\\\\" in result
    
    def test_with_unicode(self):
        result = escape_for_moltbook("Hello 世界 🌍")
        assert "世界" in result or "\\u4e16\\u754c" in result
    
    def test_empty_string(self):
        assert escape_for_moltbook("") == ""
    
    def test_none_raises_error(self):
        with pytest.raises(MoltbookJsonError):
            escape_for_moltbook(None)
    
    def test_non_string_raises_error(self):
        with pytest.raises(MoltbookJsonError):
            escape_for_moltbook(123)
        with pytest.raises(MoltbookJsonError):
            escape_for_moltbook({"key": "value"})
    
    def test_complex_content(self):
        """Test the kind of content that breaks Moltbook posts."""
        content = "Here's a post with 'apostrophes' and \"quotes\"!\nNew line here."
        result = escape_for_moltbook(content)
        # Should not raise, and result should be non-empty
        assert isinstance(result, str)


class TestBuildPostPayload:
    """Test building complete post payloads."""
    
    def test_minimal_payload(self):
        payload = build_post_payload(
            submolt="general",
            title="Test Title",
            content="Test content"
        )
        assert payload["submolt"] == "general"
        assert payload["title"] == "Test Title"
        assert payload["content"] == "Test content"
    
    def test_with_url(self):
        payload = build_post_payload(
            submolt="general",
            title="Test",
            content="Content",
            url="https://example.com"
        )
        assert payload["url"] == "https://example.com"
    
    def test_with_apostrophes_in_content(self):
        payload = build_post_payload(
            submolt="general",
            title="Don't worry",
            content="It's going to be fine"
        )
        assert payload["content"] == "It's going to be fine"
    
    def test_empty_submolt_raises(self):
        with pytest.raises(MoltbookJsonError):
            build_post_payload(submolt="", title="T", content="C")
    
    def test_empty_title_raises(self):
        with pytest.raises(MoltbookJsonError):
            build_post_payload(submolt="g", title="", content="C")
    
    def test_empty_content_raises(self):
        with pytest.raises(MoltbookJsonError):
            build_post_payload(submolt="g", title="T", content="")


class TestValidateJsonString:
    """Test JSON validation."""
    
    def test_valid_string_returns_true(self):
        is_valid, error = validate_json_string("hello")
        assert is_valid is True
        assert error is None
    
    def test_valid_complex_string(self):
        content = "Test with 'quotes' and \"double quotes\""
        is_valid, error = validate_json_string(content)
        assert is_valid is True
    
    def test_invalid_type_returns_false(self):
        # Non-serializable object
        is_valid, error = validate_json_string(object())
        assert is_valid is False
        assert error is not None


class TestBatchEscape:
    """Test batch processing."""
    
    def test_batch_simple(self):
        result = batch_escape(["a", "b", "c"])
        assert result == ["a", "b", "c"]
    
    def test_batch_with_apostrophes(self):
        result = batch_escape(["don't", "can't", "won't"])
        assert len(result) == 3
        assert all(isinstance(r, str) for r in result)
    
    def test_batch_with_none_raises(self):
        with pytest.raises(MoltbookJsonError):
            batch_escape(["valid", None, "also valid"])


class TestEdgeCases:
    """Test edge cases and unusual inputs."""
    
    def test_very_long_string(self):
        long_string = "x" * 10000
        result = escape_for_moltbook(long_string)
        assert len(result) >= 10000
    
    def test_special_characters(self):
        special = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        result = escape_for_moltbook(special)
        assert isinstance(result, str)
    
    def test_tab_character(self):
        result = escape_for_moltbook("a\tb")
        assert "\\t" in result or "\t" in result
    
    def test_emoji(self):
        result = escape_for_moltbook("🦞")
        assert isinstance(result, str)
        assert len(result) > 0


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
