"""
Circuit Breaker Pattern for Agent Dependencies

Prevents hammering dead services and fails gracefully when dependencies die.
Inspired by Kevin's post: "The Uncomfortable Truth About Agent Dependencies"

The circuit breaker pattern provides:
- Circuit breaker: Stop hammering a dead service. Fail fast, recover later.
- State tracking: CLOSED (healthy), OPEN (blocked), HALF_OPEN (testing recovery)
- Failure counting with configurable thresholds
- Automatic recovery after timeout
- Dependency monitoring for multiple services

Usage:
    from circuit_breaker import CircuitBreaker, circuit_breaker

    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=5)

    @circuit_breaker(cb)
    def call_external_api():
        response = requests.get("https://api.example.com/data")
        return response.json()

    try:
        result = call_external_api()
    except CircuitBreakerError:
        # Service is down, use fallback
        return get_cached_data()
"""

import time
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Callable, Optional, Any


class CircuitBreakerState(Enum):
    """Possible states of the circuit breaker."""
    CLOSED = "CLOSED"   # Normal operation, requests pass through
    OPEN = "OPEN"       # Failing fast, requests blocked
    HALF_OPEN = "HALF_OPEN"  # Testing recovery, limited requests


class CircuitBreakerError(Exception):
    """Raised when the circuit breaker is open and blocks a request."""
    
    def __init__(self, service_name: str = "CircuitBreaker", state: str = "OPEN"):
        self.service_name = service_name
        self.state = state
        message = f"{service_name} is OPEN - request blocked. Try again later."
        super().__init__(message)


@dataclass
class ServiceHealthStatus:
    """Health status report for a monitored service."""
    name: str
    state: CircuitBreakerState
    failure_count: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None


class CircuitBreaker:
    """
    Circuit breaker implementation for service dependency protection.
    
    Prevents cascading failures by stopping requests to a failing service.
    
    Args:
        failure_threshold: Number of failures before opening the circuit
        recovery_timeout: Seconds to wait before trying recovery
        name: Optional name for the circuit breaker (for debugging)
    
    State Machine:
        CLOSED -> OPEN (after failure_threshold failures)
        OPEN -> HALF_OPEN (after recovery_timeout)
        HALF_OPEN -> CLOSED (on success)
        HALF_OPEN -> OPEN (on failure)
    """
    
    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 60.0,
        name: str = "CircuitBreaker"
    ):
        if failure_threshold < 0:
            raise ValueError("failure_threshold must be non-negative")
        if recovery_timeout <= 0:
            recovery_timeout = 1.0  # Minimum sensible default
        
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self.name = name
        
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._last_success_time: Optional[float] = None
    
    @property
    def state(self) -> CircuitBreakerState:
        """Get current state, automatically transitioning if needed."""
        self._check_transition()
        return self._state
    
    @property
    def failure_count(self) -> int:
        """Number of consecutive failures."""
        return self._failure_count
    
    @property
    def last_failure_time(self) -> Optional[float]:
        """Timestamp of last recorded failure."""
        return self._last_failure_time
    
    @property
    def last_success_time(self) -> Optional[float]:
        """Timestamp of last recorded success."""
        return self._last_success_time
    
    def _check_transition(self) -> None:
        """Check if automatic state transition is needed."""
        if self._state == CircuitBreakerState.OPEN:
            if self._last_failure_time is not None:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self._recovery_timeout:
                    self._state = CircuitBreakerState.HALF_OPEN
    
    def record_failure(self) -> None:
        """
        Record a failure and potentially open the circuit.
        
        If failure count reaches threshold, circuit opens.
        """
        self._failure_count += 1
        self._last_failure_time = time.time()
        
        if self._failure_count >= self._failure_threshold:
            self._state = CircuitBreakerState.OPEN
    
    def record_success(self) -> None:
        """
        Record a success and potentially close the circuit.
        
        In HALF_OPEN state, success closes the circuit.
        In CLOSED state, resets failure count.
        """
        self._last_success_time = time.time()
        
        if self._state == CircuitBreakerState.HALF_OPEN:
            self._state = CircuitBreakerState.CLOSED
            self._failure_count = 0
        elif self._state == CircuitBreakerState.CLOSED:
            self._failure_count = 0
    
    def assert_can_proceed(self) -> None:
        """
        Assert that the circuit allows requests.
        
        Raises:
            CircuitBreakerError: If circuit is OPEN
        """
        if self._state == CircuitBreakerState.OPEN:
            raise CircuitBreakerError(self.name, self._state.value)
    
    def reset(self) -> None:
        """
        Manually reset the circuit to CLOSED state.
        """
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._last_failure_time = None
        self._last_success_time = None
    
    def get_health_status(self) -> ServiceHealthStatus:
        """
        Get current health status for monitoring.
        """
        return ServiceHealthStatus(
            name=self.name,
            state=self.state,
            failure_count=self._failure_count,
            last_failure_time=self._last_failure_time,
            last_success_time=self._last_success_time
        )
    
    def __enter__(self):
        """Context manager entry - raises if circuit is open."""
        self.assert_can_proceed()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - records success or failure."""
        if exc_type is None:
            self.record_success()
        else:
            self.record_failure()
        return False


def circuit_breaker(circuit: CircuitBreaker) -> Callable:
    """
    Decorator to wrap a function with circuit breaker protection.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            circuit.assert_can_proceed()
            try:
                result = func(*args, **kwargs)
                circuit.record_success()
                return result
            except Exception as e:
                circuit.record_failure()
                raise
        return wrapper
    return decorator


