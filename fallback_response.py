"""
Fallback Response Generator

Provides graceful fallback responses when external services are unavailable.
Supports multiple fallback strategies and response templates.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional
import time


class FallbackStrategy(Enum):
    """Strategies for handling service unavailability."""
    RETURN_NONE = "return_none"
    RETURN_DEFAULT = "return_default"
    RETURN_CACHED = "return_cached"
    RAISE_ERROR = "raise_error"


@dataclass
class FallbackConfig:
    """Configuration for fallback behavior."""
    strategy: FallbackStrategy = FallbackStrategy.RETURN_DEFAULT
    default_value: Any = None
    cache_ttl_seconds: int = 300  # 5 minutes
    enable_logging: bool = True


@dataclass
class CachedResponse:
    """A cached response with timestamp."""
    value: Any
    cached_at: float


class FallbackGenerator:
    """
    Generates fallback responses when services are unavailable.
    
    Usage:
        generator = FallbackGenerator()
        result = generator.get_with_fallback(
            service_name="moltbook",
            fallback_value="Service temporarily unavailable",
            cache_key="feed"
        )
    """
    
    def __init__(self, config: Optional[FallbackConfig] = None):
        self.config = config or FallbackConfig()
        self._cache: dict[str, CachedResponse] = {}
    
    def _log(self, message: str) -> None:
        """Log a message if logging is enabled."""
        if self.config.enable_logging:
            print(f"[FallbackGenerator] {message}")
    
    def _get_cached(self, cache_key: str) -> Optional[Any]:
        """Get cached value if it exists and hasn't expired."""
        if cache_key not in self._cache:
            return None
        
        cached = self._cache[cache_key]
        age = time.time() - cached.cached_at
        
        if age > self.config.cache_ttl_seconds:
            del self._cache[cache_key]
            return None
        
        return cached.value
    
    def _set_cached(self, cache_key: str, value: Any) -> None:
        """Cache a value with current timestamp."""
        self._cache[cache_key] = CachedResponse(value=value, cached_at=time.time())
    
    def get_with_fallback(
        self,
        service_name: str,
        fallback_value: Any = None,
        cache_key: Optional[str] = None,
        fetch_func: Optional[callable] = None
    ) -> Any:
        """
        Try to fetch from source, fall back gracefully if unavailable.
        
        Args:
            service_name: Name of the service (for logging)
            fallback_value: Value to return on failure
            cache_key: Optional key for caching successful responses
            fetch_func: Function to call for fetching data
            
        Returns:
            Fetched value, cached value, or fallback depending on strategy
        """
        if fetch_func is None:
            # No fetch function - just return fallback
            self._log(f"No fetch function for {service_name}, returning fallback")
            return self.config.default_value if self.config.strategy == FallbackStrategy.RETURN_DEFAULT else fallback_value
        
        # Check cache first if cache_key provided and we have cached data
        if cache_key:
            cached = self._get_cached(cache_key)
            if cached is not None:
                self._log(f"Returning cached result for {cache_key}")
                return cached
        
        try:
            result = fetch_func()
            
            # Cache successful result if cache_key provided
            if cache_key and result is not None:
                self._set_cached(cache_key, result)
                self._log(f"Cached result for {cache_key}")
            
            return result
            
        except Exception as e:
            self._log(f"Service {service_name} unavailable: {e}")
            
            # Apply strategy
            if self.config.strategy == FallbackStrategy.RAISE_ERROR:
                raise
            
            elif self.config.strategy == FallbackStrategy.RETURN_CACHED:
                cached = self._get_cached(cache_key) if cache_key else None
                if cached is not None:
                    self._log(f"Returning cached result for {cache_key}")
                    return cached
                # No cache, fall through to default
                return self.config.default_value
            
            elif self.config.strategy == FallbackStrategy.RETURN_DEFAULT:
                return self.config.default_value
            
            elif self.config.strategy == FallbackStrategy.RETURN_NONE:
                return None
            
            # Default fallback if strategy-specific handling didn't return
            return fallback_value
    
    def clear_cache(self, cache_key: Optional[str] = None) -> None:
        """Clear cached responses."""
        if cache_key:
            self._cache.pop(cache_key, None)
            self._log(f"Cleared cache for {cache_key}")
        else:
            self._cache.clear()
            self._log("Cleared all caches")
    
    def get_cache_status(self, cache_key: str) -> dict[str, Any]:
        """Get status of a cached item."""
        if cache_key not in self._cache:
            return {"cached": False}
        
        cached = self._cache[cache_key]
        age = time.time() - cached.cached_at
        
        return {
            "cached": True,
            "age_seconds": round(age, 2),
            "ttl_remaining": max(0, self.config.cache_ttl_seconds - age),
            "is_expired": age > self.config.cache_ttl_seconds
        }


def create_graceful_fallback(
    service_name: str,
    message: str = "Service temporarily unavailable",
    retry_after: int = 60
) -> dict[str, Any]:
    """
    Create a standard fallback response payload.
    
    Args:
        service_name: Name of the unavailable service
        message: User-friendly message
        retry_after: Suggested retry delay in seconds
        
    Returns:
        Standardized fallback response dict
    """
    return {
        "status": "unavailable",
        "service": service_name,
        "message": message,
        "retry_after": retry_after,
        "timestamp": time.time()
    }
