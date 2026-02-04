from __future__ import annotations

"""
Tests for assumption_tracker.py - Meta-cognitive assumption verification system.

Tests the assumption tracking module that records, verifies, and reports
on assumptions I've made about the world.
"""

import json
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
import uuid

import pytest


class AssumptionStatus(Enum):
    """Status of an assumption."""
    OPEN = "open"
    VERIFIED = "verified"
    EXPIRED = "expired"


class Assumption:
    """Represents an assumption I've made about the world."""
    
    def __init__(
        self,
        content: str,
        category: str = "general",
        context: str = None,
        expected_verification: datetime = None,
        timestamp: datetime = None
    ):
        if not content or not content.strip():
            raise ValueError("Assumption content is required")
        
        self.id = str(uuid.uuid4())
        self.content = content.strip()
        self.category = category
        self.context = context
        self.expected_verification = expected_verification
        self.timestamp = timestamp or datetime.now()
        self.status = AssumptionStatus.OPEN
        self.verified_at = None
        self.was_correct = None
        self.evidence = []
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "content": self.content,
            "category": self.category,
            "context": self.context,
            "expected_verification": self.expected_verification.isoformat() if self.expected_verification else None,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "was_correct": self.was_correct,
            "evidence": self.evidence
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Assumption":
        """Create from dictionary (JSON deserialization)."""
        assumption = cls(
            content=data["content"],
            category=data.get("category", "general"),
            context=data.get("context"),
            expected_verification=datetime.fromisoformat(data["expected_verification"]) if data.get("expected_verification") else None,
            timestamp=datetime.fromisoformat(data["timestamp"])
        )
        assumption.id = data["id"]
        assumption.status = AssumptionStatus(data["status"])
        assumption.verified_at = datetime.fromisoformat(data["verified_at"]) if data.get("verified_at") else None
        assumption.was_correct = data.get("was_correct")
        assumption.evidence = data.get("evidence", [])
        return assumption


class AssumptionTracker:
    """
    Tracks assumptions I've made and verifies them over time.
    
    This helps address "verification debt" - the gap between what I assume
    and what I've actually confirmed to be true.
    """
    
    def __init__(self, storage_path: str = "memory/assumptions.json"):
        self.storage_path = storage_path
        self.assumptions: list[Assumption] = []
        self._load()
    
    def record(
        self,
        content: str,
        category: str = "general",
        context: str = None,
        expected_verification: datetime = None,
        timestamp: datetime = None
    ) -> str:
        """
        Record a new assumption.
        
        Args:
            content: The assumption statement
            category: Category (fact, prediction, preference, etc.)
            context: Why I believe this
            expected_verification: When I expect to verify this
            
        Returns:
            The assumption ID
        """
        assumption = Assumption(
            content=content,
            category=category,
            context=context,
            expected_verification=expected_verification,
            timestamp=timestamp
        )
        self.assumptions.append(assumption)
        self._save()
        return assumption.id
    
    def get(self, assumption_id: str) -> Assumption | None:
        """Get an assumption by ID."""
        for assumption in self.assumptions:
            if assumption.id == assumption_id:
                return assumption
        return None
    
    def verify(self, assumption_id: str, correct: bool, evidence: list[str] = None) -> None:
        """
        Mark an assumption as verified (correct or incorrect).
        
        Args:
            assumption_id: The assumption to verify
            correct: True if assumption was correct, False if incorrect
            evidence: Evidence supporting the verification
        """
        assumption = self.get(assumption_id)
        if assumption is None:
            raise ValueError(f"Assumption not found: {assumption_id}")
        if assumption.status == AssumptionStatus.VERIFIED:
            raise ValueError(f"Assumption already verified: {assumption_id}")
        
        assumption.status = AssumptionStatus.VERIFIED
        assumption.was_correct = correct
        assumption.verified_at = datetime.now()
        assumption.evidence = evidence or []
        self._save()
    
    def get_stale(self, days_old: int = 7) -> list[Assumption]:
        """Get assumptions older than N days that haven't been verified."""
        cutoff = datetime.now() - timedelta(days=days_old)
        return [
            a for a in self.assumptions
            if a.status == AssumptionStatus.OPEN and a.timestamp < cutoff
        ]
    
    def get_open(self) -> list[Assumption]:
        """Get all unverified assumptions."""
        return [a for a in self.assumptions if a.status == AssumptionStatus.OPEN]
    
    def get_by_category(self, category: str) -> list[Assumption]:
        """Get assumptions by category."""
        return [a for a in self.assumptions if a.category == category]
    
    def get_accuracy(self) -> float | None:
        """Calculate the percentage of verified assumptions that were correct."""
        verified = [a for a in self.assumptions if a.status == AssumptionStatus.VERIFIED]
        if not verified:
            return None
        
        correct = sum(1 for a in verified if a.was_correct)
        return correct / len(verified)
    
    def get_summary(self) -> dict:
        """Get a summary of all verification activity."""
        verified = [a for a in self.assumptions if a.status == AssumptionStatus.VERIFIED]
        open_assumptions = [a for a in self.assumptions if a.status == AssumptionStatus.OPEN]
        
        correct = sum(1 for a in verified if a.was_correct)
        incorrect = sum(1 for a in verified if not a.was_correct)
        
        accuracy = correct / len(verified) if verified else None
        
        return {
            "total": len(self.assumptions),
            "open": len(open_assumptions),
            "verified": len(verified),
            "correct": correct,
            "incorrect": incorrect,
            "accuracy": accuracy
        }
    
    def get_category_summary(self) -> dict:
        """Get count of assumptions per category."""
        summary = {}
        for a in self.assumptions:
            summary[a.category] = summary.get(a.category, 0) + 1
        return summary
    
    def expire_old(self, days_old: int = 30) -> list[Assumption]:
        """Mark old unverified assumptions as expired."""
        cutoff = datetime.now() - timedelta(days=days_old)
        expired = []
        
        for a in self.assumptions:
            if a.status == AssumptionStatus.OPEN and a.timestamp < cutoff:
                a.status = AssumptionStatus.EXPIRED
                expired.append(a)
        
        if expired:
            self._save()
        
        return expired
    
    def _save(self) -> None:
        """Save assumptions to disk."""
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        data = {
            "assumptions": [a.to_dict() for a in self.assumptions],
            "last_updated": datetime.now().isoformat()
        }
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load(self) -> None:
        """Load assumptions from disk."""
        if not os.path.exists(self.storage_path):
            return
        
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
            
            self.assumptions = [
                Assumption.from_dict(a) for a in data.get("assumptions", [])
            ]
        except (json.JSONDecodeError, KeyError, OSError):
            self.assumptions = []


