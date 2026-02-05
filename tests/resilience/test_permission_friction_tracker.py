"""
Tests for Permission Friction Tracker
"""

import os
import json
import time
import pytest
from clawgotchi.resilience.permission_friction_tracker import (
    PermissionDecision,
    PermissionRequest,
    FrictionEvent,
    FrictionMetrics,
    PermissionFrictionTracker,
    create_friction_tracker
)


class TestPermissionRequest:
    """Tests for PermissionRequest dataclass."""
    
    def test_create_request(self):
        """Test creating a permission request."""
        req = PermissionRequest(
            permission_type="filesystem",
            requested_value="./data",
            is_default=True,
            category="storage"
        )
        
        assert req.permission_type == "filesystem"
        assert req.requested_value == "./data"
        assert req.is_default is True
        assert req.category == "storage"
    
    def test_to_dict(self):
        """Test serialization to dictionary."""
        req = PermissionRequest(
            permission_type="network",
            requested_value="api.example.com",
            is_default=False
        )
        
        data = req.to_dict()
        assert data["permission_type"] == "network"
        assert data["requested_value"] == "api.example.com"
        assert data["is_default"] is False


class TestFrictionEvent:
    """Tests for FrictionEvent dataclass."""
    
    def test_create_event(self):
        """Test creating a friction event."""
        perm = PermissionRequest("filesystem", "./data", True)
        event = FrictionEvent(
            skill_id="skill_123",
            skill_name="Test Skill",
            timestamp="2026-02-05T09:00:00",
            permission=perm,
            decision=PermissionDecision.APPROVED,
            review_time_ms=5000,
            previous_decision=None
        )
        
        assert event.skill_id == "skill_123"
        assert event.decision == PermissionDecision.APPROVED
        assert event.review_time_ms == 5000
    
    def test_to_dict(self):
        """Test serialization."""
        perm = PermissionRequest("network", "*", False)
        event = FrictionEvent(
            skill_id="skill_456",
            skill_name="Network Skill",
            timestamp="2026-02-05T09:00:00",
            permission=perm,
            decision=PermissionDecision.ESCALATED,
            review_time_ms=3000
        )
        
        data = event.to_dict()
        assert data["skill_id"] == "skill_456"
        assert data["decision"] == "escalated"
        assert data["permission"]["permission_type"] == "network"


class TestFrictionMetrics:
    """Tests for FrictionMetrics dataclass."""
    
    def test_calculate_friction_score_no_permissions(self):
        """Test friction score with no permissions."""
        metrics = FrictionMetrics(
            skill_id="test",
            total_permissions=0,
            default_permissions=0,
            escalated_permissions=0,
            denied_permissions=0,
            total_review_time_ms=0,
            average_review_time_ms=0,
            median_review_time_ms=0
        )
        
        assert metrics.calculate_friction_score() == 0.0
    
    def test_calculate_friction_score_fast_reviews(self):
        """Test friction penalty for very fast reviews."""
        metrics = FrictionMetrics(
            skill_id="test",
            total_permissions=5,
            default_permissions=5,
            escalated_permissions=0,
            denied_permissions=0,
            total_review_time_ms=1000,
            average_review_time_ms=200,
            median_review_time_ms=200
        )
        
        score = metrics.calculate_friction_score()
        assert score > 0
    
    def test_calculate_friction_score_abandonment(self):
        """Test friction score with abandonment."""
        metrics = FrictionMetrics(
            skill_id="test",
            total_permissions=3,
            default_permissions=3,
            escalated_permissions=0,
            denied_permissions=0,
            total_review_time_ms=10000,
            average_review_time_ms=3333,
            median_review_time_ms=3333,
            install_started=10,
            install_completed=2,
            install_abandoned=8
        )
        
        score = metrics.calculate_friction_score()
        assert score > 0
    
    def test_to_dict(self):
        """Test serialization."""
        metrics = FrictionMetrics(
            skill_id="test_skill",
            total_permissions=4,
            default_permissions=2,
            escalated_permissions=1,
            denied_permissions=1,
            total_review_time_ms=20000,
            average_review_time_ms=5000,
            median_review_time_ms=5000
        )
        
        data = metrics.to_dict()
        assert data["skill_id"] == "test_skill"
        assert data["permissions"]["total"] == 4
        assert data["permissions"]["escalated"] == 1
        assert "friction_score" in data


