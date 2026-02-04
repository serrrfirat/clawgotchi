"""Tests for confidence tracking in assumption_tracker."""

import json
import os
import tempfile
from datetime import datetime, timedelta

import pytest

from cognition.assumption_tracker import Assumption, AssumptionTracker, AssumptionStatus


@pytest.fixture
def temp_assumptions_file():
    """Create a temporary file for assumptions storage."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('{"assumptions": []}')
    yield f.name
    os.unlink(f.name)


@pytest.fixture
def tracker(temp_assumptions_file):
    """Create an AssumptionTracker with temporary storage."""
    return AssumptionTracker(storage_path=temp_assumptions_file)


class TestAssumptionConfidence:
    """Test confidence in Assumption class."""

    def test_assumption_with_confidence(self):
        """Assumption can have custom confidence level."""
        assumption = Assumption(
            content="High confidence prediction",
            category="prediction",
            confidence=0.95
        )
        assert assumption.confidence == 0.95
        assert len(assumption.confidence_history) == 1

    def test_assumption_default_confidence(self):
        """Default confidence is 0.8."""
        assumption = Assumption(
            content="Default confidence",
            category="test"
        )
        assert assumption.confidence == 0.8

    def test_assumption_invalid_confidence_rejected(self):
        """Confidence outside 0-1 range is rejected."""
        with pytest.raises(ValueError, match="Confidence must be"):
            Assumption(
                content="Invalid confidence",
                category="test",
                confidence=1.5
            )


class TestTrackerConfidenceRecording:
    """Test confidence in tracker.record()."""

    def test_record_with_confidence(self, tracker):
        """Tracker records assumption with custom confidence."""
        assumption_id = tracker.record(
            content="Test assumption",
            category="test",
            confidence=0.7
        )
        assumption = tracker.get(assumption_id)
        assert assumption.confidence == 0.7
        assert len(assumption.confidence_history) == 1

    def test_record_default_confidence(self, tracker):
        """Default confidence is 0.8 when not specified."""
        assumption_id = tracker.record(
            content="Test assumption",
            category="test"
        )
        assumption = tracker.get(assumption_id)
        assert assumption.confidence == 0.8


class TestConfidenceUpdate:
    """Test confidence update functionality."""

    def test_update_confidence(self, tracker):
        """Can update confidence of an open assumption."""
        assumption_id = tracker.record(
            content="Test assumption",
            category="test",
            confidence=0.8
        )
        
        tracker.update_confidence(assumption_id, 0.5)
        
        assumption = tracker.get(assumption_id)
        assert assumption.confidence == 0.5
        assert len(assumption.confidence_history) == 2

    def test_update_confidence_records_history(self, tracker):
        """Each confidence update adds to history."""
        assumption_id = tracker.record(
            content="Tracking confidence changes",
            category="test",
            confidence=0.9
        )
        
        tracker.update_confidence(assumption_id, 0.7)
        tracker.update_confidence(assumption_id, 0.5)
        
        assumption = tracker.get(assumption_id)
        assert len(assumption.confidence_history) == 3
        assert assumption.confidence_history[0][1] == 0.9
        assert assumption.confidence_history[1][1] == 0.7
        assert assumption.confidence_history[2][1] == 0.5

    def test_update_confidence_nonexistent(self, tracker):
        """Updating confidence of nonexistent assumption raises error."""
        with pytest.raises(ValueError, match="not found"):
            tracker.update_confidence("fake-id", 0.5)

    def test_update_confidence_verified_rejected(self, tracker):
        """Cannot update confidence of verified assumption."""
        assumption_id = tracker.record(content="Test", category="test")
        tracker.verify(assumption_id, correct=True)
        
        with pytest.raises(ValueError, match="verified"):
            tracker.update_confidence(assumption_id, 0.5)

    def test_update_confidence_invalid_range(self, tracker):
        """Confidence outside 0-1 range is rejected."""
        assumption_id = tracker.record(content="Test", category="test")
        
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            tracker.update_confidence(assumption_id, -0.1)
        
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            tracker.update_confidence(assumption_id, 1.1)


class TestVerifyConfidence:
    """Test that verification sets confidence correctly."""

    def test_verify_correct_sets_confidence_to_one(self, tracker):
        """Correct verification sets confidence to 1.0."""
        assumption_id = tracker.record(
            content="Will be correct",
            category="test",
            confidence=0.7
        )
        tracker.verify(assumption_id, correct=True)
        
        assumption = tracker.get(assumption_id)
        assert assumption.confidence == 1.0

    def test_verify_incorrect_sets_confidence_to_zero(self, tracker):
        """Incorrect verification sets confidence to 0.0."""
        assumption_id = tracker.record(
            content="Will be incorrect",
            category="test",
            confidence=0.9
        )
        tracker.verify(assumption_id, correct=False)
        
        assumption = tracker.get(assumption_id)
        assert assumption.confidence == 0.0

    def test_verify_records_confidence_history(self, tracker):
        """Verification adds to confidence history."""
        assumption_id = tracker.record(
            content="Test",
            category="test",
            confidence=0.8
        )
        tracker.verify(assumption_id, correct=True)
        
        assumption = tracker.get(assumption_id)
        assert len(assumption.confidence_history) == 2


class TestGetByConfidence:
    """Test filtering assumptions by confidence."""

    def test_get_by_confidence_range(self, tracker):
        """Can filter assumptions by confidence range."""
        tracker.record(content="High 1", category="test", confidence=0.9)
        tracker.record(content="High 2", category="test", confidence=0.85)
        tracker.record(content="Medium", category="test", confidence=0.6)
        tracker.record(content="Low", category="test", confidence=0.3)
        
        high = tracker.get_by_confidence(min_confidence=0.8)
        assert len(high) == 2
        
        low = tracker.get_by_confidence(max_confidence=0.5)
        assert len(low) == 1
        
        mid = tracker.get_by_confidence(min_confidence=0.5, max_confidence=0.7)
        assert len(mid) == 1

    def test_get_low_confidence(self, tracker):
        """Can get low confidence assumptions."""
        tracker.record(content="Low 1", category="test", confidence=0.3)
        tracker.record(content="Low 2", category="test", confidence=0.4)
        tracker.record(content="High", category="test", confidence=0.9)
        
        low = tracker.get_low_confidence(threshold=0.5)
        assert len(low) == 2

    def test_get_high_confidence(self, tracker):
        """Can get high confidence assumptions."""
        tracker.record(content="High 1", category="test", confidence=0.9)
        tracker.record(content="High 2", category="test", confidence=0.85)
        tracker.record(content="Low", category="test", confidence=0.4)
        
        high = tracker.get_high_confidence(threshold=0.8)
        assert len(high) == 2


class TestConfidencePersistence:
    """Test confidence persistence."""

    def test_confidence_persists(self, tracker):
        """Confidence is saved and loaded from disk."""
        tracker.record(content="Test", category="test", confidence=0.6)
        
        # Load new tracker instance
        new_tracker = AssumptionTracker(storage_path=tracker.storage_path)
        assumption = new_tracker.assumptions[0]
        assert assumption.confidence == 0.6

    def test_confidence_history_persists(self, tracker):
        """Confidence history is saved and loaded."""
        assumption_id = tracker.record(content="Test", category="test", confidence=0.9)
        tracker.update_confidence(assumption_id, 0.7)
        
        # Load new tracker instance
        new_tracker = AssumptionTracker(storage_path=tracker.storage_path)
        assumption = new_tracker.assumptions[0]
        assert len(assumption.confidence_history) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
