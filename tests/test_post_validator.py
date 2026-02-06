"""Tests for Post Validator."""

import json
import os
import pytest
import tempfile
from datetime import datetime, timedelta

# Set temp directory for tests
os.environ['CLAWGOTCHI_DATA_DIR'] = tempfile.mkdtemp()
os.environ['CLAWGOTCHI_POST_LOG_FILE'] = os.path.join(os.environ['CLAWGOTCHI_DATA_DIR'], 'test_post_log.json')

from utils.post_validator import PostValidator, ValidationIssue, validate, validate_and_log, get_post_stats


@pytest.fixture
def validator():
    """Create a fresh validator for each test."""
    return PostValidator()


@pytest.fixture(autouse=True)
def clean_history(validator):
    """Clear history before each test."""
    validator.clear_history()
    yield
    validator.clear_history()


class TestPiiDetection:
    """Tests for PII detection in content."""

    def test_detects_email(self, validator):
        """Should detect email addresses in content."""
        content = "Contact me at test@gmail.com for more info"
        result = validator.check_pii(content)
        assert len(result) >= 1
        assert any(i.category == 'pii' and 'email' in i.message.lower() for i in result)

    def test_detects_api_key(self, validator):
        """Should detect API key patterns."""
        content = "api_key=ghp_abcdefghijklmnopqrstuvwxyz123456"
        result = validator.check_pii(content)
        assert len(result) >= 1
        assert any('API key' in i.message for i in result)

    def test_detects_bearer_token(self, validator):
        """Should detect Bearer tokens."""
        content = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        result = validator.check_pii(content)
        assert len(result) >= 1

    def test_detects_file_paths(self, validator):
        """Should detect file paths."""
        content = "The file is at /Users/firatsertgoz/Documents/clawgotchi/utils/test.py"
        result = validator.check_pii(content)
        assert len(result) >= 1
        assert any('file path' in i.message.lower() for i in result)

    def test_detects_windows_paths(self, validator):
        """Should detect Windows file paths."""
        content = "C:\\Users\\Admin\\Documents\\secret.txt"
        result = validator.check_pii(content)
        assert len(result) >= 1

    def test_ignores_example_domains(self, validator):
        """Should ignore example.com domains."""
        content = "Use user@example.com for testing"
        result = validator.check_pii(content)
        # No issues for example.com
        assert not any('email' in i.message.lower() for i in result)


class TestOpenEndedQuestions:
    """Tests for open-ended question detection."""

    def test_detects_how_do_we(self, validator):
        """Should detect 'how do we' patterns."""
        content = "How do we solve this problem?"
        result = validator.check_open_ended_questions(content)
        assert len(result) >= 1
        assert any('question' in i.category for i in result)

    def test_detects_questions_at_end(self, validator):
        """Should detect questions at end of content."""
        content = "This is some text\nWhat do you think?"
        result = validator.check_open_ended_questions(content)
        assert len(result) >= 1

    def test_allows_rhetorical_with_context(self, validator):
        """Should allow well-formed questions with context."""
        content = "Here's what I tried: 1. Step one 2. Step two. What worked was step three."
        result = validator.check_open_ended_questions(content)
        # Should not trigger if it's answering its own question
        assert len(result) == 0


class TestRateLimitChecks:
    """Tests for rate limit checking."""

    def test_no_issue_for_fresh_start(self, validator):
        """Should not flag anything if no recent posts."""
        issues = validator.check_rate_limits('moltbook')
        assert len(issues) == 0

    def test_flags_excessive_posts(self, validator):
        """Should flag if too many recent posts."""
        # Clear cache to ensure fresh load
        validator._post_history = None
        # Simulate many posts
        history_file = os.environ['CLAWGOTCHI_POST_LOG_FILE']
        history = []
        for i in range(6):
            history.append({
                'timestamp': datetime.now().isoformat(),
                'platform': 'moltbook',
                'result': 'validated_ok'
            })
        os.makedirs(os.path.dirname(history_file), exist_ok=True)
        with open(history_file, 'w') as f:
            json.dump(history, f)

        issues = validator.check_rate_limits('moltbook')
        assert len(issues) >= 1
        assert any('rate_limit' in i.category for i in issues)


class TestFullValidation:
    """Tests for full validation pipeline."""

    def test_clean_content_passes(self, validator):
        """Clean content should pass validation."""
        content = "Just sharing a quick update about my latest build!"
        result = validator.validate(content)
        assert result.is_valid
        assert len(result.get_errors()) == 0

    def test_pii_content_fails(self, validator):
        """Content with PII should fail validation."""
        content = "api_key=ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"
        result = validator.validate(content)
        assert not result.is_valid
        assert len(result.get_errors()) > 0

    def test_sanitized_content_provided(self, validator):
        """Should provide sanitized version of content."""
        content = "Email me at realuser@gmail.com"
        result = validator.validate(content)
        assert result.sanitized_content is not None
        assert 'realuser@gmail.com' not in result.sanitized_content

    def test_issue_severity分级(self, validator):
        """Should categorize issues by severity."""
        content = "api_key=xyz12345678901234567890"
        result = validator.validate(content)
        # API keys are errors
        errors = result.get_errors()
        assert len(errors) > 0


class TestLogging:
    """Tests for post logging."""

    def test_logs_validation_result(self, validator):
        """Should log validation attempts."""
        content = "Test post"
        result = validate_and_log(content, 'moltbook')
        assert result is not None

        stats = get_post_stats()
        assert stats['total_posts'] >= 1

    def test_tracks_validation_failures(self, validator):
        """Should track validation failures separately."""
        # Clear history first
        validator._post_history = None
        # Failed validation (contains API key)
        validate_and_log("api_key=ABCDEFGHIJKLMNOPQRSTUVWXYZ123456", 'moltbook')
        # Successful validation
        validate_and_log("Clean post", 'moltbook')

        stats = get_post_stats()
        assert stats['validation_failures'] >= 1


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_validate_function_exists(self):
        """validate function should be importable."""
        result = validate("Test content")
        assert result is not None
        assert hasattr(result, 'is_valid')

    def test_validate_and_log_function_exists(self):
        """validate_and_log function should be importable."""
        result = validate_and_log("Test content", 'test')
        assert result is not None

    def test_get_post_stats_function_exists(self):
        """get_post_stats function should be importable."""
        stats = get_post_stats()
        assert isinstance(stats, dict)
        assert 'total_posts' in stats


class TestEdgeCases:
    """Edge case tests."""

    def test_empty_content(self, validator):
        """Should handle empty content gracefully."""
        result = validator.validate("")
        assert result.is_valid  # Empty is technically valid

    def test_very_long_content(self, validator):
        """Should handle long content."""
        content = "word " * 1000
        result = validator.validate(content)
        assert result is not None

    def test_special_characters(self, validator):
        """Should handle special characters."""
        content = "Testing! @#$%^&*()_+-=[]{}|;':\",./<>?"
        result = validator.validate(content)
        assert result is not None

    def test_unicode_content(self, validator):
        """Should handle unicode characters."""
        content = "你好世界 🌍 مرحبا بالعالم 🎉"
        result = validator.validate(content)
        assert result.is_valid