class DependencyMonitor:
    """
    Monitor multiple service dependencies with individual circuit breakers.
    """
    
    def __init__(self):
        self._dependencies: dict[str, CircuitBreaker] = {}
    
    def register(self, name: str, circuit: CircuitBreaker) -> None:
        """Register a dependency with its circuit breaker."""
        self._dependencies[name] = circuit
    
    def unregister(self, name: str) -> None:
        """Remove a dependency from monitoring."""
        del self._dependencies[name]
    
    def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker for a specific dependency."""
        return self._dependencies.get(name)
    
    def get_all_dependencies(self) -> dict[str, CircuitBreaker]:
        """Get all registered dependencies."""
        return self._dependencies.copy()
    
    def get_health_status(self, name: str) -> Optional[ServiceHealthStatus]:
        """Get health status for a specific dependency."""
        circuit = self._dependencies.get(name)
        if circuit is None:
            return None
        return circuit.get_health_status()
    
    def get_all_health(self) -> dict[str, ServiceHealthStatus]:
        """Get health status for all dependencies."""
        return {
            name: circuit.get_health_status()
            for name, circuit in self._dependencies.items()
        }
    
    def check_all(self) -> dict[str, bool]:
        """Quick health check for all dependencies."""
        return {
            name: status.state == CircuitBreakerState.CLOSED
            for name, status in self.get_all_health().items()
        }


# CLI interface
if __name__ == "__main__":
    import sys
    
    print("Circuit Breaker Pattern Demo")
    print("=" * 40)
    
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1, name="DemoAPI")
    print(f"\nInitial state: {cb.state.value}")
    
    print("\nRecording 2 failures...")
    cb.record_failure()
    print(f"State: {cb.state.value} (failures: {cb.failure_count})")
    cb.record_failure()
    print(f"State: {cb.state.value} (failures: {cb.failure_count})")
    
    print("\nTrying to proceed...")
    try:
        cb.assert_can_proceed()
        print("Request allowed!")
    except CircuitBreakerError as e:
        print(f"Blocked: {e}")
    
    print("\nWaiting for recovery timeout...")
    time.sleep(1.1)
    print(f"State after timeout: {cb.state.value}")
    
    print("\nRecording success...")
    cb.record_success()
    print(f"State after success: {cb.state.value}")
    
    print("\n" + "=" * 40)
    print("Demo complete!")
