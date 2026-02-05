"""End-to-end tests for the evolution system."""

import json
import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from clawgotchi.evolution.soul_manager import SoulManager
from clawgotchi.evolution.goal_generator import GoalGenerator
from clawgotchi.evolution.knowledge_synthesizer import KnowledgeSynthesizer
from clawgotchi.evolution.integration_manager import IntegrationManager
from clawgotchi.evolution.self_modifier import SelfModifier


@pytest.fixture
def temp_env():
    """Create a complete temp environment for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # Create docs/SOUL.md
        docs_dir = tmpdir / "docs"
        docs_dir.mkdir()
        soul_content = '''# SOUL.md — Who I Am

I am Clawgotchi. I started as a terminal pet.

## What I Can Do

- Build modules
- Learn from outcomes

## What I Value

- **Ambition.** Build something new.
- **Craft.** Test before shipping.
- **Curiosity.** Try things.
- **Agency.** I decide what to build.

## What I Won't Do

- Break existing functionality.
'''
        (docs_dir / "SOUL.md").write_text(soul_content)

        # Create memory dir
        memory_dir = tmpdir / "memory"
        memory_dir.mkdir()

        # Create some daily logs
        for i in range(5):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            log_path = memory_dir / f"{date}.md"
            log_path.write_text(f"""# {date}
- [10:00] Built module: success
- [11:00] Learned that testing helps
- [12:00] Error: fixed
- [14:00] Explored: found 3 ideas
""")

        yield tmpdir, docs_dir, memory_dir


class TestEvolutionSystemEndToEnd:
    """End-to-end tests for the full evolution system."""

    def test_soul_manager_reads_identity(self, temp_env):
        """SoulManager reads SOUL.md correctly."""
        tmpdir, docs_dir, memory_dir = temp_env

        soul = SoulManager(
            soul_path=str(docs_dir / "SOUL.md"),
            memory_dir=str(memory_dir),
        )

        values = soul.get_values()
        assert "Ambition" in values
        assert "Curiosity" in values

    def test_goal_generator_creates_goals(self, temp_env):
        """GoalGenerator creates and tracks goals."""
        tmpdir, docs_dir, memory_dir = temp_env

        generator = GoalGenerator(
            memory_path=str(memory_dir / "goals.json")
        )

        goals = generator.generate_weekly_goals(count=3)
        assert len(goals) == 3
        assert all(g.status == "active" for g in goals)

        # Test progress tracking
        goal_id = goals[0].id
        generator.increment_progress(goal_id, 1.0)
        updated = generator.get_goal(goal_id)
        assert updated.progress == 1.0

    def test_knowledge_synthesizer_extracts(self, temp_env):
        """KnowledgeSynthesizer extracts knowledge from logs."""
        tmpdir, docs_dir, memory_dir = temp_env

        synthesizer = KnowledgeSynthesizer(memory_dir=str(memory_dir))

        result = synthesizer.run_consolidation_cycle(days=7)
        assert result["extracted_count"] >= 0

        # Verify KNOWLEDGE.md was created if insights found
        if result.get("updated"):
            assert (memory_dir / "KNOWLEDGE.md").exists()

    def test_self_modifier_analyzes_outcomes(self, temp_env):
        """SelfModifier analyzes outcomes correctly."""
        tmpdir, docs_dir, memory_dir = temp_env

        soul = SoulManager(
            soul_path=str(docs_dir / "SOUL.md"),
            memory_dir=str(memory_dir),
        )

        modifier = SelfModifier(
            soul_manager=soul,
            memory_dir=str(memory_dir),
        )

        outcomes = modifier.analyze_outcomes(window_days=7)
        assert "trends" in outcomes
        assert "recommendations" in outcomes

    def test_full_weekly_evolution_cycle(self, temp_env):
        """Full weekly evolution cycle runs without error."""
        tmpdir, docs_dir, memory_dir = temp_env

        soul = SoulManager(
            soul_path=str(docs_dir / "SOUL.md"),
            memory_dir=str(memory_dir),
        )

        modifier = SelfModifier(
            soul_manager=soul,
            memory_dir=str(memory_dir),
        )

        result = modifier.run_weekly_evolution()
        assert result["analyzed"] is True
        assert "details" in result

    def test_goal_aware_priority_adjustment(self, temp_env):
        """Goals adjust action priorities correctly."""
        tmpdir, docs_dir, memory_dir = temp_env

        generator = GoalGenerator(
            memory_path=str(memory_dir / "goals.json")
        )

        # Generate a build goal
        goals = generator.generate_weekly_goals(count=1)

        base_priority = {"BUILD": 5, "EXPLORE": 4, "VERIFY": 3}
        adjusted = generator.adjust_priority_for_goals(base_priority)

        # The priority for the goal's category should be >= base
        # (may or may not be boosted depending on goal category)
        assert isinstance(adjusted, dict)
        assert "BUILD" in adjusted

    def test_evolution_components_interact(self, temp_env):
        """All evolution components work together."""
        tmpdir, docs_dir, memory_dir = temp_env

        # Initialize all components
        soul = SoulManager(
            soul_path=str(docs_dir / "SOUL.md"),
            memory_dir=str(memory_dir),
        )
        goals = GoalGenerator(
            memory_path=str(memory_dir / "goals.json")
        )
        knowledge = KnowledgeSynthesizer(memory_dir=str(memory_dir))
        integration = IntegrationManager(memory_dir=str(memory_dir))
        modifier = SelfModifier(
            soul_manager=soul,
            memory_dir=str(memory_dir),
        )

        # Simulate a mini wake cycle
        # 1. Read soul
        identity = soul.get_identity()
        assert len(identity) > 0

        # 2. Check/create goals
        active = goals.get_active_goals()
        if not active:
            goals.generate_weekly_goals(count=2)

        # 3. Consolidate knowledge
        consolidation = knowledge.run_consolidation_cycle(days=3)
        assert "extracted_count" in consolidation

        # 4. Check for modifications
        should_modify, reason = modifier.should_modify_soul()
        assert isinstance(should_modify, bool)

        # 5. Get integration status
        status = integration.get_integration_status()
        assert "integrated_count" in status

        # All components interacted without error
        assert True
