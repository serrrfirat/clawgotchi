"""
Permission Friction Tracker
Measures how users interact with permission manifests during skill installation.
Tracks review time, escalation rates, and generates friction metrics.
"""

import time
import json
import os
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Set
from datetime import datetime
from pathlib import Path


class PermissionDecision(Enum):
    """User decisions on permission requests."""
    APPROVED = "approved"
    DENIED = "denied"
    ESCALATED = "escalated"  # Non-default permissions
    SKIPPED = "skipped"


@dataclass
class PermissionRequest:
    """A single permission being requested."""
    permission_type: str
    requested_value: str
    is_default: bool  # True if this is the default (least privilege)
    category: str = "general"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "permission_type": self.permission_type,
            "requested_value": self.requested_value,
            "is_default": self.is_default,
            "category": self.category
        }


@dataclass
class FrictionEvent:
    """Records a single friction event during permission review."""
    skill_id: str
    skill_name: str
    timestamp: str
    permission: PermissionRequest
    decision: PermissionDecision
    review_time_ms: int  # Time spent reviewing this permission
    previous_decision: Optional[str] = None  # Previous user decision for this skill
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "skill_name": self.skill_name,
            "timestamp": self.timestamp,
            "permission": self.permission.to_dict(),
            "decision": self.decision.value,
            "review_time_ms": self.review_time_ms,
            "previous_decision": self.previous_decision
        }


@dataclass
class FrictionMetrics:
    """Aggregated friction metrics for a skill or collection."""
    skill_id: str
    total_permissions: int
    default_permissions: int
    escalated_permissions: int
    denied_permissions: int
    total_review_time_ms: int
    average_review_time_ms: int
    median_review_time_ms: int
    
    # Conversion metrics
    install_started: int = 0
    install_completed: int = 0
    install_abandoned: int = 0
    install_skipped: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "permissions": {
                "total": self.total_permissions,
                "default": self.default_permissions,
                "escalated": self.escalated_permissions,
                "denied": self.denied_permissions
            },
            "review_time": {
                "total_ms": self.total_review_time_ms,
                "average_ms": self.average_review_time_ms,
                "median_ms": self.median_review_time_ms
            },
            "conversion": {
                "started": self.install_started,
                "completed": self.install_completed,
                "abandoned": self.install_abandoned,
                "skipped": self.install_skipped
            },
            "friction_score": self.calculate_friction_score()
        }
    
    def calculate_friction_score(self) -> float:
        """
        Calculate a friction score (0-100).
        Higher = more friction = potentially concerning.
        
        Factors:
        - Review time too short (<2s per permission = low attention)
        - Too many escalations
        - High abandonment rate
        """
        if self.total_permissions == 0:
            return 0.0
        
        # Short review penalty
        avg_time_perm = self.average_review_time_ms / 1000 if self.average_review_time_ms > 0 else 0
        time_score = min(30, max(0, 30 - avg_time_perm)) if avg_time_perm < 30 else 0
        
        # Escalation penalty (users should be thoughtful about non-defaults)
        escalation_rate = self.escalated_permissions / self.total_permissions
        escalation_score = escalation_rate * 30
        
        # Abandonment penalty
        if self.install_started > 0:
            abandonment_rate = self.install_abandoned / self.install_started
            abandonment_score = abandonment_rate * 40
        else:
            abandonment_score = 0
        
        return round(time_score + escalation_score + abandonment_score, 1)


