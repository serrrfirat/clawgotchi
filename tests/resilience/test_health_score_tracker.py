"""Tests for Health Score Tracker."""
import pytest
import json
import os
from datetime import datetime, timedelta

from clawgotchi.resilience.health_score_tracker import (
    HealthScoreTracker,
    HealthEvent,
    ScoreCategory,
    load_health_history,
    save_health_history
)


class TestHealthScoreTracker:
    """Test HealthScoreTracker functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.test_db_path = "/tmp/test_health_tracker.json"
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
        self.tracker = HealthScoreTracker(db_path=self.test_db_path)
    
    def teardown_method(self):
        """Clean up test files."""
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)
    
    def test_record_health_event(self):
        """Test recording a health event."""
        event = self.tracker.record_health_event(
            category=ScoreCategory.RESILIENCE,
            score=85,
            component="circuit_breaker",
            details={"failures": 0}
        )
        assert event.id is not None
        assert event.category == ScoreCategory.RESILIENCE
        assert event.score == 85
        assert event.component == "circuit_breaker"
    
    def test_get_current_score(self):
        """Test getting current health score."""
        # Record some events
        self.tracker.record_health_event(ScoreCategory.RESILIENCE, 90, "cb1")
        self.tracker.record_health_event(ScoreCategory.MEMORY, 80, "mem1")
        self.tracker.record_health_event(ScoreCategory.SECURITY, 95, "sec1")
        
        current = self.tracker.get_current_score()
        assert current.total_score == 88  # (90+80+95)/3
        assert len(current.category_scores) == 3
    
    def test_get_score_trend(self):
        """Test score trend analysis over time."""
        # Record events at different times
        base_time = datetime.now()
        
        # Old low score
        old_event = HealthEvent(
            id="old1",
            timestamp=base_time - timedelta(hours=12),
            category=ScoreCategory.RESILIENCE,
            score=60,
            component="test",
            details={}
        )
        
        # Recent high score
        new_event = HealthEvent(
            id="new1",
            timestamp=base_time - timedelta(minutes=30),
            category=ScoreCategory.RESILIENCE,
            score=90,
            component="test",
            details={}
        )
        
        history = [old_event, new_event]
        trend = self.tracker._calculate_trend(history)
        assert trend.direction == "improving"
        assert trend.change_percentage == 50.0
    
    def test_generate_health_report(self):
        """Test health report generation."""
        # Add some events
        self.tracker.record_health_event(ScoreCategory.RESILIENCE, 85, "cb1")
        self.tracker.record_health_event(ScoreCategory.RESILIENCE, 90, "cb2")
        self.tracker.record_health_event(ScoreCategory.MEMORY, 75, "mem1")
        
        report = self.tracker.generate_health_report()
        assert report.overall_score > 0
        assert report.category_breakdown is not None
        assert report.trend is not None
        assert report.recommendations is not None
    
    def test_get_health_summary(self):
        """Test quick health summary."""
        self.tracker.record_health_event(ScoreCategory.SECURITY, 95, "auth")
        self.tracker.record_health_event(ScoreCategory.RESILIENCE, 88, "cb")
        
        summary = self.tracker.get_health_summary()
        assert "total_score" in summary
        assert "category_scores" in summary
        assert "status" in summary  # healthy/degraded/critical
    
    def test_persistence(self):
        """Test that data persists across tracker instances."""
        # Record events with first tracker
        self.tracker.record_health_event(ScoreCategory.RESILIENCE, 85, "test1")
        tracker2 = HealthScoreTracker(db_path=self.test_db_path)
        
        # Should have same count
        assert len(tracker2.get_health_history()) == 1
    
    def test_health_status_levels(self):
        """Test health status determination."""
        tracker = HealthScoreTracker()
        
        assert tracker._get_status(95) == "healthy"
        assert tracker._get_status(75) == "healthy"
        assert tracker._get_status(60) == "degraded"
        assert tracker._get_status(40) == "critical"
        assert tracker._get_status(25) == "critical"
    
    def test_recommendations_generation(self):
        """Test that recommendations are generated based on low scores."""
        # Record a low security score
        self.tracker.record_health_event(ScoreCategory.SECURITY, 45, "auth")
        self.tracker.record_health_event(ScoreCategory.MEMORY, 90, "mem")
        
        report = self.tracker.generate_health_report()
        assert len(report.recommendations) > 0
        # Should have security-related recommendation
        rec_text = " ".join(report.recommendations).lower()
        assert "security" in rec_text or "permission" in rec_text


class TestLoadSaveFunctions:
    """Test load/save utility functions."""
    
    def test_load_empty_history(self):
        """Test loading empty history."""
        path = "/tmp/nonexistent_history.json"
        if os.path.exists(path):
            os.remove(path)
        
        history = load_health_history(path)
        assert history == []
    
    def test_save_and_load_history(self):
        """Test saving and loading history."""
        path = "/tmp/test_save_history.json"
        events = [
            HealthEvent(
                id="test1",
                timestamp=datetime.now(),
                category=ScoreCategory.RESILIENCE,
                score=85,
                component="test",
                details={}
            )
        ]
        
        save_health_history(path, events)
        loaded = load_health_history(path)
        
        assert len(loaded) == 1
        assert loaded[0].id == "test1"
        
        # Cleanup
        os.remove(path)


class TestScoreCategory:
    """Test ScoreCategory enum."""
    
    def test_all_categories_defined(self):
        """Ensure all expected categories exist."""
        assert ScoreCategory.RESILIENCE.value == "resilience"
        assert ScoreCategory.MEMORY.value == "memory"
        assert ScoreCategory.SECURITY.value == "security"
        assert ScoreCategory.PERFORMANCE.value == "performance"
        assert ScoreCategory.AVAILABILITY.value == "availability"
