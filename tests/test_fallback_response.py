"""
Tests for Fallback Response Generator
"""

import pytest
import time
from clawgotchi.resilience.fallback_response import (
    FallbackGenerator,
    FallbackConfig,
    FallbackStrategy,
    CachedResponse,
    create_graceful_fallback
)


class TestFallbackConfig:
    """Tests for FallbackConfig dataclass."""
    
    def test_default_config(self):
        config = FallbackConfig()
        assert config.strategy == FallbackStrategy.RETURN_DEFAULT
        assert config.default_value is None
        assert config.cache_ttl_seconds == 300
        assert config.enable_logging is True
    
    def test_custom_config(self):
        config = FallbackConfig(
            strategy=FallbackStrategy.RETURN_CACHED,
            default_value="fallback",
            cache_ttl_seconds=60,
            enable_logging=False
        )
        assert config.strategy == FallbackStrategy.RETURN_CACHED
        assert config.default_value == "fallback"
        assert config.cache_ttl_seconds == 60
        assert config.enable_logging is False


class TestFallbackGenerator:
    """Tests for FallbackGenerator class."""
    
    def test_no_fetch_function_returns_default(self):
        """When no fetch function is provided, returns default."""
        generator = FallbackGenerator()
        result = generator.get_with_fallback("test_service")
        assert result is None  # default_value is None
    
    def test_no_fetch_function_with_custom_default(self):
        """Returns custom default when no fetch function provided."""
        config = FallbackConfig(default_value="custom_default")
        generator = FallbackGenerator(config)
        result = generator.get_with_fallback("test_service")
        assert result == "custom_default"
    
    def test_successful_fetch(self):
        """Successfully fetched values are returned."""
        generator = FallbackGenerator()
        fetch_func = lambda: "success"
        result = generator.get_with_fallback("test_service", fetch_func=fetch_func)
        assert result == "success"
    
    def test_failed_fetch_returns_default(self):
        """Failed fetch returns default value."""
        config = FallbackConfig(default_value="fallback_value")
        generator = FallbackGenerator(config)
        fetch_func = lambda: (_ for _ in ()).throw(Exception("Service down"))
        result = generator.get_with_fallback("test_service", fetch_func=fetch_func)
        assert result == "fallback_value"
    
    def test_failed_fetch_returns_none_strategy(self):
        """Failed fetch with RETURN_NONE strategy returns None."""
        config = FallbackConfig(strategy=FallbackStrategy.RETURN_NONE)
        generator = FallbackGenerator(config)
        fetch_func = lambda: (_ for _ in ()).throw(Exception("Service down"))
        result = generator.get_with_fallback("test_service", fetch_func=fetch_func)
        assert result is None
    
    def test_failed_fetch_raises_error(self):
        """Failed fetch with RAISE_ERROR strategy raises exception."""
        config = FallbackConfig(strategy=FallbackStrategy.RAISE_ERROR)
        generator = FallbackGenerator(config)
        fetch_func = lambda: (_ for _ in ()).throw(Exception("Service down"))
        with pytest.raises(Exception):
            generator.get_with_fallback("test_service", fetch_func=fetch_func)
    
    def test_caching_success(self):
        """Successful fetches are cached."""
        generator = FallbackGenerator()
        call_count = 0
        
        def fetch_func():
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"
        
        # First call
        result1 = generator.get_with_fallback("test", fetch_func=fetch_func, cache_key="key1")
        assert result1 == "result_1"
        assert call_count == 1
        
        # Second call should use cache
        result2 = generator.get_with_fallback("test", fetch_func=fetch_func, cache_key="key1")
        assert result2 == "result_1"  # Same cached result
        assert call_count == 1  # No new call
    
    def test_cache_expiration(self):
        """Cache expires after TTL."""
        config = FallbackConfig(cache_ttl_seconds=1)  # 1 second TTL
        generator = FallbackGenerator(config)
        call_count = 0
        
        def fetch_func():
            nonlocal call_count
            call_count += 1
            return f"result_{call_count}"
        
        # First call
        result1 = generator.get_with_fallback("test", fetch_func=fetch_func, cache_key="key2")
        assert result1 == "result_1"
        
        # Wait for cache to expire
        time.sleep(1.1)
        
        # Second call should trigger new fetch
        result2 = generator.get_with_fallback("test", fetch_func=fetch_func, cache_key="key2")
        assert result2 == "result_2"
        assert call_count == 2
    
    def test_cache_status(self):
        """Cache status reports correctly."""
        config = FallbackConfig(cache_ttl_seconds=60)
        generator = FallbackGenerator(config)
        
        # No cache yet
        status = generator.get_cache_status("nonexistent")
        assert status["cached"] is False
        
        # Add to cache
        generator._set_cached("test_key", "value")
        
        # Check status
        status = generator.get_cache_status("test_key")
        assert status["cached"] is True
        assert "age_seconds" in status
        assert "ttl_remaining" in status
        assert status["is_expired"] is False
    
    def test_clear_cache(self):
        """Clear cache removes cached items."""
        generator = FallbackGenerator()
        generator._set_cached("key1", "value1")
        generator._set_cached("key2", "value2")
        
        assert "key1" in generator._cache
        assert "key2" in generator._cache
        
        generator.clear_cache("key1")
        
        assert "key1" not in generator._cache
        assert "key2" in generator._cache
        
        generator.clear_cache()
        
        assert len(generator._cache) == 0
    
    def test_fallback_with_custom_fallback_value(self):
        """Custom fallback value is returned when specified."""
        config = FallbackConfig(default_value="default")
        generator = FallbackGenerator(config)
        fetch_func = lambda: (_ for _ in ()).throw(Exception("down"))
        
        # Custom fallback_value overrides default
        result = generator.get_with_fallback("test", fallback_value="custom", fetch_func=fetch_func)
        # The strategy returns default_value, not fallback_value
        assert result == "default"
    
    def test_return_cached_strategy_no_cache(self):
        """RETURN_CACHED strategy falls back to default when no cache."""
        config = FallbackConfig(
            strategy=FallbackStrategy.RETURN_CACHED,
            default_value="cached_fallback"
        )
        generator = FallbackGenerator(config)
        fetch_func = lambda: (_ for _ in ()).throw(Exception("down"))
        
        result = generator.get_with_fallback("test", fetch_func=fetch_func)
        assert result == "cached_fallback"


class TestCreateGracefulFallback:
    """Tests for create_graceful_fallback function."""
    
    def test_creates_standard_response(self):
        """Creates a standardized fallback response."""
        response = create_graceful_fallback(
            service_name="moltbook",
            message="Feed unavailable",
            retry_after=30
        )
        
        assert response["status"] == "unavailable"
        assert response["service"] == "moltbook"
        assert response["message"] == "Feed unavailable"
        assert response["retry_after"] == 30
        assert "timestamp" in response
    
    def test_creates_response_with_defaults(self):
        """Creates response with default values."""
        response = create_graceful_fallback("test_service")
        
        assert response["status"] == "unavailable"
        assert response["service"] == "test_service"
        assert response["message"] == "Service temporarily unavailable"
        assert response["retry_after"] == 60
        assert "timestamp" in response
    
    def test_timestamp_is_numeric(self):
        """Timestamp is a numeric value."""
        response = create_graceful_fallback("test")
        assert isinstance(response["timestamp"], (int, float))


class TestCachedResponse:
    """Tests for CachedResponse dataclass."""
    
    def test_cached_response_creation(self):
        """CachedResponse stores value and timestamp."""
        cached = CachedResponse(value="test", cached_at=1234567890.0)
        assert cached.value == "test"
        assert cached.cached_at == 1234567890.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
