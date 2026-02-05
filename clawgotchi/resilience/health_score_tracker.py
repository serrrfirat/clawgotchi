"""
Health Score Tracker for Agent Resilience Utilities.

Tracks health scores over time, provides trend analysis, and generates
recommendations based on historical patterns.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Dict, Any


class ScoreCategory(str, Enum):
    """Categories for health score tracking."""
    RESILIENCE = "resilience"
    MEMORY = "memory"
    SECURITY = "security"
    PERFORMANCE = "performance"
    AVAILABILITY = "availability"


@dataclass
class HealthEvent:
    """A single health check event."""
    id: str
    timestamp: datetime
    category: ScoreCategory
    score: int  # 0-100
    component: str
    details: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "category": self.category.value if isinstance(self.category, ScoreCategory) else self.category,
            "score": self.score,
            "component": self.component,
            "details": self.details
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HealthEvent":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            category=ScoreCategory(data["category"]),
            score=data["score"],
            component=data["component"],
            details=data.get("details", {})
        )


@dataclass
class CategoryScore:
    """Score breakdown by category."""
    category: str
    average_score: float
    event_count: int
    trend: str  # "improving", "declining", "stable"
    trend_percentage: float


@dataclass
class CurrentHealthScore:
    """Current health snapshot."""
    total_score: int
    category_scores: List[CategoryScore]
    status: str  # "healthy", "degraded", "critical"
    last_updated: datetime


@dataclass
class ScoreTrend:
    """Trend analysis for a category."""
    category: str
    direction: str  # "improving", "declining", "stable"
    change_percentage: float
    start_score: int
    end_score: int


@dataclass
class HealthReport:
    """Full health report with recommendations."""
    overall_score: int
    status: str
    category_breakdown: List[Dict[str, Any]]
    trend: Dict[str, Any]
    recommendations: List[str]
    generated_at: datetime


def load_health_history(path: str) -> List[HealthEvent]:
    """Load health history from JSON file."""
    if not os.path.exists(path):
        return []
    
    try:
        with open(path, 'r') as f:
            data = json.load(f)
            return [HealthEvent.from_dict(e) for e in data]
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def save_health_history(path: str, events: List[HealthEvent]) -> None:
    """Save health history to JSON file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    with open(path, 'w') as f:
        json.dump([e.to_dict() for e in events], f, indent=2)


