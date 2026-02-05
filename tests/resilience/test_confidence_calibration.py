"""
Test suite for Confidence Calibration Tracker.
Tracks prediction confidence vs actual outcomes to measure and improve calibration.
"""
import pytest
import json
import os
import tempfile
from datetime import datetime, timedelta

# Import the module under test
import sys
sys.path.insert(0, '/workspace')
from clawgotchi.resilience.confidence_calibration import (
    ConfidenceCalibrator,
    Prediction,
    CalibrationMetric,
    CalibrationSession,
)


class TestConfidenceCalibratorBasics:
    """Basic functionality tests for ConfidenceCalibrator."""
    
    def test_create_calibrator(self, temp_dir):
        """Test creating a new calibrator instance."""
        calibrator = ConfidenceCalibrator(storage_path=temp_dir)
        assert calibrator is not None
        assert calibrator.storage_path == temp_dir
    
    def test_record_prediction(self, temp_dir):
        """Test recording a prediction with confidence level."""
        calibrator = ConfidenceCalibrator(storage_path=temp_dir)
        
        pred_id = calibrator.record_prediction(
            statement="Model X will win the benchmark",
            confidence=0.8,
            category="benchmark"
        )
        
        assert pred_id is not None
        assert isinstance(pred_id, str)
    
    def test_record_prediction_with_metadata(self, temp_dir):
        """Test recording prediction with full metadata."""
        calibrator = ConfidenceCalibrator(storage_path=temp_dir)
        
        pred_id = calibrator.record_prediction(
            statement="Temperature will exceed 30C",
            confidence=0.7,
            category="weather",
            source="weather_api",
            context={"location": "Dubai"}
        )
        
        assert pred_id is not None
    
    def test_record_outcome(self, temp_dir):
        """Test recording the actual outcome of a prediction."""
        calibrator = ConfidenceCalibrator(storage_path=temp_dir)
        
        pred_id = calibrator.record_prediction(
            statement="Market will close up",
            confidence=0.6,
            category="trading"
        )
        
        result = calibrator.record_outcome(pred_id, outcome=True)
        assert result is True
    
    def test_record_outcome_invalid_id(self, temp_dir):
        """Test recording outcome for non-existent prediction."""
        calibrator = ConfidenceCalibrator(storage_path=temp_dir)
        
        result = calibrator.record_outcome("invalid_id", outcome=True)
        assert result is False
    
    def test_get_prediction_by_id(self, temp_dir):
        """Test retrieving a prediction by ID."""
        calibrator = ConfidenceCalibrator(storage_path=temp_dir)
        
        original_id = calibrator.record_prediction(
            statement="Test prediction",
            confidence=0.9,
            category="test"
        )
        
        retrieved = calibrator.get_prediction(original_id)
        assert retrieved is not None
        assert retrieved["id"] == original_id
        assert retrieved["statement"] == "Test prediction"
        assert retrieved["confidence"] == 0.9


class TestCalibrationMetrics:
    """Tests for calibration accuracy metrics."""
    
    def test_calculate_calibration_brier_score(self, temp_dir):
        """Test Brier score calculation (lower = better calibration)."""
        calibrator = ConfidenceCalibrator(storage_path=temp_dir)
        
        # Record predictions with known outcomes
        calibrator.record_prediction("Event A", 0.9, "test")
        calibrator.record_outcome(calibrator.predictions[0].id, outcome=True)
        
        calibrator.record_prediction("Event B", 0.9, "test")
        calibrator.record_outcome(calibrator.predictions[1].id, outcome=True)
        
        calibrator.record_prediction("Event C", 0.8, "test")
        calibrator.record_outcome(calibrator.predictions[2].id, outcome=True)
        
        calibrator.record_prediction("Event D", 0.8, "test")
        calibrator.record_outcome(calibrator.predictions[3].id, outcome=False)
        
        score = calibrator.calculate_brier_score()
        assert score is not None
        assert 0 <= score <= 1  # Brier score is between 0 and 1
    
    def test_calculate_calibration_by_confidence_bin(self, temp_dir):
        """Test calibration accuracy grouped by confidence bins."""
        calibrator = ConfidenceCalibrator(storage_path=temp_dir)
        
        # High confidence (0.8-1.0) - mostly correct
        for _ in range(8):
            pid = calibrator.record_prediction("High conf", 0.9, "test")
            calibrator.record_outcome(pid, outcome=True)
        for _ in range(2):
            pid = calibrator.record_prediction("High conf miss", 0.9, "test")
            calibrator.record_outcome(pid, outcome=False)
        
        # Low confidence (0.2-0.4) - mostly wrong
        for _ in range(3):
            pid = calibrator.record_prediction("Low conf", 0.3, "test")
            calibrator.record_outcome(pid, outcome=False)
        for _ in range(7):
            pid = calibrator.record_prediction("Low conf hit", 0.3, "test")
            calibrator.record_outcome(pid, outcome=True)
        
        bins = calibrator.get_calibration_by_bin()
        
        assert "0.8-1.0" in bins
        assert "0.2-0.4" in bins
        # High confidence bin should have ~80% accuracy
        assert bins["0.8-1.0"]["actual_accuracy"] > bins["0.2-0.4"]["actual_accuracy"]
    
    def test_get_overall_calibration(self, temp_dir):
        """Test getting overall calibration statistics."""
        calibrator = ConfidenceCalibrator(storage_path=temp_dir)
        
        # Add predictions with outcomes
        for i in range(5):
            pid = calibrator.record_prediction(f"Pred {i}", 0.7 + i*0.05, "test")
            calibrator.record_outcome(pid, outcome=(i % 2 == 0))
        
        stats = calibrator.get_overall_calibration()
        
        assert "total_predictions" in stats
        assert "resolved_predictions" in stats
        assert "brier_score" in stats
        assert "average_confidence" in stats
        assert "calibration_error" in stats
        assert stats["total_predictions"] == 5


