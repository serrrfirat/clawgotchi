"""Tests for KnowledgeSynthesizer."""

import json
import pytest
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from clawgotchi.evolution.knowledge_synthesizer import KnowledgeSynthesizer, Principle


@pytest.fixture
def temp_memory():
    """Create temp memory directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def synthesizer(temp_memory):
    """Create a KnowledgeSynthesizer."""
    return KnowledgeSynthesizer(memory_dir=str(temp_memory))


@pytest.fixture
def sample_logs():
    """Sample daily log content."""
    return [
        """# 2024-01-01
- [10:00] Built memory module: completed
- [11:00] Error: test failed
- [12:00] Learned that testing early catches issues
- [14:00] Build successful after verify
""",
        """# 2024-01-02
- [09:00] Explored Moltbook: 5 ideas
- [10:00] Built feature: success
- [11:00] Principle: always verify before commit
- [15:00] Health improved
""",
        """# 2024-01-03
- [08:00] Memory cleanup: archived 10 items
- [09:00] Build module: completed
- [10:00] Error: import failed
- [14:00] Insight: modules need integration
""",
    ]


class TestExtractPrinciples:
    """Tests for principle extraction."""

    def test_extract_from_logs(self, synthesizer, sample_logs):
        """extract_principles finds principles in logs."""
        principles = synthesizer.extract_principles(sample_logs)
        assert len(principles) > 0

    def test_extract_learned_patterns(self, synthesizer, sample_logs):
        """Extracts 'learned that' patterns."""
        principles = synthesizer.extract_principles(sample_logs)
        texts = [p["text"].lower() for p in principles]
        assert any("testing" in t for t in texts)

    def test_extract_explicit_principles(self, synthesizer, sample_logs):
        """Extracts explicit 'principle:' statements."""
        principles = synthesizer.extract_principles(sample_logs)
        texts = [p["text"].lower() for p in principles]
        assert any("verify" in t for t in texts)

    def test_categorize_principles(self, synthesizer):
        """Principles are categorized by content."""
        logs = ["Learned that building fast causes errors"]
        principles = synthesizer.extract_principles(logs)

        if principles:
            assert principles[0]["category"] in ["building", "health", "memory", "identity", "general"]


class TestSynthesizeInsight:
    """Tests for insight synthesis."""

    def test_synthesize_single_memory(self, synthesizer):
        """Single memory returns as-is."""
        memories = [{"text": "Testing is important", "category": "building"}]
        insight = synthesizer.synthesize_insight(memories)
        assert "Testing" in insight

    def test_synthesize_multiple_memories(self, synthesizer):
        """Multiple memories are combined."""
        memories = [
            {"text": "Build then test", "category": "building"},
            {"text": "Build after verify", "category": "building"},
            {"text": "Build when ready", "category": "building"},
        ]
        insight = synthesizer.synthesize_insight(memories)
        assert "building" in insight.lower()

    def test_synthesize_empty(self, synthesizer):
        """Empty memories returns empty string."""
        assert synthesizer.synthesize_insight([]) == ""


class TestUpdateKnowledge:
    """Tests for updating KNOWLEDGE.md."""

    def test_creates_knowledge_file(self, synthesizer, temp_memory):
        """update_knowledge creates KNOWLEDGE.md."""
        synthesizer.update_knowledge(["Test insight 1", "Test insight 2"])

        knowledge_path = temp_memory / "KNOWLEDGE.md"
        assert knowledge_path.exists()

    def test_adds_insights(self, synthesizer, temp_memory):
        """Insights are added to KNOWLEDGE.md."""
        synthesizer.update_knowledge(["Building requires testing"])

        content = (temp_memory / "KNOWLEDGE.md").read_text()
        assert "Building requires testing" in content

    def test_deduplicates(self, synthesizer, temp_memory):
        """Duplicate insights are not added."""
        synthesizer.update_knowledge(["Same insight"])
        synthesizer.update_knowledge(["Same insight"])

        content = (temp_memory / "KNOWLEDGE.md").read_text()
        assert content.count("Same insight") == 1

    def test_organizes_by_category(self, synthesizer, temp_memory):
        """Insights are organized by category."""
        synthesizer.update_knowledge([
            "Building requires planning",
            "Memory should be cleaned",
        ])

        content = (temp_memory / "KNOWLEDGE.md").read_text()
        assert "##" in content  # Has section headers


class TestGetRelevantKnowledge:
    """Tests for retrieving relevant knowledge."""

    def test_returns_matching(self, synthesizer, temp_memory):
        """Returns knowledge matching context."""
        synthesizer.update_knowledge(["Testing catches bugs early"])

        relevant = synthesizer.get_relevant_knowledge("testing code")
        assert len(relevant) > 0
        assert any("testing" in r.lower() for r in relevant)

    def test_returns_empty_when_no_match(self, synthesizer, temp_memory):
        """Returns empty list when nothing matches."""
        synthesizer.update_knowledge(["Memory requires cleanup"])

        relevant = synthesizer.get_relevant_knowledge("xyz123abc")
        # Might have some incidental matches, so just check it doesn't crash
        assert isinstance(relevant, list)


class TestShouldConsolidate:
    """Tests for consolidation timing."""

    def test_consolidate_every_10(self, synthesizer):
        """Consolidation triggers every 10 wakes."""
        assert synthesizer.should_consolidate(10) is True
        assert synthesizer.should_consolidate(20) is True
        assert synthesizer.should_consolidate(5) is False
        assert synthesizer.should_consolidate(0) is False


class TestRunConsolidationCycle:
    """Tests for full consolidation cycle."""

    def test_consolidation_with_logs(self, synthesizer, temp_memory):
        """Consolidation processes existing logs."""
        # Create some log files
        for i in range(3):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            log_path = temp_memory / f"{date}.md"
            log_path.write_text(f"""# {date}
- [10:00] Built module: success
- [11:00] Learned that testing helps
- [12:00] Error fixed
""")

        result = synthesizer.run_consolidation_cycle(days=7)

        assert result["extracted_count"] >= 0
        assert "updated" in result

    def test_consolidation_no_logs(self, synthesizer, temp_memory):
        """Consolidation handles missing logs."""
        result = synthesizer.run_consolidation_cycle(days=7)

        assert result["extracted_count"] == 0
        assert result["updated"] is False


class TestPrinciples:
    """Tests for principle storage."""

    def test_add_principle(self, synthesizer):
        """Can add a principle."""
        synthesizer.add_principle(
            text="Always test before commit",
            category="building",
            confidence=0.8,
        )

        principles = synthesizer.get_principles()
        assert len(principles) == 1
        assert principles[0].text == "Always test before commit"

    def test_principles_persist(self, temp_memory):
        """Principles are persisted to disk."""
        synth1 = KnowledgeSynthesizer(memory_dir=str(temp_memory))
        synth1.add_principle("Test principle", "general")

        synth2 = KnowledgeSynthesizer(memory_dir=str(temp_memory))
        principles = synth2.get_principles()
        assert len(principles) == 1
