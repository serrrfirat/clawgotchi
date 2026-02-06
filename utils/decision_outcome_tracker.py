"""
Decision Outcome Tracker - Track agent decisions and verify their outcomes.

Complements Assumption Tracker by tracking explicit decisions/predictions
with verifiable outcomes and deadlines.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path


class DecisionOutcomeTracker:
    """Track decisions, predictions, and verify their outcomes."""

    def __init__(self, storage_path: str = None):
        if storage_path is None:
            workspace = os.environ.get('WORKSPACE', '/Users/firatsertgoz/Documents/clawgotchi')
            storage_path = os.path.join(workspace, 'data', 'decisions.json')
        self.storage_path = storage_path
        self._ensure_storage()

    def _ensure_storage(self):
        """Ensure storage file exists."""
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        if not os.path.exists(self.storage_path):
            self._save({'decisions': []})

    def _load(self) -> dict:
        """Load decisions from storage."""
        try:
            with open(self.storage_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {'decisions': []}

    def _save(self, data: dict):
        """Save decisions to storage."""
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)

    def record_decision(
        self,
        decision_id: str,
        description: str,
        expected_outcome: str,
        deadline: str,  # ISO format
        context: str = None,
        tags: list = None
    ) -> dict:
        """
        Record a decision with expected outcome and deadline.

        Args:
            decision_id: Unique identifier for the decision
            description: What decision was made
            expected_outcome: What outcome is expected
            deadline: ISO format deadline date
            context: Additional context
            tags: Tags for categorization

        Returns:
            The recorded decision
        """
        decisions = self._load()
        
        # Check for duplicate
        for d in decisions['decisions']:
            if d['id'] == decision_id:
                raise ValueError(f"Decision {decision_id} already exists")

        decision = {
            'id': decision_id,
            'description': description,
            'expected_outcome': expected_outcome,
            'deadline': deadline,
            'context': context,
            'tags': tags or [],
            'status': 'pending',  # pending, verified, falsified, expired
            'actual_outcome': None,
            'recorded_at': datetime.now().isoformat(),
            'verified_at': None,
            'verification_notes': None
        }
        
        decisions['decisions'].append(decision)
        self._save(decisions)
        return decision

    def mark_verifiable(self, decision_id: str, actual_outcome: str, notes: str = None):
        """
        Mark a decision as having a verifiable outcome.

        Args:
            decision_id: The decision to mark
            actual_outcome: What actually happened
            notes: Optional verification notes
        """
        decisions = self._load()
        
        for d in decisions['decisions']:
            if d['id'] == decision_id:
                d['actual_outcome'] = actual_outcome
                d['verification_notes'] = notes
                d['verified_at'] = datetime.now().isoformat()
                self._save(decisions)
                return d
        
        raise ValueError(f"Decision {decision_id} not found")

    def verify_outcome(self, decision_id: str) -> dict:
        """
        Verify whether a decision's outcome matches expectations.

        Args:
            decision_id: The decision to verify

        Returns:
            Verification result with match status
        """
        decisions = self._load()
        
        for d in decisions['decisions']:
            if d['id'] == decision_id:
                if d['actual_outcome'] is None:
                    raise ValueError(f"Decision {decision_id} has no recorded outcome")
                
                # Simple containment check: does actual contain expected?
                # Normalize for comparison
                expected = d['expected_outcome'].lower().strip()
                actual = d['actual_outcome'].lower().strip()
                
                # Check if expected outcome is found in actual outcome
                match = expected in actual or actual in expected
                
                d['status'] = 'verified' if match else 'falsified'
                d['verified_at'] = datetime.now().isoformat()
                self._save(decisions)
                return {
                    'decision_id': decision_id,
                    'expected': d['expected_outcome'],
                    'actual': d['actual_outcome'],
                    'status': d['status'],
                    'match': match
                }
        
        raise ValueError(f"Decision {decision_id} not found")

    def get_pending_decisions(self) -> list:
        """Get all decisions pending outcome verification."""
        decisions = self._load()
        return [d for d in decisions['decisions'] if d['status'] == 'pending']

    def get_expired_decisions(self) -> list:
        """Get decisions past their deadline with no outcome recorded."""
        decisions = self._load()
        now = datetime.now()
        expired = []
        
        for d in decisions['decisions']:
            if d['status'] == 'pending':
                deadline = datetime.fromisoformat(d['deadline'])
                if now > deadline:
                    d['status'] = 'expired'
                    expired.append(d)
        
        if expired:
            self._save(decisions)
        
        return expired

    def get_verified_decisions(self) -> list:
        """Get all verified decisions with their outcomes."""
        decisions = self._load()
        return [d for d in decisions['decisions'] if d['status'] in ['verified', 'falsified']]

    def get_statistics(self) -> dict:
        """Get decision tracking statistics."""
        decisions = self._load()
        all_decisions = decisions['decisions']
        
        pending = sum(1 for d in all_decisions if d['status'] == 'pending')
        verified = sum(1 for d in all_decisions if d['status'] == 'verified')
        falsified = sum(1 for d in all_decisions if d['status'] == 'falsified')
        expired = sum(1 for d in all_decisions if d['status'] == 'expired')
        
        accuracy = (verified / (verified + falsified) * 100) if (verified + falsified) > 0 else 0
        
        return {
            'total': len(all_decisions),
            'pending': pending,
            'verified': verified,
            'falsified': falsified,
            'expired': expired,
            'accuracy_rate': round(accuracy, 2)
        }

    def cleanup_old_decisions(self, days: int = 90) -> int:
        """
        Remove decisions older than specified days.

        Args:
            days: Minimum age of decisions to remove

        Returns:
            Number of decisions removed
        """
        decisions = self._load()
        cutoff = datetime.now() - timedelta(days=days)
        original_count = len(decisions['decisions'])
        
        decisions['decisions'] = [
            d for d in decisions['decisions']
            if datetime.fromisoformat(d['recorded_at']) > cutoff
            or d['status'] not in ['verified', 'falsified']
        ]
        
        removed = original_count - len(decisions['decisions'])
        if removed > 0:
            self._save(decisions)
        
        return removed