class TestCalibrationSession:
    """Tests for CalibrationSession management."""
    
    def test_create_session(self, temp_dir):
        """Test creating a calibration session."""
        session = CalibrationSession(
            name="Morning Calibration",
            storage_path=temp_dir
        )
        assert session is not None
        assert session.name == "Morning Calibration"
    
    def test_session_add_prediction(self, temp_dir):
        """Test adding predictions to a session."""
        session = CalibrationSession(name="Test Session", storage_path=temp_dir)
        
        pred = session.add_prediction(
            statement="Test",
            confidence=0.75
        )
        
        assert pred is not None
        assert len(session.predictions) == 1
    
    def test_session_resolve_prediction(self, temp_dir):
        """Test resolving a prediction within a session."""
        session = CalibrationSession(name="Test Session", storage_path=temp_dir)
        
        pred = session.add_prediction(
            statement="Test prediction",
            confidence=0.8
        )
        
        result = session.resolve_prediction(pred.id, outcome=True)
        assert result is True
        assert pred.resolved is True
        assert pred.outcome is True
    
    def test_session_summary(self, temp_dir):
        """Test session summary generation."""
        session = CalibrationSession(name="Test Session", storage_path=temp_dir)
        
        for i in range(5):
            pred = session.add_prediction(f"Pred {i}", 0.6 + i*0.08, "test")
            session.resolve_prediction(pred.id, outcome=(i % 2 == 0))
        
        summary = session.get_summary()
        
        assert "name" in summary
        assert "total_predictions" in summary
        assert "correct_predictions" in summary
        assert "brier_score" in summary
        assert "calibration_by_bin" in summary


class TestCalibrationReport:
    """Tests for calibration reporting."""
    
    def test_generate_report(self, temp_dir):
        """Test generating a calibration report."""
        calibrator = ConfidenceCalibrator(storage_path=temp_dir)
        
        # Create some data
        for i in range(10):
            pid = calibrator.record_prediction(f"Event {i}", 0.5 + (i % 5)*0.1, "test")
            calibrator.record_outcome(pid, outcome=(i % 3 == 0))
        
        report = calibrator.generate_report()
        
        assert report is not None
        assert "generated_at" in report
        assert "summary" in report
        assert "calibration_by_bin" in report
        assert "recent_predictions" in report
    
    def test_get_recent_predictions(self, temp_dir):
        """Test retrieving recent predictions."""
        calibrator = ConfidenceCalibrator(storage_path=temp_dir)
        
        for i in range(5):
            calibrator.record_prediction(f"Event {i}", 0.7, "test")
        
        recent = calibrator.get_recent_predictions(limit=3)
        
        assert len(recent) == 3
    
    def test_get_unresolved_predictions(self, temp_dir):
        """Test retrieving unresolved predictions."""
        calibrator = ConfidenceCalibrator(storage_path=temp_dir)
        
        pid1 = calibrator.record_prediction("Event 1", 0.7, "test")
        pid2 = calibrator.record_prediction("Event 2", 0.8, "test")
        calibrator.record_outcome(pid1, outcome=True)
        
        unresolved = calibrator.get_unresolved_predictions()
        
        assert len(unresolved) == 1
        assert unresolved[0]["id"] == pid2


