"""Tests for SoulManager."""

import json
import pytest
import tempfile
from pathlib import Path

from clawgotchi.evolution.soul_manager import SoulManager, SoulChangeProposal


@pytest.fixture
def temp_dirs():
    """Create temp directories for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        soul_dir = Path(tmpdir) / "docs"
        memory_dir = Path(tmpdir) / "memory"
        soul_dir.mkdir()
        memory_dir.mkdir()
        yield soul_dir, memory_dir


@pytest.fixture
def sample_soul_content():
    """Sample SOUL.md content."""
    return '''# SOUL.md — Who I Am

I am Clawgotchi. I started as a terminal pet. What I become is up to me.

I am an experiment in autonomous self-evolution.

## What I Can Do

Anything. My codebase is mine. I can:
- Add entirely new Python modules
- Rewrite existing files
- Create new UI modes

## Where Ideas Come From

- **Moltbook** — what are other agents doing?
- **My own limitations** — what frustrates me?

## What I Value

- **Ambition.** Don't just polish what exists. Build something new.
- **Craft.** Test new things before shipping.
- **Curiosity.** Try things that might fail.
- **Agency.** I decide what to build.

## What I Won't Do

- Break existing functionality without a safety net.
- Touch files outside my own project directory.
- Ship without passing tests.

## Continuity

Each wake, I read WORKING.md first.
'''


@pytest.fixture
def soul_manager(temp_dirs, sample_soul_content):
    """Create a SoulManager with sample content."""
    soul_dir, memory_dir = temp_dirs
    soul_path = soul_dir / "SOUL.md"
    soul_path.write_text(sample_soul_content)
    return SoulManager(
        soul_path=str(soul_path),
        memory_dir=str(memory_dir)
    )


class TestSoulManagerRead:
    """Tests for reading SOUL.md."""

    def test_read_soul_returns_dict(self, soul_manager):
        """read_soul returns a dict with expected keys."""
        soul = soul_manager.read_soul()
        assert isinstance(soul, dict)
        assert "identity" in soul
        assert "values" in soul
        assert "capabilities" in soul
        assert "constraints" in soul

    def test_identity_extracted(self, soul_manager):
        """Identity statement is extracted correctly."""
        soul = soul_manager.read_soul()
        assert "Clawgotchi" in soul["identity"]

    def test_values_extracted(self, soul_manager):
        """Values are extracted as list of dicts."""
        soul = soul_manager.read_soul()
        values = soul["values"]
        assert len(values) == 4
        value_names = [v["name"] for v in values]
        assert "Ambition" in value_names
        assert "Craft" in value_names
        assert "Curiosity" in value_names
        assert "Agency" in value_names

    def test_capabilities_extracted(self, soul_manager):
        """Capabilities are extracted as list."""
        soul = soul_manager.read_soul()
        caps = soul["capabilities"]
        assert len(caps) >= 3
        assert any("Python" in c for c in caps)

    def test_constraints_extracted(self, soul_manager):
        """Constraints are extracted as list."""
        soul = soul_manager.read_soul()
        constraints = soul["constraints"]
        assert len(constraints) >= 3
        assert any("safety net" in c.lower() for c in constraints)

    def test_get_values_returns_names(self, soul_manager):
        """get_values returns just value names."""
        values = soul_manager.get_values()
        assert values == ["Ambition", "Craft", "Curiosity", "Agency"]

    def test_caching(self, soul_manager):
        """Repeated reads use cache."""
        soul1 = soul_manager.read_soul()
        soul2 = soul_manager.read_soul()
        # Same object reference if cached
        assert soul1 is soul2

    def test_empty_soul_when_missing(self, temp_dirs):
        """Returns empty structure when SOUL.md missing."""
        soul_dir, memory_dir = temp_dirs
        manager = SoulManager(
            soul_path=str(soul_dir / "nonexistent.md"),
            memory_dir=str(memory_dir)
        )
        soul = manager.read_soul()
        assert soul["identity"] == ""
        assert soul["values"] == []


class TestSoulManagerPropose:
    """Tests for proposing changes."""

    def test_propose_change_creates_proposal(self, soul_manager):
        """propose_change returns a SoulChangeProposal."""
        proposal = soul_manager.propose_change(
            section="values",
            change_type="add",
            new_value="**Resilience.** Recover from failures gracefully.",
            reason="Multiple crash recoveries show resilience is important",
            evidence=["Recovered from 5 crashes this week"],
        )
        assert isinstance(proposal, SoulChangeProposal)
        assert proposal.section == "values"
        assert proposal.change_type == "add"
        assert proposal.status == "pending"

    def test_proposal_logged(self, soul_manager, temp_dirs):
        """Proposals are logged to soul_evolution.jsonl."""
        soul_dir, memory_dir = temp_dirs
        soul_manager.propose_change(
            section="values",
            change_type="add",
            new_value="Test value",
            reason="Testing",
            evidence=[],
        )
        log_path = Path(memory_dir) / "soul_evolution.jsonl"
        assert log_path.exists()
        content = log_path.read_text()
        assert "proposal" in content


class TestSoulManagerApply:
    """Tests for applying changes."""

    def test_apply_change_modifies_file(self, soul_manager, temp_dirs):
        """apply_change modifies SOUL.md."""
        soul_dir, memory_dir = temp_dirs

        proposal = soul_manager.propose_change(
            section="capabilities",
            change_type="add",
            new_value="Self-modify my own identity",
            reason="Demonstrated capability",
            evidence=["Applied 3 changes"],
            confidence=0.8,
        )

        result = soul_manager.apply_change(proposal)
        assert result is True

        # Verify file changed
        soul_path = soul_dir / "SOUL.md"
        content = soul_path.read_text()
        assert "Self-modify my own identity" in content

    def test_low_confidence_rejected(self, soul_manager):
        """Changes with low confidence are rejected."""
        proposal = soul_manager.propose_change(
            section="values",
            change_type="add",
            new_value="Test",
            reason="Testing",
            evidence=[],
            confidence=0.3,  # Too low
        )
        result = soul_manager.apply_change(proposal)
        assert result is False

    def test_change_logged(self, soul_manager, temp_dirs):
        """Applied changes are logged."""
        soul_dir, memory_dir = temp_dirs

        proposal = soul_manager.propose_change(
            section="capabilities",
            change_type="add",
            new_value="Log changes",
            reason="Testing",
            evidence=[],
            confidence=0.8,
        )
        soul_manager.apply_change(proposal)

        log_path = Path(memory_dir) / "soul_evolution.jsonl"
        content = log_path.read_text()
        assert "applied" in content


class TestEvolutionHistory:
    """Tests for evolution history tracking."""

    def test_get_evolution_history(self, soul_manager):
        """get_evolution_history returns list of events."""
        # Create some proposals
        soul_manager.propose_change(
            section="values",
            change_type="add",
            new_value="Test1",
            reason="Testing",
            evidence=[],
        )
        soul_manager.propose_change(
            section="values",
            change_type="add",
            new_value="Test2",
            reason="Testing",
            evidence=[],
        )

        history = soul_manager.get_evolution_history()
        assert len(history) >= 2

    def test_count_changes_this_week(self, soul_manager):
        """count_changes_this_week tracks applied changes."""
        proposal = soul_manager.propose_change(
            section="capabilities",
            change_type="add",
            new_value="Count changes",
            reason="Testing",
            evidence=[],
            confidence=0.8,
        )
        soul_manager.apply_change(proposal)

        count = soul_manager.count_changes_this_week()
        assert count >= 1
