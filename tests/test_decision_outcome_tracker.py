"""
Tests for Decision Outcome Tracker.
"""

import pytest
import json
import os
import tempfile
from datetime import datetime, timedelta

from utils.decision_outcome_tracker import DecisionOutcomeTracker


@pytest.fixture
def tracker():
    """Create a tracker with temporary storage."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('{"decisions": []}')
        temp_path = f.name
    
    tracker = DecisionOutcomeTracker(storage_path=temp_path)
    yield tracker
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


class TestRecordDecision:
    """Tests for recording decisions."""

    def test_record_decision_basic(self, tracker):
        """Test recording a basic decision."""
        decision = tracker.record_decision(
            decision_id="test-001",
            description="Deploy to production",
            expected_outcome="System remains stable for 24 hours",
            deadline=(datetime.now() + timedelta(days=1)).isoformat(),
            context="After completing all tests",
            tags=["deployment", "stability"]
        )
        
        assert decision['id'] == "test-001"
        assert decision['description'] == "Deploy to production"
        assert decision['expected_outcome'] == "System remains stable for 24 hours"
        assert decision['status'] == "pending"
        assert decision['tags'] == ["deployment", "stability"]

    def test_record_decision_defaults(self, tracker):
        """Test recording with minimal fields."""
        deadline = (datetime.now() + timedelta(days=7)).isoformat()
        decision = tracker.record_decision(
            decision_id="test-002",
            description="Launch feature X",
            expected_outcome="Users engage with feature",
            deadline=deadline
        )
        
        assert decision['context'] is None
        assert decision['tags'] == []
        assert decision['actual_outcome'] is None

    def test_record_decision_duplicate_raises(self, tracker):
        """Test that duplicate decision_id raises error."""
        deadline = (datetime.now() + timedelta(days=1)).isoformat()
        tracker.record_decision(
            decision_id="dup-001",
            description="First decision",
            expected_outcome="First outcome",
            deadline=deadline
        )
        
        with pytest.raises(ValueError, match="already exists"):
            tracker.record_decision(
                decision_id="dup-001",
                description="Duplicate",
                expected_outcome="Duplicate",
                deadline=deadline
            )


class TestMarkVerifiable:
    """Tests for marking decisions as verifiable."""

    def test_mark_verifiable(self, tracker):
        """Test marking a decision with actual outcome."""
        deadline = (datetime.now() + timedelta(days=1)).isoformat()
        tracker.record_decision(
            decision_id="verify-001",
            description="Test decision",
            expected_outcome="Expected result",
            deadline=deadline
        )
        
        result = tracker.mark_verifiable(
            decision_id="verify-001",
            actual_outcome="Actual result observed",
            notes="Verified by tests"
        )
        
        assert result['actual_outcome'] == "Actual result observed"
        assert result['verification_notes'] == "Verified by tests"
        assert result['verified_at'] is not None

    def test_mark_verifiable_not_found(self, tracker):
        """Test marking non-existent decision."""
        with pytest.raises(ValueError, match="not found"):
            tracker.mark_verifiable(
                decision_id="nonexistent",
                actual_outcome="Test",
                notes="Notes"
            )


class TestVerifyOutcome:
    """Tests for outcome verification."""

    def test_verify_outcome_match(self, tracker):
        """Test verifying when outcomes match."""
        deadline = (datetime.now() + timedelta(days=1)).isoformat()
        tracker.record_decision(
            decision_id="match-001",
            description="Test",
            expected_outcome="Success",
            deadline=deadline
        )
        tracker.mark_verifiable(
            decision_id="match-001",
            actual_outcome="Operation was Success"
        )
        
        result = tracker.verify_outcome("match-001")
        
        assert result['status'] == 'verified'
        assert result['match'] is True

    def test_verify_outcome_no_match(self, tracker):
        """Test verifying when outcomes don't match."""
        deadline = (datetime.now() + timedelta(days=1)).isoformat()
        tracker.record_decision(
            decision_id="nomatch-001",
            description="Test",
            expected_outcome="Success",
            deadline=deadline
        )
        tracker.mark_verifiable(
            decision_id="nomatch-001",
            actual_outcome="Complete failure"
        )
        
        result = tracker.verify_outcome("nomatch-001")
        
        assert result['status'] == 'falsified'
        assert result['match'] is False

    def test_verify_outcome_no_actual(self, tracker):
        """Test verifying without actual outcome recorded."""
        deadline = (datetime.now() + timedelta(days=1)).isoformat()
        tracker.record_decision(
            decision_id="noactual-001",
            description="Test",
            expected_outcome="Success",
            deadline=deadline
        )
        
        with pytest.raises(ValueError, match="no recorded outcome"):
            tracker.verify_outcome("noactual-001")


