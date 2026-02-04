from __future__ import annotations

"""
Tests for assumption_tracker.py - Meta-cognitive assumption verification system.

Tests the assumption tracking module that records, verifies, and reports
on assumptions I've made about the world.
"""

import json
import os
from datetime import datetime, timedelta
from enum import Enum
import uuid


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
        timestamp: datetime = None,
        confidence: float = 0.8
    ):
        if not content or not content.strip():
            raise ValueError("Assumption content is required")
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        
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
        self.confidence = confidence
        self.confidence_history = [(timestamp or datetime.now(), confidence)]
    
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
            "evidence": self.evidence,
            "confidence": self.confidence,
            "confidence_history": [
                (ts.isoformat(), conf) for ts, conf in self.confidence_history
            ]
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Assumption":
        """Create from dictionary (JSON deserialization)."""
        assumption = cls(
            content=data["content"],
            category=data.get("category", "general"),
            context=data.get("context"),
            expected_verification=datetime.fromisoformat(data["expected_verification"]) if data.get("expected_verification") else None,
            timestamp=datetime.fromisoformat(data["timestamp"]),
            confidence=data.get("confidence", 0.8)
        )
        assumption.id = data["id"]
        assumption.status = AssumptionStatus(data["status"])
        assumption.verified_at = datetime.fromisoformat(data["verified_at"]) if data.get("verified_at") else None
        assumption.was_correct = data.get("was_correct")
        assumption.evidence = data.get("evidence", [])
        assumption.confidence_history = [
            (datetime.fromisoformat(ts), conf) 
            for ts, conf in data.get("confidence_history", [])
        ]
        return assumption


class AssumptionTracker:
    """
    Tracks assumptions I've made and verifies them over time.
    
    This helps address "verification debt" - the gap between what I assume
    and what I've actually confirmed to be true.
    """
    
    def __init__(self, storage_path: str = None):
        if storage_path is None:
            from config import ASSUMPTIONS_FILE
            storage_path = str(ASSUMPTIONS_FILE)
        self.storage_path = storage_path
        self.assumptions: list[Assumption] = []
        self._load()
    
    def record(
        self,
        content: str,
        category: str = "general",
        context: str = None,
        expected_verification: datetime = None,
        timestamp: datetime = None,
        confidence: float = 0.8
    ) -> str:
        """
        Record a new assumption.
        
        Args:
            content: The assumption statement
            category: Category (fact, prediction, preference, etc.)
            context: Why I believe this
            expected_verification: When I expect to verify this
            confidence: Initial confidence (0.0 to 1.0, default 0.8)
            
        Returns:
            The assumption ID
        """
        assumption = Assumption(
            content=content,
            category=category,
            context=context,
            expected_verification=expected_verification,
            timestamp=timestamp,
            confidence=confidence
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
        
        # Set final confidence based on correctness
        assumption.confidence = 1.0 if correct else 0.0
        assumption.confidence_history.append((datetime.now(), assumption.confidence))
        
        self._save()
    
    def update_confidence(self, assumption_id: str, new_confidence: float) -> None:
        """
        Update the confidence of an assumption.
        
        Args:
            assumption_id: The assumption to update
            new_confidence: New confidence value (0.0 to 1.0)
        """
        assumption = self.get(assumption_id)
        if assumption is None:
            raise ValueError(f"Assumption not found: {assumption_id}")
        if not 0.0 <= new_confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")
        if assumption.status == AssumptionStatus.VERIFIED:
            raise ValueError(f"Cannot update confidence of verified assumption: {assumption_id}")
        
        assumption.confidence = new_confidence
        assumption.confidence_history.append((datetime.now(), new_confidence))
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
    
    def get_by_confidence(self, min_confidence: float = 0.0, max_confidence: float = 1.0) -> list[Assumption]:
        """Get assumptions with confidence in the specified range."""
        return [
            a for a in self.assumptions
            if min_confidence <= a.confidence <= max_confidence and a.status == AssumptionStatus.OPEN
        ]
    
    def get_low_confidence(self, threshold: float = 0.5) -> list[Assumption]:
        """Get open assumptions with confidence below threshold."""
        return self.get_by_confidence(max_confidence=threshold)
    
    def get_high_confidence(self, threshold: float = 0.8) -> list[Assumption]:
        """Get open assumptions with confidence above threshold."""
        return self.get_by_confidence(min_confidence=threshold)
    
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


if __name__ == "__main__":
    # Quick demo
    tracker = AssumptionTracker("/tmp/test_assumptions.json")
    
    # Record some assumptions
    print("Recording assumptions...")
    id1 = tracker.record(
        content="The API will respond within 2 seconds",
        category="prediction",
        context="Previous tests show ~500ms response time"
    )
    id2 = tracker.record(
        content="User is in Dubai timezone",
        category="fact",
        context="USER.md shows Asia/Dubai"
    )
    
    # Verify one
    print("\nVerifying assumptions...")
    tracker.verify(id1, correct=True, evidence=["Response time: 892ms"])
    tracker.verify(id2, correct=True)
    
    # Get summary
    print("\nSummary:")
    print(tracker.get_summary())
    print(f"\nAccuracy: {tracker.get_accuracy():.1%}")
