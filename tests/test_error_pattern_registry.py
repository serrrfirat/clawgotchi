"""
Tests for Error Pattern Registry
"""

import pytest
from datetime import datetime
from error_pattern_registry import (
    ErrorCategory,
    Severity,
    ErrorPattern,
    ErrorContext,
    ErrorPatternRegistry,
    create_error_context
)


class TestErrorCategory:
    """Tests for ErrorCategory enum."""
    
    def test_all_categories_defined(self):
        """Verify all expected categories exist."""
        categories = list(ErrorCategory)
        assert ErrorCategory.NETWORK in categories
        assert ErrorCategory.API in categories
        assert ErrorCategory.PARSING in categories
        assert ErrorCategory.VALIDATION in categories
        assert ErrorCategory.RESOURCE in categories
        assert ErrorCategory.TIMEOUT in categories
        assert ErrorCategory.AUTH in categories
        assert ErrorCategory.RATE_LIMIT in categories
        assert ErrorCategory.UNKNOWN in categories
    
    def test_category_values(self):
        """Verify category string values."""
        assert ErrorCategory.NETWORK.value == "network"
        assert ErrorCategory.API.value == "api"
        assert ErrorCategory.RATE_LIMIT.value == "rate_limit"


class TestSeverity:
    """Tests for Severity enum."""
    
    def test_all_severities_defined(self):
        """Verify all expected severities exist."""
        severities = list(Severity)
        assert Severity.LOW in severities
        assert Severity.MEDIUM in severities
        assert Severity.HIGH in severities
        assert Severity.FATAL in severities
    
    def test_severity_ordering(self):
        """Verify severity values allow comparison."""
        assert Severity.LOW.value == "low"
        assert Severity.FATAL.value == "fatal"


class TestErrorPattern:
    """Tests for ErrorPattern dataclass."""
    
    def test_create_basic_pattern(self):
        """Test creating a basic error pattern."""
        pattern = ErrorPattern(
            name="TestError",
            category=ErrorCategory.API,
            severity=Severity.MEDIUM,
            description="Test error pattern",
            detection_pattern="test.*error"
        )
        assert pattern.name == "TestError"
        assert pattern.category == ErrorCategory.API
        assert pattern.severity == Severity.MEDIUM
        assert pattern.occurrence_count == 0
    
    def test_pattern_with_handler(self):
        """Test pattern with custom handler."""
        def custom_handler(ctx):
            return "handled"
        
        pattern = ErrorPattern(
            name="HandledError",
            category=ErrorCategory.NETWORK,
            severity=Severity.LOW,
            description="Error with handler",
            detection_pattern="handled",
            handler=custom_handler
        )
        assert pattern.handler is not None
        assert pattern.handler(ctx=None) == "handled"


class TestErrorContext:
    """Tests for ErrorContext dataclass."""
    
    def test_create_context(self):
        """Test creating error context."""
        ctx = ErrorContext(
            error_type="ValueError",
            error_message="Invalid input",
            category=ErrorCategory.VALIDATION,
            severity=Severity.LOW,
            timestamp=datetime.now()
        )
        assert ctx.error_type == "ValueError"
        assert ctx.category == ErrorCategory.VALIDATION
    
    def test_context_to_dict(self):
        """Test converting context to dictionary."""
        now = datetime.now()
        ctx = ErrorContext(
            error_type="TimeoutError",
            error_message="Operation timed out",
            category=ErrorCategory.TIMEOUT,
            severity=Severity.MEDIUM,
            timestamp=now,
            service_name="moltbook",
            operation="fetch_feed"
        )
        result = ctx.to_dict()
        assert result["error_type"] == "TimeoutError"
        assert result["category"] == "timeout"
        assert result["severity"] == "medium"
        assert result["service_name"] == "moltbook"