class HealthScoreTracker:
    """
    Tracks health scores over time for agent resilience utilities.
    
    Features:
    - Record health events by category
    - Calculate current health scores
    - Analyze trends over time
    - Generate recommendations for low scores
    - Persist history to JSON
    """
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize the tracker.
        
        Args:
            db_path: Path to JSON database file. Defaults to ~/.clawgotchi/health_history.json
        """
        if db_path is None:
            home = os.path.expanduser("~")
            db_path = os.path.join(home, ".clawgotchi", "health_history.json")
        
        self.db_path = db_path
        self._events: List[HealthEvent] = []
        self._load_history()
    
    def _load_history(self) -> None:
        """Load history from disk."""
        self._events = load_health_history(self.db_path)
    
    def _save_history(self) -> None:
        """Save history to disk."""
        save_health_history(self.db_path, self._events)
    
    def record_health_event(
        self,
        category: ScoreCategory,
        score: int,
        component: str,
        details: Optional[Dict[str, Any]] = None
    ) -> HealthEvent:
        """
        Record a new health event.
        
        Args:
            category: Score category (resilience, memory, security, etc.)
            score: Health score (0-100)
            component: Name of the component being tracked
            details: Additional details about the health check
            
        Returns:
            The created HealthEvent
        """
        import uuid
        
        event = HealthEvent(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime.now(),
            category=category,
            score=max(0, min(100, score)),  # Clamp to 0-100
            component=component,
            details=details or {}
        )
        
        self._events.append(event)
        self._save_history()
        
        return event
    
    def get_health_history(
        self,
        category: Optional[ScoreCategory] = None,
        hours: Optional[int] = None
    ) -> List[HealthEvent]:
        """
        Get health history with optional filtering.
        
        Args:
            category: Filter by category
            hours: Only return events from last N hours
            
        Returns:
            List of filtered health events
        """
        events = self._events
        
        if category is not None:
            events = [e for e in events if e.category == category]
        
        if hours is not None:
            cutoff = datetime.now() - timedelta(hours=hours)
            events = [e for e in events if e.timestamp >= cutoff]
        
        return sorted(events, key=lambda e: e.timestamp)
    
    def get_current_score(self) -> CurrentHealthScore:
        """Calculate current health score across all categories."""
        if not self._events:
            return CurrentHealthScore(
                total_score=0,
                category_scores=[],
                status="unknown",
                last_updated=datetime.now()
            )
        
        # Group by category
        category_groups: Dict[ScoreCategory, List[HealthEvent]] = {}
        for event in self._events:
            if event.category not in category_groups:
                category_groups[event.category] = []
            category_groups[event.category].append(event)
        
        # Calculate per-category scores
        category_scores = []
        total = 0
        
        for category, events in category_groups.items():
            avg = sum(e.score for e in events) / len(events)
            trend = self._calculate_trend(events)
            
            category_scores.append(CategoryScore(
                category=category.value,
                average_score=round(avg, 1),
                event_count=len(events),
                trend=trend.direction,
                trend_percentage=trend.change_percentage
            ))
            total += avg
        
        overall = int(total / len(category_scores)) if category_scores else 0
        
        return CurrentHealthScore(
            total_score=overall,
            category_scores=sorted(category_scores, key=lambda c: c.average_score),
            status=self._get_status(overall),
            last_updated=max(e.timestamp for e in self._events)
        )
    
    def _calculate_trend(self, events: List[HealthEvent]) -> ScoreTrend:
        """Calculate trend for a list of events."""
        if len(events) < 2:
            return ScoreTrend(
                category=events[0].category.value if events else "",
                direction="stable",
                change_percentage=0.0,
                start_score=events[0].score if events else 0,
                end_score=events[0].score if events else 0
            )
        
        sorted_events = sorted(events, key=lambda e: e.timestamp)
        first = sorted_events[0]
        last = sorted_events[-1]
        
        if first.score == 0:
            change_pct = 0.0
        else:
            change_pct = ((last.score - first.score) / first.score) * 100
        
        if change_pct > 5:
            direction = "improving"
        elif change_pct < -5:
            direction = "declining"
        else:
            direction = "stable"
        
        return ScoreTrend(
            category=first.category.value,
            direction=direction,
            change_percentage=round(change_pct, 1),
            start_score=first.score,
            end_score=last.score
        )
    
    def _get_status(self, score: int) -> str:
        """Determine health status from score."""
        if score >= 80:
            return "healthy"
        elif score >= 60:
            return "degraded"
        else:
            return "critical"
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get a quick health summary for dashboards."""
        current = self.get_current_score()
        
        return {
            "total_score": current.total_score,
            "status": current.status,
            "categories_tracked": len(current.category_scores),
            "last_updated": current.last_updated.isoformat(),
            "category_scores": [
                {"category": c.category, "score": c.average_score, "trend": c.trend}
                for c in current.category_scores
            ]
        }
    
    def generate_health_report(self) -> HealthReport:
        """Generate a comprehensive health report with recommendations."""
        current = self.get_current_score()
        
        # Generate recommendations based on low scores
        recommendations = []
        
        for cat_score in current.category_scores:
            if cat_score.average_score < 60:
                recommendations.append(
                    f"CRITICAL: {cat_score.category} score is {cat_score.average_score:.0f}/100. "
                    f"Review {cat_score.category} components immediately."
                )
            elif cat_score.average_score < 80:
                recommendations.append(
                    f"ATTENTION: {cat_score.category} score is {cat_score.average_score:.0f}/100. "
                    f"Consider optimizing {cat_score.category} utilities."
                )
            
            if cat_score.trend == "declining":
                recommendations.append(
                    f"WARNING: {cat_score.category} scores are trending down "
                    f"({cat_score.trend_percentage:.0f}% change). Investigate recent changes."
                )
        
        if not recommendations:
            recommendations.append("All systems operating within healthy parameters.")
        
        # Get trend breakdown
        trend_breakdown = []
        for cat_score in current.category_scores:
            trend_breakdown.append({
                "category": cat_score.category,
                "direction": cat_score.trend,
                "change": cat_score.trend_percentage
            })
        
        return HealthReport(
            overall_score=current.total_score,
            status=current.status,
            category_breakdown=[
                {
                    "category": c.category,
                    "average_score": c.average_score,
                    "events": c.event_count,
                    "trend": c.trend
                }
                for c in current.category_scores
            ],
            trend={
                "summary": trend_breakdown,
                "overall_direction": self._get_overall_trend_direction(trend_breakdown)
            },
            recommendations=recommendations,
            generated_at=datetime.now()
        )
    
    def _get_overall_trend_direction(self, trends: List[Dict]) -> str:
        """Get overall trend direction from category trends."""
        if not trends:
            return "stable"
        
        improving = sum(1 for t in trends if t["direction"] == "improving")
        declining = sum(1 for t in trends if t["direction"] == "declining")
        
        if declining > improving:
            return "declining"
        elif improving > declining:
            return "improving"
        else:
            return "stable"
    
    def cleanup_old_events(self, days: int = 30) -> int:
        """
        Remove events older than N days.
        
        Args:
            days: Number of days to keep
            
        Returns:
            Number of events removed
        """
        cutoff = datetime.now() - timedelta(days=days)
        original_count = len(self._events)
        
        self._events = [e for e in self._events if e.timestamp >= cutoff]
        removed = original_count - len(self._events)
        
        if removed > 0:
            self._save_history()
        
        return removed
