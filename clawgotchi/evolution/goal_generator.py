"""
GoalGenerator - Generate and track weekly goals.

Instead of just reacting to external stimuli (Moltbook posts),
the agent sets its own weekly goals to provide self-direction.

Goals are:
- Measurable (have target metrics)
- Time-bound (weekly deadline)
- Self-generated (based on gap analysis)
- Progress-tracked (updated as work happens)
"""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


@dataclass
class Goal:
    """A weekly goal with progress tracking."""
    id: str
    description: str
    category: str  # build, explore, improve, consolidate, integrate
    target_metric: str  # what to measure
    target_value: float  # success threshold
    deadline: str  # ISO format datetime
    progress: float = 0.0
    status: str = "active"  # active, completed, failed, abandoned
    created_at: str = ""
    completed_at: Optional[str] = None
    notes: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Goal":
        return cls(**data)

    def is_overdue(self) -> bool:
        """Check if goal is past deadline."""
        try:
            deadline = datetime.fromisoformat(self.deadline)
            return datetime.now() > deadline and self.status == "active"
        except ValueError:
            return False

    def completion_percentage(self) -> float:
        """Get progress as percentage of target."""
        if self.target_value == 0:
            return 100.0 if self.progress > 0 else 0.0
        return min(100.0, (self.progress / self.target_value) * 100)