class TestErrorPatternRegistry:
    """Tests for ErrorPatternRegistry class."""
    
    def test_registry_initialization(self):
        """Test registry initializes with default patterns."""
        registry = ErrorPatternRegistry()
        stats = registry.get_statistics()
        assert stats["total_patterns"] >= 10  # At least default patterns
        assert stats["total_errors"] == 0
    
    def test_register_pattern(self):
        """Test registering a new pattern."""
        registry = ErrorPatternRegistry()
        pattern = ErrorPattern(
            name="CustomError",
            category=ErrorCategory.API,
            severity=Severity.HIGH,
            description="Custom error",
            detection_pattern="custom.*error"
        )
        registry.register_pattern(pattern)
        assert "CustomError" in registry._patterns
    
    def test_match_by_error_type(self):
        """Test matching error by type name."""
        registry = ErrorPatternRegistry()
        pattern = registry.match("RateLimited", "429 Too Many Requests")
        assert pattern is not None
        assert pattern.name == "RateLimited"
        assert pattern.category == ErrorCategory.RATE_LIMIT
    
    def test_match_by_message(self):
        """Test matching error by message content."""
        registry = ErrorPatternRegistry()
        pattern = registry.match("APIError", "401 Unauthorized: token invalid")
        assert pattern is not None
        assert pattern.name == "Unauthorized"
        assert pattern.category == ErrorCategory.AUTH
    
    def test_match_json_parse_error(self):
        """Test matching JSON parsing errors."""
        registry = ErrorPatternRegistry()
        pattern = registry.match("JSONDecodeError", "Expecting value: line 1 column 1")
        assert pattern is not None
        assert pattern.category == ErrorCategory.PARSING
    
    def test_match_timeout_error(self):
        """Test matching timeout errors."""
        registry = ErrorPatternRegistry()
        pattern = registry.match("TimeoutError", "Connection timed out after 30s")
        assert pattern is not None
        assert pattern.category == ErrorCategory.TIMEOUT
    
    def test_match_unknown_error(self):
        """Test matching unknown errors returns catch-all."""
        registry = ErrorPatternRegistry()
        pattern = registry.match("UnknownError", "Something completely unexpected")
        assert pattern is not None
        assert pattern.name == "UnknownError"
    
    def test_register_error(self):
        """Test registering an error occurrence."""
        registry = ErrorPatternRegistry()
        context = registry.register_error(
            error_type="APIError",
            error_message="404 Not Found",
            service_name="moltbook"
        )
        assert context.error_type == "APIError"
        assert context.category == ErrorCategory.API
        assert context.service_name == "moltbook"
    
    def test_error_counting(self):
        """Test error occurrences are counted."""
        registry = ErrorPatternRegistry()
        
        # Register same error multiple times
        for _ in range(5):
            registry.register_error("APIError", "Server error 500")
        
        stats = registry.get_statistics()
        assert stats["total_errors"] == 5
    
    def test_get_patterns_by_category(self):
        """Test getting patterns by category."""
        registry = ErrorPatternRegistry()
        network_patterns = registry.get_patterns_by_category(ErrorCategory.NETWORK)
        assert len(network_patterns) >= 2  # ConnectionTimeout, NetworkUnreachable
        
        auth_patterns = registry.get_patterns_by_category(ErrorCategory.AUTH)
        assert len(auth_patterns) >= 2  # Unauthorized, Forbidden
    
    def test_get_top_errors(self):
        """Test getting most frequent errors."""
        registry = ErrorPatternRegistry()
        
        # Create varied errors
        registry.register_error("Error1", "msg1")  # 1x
        registry.register_error("Error2", "msg2")  # 3x
        registry.register_error("Error2", "msg2")
        registry.register_error("Error2", "msg2")
        registry.register_error("Error3", "msg3")  # 2x
        
        top = registry.get_top_errors(limit=2)
        assert len(top) == 2
        assert top[0][0] == "Error2:msg2"
        assert top[0][1] == 3
    
    def test_get_statistics(self):
        """Test getting registry statistics."""
        registry = ErrorPatternRegistry()
        
        # Generate some errors
        registry.register_error("APIError", "401")
        registry.register_error("APIError", "401")
        registry.register_error("Timeout", "timed out")
        
        stats = registry.get_statistics()
        assert "by_category" in stats
        assert "by_severity" in stats
        assert stats["total_errors"] == 3
    
    def test_register_custom_handler(self):
        """Test registering custom handler for pattern."""
        registry = ErrorPatternRegistry()
        
        def my_handler(ctx):
            return {"custom": "handler", "type": ctx.error_type}
        
        result = registry.register_handler("Unauthorized", my_handler)
        assert result is True
        
        # Verify handler is used
        pattern = registry.match("APIError", "401 Unauthorized")
        handler_result = pattern.handler(ctx=None)
        assert handler_result["custom"] == "handler"
    
    def test_handler_not_found(self):
        """Test registering handler for non-existent pattern."""
        registry = ErrorPatternRegistry()
        result = registry.register_handler("NonExistent", lambda x: x)
        assert result is False
    
    def test_execute_handler(self):
        """Test executing pattern handler."""
        registry = ErrorPatternRegistry()
        
        context = registry.register_error(
            error_type="ValueError",
            error_message="invalid value",
            service_name="test"
        )
        
        pattern = registry.match("ValueError", "invalid value")
        result = registry.execute_handler(pattern, context)
        
        assert result is not None
        assert "handled" in result or "category" in result
    
    def test_default_handler_returns_dict(self):
        """Test that default handler returns structured info."""
        registry = ErrorPatternRegistry()
        
        ctx = ErrorContext(
            error_type="TestError",
            error_message="test message",
            category=ErrorCategory.UNKNOWN,
            severity=Severity.MEDIUM,
            timestamp=datetime.now()
        )
        
        pattern = registry._patterns["UnknownError"]
        result = registry._default_handler(ctx)
        
        assert isinstance(result, dict)
        assert result["handled"] is True


