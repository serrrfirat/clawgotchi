"""Tests for GoalGenerator."""

import json
import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from clawgotchi.evolution.goal_generator import GoalGenerator, Goal


@pytest.fixture
def temp_memory():
    """Create temp directory for goals.json."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "goals.json"


@pytest.fixture
def goal_generator(temp_memory):
    """Create a GoalGenerator with temp storage."""
    return GoalGenerator(memory_path=str(temp_memory))


class TestGoal:
    """Tests for the Goal dataclass."""

    def test_goal_creation(self):
        """Goal can be created with required fields."""
        goal = Goal(
            id="test-1",
            description="Test goal",
            category="build",
            target_metric="modules_built",
            target_value=3,
            deadline=(datetime.now() + timedelta(days=7)).isoformat(),
        )
        assert goal.status == "active"
        assert goal.progress == 0.0

    def test_goal_to_dict(self):
        """Goal can be serialized to dict."""
        goal = Goal(
            id="test-1",
            description="Test goal",
            category="build",
            target_metric="test",
            target_value=5,
            deadline=datetime.now().isoformat(),
        )
        d = goal.to_dict()
        assert d["id"] == "test-1"
        assert d["category"] == "build"

    def test_goal_from_dict(self):
        """Goal can be deserialized from dict."""
        data = {
            "id": "test-2",
            "description": "From dict",
            "category": "explore",
            "target_metric": "ideas",
            "target_value": 10,
            "deadline": datetime.now().isoformat(),
            "progress": 3.0,
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "completed_at": None,
            "notes": [],
        }
        goal = Goal.from_dict(data)
        assert goal.id == "test-2"
        assert goal.progress == 3.0

    def test_completion_percentage(self):
        """completion_percentage calculates correctly."""
        goal = Goal(
            id="test",
            description="Test",
            category="build",
            target_metric="test",
            target_value=10,
            deadline=datetime.now().isoformat(),
            progress=5.0,
        )
        assert goal.completion_percentage() == 50.0

    def test_is_overdue(self):
        """is_overdue detects past deadline."""
        past = (datetime.now() - timedelta(days=1)).isoformat()
        goal = Goal(
            id="test",
            description="Test",
            category="build",
            target_metric="test",
            target_value=10,
            deadline=past,
        )
        assert goal.is_overdue() is True

        future = (datetime.now() + timedelta(days=1)).isoformat()
        goal.deadline = future
        assert goal.is_overdue() is False


class TestGoalGeneratorBasics:
    """Basic GoalGenerator tests."""

    def test_init_creates_empty_goals(self, goal_generator):
        """New generator has no active goals."""
        assert goal_generator.get_active_goals() == []

    def test_generate_weekly_goals(self, goal_generator):
        """generate_weekly_goals creates goals."""
        goals = goal_generator.generate_weekly_goals(count=3)
        assert len(goals) == 3
        assert all(g.status == "active" for g in goals)

    def test_goals_persisted(self, temp_memory):
        """Goals are saved to disk."""
        gen1 = GoalGenerator(memory_path=str(temp_memory))
        gen1.generate_weekly_goals(count=2)

        gen2 = GoalGenerator(memory_path=str(temp_memory))
        assert len(gen2.get_active_goals()) == 2

    def test_get_goal_by_id(self, goal_generator):
        """get_goal returns goal by ID."""
        goals = goal_generator.generate_weekly_goals(count=1)
        goal_id = goals[0].id

        found = goal_generator.get_goal(goal_id)
        assert found is not None
        assert found.id == goal_id

    def test_get_goal_not_found(self, goal_generator):
        """get_goal returns None for unknown ID."""
        assert goal_generator.get_goal("nonexistent") is None


class TestGapAnalysis:
    """Tests for gap analysis."""

    def test_analyze_gaps_empty_context(self, goal_generator):
        """analyze_gaps works with empty context."""
        gaps = goal_generator.analyze_gaps()
        assert isinstance(gaps, list)

    def test_analyze_gaps_low_health(self, goal_generator):
        """Low health creates improvement gap."""
        gaps = goal_generator.analyze_gaps({"health_score": 75})
        improve_gaps = [g for g in gaps if g["category"] == "improve"]
        assert len(improve_gaps) > 0

    def test_analyze_gaps_orphaned_modules(self, goal_generator):
        """Orphaned modules create integration gap."""
        gaps = goal_generator.analyze_gaps({"orphaned_modules": 5})
        integrate_gaps = [g for g in gaps if g["category"] == "integrate"]
        assert len(integrate_gaps) > 0

    def test_analyze_gaps_sorted_by_severity(self, goal_generator):
        """Gaps are sorted by severity."""
        gaps = goal_generator.analyze_gaps({
            "health_score": 70,
            "orphaned_modules": 10,
        })
        if len(gaps) >= 2:
            assert gaps[0]["severity"] >= gaps[1]["severity"]


class TestProgressTracking:
    """Tests for goal progress tracking."""

    def test_update_progress(self, goal_generator):
        """update_progress sets progress value."""
        goals = goal_generator.generate_weekly_goals(count=1)
        goal_id = goals[0].id

        goal_generator.update_progress(goal_id, 5.0)
        goal = goal_generator.get_goal(goal_id)
        assert goal.progress == 5.0

    def test_increment_progress(self, goal_generator):
        """increment_progress adds to current progress."""
        goals = goal_generator.generate_weekly_goals(count=1)
        goal_id = goals[0].id

        goal_generator.increment_progress(goal_id, 2.0)
        goal_generator.increment_progress(goal_id, 3.0)
        goal = goal_generator.get_goal(goal_id)
        assert goal.progress == 5.0

    def test_auto_complete_on_target(self, goal_generator):
        """Goal auto-completes when target reached."""
        goals = goal_generator.generate_weekly_goals(count=1)
        goal = goals[0]
        target = goal.target_value

        goal_generator.update_progress(goal.id, target)
        updated = goal_generator.get_goal(goal.id)
        assert updated.status == "completed"

    def test_progress_with_note(self, goal_generator):
        """Progress updates can include notes."""
        goals = goal_generator.generate_weekly_goals(count=1)
        goal_id = goals[0].id

        goal_generator.update_progress(goal_id, 1.0, note="First step done")
        goal = goal_generator.get_goal(goal_id)
        assert len(goal.notes) > 0
        assert "First step" in goal.notes[-1]


class TestWeekEvaluation:
    """Tests for weekly evaluation."""

    def test_evaluate_week_empty(self, goal_generator):
        """evaluate_week works with no goals."""
        result = goal_generator.evaluate_week()
        assert "completed" in result
        assert "failed" in result
        assert "insights" in result

    def test_evaluate_week_completed(self, goal_generator):
        """Completed goals are counted."""
        goals = goal_generator.generate_weekly_goals(count=1)
        goal = goals[0]
        goal_generator.update_progress(goal.id, goal.target_value)

        result = goal_generator.evaluate_week()
        assert len(result["completed"]) == 1

    def test_evaluate_week_generates_insights(self, goal_generator):
        """Evaluation generates insights."""
        goal_generator.generate_weekly_goals(count=2)
        result = goal_generator.evaluate_week()
        assert len(result["insights"]) > 0


class TestPriorityAdjustment:
    """Tests for goal-aware priority adjustment."""

    def test_adjust_priority_no_goals(self, goal_generator):
        """Returns base priority when no goals."""
        base = {"BUILD": 5, "EXPLORE": 4, "VERIFY": 3}
        adjusted = goal_generator.adjust_priority_for_goals(base)
        assert adjusted == base

    def test_adjust_priority_boosts_relevant(self, goal_generator):
        """Active goals boost relevant action types."""
        goals = goal_generator.generate_weekly_goals(count=1)
        # Get the category of the generated goal
        cat = goals[0].category

        base = {"BUILD": 5, "EXPLORE": 4, "VERIFY": 3, "CURATE": 2, "INTEGRATE": 1}
        adjusted = goal_generator.adjust_priority_for_goals(base)

        # The action corresponding to the goal category should be boosted
        category_actions = {
            "build": "BUILD",
            "explore": "EXPLORE",
            "improve": "VERIFY",
            "consolidate": "CURATE",
            "integrate": "INTEGRATE",
        }
        action = category_actions.get(cat)
        if action:
            assert adjusted[action] >= base[action]


class TestGoalSummary:
    """Tests for goal summary."""

    def test_get_goal_summary(self, goal_generator):
        """get_goal_summary returns summary dict."""
        goal_generator.generate_weekly_goals(count=2)
        summary = goal_generator.get_goal_summary()

        assert "active_count" in summary
        assert "goals" in summary
        assert "categories" in summary
        assert summary["active_count"] == 2
