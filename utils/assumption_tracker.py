"""Assumption Tracker - Track and validate assumptions made by the agent."""

import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from uuid import uuid4

DATA_DIR = os.environ.get('CLAWGOTCHI_DATA_DIR', 'memory')
ASSUMPTIONS_FILE = os.environ.get('CLAWGOTCHI_ASSUMPTIONS_FILE', os.path.join(DATA_DIR, 'assumptions.json'))


def _load_assumptions() -> List[Dict]:
    if not os.path.exists(ASSUMPTIONS_FILE):
        return []
    with open(ASSUMPTIONS_FILE, 'r') as f:
        return json.load(f)


def _save_assumptions(assumptions: List[Dict]) -> None:
    os.makedirs(os.path.dirname(ASSUMPTIONS_FILE), exist_ok=True)
    with open(ASSUMPTIONS_FILE, 'w') as f:
        json.dump(assumptions, f, indent=2)


def add_assumption(text: str, context: str = "", expires_hours: int = 24) -> str:
    assumptions = _load_assumptions()
    now = datetime.now()
    assumption = {
        'id': str(uuid4())[:8],
        'text': text,
        'context': context,
        'status': 'open',
        'created_at': now.isoformat(),
        'expires_at': (now + timedelta(hours=expires_hours)).isoformat(),
        'verified_at': None,
        'invalidated_at': None,
        'invalidation_reason': None,
        'notes': []
    }
    assumptions.append(assumption)
    _save_assumptions(assumptions)
    return assumption['id']


def verify_assumption(ass_id: str) -> bool:
    assumptions = _load_assumptions()
    for ass in assumptions:
        if ass['id'] == ass_id:
            ass['status'] = 'verified'
            ass['verified_at'] = datetime.now().isoformat()
            _save_assumptions(assumptions)
            return True
    return False


def invalidate_assumption(ass_id: str, reason: str) -> bool:
    assumptions = _load_assumptions()
    for ass in assumptions:
        if ass['id'] == ass_id:
            ass['status'] = 'invalid'
            ass['invalidated_at'] = datetime.now().isoformat()
            ass['invalidation_reason'] = reason
            _save_assumptions(assumptions)
            return True
    return False


def list_assumptions(status: Optional[str] = None) -> List[Dict]:
    assumptions = _load_assumptions()
    if status:
        return [a for a in assumptions if a['status'] == status]
    return assumptions


def get_assumption(ass_id: str) -> Optional[Dict]:
    assumptions = _load_assumptions()
    for ass in assumptions:
        if ass['id'] == ass_id:
            return ass
    return None


def add_note(ass_id: str, note: str) -> bool:
    assumptions = _load_assumptions()
    for ass in assumptions:
        if ass['id'] == ass_id:
            ass['notes'].append({'text': note, 'at': datetime.now().isoformat()})
            _save_assumptions(assumptions)
            return True
    return False


def cleanup_expired() -> int:
    assumptions = _load_assumptions()
    now = datetime.now()
    count = 0
    for ass in assumptions:
        if ass['status'] == 'open':
            expires_at = datetime.fromisoformat(ass['expires_at'])
            if now > expires_at:
                ass['status'] = 'expired'
                count += 1
    if count > 0:
        _save_assumptions(assumptions)
    return count


def check_stale(grace_hours: int = 6) -> List[Dict]:
    assumptions = _load_assumptions()
    now = datetime.now()
    stale = []
    for ass in assumptions:
        if ass['status'] == 'open':
            expires_at = datetime.fromisoformat(ass['expires_at'])
            stale_at = expires_at + timedelta(hours=grace_hours)
            if now > stale_at:
                stale.append(ass)
    return stale


def get_summary() -> Dict:
    assumptions = _load_assumptions()
    return {
        'total': len(assumptions),
        'open': len([a for a in assumptions if a['status'] == 'open']),
        'verified': len([a for a in assumptions if a['status'] == 'verified']),
        'invalid': len([a for a in assumptions if a['status'] == 'invalid']),
        'expired': len([a for a in assumptions if a['status'] == 'expired'])
    }


def clear_all() -> None:
    if os.path.exists(ASSUMPTIONS_FILE):
        os.remove(ASSUMPTIONS_FILE)