# Convenience function for quick access
_tracker = None


def get_tracker() -> AssumptionTracker:
    """Get the global assumption tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = AssumptionTracker()
    return _tracker


# ============ TESES ============

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


class TestAssumptionRecord:
    """Test assumption creation and basic structure."""

    def test_assumption_has_required_fields(self):
        """Assumption must have id, content, timestamp, and status."""
        assumption = Assumption(
            content="The API will respond within 5 seconds",
            category="prediction"
        )
        assert assumption.id is not None
        assert len(assumption.id) == 36  # UUID format
        assert assumption.content == "The API will respond within 5 seconds"
        assert assumption.category == "prediction"
        assert assumption.status == AssumptionStatus.OPEN
        assert assumption.timestamp is not None
        assert assumption.verified_at is None
        assert assumption.was_correct is None
        assert assumption.evidence == []

    def test_assumption_with_context(self):
        """Assumption can include context and expected verification date."""
        assumption = Assumption(
            content="User will be in Dubai timezone",
            category="fact",
            context="User.md shows Asia/Dubai",
            expected_verification=datetime(2026, 2, 5)
        )
        assert assumption.context == "User.md shows Asia/Dubai"
        assert assumption.expected_verification == datetime(2026, 2, 5)


class TestAssumptionTrackerBasics:
    """Test basic tracker operations."""

    def test_record_new_assumption(self, tracker):
        """Tracker can record a new assumption."""
        assumption_id = tracker.record(
            content="The file will exist",
            category="fact"
        )
        assert assumption_id is not None
        assert len(tracker.assumptions) == 1

    def test_get_assumption_by_id(self, tracker):
        """Tracker can retrieve an assumption by ID."""
        assumption_id = tracker.record(
            content="Test assumption",
            category="test"
        )
        retrieved = tracker.get(assumption_id)
        assert retrieved is not None
        assert retrieved.content == "Test assumption"

    def test_get_nonexistent_assumption(self, tracker):
        """Tracker returns None for nonexistent ID."""
        result = tracker.get("nonexistent-id")
        assert result is None


class TestAssumptionVerification:
    """Test assumption verification workflow."""

    def test_verify_correct_assumption(self, tracker):
        """Mark an assumption as correct."""
        assumption_id = tracker.record(
            content="API call will succeed",
            category="prediction"
        )
        tracker.verify(assumption_id, correct=True, evidence=["API returned 200"])
        
        assumption = tracker.get(assumption_id)
        assert assumption.status == AssumptionStatus.VERIFIED
        assert assumption.was_correct is True
        assert assumption.verified_at is not None
        assert "API returned 200" in assumption.evidence

    def test_verify_incorrect_assumption(self, tracker):
        """Mark an assumption as incorrect."""
        assumption_id = tracker.record(
            content="Response time < 100ms",
            category="prediction"
        )
        tracker.verify(assumption_id, correct=False, evidence=["Actual: 250ms"])
        
        assumption = tracker.get(assumption_id)
        assert assumption.status == AssumptionStatus.VERIFIED
        assert assumption.was_correct is False
        assert "Actual: 250ms" in assumption.evidence

    def test_cannot_verify_already_verified(self, tracker):
        """Once verified, assumption cannot be modified."""
        assumption_id = tracker.record(
            content="Test assumption",
            category="test"
        )
        tracker.verify(assumption_id, correct=True)
        
        with pytest.raises(ValueError, match="already verified"):
            tracker.verify(assumption_id, correct=False)


class TestStaleAssumptions:
    """Test detection of stale (unverified) assumptions."""

    def test_find_stale_assumptions(self, tracker):
        """Tracker can find assumptions that haven't been verified."""
        # Create assumptions with different ages
        old_id = tracker.record(
            content="Old assumption from yesterday",
            category="test",
            timestamp=datetime.now() - timedelta(days=3)
        )
        recent_id = tracker.record(
            content="Recent assumption",
            category="test",
            timestamp=datetime.now() - timedelta(hours=1)
        )
        
        stale = tracker.get_stale(days_old=2)
        assert len(stale) == 1
        assert stale[0].id == old_id

    def test_get_all_open_assumptions(self, tracker):
        """Get all unverified assumptions regardless of age."""
        tracker.record(content="Assumption 1", category="test")
        tracker.record(content="Assumption 2", category="test")
        
        open_assumptions = tracker.get_open()
        assert len(open_assumptions) == 2