class GoalGenerator:
    """Generate and track weekly goals."""

    # Goal templates by category
    GOAL_TEMPLATES = {
        "build": [
            {
                "description": "Build {count} resilience modules",
                "metric": "modules_built",
                "default_target": 2,
            },
            {
                "description": "Complete {count} features from curiosity queue",
                "metric": "features_completed",
                "default_target": 3,
            },
        ],
        "explore": [
            {
                "description": "Discover {count} new ideas from Moltbook",
                "metric": "ideas_discovered",
                "default_target": 5,
            },
            {
                "description": "Explore {count} new topic categories",
                "metric": "categories_explored",
                "default_target": 3,
            },
        ],
        "improve": [
            {
                "description": "Increase health score to {value}",
                "metric": "health_score",
                "default_target": 95,
            },
            {
                "description": "Reduce error rate to under {value}%",
                "metric": "error_rate_percent",
                "default_target": 5,
            },
        ],
        "consolidate": [
            {
                "description": "Archive {count} stale memories",
                "metric": "memories_archived",
                "default_target": 10,
            },
            {
                "description": "Extract {count} principles from logs",
                "metric": "principles_extracted",
                "default_target": 5,
            },
        ],
        "integrate": [
            {
                "description": "Wire {count} orphaned modules into operation",
                "metric": "modules_integrated",
                "default_target": 3,
            },
            {
                "description": "Add {count} modules to health checks",
                "metric": "health_checks_added",
                "default_target": 2,
            },
        ],
    }

    def __init__(self, memory_path: str = "memory/goals.json"):
        self.goals_path = Path(memory_path)
        self._goals: list[Goal] = []
        self._history: list[dict] = []
        self._load()

    def _load(self):
        """Load goals from disk."""
        if self.goals_path.exists():
            try:
                data = json.loads(self.goals_path.read_text())
                self._goals = [Goal.from_dict(g) for g in data.get("goals", [])]
                self._history = data.get("history", [])
            except (json.JSONDecodeError, KeyError):
                self._goals = []
                self._history = []

    def _save(self):
        """Persist goals to disk."""
        self.goals_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "goals": [g.to_dict() for g in self._goals],
            "history": self._history,
            "updated_at": datetime.now().isoformat(),
        }
        self.goals_path.write_text(json.dumps(data, indent=2))

    def analyze_gaps(self, context: dict = None) -> list[dict]:
        """Identify gaps and opportunities.

        Analyzes:
        - Low-coverage categories in curiosity queue
        - Modules built but not integrated
        - Declining health areas
        - Under-explored Moltbook topics

        Args:
            context: Optional dict with current state info:
                - curiosity_queue: list of curiosity items
                - orphaned_modules: count of unintegrated modules
                - health_score: current health
                - health_trend: "up", "down", "stable"
                - explore_count: recent exploration count

        Returns:
            List of gap dicts with category, severity, description
        """
        context = context or {}
        gaps = []

        # Check curiosity queue coverage
        curiosity = context.get("curiosity_queue", [])
        if curiosity:
            categories = {}
            for item in curiosity:
                for cat in item.get("categories", []):
                    categories[cat] = categories.get(cat, 0) + 1

            # Find under-represented categories
            if categories:
                avg = sum(categories.values()) / len(categories)
                for cat, count in categories.items():
                    if count < avg * 0.5:
                        gaps.append({
                            "category": "explore",
                            "severity": 0.6,
                            "description": f"Category '{cat}' under-explored ({count} items)",
                            "suggested_action": f"Explore more {cat} topics",
                        })

        # Check orphaned modules
        orphaned = context.get("orphaned_modules", 0)
        if orphaned > 0:
            gaps.append({
                "category": "integrate",
                "severity": min(1.0, orphaned * 0.2),
                "description": f"{orphaned} modules built but not integrated",
                "suggested_action": "Wire orphaned modules into operation",
            })

        # Check health
        health = context.get("health_score", 100)
        trend = context.get("health_trend", "stable")
        if health < 90:
            gaps.append({
                "category": "improve",
                "severity": (100 - health) / 100,
                "description": f"Health score low: {health}/100",
                "suggested_action": "Focus on health improvements",
            })
        if trend == "down":
            gaps.append({
                "category": "improve",
                "severity": 0.7,
                "description": "Health trending downward",
                "suggested_action": "Investigate and fix health issues",
            })

        # Check exploration frequency
        explore_count = context.get("explore_count", 0)
        if explore_count < 3:
            gaps.append({
                "category": "explore",
                "severity": 0.5,
                "description": f"Low exploration activity ({explore_count} recent)",
                "suggested_action": "Increase Moltbook exploration",
            })

        # Check build activity
        build_count = context.get("build_count", 0)
        if build_count < 2:
            gaps.append({
                "category": "build",
                "severity": 0.4,
                "description": f"Low build activity ({build_count} recent)",
                "suggested_action": "Build more features from mature ideas",
            })

        # Sort by severity
        gaps.sort(key=lambda g: g["severity"], reverse=True)
        return gaps

    def generate_weekly_goals(self, count: int = 3, context: dict = None) -> list[Goal]:
        """Generate goals for the coming week.

        Creates a balanced mix of goal types based on gap analysis.

        Args:
            count: Number of goals to generate (default 3)
            context: Current state context for gap analysis

        Returns:
            List of newly created Goal objects
        """
        # Analyze gaps to prioritize categories
        gaps = self.analyze_gaps(context)

        # Get priority categories from gaps
        priority_categories = []
        for gap in gaps[:count]:
            if gap["category"] not in priority_categories:
                priority_categories.append(gap["category"])

        # Fill remaining with balanced mix
        all_categories = list(self.GOAL_TEMPLATES.keys())
        while len(priority_categories) < count:
            for cat in all_categories:
                if cat not in priority_categories:
                    priority_categories.append(cat)
                    break

        # Generate goals
        deadline = (datetime.now() + timedelta(days=7)).isoformat()
        new_goals = []

        for i, category in enumerate(priority_categories[:count]):
            templates = self.GOAL_TEMPLATES.get(category, [])
            if not templates:
                continue

            # Pick template (alternate if multiple)
            template = templates[i % len(templates)]

            # Create goal
            target = template["default_target"]
            description = template["description"].format(
                count=target,
                value=target,
            )

            goal = Goal(
                id=f"goal-{uuid.uuid4().hex[:8]}",
                description=description,
                category=category,
                target_metric=template["metric"],
                target_value=target,
                deadline=deadline,
            )

            # Add context note if from gap analysis
            matching_gap = next((g for g in gaps if g["category"] == category), None)
            if matching_gap:
                goal.notes.append(f"Gap: {matching_gap['description']}")

            new_goals.append(goal)
            self._goals.append(goal)

        self._save()
        return new_goals

    def get_active_goals(self) -> list[Goal]:
        """Return currently active goals."""
        return [g for g in self._goals if g.status == "active"]

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        """Get a goal by ID."""
        for g in self._goals:
            if g.id == goal_id:
                return g
        return None

    def update_progress(self, goal_id: str, progress: float, note: str = None):
        """Update goal progress based on actions taken.

        Args:
            goal_id: The goal to update
            progress: New progress value (absolute, not delta)
            note: Optional note about the progress
        """
        goal = self.get_goal(goal_id)
        if not goal:
            return

        goal.progress = progress

        if note:
            goal.notes.append(f"[{datetime.now().strftime('%Y-%m-%d')}] {note}")

        # Auto-complete if target reached
        if goal.progress >= goal.target_value and goal.status == "active":
            goal.status = "completed"
            goal.completed_at = datetime.now().isoformat()

        self._save()

    def increment_progress(self, goal_id: str, delta: float = 1.0, note: str = None):
        """Increment goal progress by delta."""
        goal = self.get_goal(goal_id)
        if goal:
            self.update_progress(goal_id, goal.progress + delta, note)

    def find_goal_by_metric(self, metric: str) -> Optional[Goal]:
        """Find an active goal that tracks a specific metric."""
        for goal in self.get_active_goals():
            if goal.target_metric == metric:
                return goal
        return None

    def evaluate_week(self) -> dict:
        """Score goal completion at week end.

        Returns dict with:
        - completed: list of completed goals
        - failed: list of failed (overdue) goals
        - partial: list of goals with some progress
        - completion_rate: percentage of goals completed
        - insights: list of insights from the week
        """
        now = datetime.now()
        completed = []
        failed = []
        partial = []
        insights = []

        for goal in self._goals:
            if goal.status == "completed":
                completed.append(goal)
            elif goal.is_overdue():
                if goal.progress > 0:
                    partial.append(goal)
                    pct = goal.completion_percentage()
                    insights.append(
                        f"Goal '{goal.description}' partially completed ({pct:.0f}%)"
                    )
                else:
                    failed.append(goal)
                    insights.append(
                        f"Goal '{goal.description}' failed - no progress"
                    )
                # Mark as failed
                goal.status = "failed"

        total = len(completed) + len(failed) + len(partial)
        completion_rate = (len(completed) / total * 100) if total > 0 else 0

        # Generate insights
        if completion_rate >= 80:
            insights.append("Excellent week - most goals achieved")
        elif completion_rate >= 50:
            insights.append("Moderate progress - room for improvement")
        else:
            insights.append("Challenging week - consider reducing goal count")

        # Category analysis
        completed_cats = [g.category for g in completed]
        failed_cats = [g.category for g in failed]

        for cat in set(failed_cats):
            if cat not in completed_cats:
                insights.append(f"Struggling with '{cat}' goals")

        # Archive to history
        self._history.append({
            "week_ending": now.isoformat(),
            "completed": len(completed),
            "failed": len(failed),
            "partial": len(partial),
            "completion_rate": completion_rate,
            "goals": [g.to_dict() for g in completed + failed + partial],
        })

        self._save()

        return {
            "completed": completed,
            "failed": failed,
            "partial": partial,
            "completion_rate": completion_rate,
            "insights": insights,
        }

    def adjust_priority_for_goals(self, base_priority: dict) -> dict:
        """Modify action priorities to align with goals.

        Takes a dict of action_type -> priority_score and adjusts
        based on active goals.

        Args:
            base_priority: Dict like {"BUILD": 5, "EXPLORE": 4, ...}

        Returns:
            Adjusted priority dict
        """
        adjusted = base_priority.copy()
        active = self.get_active_goals()

        for goal in active:
            # Boost relevant action types
            cat = goal.category
            pct = goal.completion_percentage()

            # More boost if goal is behind schedule
            urgency = 1.0
            if goal.is_overdue():
                urgency = 1.5
            elif pct < 50:
                try:
                    deadline = datetime.fromisoformat(goal.deadline)
                    days_left = (deadline - datetime.now()).days
                    if days_left <= 2:
                        urgency = 1.3
                except ValueError:
                    pass

            # Map category to action type
            category_actions = {
                "build": "BUILD",
                "explore": "EXPLORE",
                "improve": "VERIFY",
                "consolidate": "CURATE",
                "integrate": "INTEGRATE",
            }

            action = category_actions.get(cat)
            if action and action in adjusted:
                adjusted[action] = int(adjusted[action] * (1 + 0.2 * urgency))

        return adjusted

    def get_goal_summary(self) -> dict:
        """Get summary of current goals for display."""
        active = self.get_active_goals()
        return {
            "active_count": len(active),
            "goals": [
                {
                    "description": g.description,
                    "progress": g.completion_percentage(),
                    "status": g.status,
                    "overdue": g.is_overdue(),
                }
                for g in active
            ],
            "categories": list(set(g.category for g in active)),
        }

    def clear_completed(self):
        """Remove completed and failed goals (keep in history)."""
        self._goals = [g for g in self._goals if g.status == "active"]
        self._save()
