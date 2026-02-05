"""
Tests for Graceful Degradation Coordinator.
Inspired by FreightWatcher's "Graceful Degradation: Lessons from 50-Port Monitoring at Scale"
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from clawgotchi.resilience.degradation_coordinator import (
    DegradationLevel,
    DegradationConfig,
    DegradationState,
    DegradationContext,
    GracefulDegradationCoordinator,
    DegradationOperation,
    create_degradation_coordinator,
)


class TestDegradationState:
    """Tests for DegradationState tracking."""
    
    def test_initial_state_is_full(self):
        state = DegradationState()
        assert state.level == DegradationLevel.FULL
        assert state.consecutive_failures == 0
        assert state.operation_count == 0
    
    def test_record_failure_increments_counter(self):
        state = DegradationState()
        state.record_failure()
        assert state.consecutive_failures == 1
        state.record_failure()
        assert state.consecutive_failures == 2
    
    def test_record_success_resets_counter(self):
        state = DegradationState()
        state.record_failure()
        state.record_failure()
        state.record_success()
        assert state.consecutive_failures == 0
    
    def test_operation_count_increments(self):
        state = DegradationState()
        state.record_failure()
        state.record_success()
        assert state.operation_count == 2
    
    def test_degradation_log_tracks_changes(self):
        state = DegradationState()
        state.upgrade_level("test reason")
        state.downgrade_level("recovery")
        
        assert len(state.degradation_log) == 2
        assert state.degradation_log[0]["reason"] == "test reason"
        assert state.degradation_log[1]["reason"] == "recovery"
    
    def test_timestamps_are_recorded(self):
        state = DegradationState()
        state.record_failure()
        assert state.last_failure_time is not None
        assert isinstance(state.last_failure_time, datetime)


class TestDegradationConfig:
    """Tests for DegradationConfig."""
    
    def test_default_config_values(self):
        config = DegradationConfig()
        assert config.cache_ttl_seconds == 300
        assert config.reduced_scope_ratio == 0.2
        assert config.handoff_enabled is True
    
    def test_custom_config(self):
        config = DegradationConfig(
            cache_ttl_seconds=600,
            reduced_scope_ratio=0.1,
            handoff_enabled=False
        )
        assert config.cache_ttl_seconds == 600
        assert config.reduced_scope_ratio == 0.1
        assert config.handoff_enabled is False


class TestGracefulDegradationCoordinator:
    """Tests for the main coordinator."""
    
    def test_initial_state_is_full(self):
        coordinator = GracefulDegradationCoordinator()
        ctx = coordinator.get_context()
        assert ctx.current_level == DegradationLevel.FULL
    
    def test_single_failure_stays_full(self):
        coordinator = GracefulDegradationCoordinator()
        state = coordinator.state
        state.record_failure()  # 1 failure
        
        ctx = coordinator.get_context()
        assert ctx.current_level == DegradationLevel.FULL
    
    def test_threshold_2_triggers_reduced(self):
        coordinator = GracefulDegradationCoordinator()
        for _ in range(3):  # Default threshold is 3
            coordinator.state.record_failure()
        
        ctx = coordinator.get_context()
        assert ctx.current_level == DegradationLevel.REDUCED
    
    def test_threshold_3_triggers_minimal(self):
        coordinator = GracefulDegradationCoordinator()
        for _ in range(6):  # 2x threshold for MINIMAL
            coordinator.state.record_failure()
        
        ctx = coordinator.get_context()
        assert ctx.current_level == DegradationLevel.MINIMAL
    
    def test_success_downgrades_to_full(self):
        coordinator = GracefulDegradationCoordinator()
        for _ in range(4):  # Push to REDUCED
            coordinator.state.record_failure()
        
        coordinator.state.record_success()  # Should reset
        
        ctx = coordinator.get_context()
        assert ctx.current_level == DegradationLevel.FULL
    
    def test_confidence_score_starts_at_one(self):
        coordinator = GracefulDegradationCoordinator()
        ctx = coordinator.get_context()
        assert ctx.confidence_score == 1.0
    
    def test_confidence_decreases_with_failures(self):
        coordinator = GracefulDegradationCoordinator()
        for _ in range(3):
            coordinator.state.record_failure()
        
        ctx = coordinator.get_context()
        assert ctx.confidence_score < 1.0
    
    def test_capabilities_reflect_level(self):
        coordinator = GracefulDegradationCoordinator()
        ctx = coordinator.get_context()
        
        assert ctx.fallback_available is True
        assert ctx.reduced_scope_available is False
        assert ctx.handoff_available is True
    
    def test_should_escalate_to_human(self):
        coordinator = GracefulDegradationCoordinator(
            DegradationConfig(handoff_enabled=True)
        )
        
        # Push to minimal with low confidence
        for _ in range(6):
            coordinator.state.record_failure()
        
        assert coordinator.should_escalate_to_human() is True
    
    def test_handoff_disabled_prevents_escalation(self):
        coordinator = GracefulDegradationCoordinator(
            DegradationConfig(handoff_enabled=False)
        )
        
        for _ in range(6):
            coordinator.state.record_failure()
        
        assert coordinator.should_escalate_to_human() is False
    
    def test_degradation_report_structure(self):
        coordinator = GracefulDegradationCoordinator()
        report = coordinator.get_degradation_report()
        
        assert "timestamp" in report
        assert "current_level" in report
        assert "confidence_score" in report
        assert "capabilities" in report
        assert "statistics" in report
        assert "recommendation" in report
    
    def test_recommendation_text_changes_with_level(self):
        coordinator = GracefulDegradationCoordinator()
        
        report_full = coordinator.get_degradation_report()
        assert "All systems operational" in report_full["recommendation"]
        
        for _ in range(4):
            coordinator.state.record_failure()
        
        report_reduced = coordinator.get_degradation_report()
        assert "Degraded mode" in report_reduced["recommendation"]
        
        for _ in range(4):
            coordinator.state.record_failure()
        
        report_minimal = coordinator.get_degradation_report()
        assert "Critical degradation" in report_minimal["recommendation"]
    
    def test_factory_function(self):
        coordinator = create_degradation_coordinator(
            cache_ttl=500,
            reduced_scope_ratio=0.15,
            handoff_enabled=False
        )
        
        assert coordinator.config.cache_ttl_seconds == 500
        assert coordinator.config.reduced_scope_ratio == 0.15
        assert coordinator.config.handoff_enabled is False


class TestDegradationOperation:
    """Tests for DegradationOperation context manager."""
    
    def test_successful_operation(self):
        coordinator = GracefulDegradationCoordinator()
        
        with coordinator.operation("test_op") as op:
            op.mark_success()
        
        assert coordinator.state.consecutive_failures == 0
        assert coordinator.state.operation_count == 1
    
    def test_failed_operation_with_fallback(self):
        coordinator = GracefulDegradationCoordinator()
        
        with coordinator.operation("test_op") as op:
            op.mark_failure(Exception("test error"))
        
        assert coordinator.state.consecutive_failures == 1
        assert op.result is not None  # Fallback returned
    
    def test_exception_suppressed_with_fallback(self):
        coordinator = GracefulDegradationCoordinator()
        
        with coordinator.operation("test_op") as op:
            raise ValueError("simulated failure")
        
        # Should not raise - fallback handled it
        assert op.result is not None
    
    def test_operation_context_provides_level(self):
        coordinator = GracefulDegradationCoordinator()
        
        with coordinator.operation("test_op") as op:
            assert op.context is not None
            assert op.context.current_level == DegradationLevel.FULL
    
    def test_multiple_operations_track_correctly(self):
        coordinator = GracefulDegradationCoordinator()
        
        with coordinator.operation("op1") as op:
            op.mark_success()
        with coordinator.operation("op2") as op:
            op.mark_failure()
        with coordinator.operation("op3") as op:
            op.mark_failure()
        
        assert coordinator.state.operation_count == 3
        assert coordinator.state.consecutive_failures == 2
    
    def test_is_fallback_detection(self):
        coordinator = GracefulDegradationCoordinator()
        
        with coordinator.operation("test") as op:
            op.mark_failure(Exception("error"))
        
        assert op.is_fallback is True
        
        with coordinator.operation("test") as op:
            op.mark_success()
        
        assert op.is_fallback is False
    
    def test_get_fallback_data(self):
        coordinator = GracefulDegradationCoordinator()
        
        with coordinator.operation("test") as op:
            op.mark_failure(Exception("error"))
        
        data = op.get_fallback_data("key", "default")
        assert data == "default"


class TestDegradationLevel:
    """Tests for DegradationLevel enum."""
    
    def test_all_levels_exist(self):
        assert DegradationLevel.FULL.value == "full"
        assert DegradationLevel.REDUCED.value == "reduced"
        assert DegradationLevel.MINIMAL.value == "minimal"


class TestIntegration:
    """Integration tests for the complete degradation system."""
    
    def test_full_lifecycle_with_circuit_breaker(self):
        """Test full lifecycle: full → reduced → minimal → recovery."""
        coordinator = GracefulDegradationCoordinator()
        
        # Start at full
        assert coordinator.get_context().current_level == DegradationLevel.FULL
        
        # Accumulate failures
        for _ in range(3):
            coordinator.state.record_failure()
        assert coordinator.get_context().current_level == DegradationLevel.REDUCED
        
        for _ in range(3):
            coordinator.state.record_failure()
        assert coordinator.get_context().current_level == DegradationLevel.MINIMAL
        
        # Recovery
        coordinator.state.record_success()
        assert coordinator.get_context().current_level == DegradationLevel.FULL
    
    def test_metadata_in_context(self):
        coordinator = GracefulDegradationCoordinator()
        coordinator.state.record_failure()
        
        ctx = coordinator.get_context()
        assert "consecutive_failures" in ctx.metadata
        assert "operation_count" in ctx.metadata
        assert "circuit_state" in ctx.metadata
    
    def test_statistics_in_report(self):
        coordinator = GracefulDegradationCoordinator()
        
        for _ in range(5):
            coordinator.state.record_failure()
        
        report = coordinator.get_degradation_report()
        assert report["statistics"]["total_operations"] == 5
        assert report["statistics"]["consecutive_failures"] == 5
    
    def test_backwards_compatibility_alias(self):
        """Ensure DegradationCoordinator alias works."""
        from clawgotchi.resilience.degradation_coordinator import DegradationCoordinator
        assert DegradationCoordinator is GracefulDegradationCoordinator