class TestGetPendingDecisions:
    """Tests for getting pending decisions."""

    def test_get_pending_decisions(self, tracker):
        """Test getting pending decisions."""
        deadline = (datetime.now() + timedelta(days=1)).isoformat()
        
        tracker.record_decision(
            decision_id="pending-001",
            description="Pending 1",
            expected_outcome="Outcome 1",
            deadline=deadline
        )
        tracker.record_decision(
            decision_id="pending-002",
            description="Pending 2",
            expected_outcome="Outcome 2",
            deadline=deadline
        )
        
        pending = tracker.get_pending_decisions()
        assert len(pending) == 2


class TestGetStatistics:
    """Tests for statistics."""

    def test_get_statistics_empty(self, tracker):
        """Test statistics with no decisions."""
        stats = tracker.get_statistics()
        
        assert stats['total'] == 0
        assert stats['pending'] == 0
        assert stats['verified'] == 0
        assert stats['accuracy_rate'] == 0

    def test_get_statistics_with_data(self, tracker):
        """Test statistics with various decisions."""
        deadline = (datetime.now() + timedelta(days=1)).isoformat()
        
        # Add pending
        tracker.record_decision("stat-1", "D1", "O1", deadline)
        
        # Add verified
        tracker.record_decision("stat-2", "D2", "O2", deadline)
        tracker.mark_verifiable("stat-2", "O2 observed")
        tracker.verify_outcome("stat-2")
        
        # Add falsified
        tracker.record_decision("stat-3", "D3", "O3", deadline)
        tracker.mark_verifiable("stat-3", "Different outcome")
        tracker.verify_outcome("stat-3")
        
        stats = tracker.get_statistics()
        
        assert stats['total'] == 3
        assert stats['pending'] == 1
        assert stats['verified'] == 1
        assert stats['falsified'] == 1
        assert stats['accuracy_rate'] == 50.0


class TestCleanupOldDecisions:
    """Tests for cleanup functionality."""

    def test_cleanup_old_verified(self, tracker):
        """Test removing old verified decisions."""
        # Add old verified decision
        old_decision = {
            'id': 'old-001',
            'description': 'Old',
            'expected_outcome': 'Outcome',
            'deadline': (datetime.now() - timedelta(days=100)).isoformat(),
            'context': None,
            'tags': [],
            'status': 'verified',
            'actual_outcome': 'Observed',
            'recorded_at': (datetime.now() - timedelta(days=100)).isoformat(),
            'verified_at': (datetime.now() - timedelta(days=100)).isoformat(),
            'verification_notes': None
        }
        
        # Manually add to storage
        with open(tracker.storage_path, 'w') as f:
            json.dump({'decisions': [old_decision]}, f)
        
        # Should remove old verified
        removed = tracker.cleanup_old_decisions(days=90)
        assert removed == 1
        
        stats = tracker.get_statistics()
        assert stats['total'] == 0

    def test_cleanup_preserves_recent(self, tracker):
        """Test that recent decisions are preserved."""
        # Add recent decision
        recent = {
            'id': 'recent-001',
            'description': 'Recent',
            'expected_outcome': 'Outcome',
            'deadline': (datetime.now() - timedelta(days=5)).isoformat(),
            'context': None,
            'tags': [],
            'status': 'pending',
            'actual_outcome': None,
            'recorded_at': (datetime.now() - timedelta(days=5)).isoformat(),
            'verified_at': None,
            'verification_notes': None
        }
        
        with open(tracker.storage_path, 'w') as f:
            json.dump({'decisions': [recent]}, f)
        
        removed = tracker.cleanup_old_decisions(days=90)
        assert removed == 0
        
        stats = tracker.get_statistics()
        assert stats['total'] == 1
