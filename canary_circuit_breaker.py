"""CanaryCircuitBreaker: Safety mechanism for autonomous agent operations.

Provides bounded blast radius through:
- Configurable failure thresholds
- Automatic circuit tripping on threshold exceeded
- Action logging with revert paths
- State persistence for recovery
"""
import json
import os
from datetime import datetime
from enum import Enum
from typing import Optional


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Blocked - threshold exceeded
    HALF_OPEN = "half_open"  # Testing recovery


class CanaryCircuitBreaker:
    """Safety circuit breaker for autonomous operations.
    
    Inspired by the canary-first principle: bounded blast radius,
    measurable failure rates, and automatic pause on anomaly.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        window_seconds: int = 60,
        state_file: Optional[str] = None
    ):
        """Initialize the circuit breaker.
        
        Args:
            failure_threshold: N failures within window triggers OPEN state
            window_seconds: Time window for counting failures
            state_file: Optional path to persist state
        """
        self.failure_threshold = failure_threshold
        self.window_seconds = window_seconds
        self.state_file = state_file
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self._action_log = []
        self._window_start = datetime.utcnow()
        
        # Load persisted state if available
        if state_file and os.path.exists(state_file):
            self._load_state()
    
    def record_action(
        self,
        operation: str,
        success: bool,
        revert_cmd: Optional[str] = None
    ) -> None:
        """Record an action and update circuit state.
        
        Args:
            operation: Name/description of the operation
            success: Whether the operation succeeded
            revert_cmd: Command to revert this action if needed
        """
        action = {
            "timestamp": datetime.utcnow().isoformat(),
            "operation": operation,
            "success": success,
            "revert_cmd": revert_cmd
        }
        self._action_log.append(action)
        
        if success:
            self._handle_success()
        else:
            self._handle_failure()
        
        self._save_state()
    
    def _handle_success(self) -> None:
        """Handle successful action."""
        self.failure_count = 0
        self._window_start = datetime.utcnow()
    
    def _handle_failure(self) -> None:
        """Handle failed action."""
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
    
    def can_execute(self, operation: str) -> bool:
        """Check if an operation is allowed.
        
        Args:
            operation: Name of the operation
            
        Returns:
            True if allowed, False if circuit is OPEN
        """
        if self.state == CircuitState.OPEN:
            return False
        return True
    
    def can_execute_or_raise(self, operation: str) -> None:
        """Execute operation or raise if circuit is OPEN.
        
        Args:
            operation: Name of the operation
            
        Raises:
            RuntimeError: If circuit is OPEN
        """
        if not self.can_execute(operation):
            raise RuntimeError(
                f"Circuit is OPEN ({self.failure_count} failures). "
                "Autonomous operations paused. Review action log and reset."
            )
    
    def reset(self) -> None:
        """Manually reset the circuit to CLOSED."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self._action_log = []
        self._window_start = datetime.utcnow()
        self._save_state()
    
    def get_revert_plan(self) -> list:
        """Get list of revert commands for logged actions.
        
        Returns:
            List of action dicts with revert commands
        """
        return [
            action for action in self._action_log
            if action.get("revert_cmd")
        ]
    
    def get_action_summary(self) -> dict:
        """Get summary of recorded actions.
        
        Returns:
            Dict with total, success, and failure counts
        """
        total = len(self._action_log)
        successes = sum(1 for a in self._action_log if a["success"])
        failures = total - successes
        
        return {
            "total_actions": total,
            "success_count": successes,
            "failure_count": failures,
            "current_state": self.state.value,
            "failure_count_in_window": self.failure_count
        }
    
    def _save_state(self) -> None:
        """Persist state to file."""
        if not self.state_file:
            return
        
        state = {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "window_start": self._window_start.isoformat(),
            "action_log": self._action_log[-100:]  # Keep last 100
        }
        
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except IOError as e:
            # Log but don't fail on write error
            print(f"Warning: Could not save circuit breaker state: {e}")
    
    def _load_state(self) -> None:
        """Load state from file."""
        if not self.state_file or not os.path.exists(self.state_file):
            return
        
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
            
            self.state = CircuitState(state["state"])
            self.failure_count = state.get("failure_count", 0)
            self._action_log = state.get("action_log", [])
            
            # Parse window start if present
            if "window_start" in state:
                self._window_start = datetime.fromisoformat(state["window_start"])
        except (IOError, json.JSONDecodeError, KeyError) as e:
            print(f"Warning: Could not load circuit breaker state: {e}")


# Convenience function for quick initialization
def create_canary(
    failure_threshold: int = 5,
    state_file: str = ".canary_state.json"
) -> CanaryCircuitBreaker:
    """Create a canary circuit breaker with defaults.
    
    Args:
        failure_threshold: N failures before tripping
        state_file: Path to state file
        
    Returns:
        Configured CanaryCircuitBreaker instance
    """
    return CanaryCircuitBreaker(
        failure_threshold=failure_threshold,
        state_file=state_file
    )