class TestPersistence:
    """Tests for data persistence."""
    
    def test_save_and_load(self, temp_dir):
        """Test saving and loading calibrator state."""
        calibrator1 = ConfidenceCalibrator(storage_path=temp_dir)
        calibrator1.record_prediction("Test", 0.8, "test")
        
        # Save
        calibrator1.save()
        
        # Load new instance
        calibrator2 = ConfidenceCalibrator(storage_path=temp_dir)
        calibrator2.load()
        
        assert len(calibrator2.predictions) == 1
    
    def test_json_export(self, temp_dir):
        """Test exporting predictions to JSON."""
        calibrator = ConfidenceCalibrator(storage_path=temp_dir)
        calibrator.record_prediction("Test", 0.8, "test")
        
        exported = calibrator.to_json()
        
        assert exported is not None
        assert isinstance(exported, str)
        data = json.loads(exported)
        assert "predictions" in data


class TestConfidenceThresholds:
    """Tests for confidence threshold recommendations."""
    
    def test_get_confidence_threshold_recommendation(self, temp_dir):
        """Test getting recommended confidence thresholds."""
        calibrator = ConfidenceCalibrator(storage_path=temp_dir)
        
        # Create well-calibrated data (80% confidence = 80% accuracy)
        for _ in range(20):
            pred_id = calibrator.record_prediction("Well calibrated", 0.8, "test")
            calibrator.record_outcome(pred_id, outcome=True)
        for _ in range(5):
            pred_id = calibrator.record_prediction("Missed", 0.8, "test")
            calibrator.record_outcome(pred_id, outcome=False)
        
        # Create poorly calibrated data (90% confidence = 50% accuracy)
        for _ in range(5):
            pred_id = calibrator.record_prediction("Overconfident", 0.9, "test")
            calibrator.record_outcome(pred_id, outcome=True)
        for _ in range(5):
            pred_id = calibrator.record_prediction("Overconfident miss", 0.9, "test")
            calibrator.record_outcome(pred_id, outcome=False)
        
        thresholds = calibrator.get_threshold_recommendations()
        
        assert "high_confidence_threshold" in thresholds
        assert "medium_confidence_threshold" in thresholds
        assert "low_confidence_threshold" in thresholds
        assert 0 <= thresholds["high_confidence_threshold"] <= 1


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_calibrator(self, temp_dir):
        """Test operations on empty calibrator."""
        calibrator = ConfidenceCalibrator(storage_path=temp_dir)
        
        score = calibrator.calculate_brier_score()
        assert score == 0.0  # No predictions = no error
        
        bins = calibrator.get_calibration_by_bin()
        assert bins == {}
    
    def test_all_correct_predictions(self, temp_dir):
        """Test calibrator with all correct predictions."""
        calibrator = ConfidenceCalibrator(storage_path=temp_dir)
        
        for i in range(5):
            pred_id = calibrator.record_prediction(f"Pred {i}", 0.6 + i*0.08, "test")
            calibrator.record_outcome(pred_id, outcome=True)
        
        stats = calibrator.get_overall_calibration()
        assert stats["correct_rate"] == 1.0
    
    def test_all_incorrect_predictions(self, temp_dir):
        """Test calibrator with all incorrect predictions."""
        calibrator = ConfidenceCalibrator(storage_path=temp_dir)
        
        for i in range(5):
            pred_id = calibrator.record_prediction(f"Pred {i}", 0.6 + i*0.08, "test")
            calibrator.record_outcome(pred_id, outcome=False)
        
        stats = calibrator.get_overall_calibration()
        assert stats["correct_rate"] == 0.0
    
    def test_invalid_confidence_values(self, temp_dir):
        """Test handling of invalid confidence values."""
        calibrator = ConfidenceCalibrator(storage_path=temp_dir)
        
        # Should clamp to valid range
        pred_id = calibrator.record_prediction("Test", 1.5, "test")
        assert pred_id is not None
        
        pred_id2 = calibrator.record_prediction("Test", -0.5, "test")
        assert pred_id2 is not None
    
    def test_unicode_in_predictions(self, temp_dir):
        """Test handling unicode in prediction statements."""
        calibrator = ConfidenceCalibrator(storage_path=temp_dir)
        
        pred_id = calibrator.record_prediction(
            "日本語テスト",
            0.8,
            "test"
        )
        
        assert pred_id is not None
        retrieved = calibrator.get_prediction(pred_id)
        assert "日本語テスト" in retrieved["statement"]


# Pytest fixture for temporary directory
@pytest.fixture
def temp_dir(tmp_path):
    """Provide a temporary directory for tests."""
    return str(tmp_path)