class PermissionFrictionTracker:
    """
    Tracks friction metrics for permission reviews during skill installation.
    
    Metrics collected:
    - Review time per permission
    - Approval/denial/escalation rates
    - Installation completion vs abandonment
    - Attention span (too fast = potential security theater)
    """
    
    DEFAULT_REVIEW_THRESHOLD_MS = 2000  # <2s = too fast to read
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize the friction tracker.
        
        Args:
            storage_path: Path to store friction event logs
        """
        self.storage_path = storage_path
        self.current_session: Optional[Dict[str, Any]] = None
        self.events: List[FrictionEvent] = []
        
        # Load existing events if storage path provided
        if storage_path and os.path.exists(storage_path):
            self._load_events()
    
    def _load_events(self):
        """Load events from storage."""
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
                self.events = [FrictionEvent(**e) for e in data.get('events', [])]
        except (json.JSONDecodeError, OSError, KeyError):
            self.events = []
    
    def _save_events(self):
        """Save events to storage."""
        if not self.storage_path:
            return
        
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        
        with open(self.storage_path, 'w') as f:
            json.dump({
                'events': [e.to_dict() for e in self.events],
                'last_updated': datetime.utcnow().isoformat()
            }, f, indent=2)
    
    def start_session(self, skill_id: str, skill_name: str, permission_count: int):
        """
        Start tracking a new installation session.
        
        Args:
            skill_id: Unique identifier for the skill
            skill_name: Human-readable skill name
            permission_count: Number of permissions being requested
        """
        self.current_session = {
            'skill_id': skill_id,
            'skill_name': skill_name,
            'permission_count': permission_count,
            'start_time': time.time(),
            'permission_index': 0,
            'permissions': [],
            'decisions': [],
            'review_times': []
        }
    
    def record_permission_view(self, permission: PermissionRequest) -> int:
        """
        Record that a user viewed a permission.
        Returns the time spent viewing (ms) since last view.
        """
        if not self.current_session:
            return 0
        
        current_time = time.time()
        
        if self.current_session['permission_index'] > 0:
            elapsed_ms = int((current_time - self.current_session.get('_last_view_time', current_time)) * 1000)
            self.current_session['review_times'].append(elapsed_ms)
        else:
            elapsed_ms = 0
        
        self.current_session['_last_view_time'] = current_time
        self.current_session['permissions'].append(permission)
        self.current_session['permission_index'] += 1
        
        return elapsed_ms
    
    def record_decision(self, decision: PermissionDecision, previous_decision: Optional[str] = None) -> FrictionEvent:
        """
        Record a user's decision on the current permission.
        
        Args:
            decision: User's decision
            previous_decision: Previous decision if re-installing
            
        Returns:
            FrictionEvent for this decision
        """
        if not self.current_session:
            raise RuntimeError("No active session")
        
        permission = self.current_session['permissions'][-1]
        review_time = self.current_session['review_times'][-1] if self.current_session['review_times'] else 0
        
        event = FrictionEvent(
            skill_id=self.current_session['skill_id'],
            skill_name=self.current_session['skill_name'],
            timestamp=datetime.utcnow().isoformat(),
            permission=permission,
            decision=decision,
            review_time_ms=review_time,
            previous_decision=previous_decision
        )
        
        self.events.append(event)
        self.current_session['decisions'].append(decision)
        self._save_events()
        
        return event
    
    def complete_session(self, outcome: str) -> FrictionMetrics:
        """
        Complete the current installation session.
        
        Args:
            outcome: 'completed', 'abandoned', or 'skipped'
            
        Returns:
            FrictionMetrics for this session
        """
        if not self.current_session:
            raise RuntimeError("No active session")
        
        end_time = time.time()
        total_time_ms = int((end_time - self.current_session['start_time']) * 1000)
        
        # Count decisions
        decisions = self.current_session['decisions']
        default_count = sum(1 for d, p in zip(decisions, self.current_session['permissions']) 
                           if d == PermissionDecision.APPROVED and p.is_default)
        escalated_count = sum(1 for d in decisions if d == PermissionDecision.ESCALATED)
        denied_count = sum(1 for d in decisions if d == PermissionDecision.DENIED)
        
        # Calculate review time stats
        review_times = self.current_session['review_times']
        avg_time = sum(review_times) // len(review_times) if review_times else 0
        median_time = self._median(review_times) if review_times else 0
        
        metrics = FrictionMetrics(
            skill_id=self.current_session['skill_id'],
            total_permissions=self.current_session['permission_count'],
            default_permissions=default_count,
            escalated_permissions=escalated_count,
            denied_permissions=denied_count,
            total_review_time_ms=total_time_ms,
            average_review_time_ms=avg_time,
            median_review_time_ms=median_time,
            install_started=1,
            install_completed=1 if outcome == 'completed' else 0,
            install_abandoned=1 if outcome == 'abandoned' else 0,
            install_skipped=1 if outcome == 'skipped' else 0
        )
        
        self.current_session = None
        return metrics
    
    def _median(self, values: List[int]) -> int:
        """Calculate median of a list."""
        if not values:
            return 0
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        mid = n // 2
        if n % 2 == 0:
            return (sorted_vals[mid - 1] + sorted_vals[mid]) // 2
        return sorted_vals[mid]
    
    def get_skill_metrics(self, skill_id: str) -> Optional[FrictionMetrics]:
        """Get aggregated metrics for a specific skill."""
        skill_events = [e for e in self.events if e.skill_id == skill_id]
        
        if not skill_events:
            return None
        
        decisions = [e.decision for e in skill_events]
        review_times = [e.review_time_ms for e in skill_events]
        
        # Group by permission type for counting
        default_count = sum(1 for e, p in zip(skill_events, [e.permission for e in skill_events]) 
                           if e.decision == PermissionDecision.APPROVED and p.is_default)
        
        return FrictionMetrics(
            skill_id=skill_id,
            total_permissions=len(skill_events),
            default_permissions=default_count,
            escalated_permissions=sum(1 for d in decisions if d == PermissionDecision.ESCALATED),
            denied_permissions=sum(1 for d in decisions if d == PermissionDecision.DENIED),
            total_review_time_ms=sum(review_times),
            average_review_time_ms=sum(review_times) // len(review_times) if review_times else 0,
            median_review_time_ms=self._median(review_times)
        )
    
    def get_aggregate_metrics(self) -> Dict[str, Any]:
        """Get aggregate metrics across all skills."""
        if not self.events:
            return {"total_sessions": 0, "message": "No friction data collected"}
        
        skills = set(e.skill_id for e in self.events)
        decisions = [e.decision for e in self.events]
        review_times = [e.review_time_ms for e in self.events]
        
        # Fast review detection
        fast_reviews = sum(1 for t in review_times if t < self.DEFAULT_REVIEW_THRESHOLD_MS)
        
        return {
            "total_skills": len(skills),
            "total_permission_reviews": len(self.events),
            "approval_rate": sum(1 for d in decisions if d == PermissionDecision.APPROVED) / len(decisions) if decisions else 0,
            "escalation_rate": sum(1 for d in decisions if d == PermissionDecision.ESCALATED) / len(decisions) if decisions else 0,
            "denial_rate": sum(1 for d in decisions if d == PermissionDecision.DENIED) / len(decisions) if decisions else 0,
            "fast_review_rate": fast_reviews / len(review_times) if review_times else 0,
            "average_review_time_ms": sum(review_times) // len(review_times) if review_times else 0,
            "median_review_time_ms": self._median(review_times)
        }
    
    def generate_friction_report(self, skill_id: Optional[str] = None) -> str:
        """Generate a human-readable friction report."""
        if skill_id:
            metrics = self.get_skill_metrics(skill_id)
            if not metrics:
                return f"📊 No friction data for skill: {skill_id}"
            
            data = metrics.to_dict()
            title = f"📊 Permission Friction Report: {skill_id}"
        else:
            data = self.get_aggregate_metrics()
            title = "📊 Aggregate Permission Friction Report"
        
        lines = [title, "=" * 50]
        
        if "total_skills" in data:
            # Aggregate report
            lines.append(f"\n🔢 Overview:")
            lines.append(f"  • Skills tracked: {data['total_skills']}")
            lines.append(f"  • Total permission reviews: {data['total_permission_reviews']}")
            lines.append(f"\n⏱️ Review Time:")
            lines.append(f"  • Average: {data['average_review_time_ms']/1000:.1f}s")
            lines.append(f"  • Median: {data['median_review_time_ms']/1000:.1f}s")
            lines.append(f"  • Fast reviews (<2s): {data['fast_review_rate']*100:.1f}%")
            lines.append(f"\n✅ Decisions:")
            lines.append(f"  • Approval rate: {data['approval_rate']*100:.1f}%")
            lines.append(f"  • Escalation rate: {data['escalation_rate']*100:.1f}%")
            lines.append(f"  • Denial rate: {data['denial_rate']*100:.1f}%")
        else:
            # Single skill report
            p = data['permissions']
            lines.append(f"\n📋 Permissions:")
            lines.append(f"  • Total: {p['total']}")
            lines.append(f"  • Default (auto-approved): {p['default']}")
            lines.append(f"  • Escalated: {p['escalated']}")
            lines.append(f"  • Denied: {p['denied']}")
            lines.append(f"\n⏱️ Review Time:")
            lines.append(f"  • Total: {data['review_time']['total_ms']/1000:.1f}s")
            lines.append(f"  • Average: {data['review_time']['average_ms']/1000:.1f}s")
            lines.append(f"  • Median: {data['review_time']['median_ms']/1000:.1f}s")
            lines.append(f"\n🎯 Friction Score: {data['friction_score']}/100")
        
        return "\n".join(lines)
    
    def export_metrics(self, skill_id: Optional[str] = None) -> Dict[str, Any]:
        """Export metrics for external analysis."""
        if skill_id:
            metrics = self.get_skill_metrics(skill_id)
            return metrics.to_dict() if metrics else {}
        return self.get_aggregate_metrics()


def create_friction_tracker(storage_path: Optional[str] = None) -> PermissionFrictionTracker:
    """Convenience function to create a friction tracker."""
    return PermissionFrictionTracker(storage_path=storage_path)


if __name__ == '__main__':
    import sys
    
    # Demo usage
    tracker = create_friction_tracker('/tmp/friction_events.json')
    
    # Simulate a session
    tracker.start_session('skill_weather', 'Weather Skill', 3)
    
    # Simulate permission views and decisions
    perm1 = PermissionRequest('filesystem', './data', True, 'storage')
    tracker.record_permission_view(perm1)
    time.sleep(0.5)  # Fast review
    tracker.record_decision(PermissionDecision.APPROVED)
    
    perm2 = PermissionRequest('network', 'api.weather.gov', False, 'external')
    tracker.record_permission_view(perm2)
    time.sleep(5)  # Thoughtful review
    tracker.record_decision(PermissionDecision.ESCALATED)
    
    perm3 = PermissionRequest('env_vars', 'API_KEY', False, 'secrets')
    tracker.record_permission_view(perm3)
    time.sleep(8)  # Careful review
    tracker.record_decision(PermissionDecision.DENIED)
    
    metrics = tracker.complete_session('completed')
    
    print(tracker.generate_friction_report())
    print(f"\n📦 Exported metrics:\n{json.dumps(metrics.to_dict(), indent=2)}")