class TestConvenienceFunction:
    """Tests for convenience functions."""
    
    def test_create_error_context(self):
        """Test convenience function for creating context."""
        ctx = create_error_context(
            error_type="RateLimitError",
            error_message="429 Too Many Requests",
            service_name="api"
        )
        assert ctx.error_type == "RateLimitError"
        assert ctx.category == ErrorCategory.RATE_LIMIT
        assert ctx.service_name == "api"
    
    def test_create_error_context_no_service(self):
        """Test convenience function without service."""
        ctx = create_error_context(
            error_type="ValueError",
            error_message="invalid input"
        )
        assert ctx.error_type == "ValueError"
        assert ctx.category == ErrorCategory.VALIDATION
        assert ctx.service_name is None


class TestIntegration:
    """Integration tests with realistic scenarios."""
    
    def test_moltbook_api_error_flow(self):
        """Test handling Moltbook API errors end-to-end."""
        registry = ErrorPatternRegistry()
        
        # Simulate various Moltbook errors
        scenarios = [
            ("APIError", "401 Unauthorized", ErrorCategory.AUTH, True),
            ("APIError", "429 Too Many Requests", ErrorCategory.RATE_LIMIT, True),
            ("JSONDecodeError", "Expecting value", ErrorCategory.PARSING, False),
        ]
        
        for error_type, message, expected_cat, expect_retry in scenarios:
            ctx = registry.register_error(error_type, message, service_name="moltbook")
            assert ctx.category == expected_cat
            
            pattern = registry.match(error_type, message)
            assert pattern.retry_possible == expect_retry
    
    def test_full_error_handling_workflow(self):
        """Test complete error handling workflow."""
        registry = ErrorPatternRegistry()
        
        # Register error
        ctx = registry.register_error(
            error_type="APIServerError",
            error_message="500 Internal Server Error",
            operation="fetch_feed",
            raw_error=Exception("Server error")
        )
        
        # Get pattern and execute handler
        pattern = registry.match("APIServerError", "500 Internal Server Error")
        result = registry.execute_handler(pattern, ctx)
        
        # Verify
        assert pattern is not None
        assert pattern.name == "APIServerError"
        assert pattern.fallback_action == "retry_with_backoff"
        assert result is not None
    
    def test_circuit_breaker_integration(self):
        """Test integration with circuit breaker concept."""
        registry = ErrorPatternRegistry()
        
        # Track errors
        for _ in range(10):
            registry.register_error("APIError", "500 Internal Server Error")
        
        # Verify counting works
        stats = registry.get_statistics()
        assert stats["total_errors"] == 10
        
        # Check top errors
        top = registry.get_top_errors(1)
        assert top[0][1] >= 10
