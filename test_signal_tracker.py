"""
Tests for SignalTracker
"""

import os
import json
import pytest
from signal_tracker import SignalTracker


@pytest.fixture
def tracker(tmp_path):
    """Create a SignalTracker with a temp file."""
    storage_file = tmp_path / "test_signals.json"
    tracker = SignalTracker(str(storage_file))
    yield tracker
    # Cleanup
    if os.path.exists(str(storage_file)):
        os.remove(str(storage_file))


class TestSignalTrackerEmit:
    def test_emit_creates_signal_with_id(self, tracker):
        """Emit should create a signal and return an ID."""
        signal_id = tracker.emit(
            title="Test Signal",
            description="A test signal",
            expected_outcome="Test passes",
            tags=["test"]
        )
        assert signal_id is not None
        assert len(signal_id) == 8

    def test_emit_stores_signal_data(self, tracker):
        """Emit should store all provided data."""
        signal_id = tracker.emit(
            title="Fee Assumption",
            description="Fee rate is 0.10%",
            expected_outcome="Profitable trades",
            tags=["fees", "trading"]
        )

        signal = tracker.get_signal(signal_id)
        assert signal['title'] == "Fee Assumption"
        assert signal['description'] == "Fee rate is 0.10%"
        assert signal['expected_outcome'] == "Profitable trades"
        assert signal['tags'] == ["fees", "trading"]
        assert signal['status'] == "pending"

    def test_emit_multiple_signals(self, tracker):
        """Emit should handle multiple signals."""
        id1 = tracker.emit("Signal 1", "Desc 1", "Outcome 1")
        id2 = tracker.emit("Signal 2", "Desc 2", "Outcome 2")

        assert id1 != id2
        assert len(tracker.get_all_signals()) == 2


class TestSignalTrackerValidation:
    def test_validate_changes_status(self, tracker):
        """Validate should change status from pending to validated."""
        signal_id = tracker.emit("Test", "Desc", "Outcome")

        result = tracker.validate(signal_id, "It worked!", "All good")

        assert result is True
        signal = tracker.get_signal(signal_id)
        assert signal['status'] == "validated"
        assert signal['actual_outcome'] == "It worked!"
        assert len(signal['notes']) == 1

    def test_invalidate_changes_status(self, tracker):
        """Invalidate should change status to invalidated."""
        signal_id = tracker.emit("Test", "Desc", "Outcome")

        result = tracker.invalidate(signal_id, "It failed", "Fees too high")

        assert result is True
        signal = tracker.get_signal(signal_id)
        assert signal['status'] == "invalidated"
        assert signal['actual_outcome'] == "It failed"

    def test_validate_nonexistent_signal_returns_false(self, tracker):
        """Validate should return False for unknown signal ID."""
        result = tracker.validate("nonexistent", "Outcome")
        assert result is False

    def test_invalidate_nonexistent_signal_returns_false(self, tracker):
        """Invalidate should return False for unknown signal ID."""
        result = tracker.invalidate("nonexistent", "Outcome")
        assert result is False


class TestSignalTrackerStats:
    def test_get_stats_empty(self, tracker):
        """Stats should show zero counts for empty tracker."""
        stats = tracker.get_stats()
        assert stats['total'] == 0
        assert stats['validated'] == 0
        assert stats['invalidated'] == 0
        assert stats['pending'] == 0
        assert stats['accuracy_percent'] == 0

    def test_get_stats_with_data(self, tracker):
        """Stats should calculate accuracy correctly."""
        id1 = tracker.emit("S1", "D1", "O1")
        id2 = tracker.emit("S2", "D2", "O2")
        id3 = tracker.emit("S3", "D3", "O3")

        tracker.validate(id1, "Validated outcome")
        tracker.invalidate(id2, "Invalidated outcome")

        stats = tracker.get_stats()
        assert stats['total'] == 3
        assert stats['validated'] == 1
        assert stats['invalidated'] == 1
        assert stats['pending'] == 1
        assert stats['accuracy_percent'] == 50.0  # 1/2

    def test_accuracy_with_no_conclusions(self, tracker):
        """Accuracy should be 0 when no signals resolved."""
        tracker.emit("S1", "D1", "O1")
        tracker.emit("S2", "D2", "O2")

        stats = tracker.get_stats()
        assert stats['accuracy_percent'] == 0


class TestSignalTrackerFilters:
    def test_get_pending_signals(self, tracker):
        """Should return only pending signals."""
        id1 = tracker.emit("S1", "D1", "O1")
        id2 = tracker.emit("S2", "D2", "O2")
        tracker.validate(id1, "Done")

        pending = tracker.get_pending_signals()
        assert len(pending) == 1
        assert pending[0]['id'] == id2

    def test_get_by_tag(self, tracker):
        """Should filter signals by tag."""
        id1 = tracker.emit("S1", "D1", "O1", tags=["fees", "trading"])
        id2 = tracker.emit("S2", "D2", "O2", tags=["memory"])
        tracker.emit("S3", "D3", "O3")  # No tags

        fee_signals = tracker.get_by_tag("fees")
        assert len(fee_signals) == 1
        assert fee_signals[0]['id'] == id1


class TestSignalTrackerPersistence:
    def test_signals_persist_after_reload(self, tracker):
        """Signals should persist across tracker instances."""
        tracker.emit("Persistent Signal", "Desc", "Outcome")

        # Create new tracker instance with same file
        new_tracker = SignalTracker(tracker.storage_path)

        signal = new_tracker.get_all_signals()
        assert len(signal) == 1
        assert signal[0]['title'] == "Persistent Signal"

    def test_updated_signals_persist(self, tracker):
        """Validation should persist across instances."""
        signal_id = tracker.emit("Test", "Desc", "Outcome")
        tracker.validate(signal_id, "Actual")

        new_tracker = SignalTracker(tracker.storage_path)
        signal = new_tracker.get_signal(signal_id)

        assert signal['status'] == "validated"
        assert signal['actual_outcome'] == "Actual"


class TestSignalTrackerClear:
    def test_clear_removes_all_signals(self, tracker):
        """Clear should remove all signals."""
        tracker.emit("S1", "D1", "O1")
        tracker.emit("S2", "D2", "O2")

        tracker.clear()

        assert len(tracker.get_all_signals()) == 0
        assert tracker.get_stats()['total'] == 0