class TestPermissionFrictionTracker:
    """Tests for PermissionFrictionTracker class."""
    
    @pytest.fixture
    def tracker(self, tmp_path):
        storage_path = tmp_path / "friction_test.json"
        tracker = PermissionFrictionTracker(str(storage_path))
        yield tracker
    
    def test_start_session(self, tracker):
        """Test starting a new session."""
        tracker.start_session("test_skill", "Test Skill", 5)
        
        assert tracker.current_session is not None
        assert tracker.current_session['skill_id'] == "test_skill"
        assert tracker.current_session['permission_count'] == 5
    
    def test_record_permission_view(self, tracker):
        """Test recording permission views."""
        tracker.start_session("test_skill", "Test Skill", 2)
        
        perm = PermissionRequest("filesystem", "./data", True)
        elapsed = tracker.record_permission_view(perm)
        
        assert elapsed == 0
        assert len(tracker.current_session['permissions']) == 1
    
    def test_record_decision(self, tracker):
        """Test recording decisions."""
        tracker.start_session("test_skill", "Test Skill", 1)
        
        perm = PermissionRequest("filesystem", "./data", True)
        tracker.record_permission_view(perm)
        event = tracker.record_decision(PermissionDecision.APPROVED)
        
        assert event.decision == PermissionDecision.APPROVED
        assert len(tracker.events) == 1
    
    def test_complete_session_completed(self, tracker):
        """Test completing a session successfully."""
        tracker.start_session("test_skill", "Test Skill", 2)
        
        perm1 = PermissionRequest("filesystem", "./data", True)
        tracker.record_permission_view(perm1)
        tracker.record_decision(PermissionDecision.APPROVED)
        
        perm2 = PermissionRequest("network", "api.example.com", False)
        tracker.record_permission_view(perm2)
        tracker.record_decision(PermissionDecision.ESCALATED)
        
        metrics = tracker.complete_session('completed')
        
        assert metrics.skill_id == "test_skill"
        assert metrics.install_completed == 1
        assert metrics.install_abandoned == 0
        assert metrics.escalated_permissions == 1
    
    def test_complete_session_abandoned(self, tracker):
        """Test completing a session with abandonment."""
        tracker.start_session("test_skill", "Test Skill", 2)
        
        perm = PermissionRequest("filesystem", "./data", True)
        tracker.record_permission_view(perm)
        tracker.record_decision(PermissionDecision.APPROVED)
        
        metrics = tracker.complete_session('abandoned')
        
        assert metrics.install_abandoned == 1
        assert metrics.install_completed == 0
    
    def test_events_persistence(self, tmp_path):
        """Test that events are saved to storage."""
        storage_path = tmp_path / "persist_test.json"
        
        tracker1 = PermissionFrictionTracker(str(storage_path))
        tracker1.start_session("persist_skill", "Persist Skill", 1)
        perm = PermissionRequest("network", "*", False)
        tracker1.record_permission_view(perm)
        tracker1.record_decision(PermissionDecision.ESCALATED)
        tracker1.complete_session('completed')
        
        tracker2 = PermissionFrictionTracker(str(storage_path))
        
        assert len(tracker2.events) == 1
        assert tracker2.events[0].skill_id == "persist_skill"
    
    def test_get_skill_metrics(self, tracker):
        """Test getting metrics for a specific skill."""
        tracker.start_session("skill_a", "Skill A", 1)
        perm = PermissionRequest("filesystem", "./data", True)
        tracker.record_permission_view(perm)
        tracker.record_decision(PermissionDecision.APPROVED)
        tracker.complete_session('completed')
        
        metrics = tracker.get_skill_metrics("skill_a")
        
        assert metrics is not None
        assert metrics.skill_id == "skill_a"
        assert metrics.total_permissions == 1
    
    def test_get_skill_metrics_nonexistent(self, tracker):
        """Test getting metrics for a skill that doesn't exist."""
        metrics = tracker.get_skill_metrics("nonexistent")
        
        assert metrics is None
    
    def test_get_aggregate_metrics_empty(self, tracker):
        """Test aggregate metrics with no data."""
        data = tracker.get_aggregate_metrics()
        
        assert data["total_sessions"] == 0
    
    def test_get_aggregate_metrics_with_data(self, tracker):
        """Test aggregate metrics with events."""
        tracker.start_session("skill_1", "Skill 1", 1)
        perm = PermissionRequest("filesystem", "./data", True)
        tracker.record_permission_view(perm)
        tracker.record_decision(PermissionDecision.APPROVED)
        tracker.complete_session('completed')
        
        tracker.start_session("skill_2", "Skill 2", 1)
        perm = PermissionRequest("network", "*", False)
        tracker.record_permission_view(perm)
        tracker.record_decision(PermissionDecision.ESCALATED)
        tracker.complete_session('completed')
        
        data = tracker.get_aggregate_metrics()
        
        assert data["total_skills"] == 2
        assert data["total_permission_reviews"] == 2
        assert data["approval_rate"] == 0.5
        assert data["escalation_rate"] == 0.5
    
    def test_generate_friction_report(self, tracker):
        """Test generating a friction report."""
        tracker.start_session("test_skill", "Test Skill", 2)
        perm = PermissionRequest("filesystem", "./data", True)
        tracker.record_permission_view(perm)
        tracker.record_decision(PermissionDecision.APPROVED)
        tracker.complete_session('completed')
        
        report = tracker.generate_friction_report("test_skill")
        
        assert "test_skill" in report
        assert "Friction Report" in report
    
    def test_generate_aggregate_report(self, tracker):
        """Test generating aggregate report."""
        tracker.start_session("skill_1", "Skill 1", 1)
        perm = PermissionRequest("filesystem", "./data", True)
        tracker.record_permission_view(perm)
        tracker.record_decision(PermissionDecision.APPROVED)
        tracker.complete_session('completed')
        
        report = tracker.generate_friction_report()
        
        assert "Aggregate" in report
    
    def test_fast_review_detection(self, tracker):
        """Test detection of suspiciously fast reviews."""
        tracker.start_session("fast_skill", "Fast Skill", 3)
        
        for i in range(3):
            perm = PermissionRequest("filesystem", f"./data{i}", True)
            tracker.record_permission_view(perm)
            tracker.record_decision(PermissionDecision.APPROVED)
        
        metrics = tracker.complete_session('completed')
        
        assert metrics.average_review_time_ms < 1000
    
    def test_previous_decision_tracking(self, tracker):
        """Test tracking previous decisions on re-install."""
        tracker.start_session("reinstall_skill", "Reinstall Skill", 1)
        perm = PermissionRequest("filesystem", "./data", False)
        tracker.record_permission_view(perm)
        tracker.record_decision(PermissionDecision.ESCALATED, previous_decision=None)
        tracker.complete_session('completed')
        
        tracker.start_session("reinstall_skill", "Reinstall Skill", 1)
        perm = PermissionRequest("filesystem", "./data", False)
        tracker.record_permission_view(perm)
        event = tracker.record_decision(PermissionDecision.APPROVED, previous_decision="escalated")
        
        assert event.previous_decision == "escalated"


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    def test_create_friction_tracker(self, tmp_path):
        """Test create_friction_tracker convenience function."""
        storage_path = tmp_path / "convenience_test.json"
        tracker = create_friction_tracker(str(storage_path))
        
        assert isinstance(tracker, PermissionFrictionTracker)
        assert tracker.storage_path == str(storage_path)


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_record_decision_without_session(self, tmp_path):
        """Test that recording without session raises error."""
        tracker = PermissionFrictionTracker(str(tmp_path / "test.json"))
        
        with pytest.raises(RuntimeError, match="No active session"):
            tracker.record_decision(PermissionDecision.APPROVED)
    
    def test_complete_session_without_session(self, tmp_path):
        """Test that completing without session raises error."""
        tracker = PermissionFrictionTracker(str(tmp_path / "test.json"))
        
        with pytest.raises(RuntimeError, match="No active session"):
            tracker.complete_session('completed')
    
    def test_empty_events_list(self, tmp_path):
        """Test tracker with empty events list."""
        tracker = PermissionFrictionTracker(str(tmp_path / "empty.json"))
        
        assert len(tracker.events) == 0
        assert tracker.get_skill_metrics("anything") is None


@pytest.fixture
def tracker(tmp_path):
    return PermissionFrictionTracker(str(tmp_path / "friction_events.json"))
