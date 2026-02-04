"""
Tests for Circuit Breaker Pattern

Prevents hammering dead services and fails gracefully when dependencies die.
Inspired by Kevin's post on agent dependencies.
"""

import pytest
import time
from circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerState,
    circuit_breaker,
    DependencyMonitor,
    ServiceHealthStatus
)


class TestCircuitBreakerStates:
    """Test state transitions of the circuit breaker."""
    
    def test_initial_state_is_closed(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
        assert cb.state == CircuitBreakerState.CLOSED
    
    def test_transitions_to_open_on_failure_threshold(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        
        # First failure
        cb.record_failure()
        assert cb.state == CircuitBreakerState.CLOSED
        
        # Second failure - should open
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
    
    def test_transitions_to_half_open_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        
        # Trigger failure to open
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        
        # Wait for recovery timeout
        time.sleep(0.02)
        
        # Should transition to half-open on next call
        assert cb.state == CircuitBreakerState.HALF_OPEN
    
    def test_success_in_half_open_closes_circuit(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        
        # Trigger failure
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        
        # Wait and transition to half-open
        time.sleep(0.02)
        
        # Record success should close
        cb.record_success()
        assert cb.state == CircuitBreakerState.CLOSED
    
    def test_failure_in_half_open_reopens_circuit(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        
        # Trigger failure and wait
        cb.record_failure()
        time.sleep(0.02)
        
        # Record success then failure
        cb.record_success()  # closes
        cb.record_failure()  # opens again
        assert cb.state == CircuitBreakerState.OPEN


class TestCircuitBreakerFailureTracking:
    """Test failure and success tracking."""
    
    def test_failure_count(self):
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=1)
        
        for i in range(3):
            cb.record_failure()
            assert cb.failure_count == i + 1
    
    def test_failure_count_resets_on_success(self):
        cb = CircuitBreaker(failure_threshold=5, recovery_timeout=1)
        
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.failure_count == 3
        
        cb.record_success()
        assert cb.failure_count == 0
    
    def test_last_failure_time(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        
        before = time.time()
        cb.record_failure()
        after = time.time()
        
        assert before <= cb.last_failure_time <= after
    
    def test_last_success_time(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        
        before = time.time()
        cb.record_success()
        after = time.time()
        
        assert before <= cb.last_success_time <= after


class TestCircuitBreakerError:
    """Test custom exception."""
    
    def test_error_message_contains_service_name(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
        cb.record_failure()  # opens
        
        with pytest.raises(CircuitBreakerError) as exc_info:
            cb.assert_can_proceed()
        
        assert "CircuitBreaker" in str(exc_info.value)
        assert "OPEN" in str(exc_info.value)
    
    def test_error_inherits_from_exception(self):
        error = CircuitBreakerError("Test message")
        assert isinstance(error, Exception)


class TestCircuitBreakerDecorator:
    """Test the decorator functionality."""
    
    def test_decorator_allows_success(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
        
        @circuit_breaker(cb)
        def successful_func():
            return "success"
        
        result = successful_func()
        assert result == "success"
        assert cb.state == CircuitBreakerState.CLOSED
    
    def test_decorator_blocks_when_open(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
        
        @circuit_breaker(cb)
        def failing_func():
            raise ConnectionError("Service down")
        
        # First call fails and opens circuit
        with pytest.raises(ConnectionError):
            failing_func()
        
        assert cb.state == CircuitBreakerState.OPEN
        
        # Second call should raise CircuitBreakerError
        with pytest.raises(CircuitBreakerError):
            failing_func()
    
    def test_decorator_recovers_after_timeout(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)
        
        @circuit_breaker(cb)
        def sometimes_works():
            return "works"
        
        # Trigger failure
        with pytest.raises(ConnectionError):
            sometimes_works()
        
        # Wait for timeout
        time.sleep(0.02)
        
        # Should work again (half-open state allows through)
        result = sometimes_works()
        assert result == "works"


class TestDependencyMonitor:
    """Test the dependency monitoring functionality."""
    
    def test_monitor_initializes_empty(self):
        monitor = DependencyMonitor()
        assert monitor.get_all_dependencies() == {}
    
    def test_register_dependency(self):
        monitor = DependencyMonitor()
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        
        monitor.register("api_service", cb)
        deps = monitor.get_all_dependencies()
        
        assert "api_service" in deps
        assert deps["api_service"]["state"] == "CLOSED"
    
    def test_get_health_status(self):
        monitor = DependencyMonitor()
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        monitor.register("api", cb)
        
        status = monitor.get_health_status("api")
        
        assert status["name"] == "api"
        assert status["state"] == "CLOSED"
        assert status["healthy"] is True
    
    def test_get_health_status_unhealthy(self):
        monitor = DependencyMonitor()
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
        monitor.register("api", cb)
        cb.record_failure()
        
        status = monitor.get_health_status("api")
        
        assert status["healthy"] is False
    
    def test_unregister_dependency(self):
        monitor = DependencyMonitor()
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=1)
        monitor.register("api", cb)
        
        monitor.unregister("api")
        
        assert "api" not in monitor.get_all_dependencies()
    
    def test_get_all_health(self):
        monitor = DependencyMonitor()
        
        cb1 = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
        cb2 = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
        
        monitor.register("service1", cb1)
        monitor.register("service2", cb2)
        cb1.record_failure()
        
        all_health = monitor.get_all_health()
        
        assert len(all_health) == 2
        assert all_health["service1"]["healthy"] is False
        assert all_health["service2"]["healthy"] is True


class TestServiceHealthStatus:
    """Test the health status dataclass."""
    
    def test_health_status_fields(self):
        status = ServiceHealthStatus(
            name="test_service",
            state=CircuitBreakerState.OPEN,
            failure_count=5,
            last_failure_time=1234567890.0,
            last_success_time=1234567880.0
        )
        
        assert status.name == "test_service"
        assert status.state == CircuitBreakerState.OPEN
        assert status.failure_count == 5


class TestEdgeCases:
    """Test edge cases and unusual inputs."""
    
    def test_zero_failure_threshold_opens_immediately(self):
        cb = CircuitBreaker(failure_threshold=0, recovery_timeout=1)
        
        # Should be open immediately
        assert cb.state == CircuitBreakerState.OPEN
    
    def test_reset_method(self):
        cb = CircuitBreaker(failure_threshold=1, recovery_timeout=1)
        cb.record_failure()
        assert cb.state == CircuitBreakerState.OPEN
        
        cb.reset()
        assert cb.state == CircuitBreakerState.CLOSED
        assert cb.failure_count == 0


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