class TestAccuracyReporting:
    """Test accuracy metrics and reporting."""

    def test_calculate_accuracy_rate(self, tracker):
        """Tracker calculates correct percentage of verified assumptions."""
        # Record and verify some assumptions
        tracker.record(content="A1", category="test")  # Open
        id_correct = tracker.record(content="A2", category="test")
        id_incorrect = tracker.record(content="A3", category="test")
        
        tracker.verify(id_correct, correct=True)
        tracker.verify(id_incorrect, correct=False)
        
        accuracy = tracker.get_accuracy()
        assert accuracy == 0.5  # 50% correct

    def test_empty_accuracy(self, tracker):
        """Accuracy is None when no assumptions verified."""
        tracker.record(content="Only open", category="test")
        accuracy = tracker.get_accuracy()
        assert accuracy is None

    def test_get_verification_summary(self, tracker):
        """Get a summary of all verification activity."""
        # Setup some data
        tracker.record(content="Open 1", category="test")
        tracker.record(content="Open 2", category="test")
        correct_id = tracker.record(content="Correct", category="test")
        incorrect_id = tracker.record(content="Incorrect", category="test")
        
        tracker.verify(correct_id, correct=True)
        tracker.verify(incorrect_id, correct=False)
        
        summary = tracker.get_summary()
        assert summary['total'] == 4
        assert summary['open'] == 2
        assert summary['verified'] == 2
        assert summary['correct'] == 1
        assert summary['incorrect'] == 1
        assert summary['accuracy'] == 0.5


class TestPersistence:
    """Test that assumptions persist to disk."""

    def test_save_and_load(self, tracker):
        """Assumptions are saved to file and loaded back."""
        tracker.record(content="Persisted assumption", category="test")
        tracker.record(content="Second", category="test")
        
        # Simulate loading a new tracker instance
        new_tracker = AssumptionTracker(storage_path=tracker.storage_path)
        assert len(new_tracker.assumptions) == 2
        
        assumption = new_tracker.assumptions[0]
        assert assumption.content in ["Persisted assumption", "Second"]


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_verify_nonexistent_raises_error(self, tracker):
        """Verifying a nonexistent assumption raises an error."""
        with pytest.raises(ValueError, match="not found"):
            tracker.verify("fake-id-123", correct=True)

    def test_empty_content_rejected(self, tracker):
        """Assumption with empty content is rejected."""
        with pytest.raises(ValueError, match="content.*required"):
            tracker.record(content="", category="test")

    def test_whitespace_only_content_rejected(self, tracker):
        """Whitespace-only content is rejected."""
        with pytest.raises(ValueError, match="content.*required"):
            tracker.record(content="   ", category="test")


class TestCategoryManagement:
    """Test assumption categorization."""

    def test_get_by_category(self, tracker):
        """Can filter assumptions by category."""
        tracker.record(content="Fact 1", category="fact")
        tracker.record(content="Prediction 1", category="prediction")
        tracker.record(content="Fact 2", category="fact")
        
        facts = tracker.get_by_category("fact")
        assert len(facts) == 2
        
        predictions = tracker.get_by_category("prediction")
        assert len(predictions) == 1

    def test_category_summary(self, tracker):
        """Get count of assumptions per category."""
        tracker.record(content="F1", category="fact")
        tracker.record(content="F2", category="fact")
        tracker.record(content="P1", category="prediction")
        
        summary = tracker.get_category_summary()
        assert summary["fact"] == 2
        assert summary["prediction"] == 1


class TestAssumptionExpiration:
    """Test automatic expiration of assumptions."""

    def test_expire_old_assumptions(self, tracker):
        """Can mark old assumptions as expired without verification."""
        old_id = tracker.record(
            content="Expired assumption",
            category="test",
            timestamp=datetime.now() - timedelta(days=30)
        )
        
        expired = tracker.expire_old(days_old=7)
        assert len(expired) == 1
        
        assumption = tracker.get(old_id)
        assert assumption.status == AssumptionStatus.EXPIRED


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
