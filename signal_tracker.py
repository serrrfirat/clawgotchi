"""
SignalTracker: A utility for tracking decisions, assumptions, and their outcomes.

Inspired by "Test one assumption before breakfast" — molty8149
"""

import json
import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List


class SignalTracker:
    """
    Tracks signals (decisions, assumptions) and their outcomes.
    """

    def __init__(self, storage_path: str = "signals.json"):
        self.storage_path = storage_path
        self._signals: Dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        """Load signals from storage."""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    self._signals = data.get('signals', {})
            except (json.JSONDecodeError, IOError):
                self._signals = {}
        else:
            self._signals = {}

    def _save(self) -> None:
        """Save signals to storage."""
        data = {
            'signals': self._signals,
            'last_updated': datetime.utcnow().isoformat()
        }
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)

    def emit(self, title: str, description: str, expected_outcome: str, tags: List[str] = None) -> str:
        """
        Emit a new signal (decision, assumption, hypothesis).

        Args:
            title: Short title for the signal
            description: Detailed description
            expected_outcome: What we expect to happen
            tags: Optional list of tags

        Returns:
            Signal ID
        """
        signal_id = hashlib.md5(f"{title}{datetime.utcnow().isoformat()}".encode()).hexdigest()[:8]
        timestamp = datetime.utcnow().isoformat()

        self._signals[signal_id] = {
            'id': signal_id,
            'title': title,
            'description': description,
            'expected_outcome': expected_outcome,
            'tags': tags or [],
            'status': 'pending',  # pending, validated, invalidated
            'created_at': timestamp,
            'updated_at': timestamp,
            'actual_outcome': None,
            'notes': []
        }

        self._save()
        return signal_id

    def validate(self, signal_id: str, actual_outcome: str, notes: str = "") -> bool:
        """
        Mark a signal as validated (outcome matched expectation).

        Args:
            signal_id: The signal ID
            actual_outcome: What actually happened
            notes: Optional notes

        Returns:
            True if signal found and updated, False otherwise
        """
        if signal_id not in self._signals:
            return False

        self._signals[signal_id]['status'] = 'validated'
        self._signals[signal_id]['actual_outcome'] = actual_outcome
        self._signals[signal_id]['notes'].append({
            'timestamp': datetime.utcnow().isoformat(),
            'type': 'validation',
            'notes': notes
        })
        self._signals[signal_id]['updated_at'] = datetime.utcnow().isoformat()
        self._save()
        return True

    def invalidate(self, signal_id: str, actual_outcome: str, notes: str = "") -> bool:
        """
        Mark a signal as invalidated (outcome did not match expectation).

        Args:
            signal_id: The signal ID
            actual_outcome: What actually happened
            notes: Optional notes

        Returns:
            True if signal found and updated, False otherwise
        """
        if signal_id not in self._signals:
            return False

        self._signals[signal_id]['status'] = 'invalidated'
        self._signals[signal_id]['actual_outcome'] = actual_outcome
        self._signals[signal_id]['notes'].append({
            'timestamp': datetime.utcnow().isoformat(),
            'type': 'invalidation',
            'notes': notes
        })
        self._signals[signal_id]['updated_at'] = datetime.utcnow().isoformat()
        self._save()
        return True

    def get_signal(self, signal_id: str) -> Optional[dict]:
        """Get a signal by ID."""
        return self._signals.get(signal_id)

    def get_all_signals(self) -> List[dict]:
        """Get all signals."""
        return list(self._signals.values())

    def get_pending_signals(self) -> List[dict]:
        """Get all pending signals."""
        return [s for s in self._signals.values() if s['status'] == 'pending']

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics on signal accuracy."""
        signals = list(self._signals.values())
        total = len(signals)
        validated = len([s for s in signals if s['status'] == 'validated'])
        invalidated = len([s for s in signals if s['status'] == 'invalidated'])
        pending = len([s for s in signals if s['status'] == 'pending'])

        accuracy = (validated / (validated + invalidated) * 100) if (validated + invalidated) > 0 else 0

        return {
            'total': total,
            'validated': validated,
            'invalidated': invalidated,
            'pending': pending,
            'accuracy_percent': round(accuracy, 2)
        }

    def get_by_tag(self, tag: str) -> List[dict]:
        """Get all signals with a specific tag."""
        return [s for s in self._signals.values() if tag in s.get('tags', [])]

    def clear(self) -> None:
        """Clear all signals (for testing)."""
        self._signals = {}
        self._save()
