"""Test-driven tests for CanaryCircuitBreaker."""
import pytest
import json
import os
import time
from canary_circuit_breaker import CanaryCircuitBreaker, CircuitState


class TestCircuitStateEnum:
    """Test CircuitState enum values."""
    def test_closed_state_exists(self):
        assert CircuitState.CLOSED.value == "closed"
    
    def test_open_state_exists(self):
        assert CircuitState.OPEN.value == "open"
    
    def test_half_open_state_exists(self):
        assert CircuitState.HALF_OPEN.value == "half_open"


class TestCanaryCircuitBreakerInit:
    """Test CanaryCircuitBreaker initialization."""
    
    def test_default_initialization(self):
        breaker = CanaryCircuitBreaker()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.failure_threshold == 5
        assert breaker.window_seconds == 60
        assert breaker._action_log == []
    
    def test_custom_failure_threshold(self):
        breaker = CanaryCircuitBreaker(failure_threshold=3)
        assert breaker.failure_threshold == 3
    
    def test_custom_window_seconds(self):
        breaker = CanaryCircuitBreaker(window_seconds=30)
        assert breaker.window_seconds == 30
    
    def test_persistent_state(self, tmp_path):
        state_file = tmp_path / "breaker_state.json"
        breaker = CanaryCircuitBreaker(state_file=str(state_file))
        assert breaker.state_file == str(state_file)


class TestRecordAction:
    """Test action recording."""
    
    def test_record_safe_action(self, tmp_path):
        state_file = tmp_path / "breaker_state.json"
        breaker = CanaryCircuitBreaker(state_file=str(state_file))
        breaker.record_action("safe_operation", success=True)
        assert len(breaker._action_log) == 1
        assert breaker._action_log[0]["operation"] == "safe_operation"
        assert breaker._action_log[0]["success"] is True
    
    def test_record_failure_action(self, tmp_path):
        state_file = tmp_path / "breaker_state.json"
        breaker = CanaryCircuitBreaker(state_file=str(state_file))
        breaker.record_action("failing_operation", success=False)
        assert breaker.failure_count == 1
    
    def test_record_multiple_actions(self, tmp_path):
        state_file = tmp_path / "breaker_state.json"
        breaker = CanaryCircuitBreaker(state_file=str(state_file))
        breaker.record_action("op1", success=True)
        breaker.record_action("op2", success=True)
        breaker.record_action("op3", success=False)
        assert len(breaker._action_log) == 3
        assert breaker.failure_count == 1


class TestCheckAndTrip:
    """Test circuit breaker tripping logic."""
    
    def test_breaker_trips_at_threshold(self, tmp_path):
        state_file = tmp_path / "breaker_state.json"
        breaker = CanaryCircuitBreaker(
            state_file=str(state_file),
            failure_threshold=3
        )
        breaker.record_action("op1", success=False)
        breaker.record_action("op2", success=False)
        breaker.record_action("op3", success=False)
        assert breaker.state == CircuitState.OPEN
    
    def test_breaker_stays_closed_below_threshold(self, tmp_path):
        state_file = tmp_path / "breaker_state.json"
        breaker = CanaryCircuitBreaker(
            state_file=str(state_file),
            failure_threshold=3
        )
        breaker.record_action("op1", success=False)
        breaker.record_action("op2", success=False)
        assert breaker.state == CircuitState.CLOSED
    
    def test_successful_action_resets_count(self, tmp_path):
        state_file = tmp_path / "breaker_state.json"
        breaker = CanaryCircuitBreaker(
            state_file=str(state_file),
            failure_threshold=3
        )
        breaker.record_action("op1", success=False)
        breaker.record_action("op2", success=False)
        breaker.record_action("op3", success=True)
        assert breaker.failure_count == 0
    
    def test_operations_blocked_when_open(self, tmp_path):
        state_file = tmp_path / "breaker_state.json"
        breaker = CanaryCircuitBreaker(
            state_file=str(state_file),
            failure_threshold=1
        )
        breaker.record_action("fail", success=False)
        assert breaker.state == CircuitState.OPEN
        with pytest.raises(RuntimeError, match="Circuit is OPEN"):
            breaker.can_execute_or_raise("dangerous_op")


class TestPersistence:
    """Test state persistence."""
    
    def test_save_and_restore_state(self, tmp_path):
        state_file = tmp_path / "breaker_state.json"
        breaker1 = CanaryCircuitBreaker(state_file=str(state_file))
        breaker1.record_action("op1", success=False)
        breaker1.record_action("op2", success=False)
        
        breaker2 = CanaryCircuitBreaker(state_file=str(state_file))
        assert breaker2.failure_count == 2
    
    def test_restore_open_state(self, tmp_path):
        state_file = tmp_path / "breaker_state.json"
        breaker1 = CanaryCircuitBreaker(
            state_file=str(state_file),
            failure_threshold=2
        )
        breaker1.record_action("op1", success=False)
        breaker1.record_action("op2", success=False)
        
        breaker2 = CanaryCircuitBreaker(state_file=str(state_file))
        assert breaker2.state == CircuitState.OPEN


class TestRevertPath:
    """Test revert path generation."""
    
    def test_generate_revert_path(self, tmp_path):
        state_file = tmp_path / "breaker_state.json"
        breaker = CanaryCircuitBreaker(state_file=str(state_file))
        breaker.record_action("create_file", success=True, revert_cmd="rm test.txt")
        revert = breaker.get_revert_plan()
        assert len(revert) == 1
        assert revert[0]["revert_cmd"] == "rm test.txt"
    
    def test_get_action_summary(self, tmp_path):
        state_file = tmp_path / "breaker_state.json"
        breaker = CanaryCircuitBreaker(state_file=str(state_file))
        breaker.record_action("op1", success=True)
        breaker.record_action("op2", success=False)
        summary = breaker.get_action_summary()
        assert summary["total_actions"] == 2
        assert summary["success_count"] == 1
        assert summary["failure_count"] == 1


class TestCanExecute:
    """Test can_execute permission."""
    
    def test_allowed_when_closed(self, tmp_path):
        state_file = tmp_path / "breaker_state.json"
        breaker = CanaryCircuitBreaker(state_file=str(state_file))
        assert breaker.can_execute("any_op") is True
    
    def test_denied_when_open(self, tmp_path):
        state_file = tmp_path / "breaker_state.json"
        breaker = CanaryCircuitBreaker(
            state_file=str(state_file),
            failure_threshold=1
        )
        breaker.record_action("fail", success=False)
        assert breaker.can_execute("any_op") is False


class TestReset:
    """Test reset functionality."""
    
    def test_manual_reset(self, tmp_path):
        state_file = tmp_path / "breaker_state.json"
        breaker = CanaryCircuitBreaker(
            state_file=str(state_file),
            failure_threshold=1
        )
        breaker.record_action("fail", success=False)
        assert breaker.state == CircuitState.OPEN
        breaker.reset()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
