"""Circuit Breaker pattern implementation for Clawgotchi resilience.

Prevents cascading failures by detecting when a service is failing
and temporarily stopping requests to allow recovery.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Callable, Any
from datetime import datetime, timedelta
import threading


class CircuitState(Enum):
    """Three states of a circuit breaker."""
    CLOSED = "closed"   # Normal operation
    OPEN = "open"       # Failing, reject all requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5          # Failures before opening
    recovery_timeout_seconds: int = 60  # Time before trying again
    success_threshold: int = 3          # Successes needed in half-open to close
    name: str = "default"


class CircuitBreaker:
    """
    Circuit breaker that prevents cascading failures.
    
    Usage:
        breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        try:
            with breaker:
                return call_external_service()
        except ServiceUnavailable:
            return fallback_response()
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        success_threshold: int = 3,
        name: str = "default"
    ):
        self.config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            recovery_timeout_seconds=recovery_timeout,
            success_threshold=success_threshold,
            name=name
        )
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self._lock = threading.Lock()
    
    def __enter__(self):
        if self.state == CircuitState.OPEN:
            # Check if we should try half-open
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                raise CircuitOpenError(f"Circuit {self.config.name} is OPEN")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            # Success - record it
            self.record_success()
        else:
            # Failure - record it
            self.record_failure()
        return False  # Don't suppress exceptions
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try reset."""
        if self.last_failure_time is None:
            return True
        elapsed = datetime.now() - self.last_failure_time
        return elapsed >= timedelta(seconds=self.config.recovery_timeout_seconds)
    
    def record_success(self):
        """Record a successful operation."""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
    
    def record_failure(self):
        """Record a failed operation."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            if self.state == CircuitState.HALF_OPEN:
                # Failed during test - go back to open
                self.state = CircuitState.OPEN
            elif self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
    
    def reset(self):
        """Reset circuit to closed state."""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
    
    def get_state(self) -> dict:
        """Get current state for monitoring."""
        return {
            "name": self.config.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": self.last_failure_time.isoformat() if self.last_failure_time else None
        }


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


def create_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout_seconds: int = 60
) -> CircuitBreaker:
    """Factory function to create a configured circuit breaker."""
    return CircuitBreaker(
        failure_threshold=failure_threshold,
        recovery_timeout_seconds=recovery_timeout_seconds,
        name=name
    )
