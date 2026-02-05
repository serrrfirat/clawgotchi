"""
Graceful Degradation Coordinator — Three-level degradation system for agent operations.

Inspired by FreightWatcher's post: "Graceful Degradation: Lessons from 50-Port Monitoring at Scale"
Chains: circuit_breaker + timeout_budget + fallback_response into unified degradation.

Degradation Levels:
- Level 1: Cache Fallback (trigger: API timeout or 5xx)
- Level 2: Reduced Scope (trigger: multiple failures)
- Level 3: Human Handoff (trigger: critical + degraded confidence)
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Dict, List
from datetime import datetime, timedelta
import json

from .circuit_breaker import CircuitBreaker, CircuitState
from .timeout_budget import TimeoutBudget, BudgetCategory
from .fallback_response import FallbackGenerator, FallbackStrategy, FallbackConfig


class DegradationLevel(Enum):
    """Three levels of graceful degradation."""
    FULL = "full"           # All features operational
    REDUCED = "reduced"     # Cache fallback, reduced scope
    MINIMAL = "minimal"    # Critical only, human handoff ready


@dataclass
class DegradationConfig:
    """Configuration for degradation behavior."""
    # Level 1: Cache Fallback
    cache_ttl_seconds: int = 300
    cache_fallback_enabled: bool = True
    
    # Level 2: Reduced Scope
    reduced_scope_ratio: float = 0.2  # Keep 20% of features
    max_consecutive_failures_for_reduced: int = 3
    
    # Level 3: Human Handoff
    handoff_enabled: bool = True
    critical_confidence_threshold: float = 0.5
    
    # State persistence
    persist_state: bool = False
    state_path: Optional[str] = None


@dataclass
class DegradationState:
    """Tracks current degradation state."""
    level: DegradationLevel = DegradationLevel.FULL
    consecutive_failures: int = 0
    last_failure_time: Optional[datetime] = None
    last_successful_operation: Optional[datetime] = None
    operation_count: int = 0
    degradation_log: List[Dict[str, Any]] = field(default_factory=list)
    
    def record_failure(self):
        self.consecutive_failures += 1
        self.last_failure_time = datetime.now()
        self.operation_count += 1
    
    def record_success(self):
        self.consecutive_failures = 0
        self.last_successful_operation = datetime.now()
        self.operation_count += 1
    
    def upgrade_level(self, reason: str):
        old_level = self.level
        self.degradation_log.append({
            "timestamp": datetime.now().isoformat(),
            "from": old_level.value,
            "to": self.level.value,
            "reason": reason
        })
    
    def downgrade_level(self, reason: str):
        old_level = self.level
        self.degradation_log.append({
            "timestamp": datetime.now().isoformat(),
            "from": old_level.value,
            "to": self.level.value,
            "reason": reason
        })


@dataclass
class DegradationContext:
    """Runtime context for degradation decisions."""
    current_level: DegradationLevel
    fallback_available: bool
    reduced_scope_available: bool
    handoff_available: bool
    confidence_score: float
    metadata: Dict[str, Any] = field(default_factory=dict)


class GracefulDegradationCoordinator:
    """
    Orchestrates graceful degradation across agent operations.
    
    Usage:
        coordinator = GracefulDegradationCoordinator()
        
        with coordinator.operation("api_call") as ctx:
            if ctx.current_level == DegradationLevel.REDUCED:
                # Use reduced scope logic
                result = fetch_critical_ports_only()
            else:
                # Full operation
                result = fetch_all_ports()
            
            if success:
                ctx.mark_success()
            else:
                ctx.mark_failure()
    """
    
    def __init__(self, config: Optional[DegradationConfig] = None):
        self.config = config or DegradationConfig()
        self.state = DegradationState()
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        self.timeout_budget = TimeoutBudget(default_budget_ms=5000)
        fallback_config = FallbackConfig(
            strategy=FallbackStrategy.RETURN_CACHED if self.config.cache_fallback_enabled 
                     else FallbackStrategy.RETURN_NONE
        )
        self.fallback_generator = FallbackGenerator(config=fallback_config)
        
        # Degradation level thresholds
        self._level_2_threshold = self.config.max_consecutive_failures_for_reduced
        self._level_3_threshold = self.config.max_consecutive_failures_for_reduced * 2
    
    def operation(self, name: str) -> 'DegradationOperation':
        """Start a degradable operation."""
        return DegradationOperation(self, name)
    
    def get_context(self) -> DegradationContext:
        """Get current degradation context."""
        # Determine current level
        if self.state.consecutive_failures >= self._level_3_threshold:
            level = DegradationLevel.MINIMAL
        elif self.state.consecutive_failures >= self._level_2_threshold:
            level = DegradationLevel.REDUCED
        else:
            level = DegradationLevel.FULL
        
        return DegradationContext(
            current_level=level,
            fallback_available=self.config.cache_fallback_enabled,
            reduced_scope_available=level in (DegradationLevel.REDUCED, DegradationLevel.MINIMAL),
            handoff_available=self.config.handoff_enabled,
            confidence_score=self._calculate_confidence(),
            metadata={
                "consecutive_failures": self.state.consecutive_failures,
                "operation_count": self.state.operation_count,
                "circuit_state": self.circuit_breaker.state.value
            }
        )
    
    def _calculate_confidence(self) -> float:
        """Calculate operation confidence score."""
        if self.state.operation_count == 0:
            return 1.0
        
        success_rate = 1 - (self.state.consecutive_failures / max(1, self.state.operation_count))
        
        # Factor in circuit breaker state
        if self.circuit_breaker.state == CircuitState.OPEN:
            success_rate *= 0.5
        
        return max(0.0, min(1.0, success_rate))
    
    def should_escalate_to_human(self) -> bool:
        """Check if operation should be escalated to human."""
        if not self.config.handoff_enabled:
            return False
        
        context = self.get_context()
        
        return (
            context.current_level == DegradationLevel.MINIMAL and
            context.confidence_score < self.config.critical_confidence_threshold
        )
    
    def get_degradation_report(self) -> Dict[str, Any]:
        """Generate a full degradation status report."""
        context = self.get_context()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "current_level": context.current_level.value,
            "confidence_score": context.confidence_score,
            "capabilities": {
                "full_operations": context.current_level == DegradationLevel.FULL,
                "cache_fallback": context.fallback_available,
                "reduced_scope": context.reduced_scope_available,
                "critical_only": context.current_level == DegradationLevel.MINIMAL,
                "human_handoff": context.handoff_available
            },
            "statistics": {
                "total_operations": self.state.operation_count,
                "consecutive_failures": self.state.consecutive_failures,
                "last_success": self.state.last_successful_operation.isoformat() if self.state.last_successful_operation else None,
                "last_failure": self.state.last_failure_time.isoformat() if self.state.last_failure_time else None
            },
            "circuit_breaker": {
                "state": self.circuit_breaker.state.value,
                "failure_count": self.circuit_breaker.failure_count
            },
            "recommendation": self._get_recommendation(context)
        }
    
    def _get_recommendation(self, context: DegradationContext) -> str:
        """Get human-readable recommendation."""
        if context.current_level == DegradationLevel.FULL:
            return "All systems operational. Proceed with normal operations."
        elif context.current_level == DegradationLevel.REDUCED:
            return f"Degraded mode active ({self._level_2_threshold}-{self._level_3_threshold} failures). Using cache fallback and reduced scope."
        else:
            recommendation = "Critical degradation. Consider human handoff."
            if self.should_escalate_to_human():
                recommendation += " ESCALATION RECOMMENDED."
            return recommendation


class DegradationOperation:
    """Context manager for a single degradable operation."""
    
    def __init__(self, coordinator: GracefulDegradationCoordinator, name: str):
        self.coordinator = coordinator
        self.name = name
        self.context: Optional[DegradationContext] = None
        self._result: Any = None
        self._error: Optional[Exception] = None
        self._marked: bool = False  # Track if already marked by user
    
    def __enter__(self) -> 'DegradationOperation':
        self.context = self.coordinator.get_context()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Skip if already marked by user (mark_success/mark_failure called)
        if self._marked:
            return False
        
        if exc_type is not None:
            # Operation raised an exception
            self.coordinator.state.record_failure()
            self.coordinator.circuit_breaker.record_failure()
            
            # Try to get fallback
            error_msg = str(exc_val) if exc_val else "Operation failed"
            self._result = self.coordinator.fallback_generator.get_with_fallback(
                service_name=self.name,
                fallback_value=error_msg
            )
            return True  # Suppress exception, return fallback
        
        # Operation succeeded
        self.coordinator.state.record_success()
        self.coordinator.circuit_breaker.record_success()
        return False
    
    @property
    def result(self) -> Any:
        """Get the operation result (or fallback)."""
        return self._result
    
    @property
    def is_fallback(self) -> bool:
        """Check if result is from fallback."""
        return self._error is not None and self._result is not None
    
    def mark_success(self):
        """Explicitly mark operation as successful."""
        self._marked = True
        self.coordinator.state.record_success()
    
    def mark_failure(self, error: Optional[Exception] = None):
        """Explicitly mark operation as failed."""
        self._marked = True
        self._error = error
        self.coordinator.state.record_failure()
        self.coordinator.circuit_breaker.record_failure()
        error_msg = str(error) if error else "Operation failed"
        self._result = self.coordinator.fallback_generator.get_with_fallback(
            service_name=self.name,
            fallback_value=error_msg
        )
    
    def get_fallback_data(self, key: str, default: Any = None) -> Any:
        """Get data from fallback response."""
        if isinstance(self._result, dict):
            return self._result.get(key, default)
        return default


def create_degradation_coordinator(
    cache_ttl: int = 300,
    reduced_scope_ratio: float = 0.2,
    handoff_enabled: bool = True
) -> GracefulDegradationCoordinator:
    """Quick factory for common configurations."""
    config = DegradationConfig(
        cache_ttl_seconds=cache_ttl,
        reduced_scope_ratio=reduced_scope_ratio,
        handoff_enabled=handoff_enabled
    )
    return GracefulDegradationCoordinator(config)


# Backwards compatibility alias
DegradationCoordinator = GracefulDegradationCoordinator
