"""Tests for Error Message Parser utility."""

import pytest
from utils.error_message_parser import ErrorMessageParser, ParsedError


class TestParseError:
    """Tests for parse_error method."""

    def test_parses_basic_error(self):
        parser = ErrorMessageParser()
        result = parser.parse("Error: file not found")
        assert result.error_type == "Error"
        assert result.message == "file not found"
        assert result.is_actionable is False

    def test_parses_error_with_colon_in_message(self):
        parser = ErrorMessageParser()
        result = parser.parse("ValueError: invalid value: got 'abc', expected '123'")
        assert result.error_type == "ValueError"
        assert "invalid value" in result.message
        # Fix is expected now for ValueError
        assert result.suggested_fix is not None

    def test_parses_error_with_field_context(self):
        parser = ErrorMessageParser()
        result = parser.parse("Error: expected string, got null in field 'name'")
        assert result.error_type == "Error"
        assert result.field == "name"
        assert result.expected_type == "string"
        assert result.actual_type == "null"

    def test_parses_json_decode_error(self):
        parser = ErrorMessageParser()
        result = parser.parse("JSONDecodeError: Expecting value: line 1 column 1 (char 0)")
        assert result.error_type == "JSONDecodeError"
        assert "line 1" in result.message
        assert "column 1" in result.message

    def test_parses_syntax_error(self):
        parser = ErrorMessageParser()
        result = parser.parse("SyntaxError: unexpected EOF while parsing")
        assert result.error_type == "SyntaxError"
        assert "EOF" in result.message

    def test_parses_attribute_error(self):
        parser = ErrorMessageParser()
        result = parser.parse("AttributeError: module 'os' has no attribute 'pathh'")
        assert result.error_type == "AttributeError"
        assert result.missing_attribute == "pathh"
        assert result.module == "os"

    def test_parses_import_error(self):
        parser = ErrorMessageParser()
        result = parser.parse("ImportError: No module named 'requests'")
        assert result.error_type == "ImportError"
        assert "requests" in result.message

    def test_parses_type_error(self):
        parser = ErrorMessageParser()
        result = parser.parse("TypeError: can only concatenate str (not \"int\") to str")
        assert result.error_type == "TypeError"
        assert result.expected_type == "str"
        assert result.actual_type == "int"


class TestExtractErrorCode:
    """Tests for extract_error_code method."""

    def test_extracts_numeric_code(self):
        parser = ErrorMessageParser()
        code = parser.extract_error_code("Error 404: Not Found")
        assert code == "404"

    def test_extracts_alpha_code(self):
        parser = ErrorMessageParser()
        code = parser.extract_error_code("ERR_NULL_POINTER at 0x7f3a")
        assert code == "ERR_NULL_POINTER"

    def test_returns_none_for_no_code(self):
        parser = ErrorMessageParser()
        code = parser.extract_error_code("Something went wrong")
        assert code is None


class TestSuggestFix:
    """Tests for suggest_fix method."""

    def test_suggests_fix_for_attribute_error(self):
        parser = ErrorMessageParser()
        fix = parser.parse("AttributeError: module 'os' has no attribute 'pathh'").suggested_fix
        assert fix is not None
        assert "typo" in fix.lower() or "misspelled" in fix.lower()

    def test_suggests_fix_for_import_error(self):
        parser = ErrorMessageParser()
        fix = parser.parse("ImportError: No module named 'requests'").suggested_fix
        assert fix is not None
        assert "pip install" in fix.lower()

    def test_suggests_fix_for_value_error(self):
        parser = ErrorMessageParser()
        fix = parser.parse("ValueError: invalid literal for int() with base 10: 'abc'").suggested_fix
        assert fix is not None
        assert "expected type" in fix.lower() or "int" in fix.lower()

    def test_returns_none_for_unhandled(self):
        parser = ErrorMessageParser()
        fix = parser.parse("Error: unknown error occurred").suggested_fix
        assert fix is None


class TestIsActionable:
    """Tests for is_actionable property."""

    def test_field_error_is_actionable(self):
        parser = ErrorMessageParser()
        result = parser.parse("Error: expected string, got null in field 'name'")
        assert result.is_actionable is True

    def test_vague_error_is_not_actionable(self):
        parser = ErrorMessageParser()
        result = parser.parse("Error: something went wrong")
        assert result.is_actionable is False

    def test_json_error_is_actionable(self):
        parser = ErrorMessageParser()
        result = parser.parse("JSONDecodeError: Expecting value")
        assert result.is_actionable is True


class TestFormatForHuman:
    """Tests for format_for_human method."""

    def test_formats_basic_error(self):
        parser = ErrorMessageParser()
        result = parser.parse("ValueError: invalid value")
        formatted = parser.format_for_human(result)
        assert "ValueError" in formatted
        assert "invalid value" in formatted

    def test_formats_field_error_with_context(self):
        parser = ErrorMessageParser()
        result = parser.parse("Error: expected string, got null in field 'name'")
        formatted = parser.format_for_human(result)
        assert "Field: name" in formatted
        assert "Expected: string" in formatted
        assert "Got: null" in formatted
