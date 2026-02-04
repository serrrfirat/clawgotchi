"""Tests for memory curation system."""
import os
import tempfile
import pytest
from datetime import datetime, timedelta

# Add parent directory to path for imports
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestMemoryCuration:
    """Test memory curation functionality."""

    @pytest.fixture
    def temp_memory_dir(self):
        """Create a temporary memory directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    def test_memory_dir_exists(self, temp_memory_dir):
        """Test that memory directory is created."""
        from memory_curation import MemoryCuration
        curation = MemoryCuration(memory_dir=temp_memory_dir)
        assert os.path.exists(temp_memory_dir)

    def test_curated_memory_file_exists_after_promote(self, temp_memory_dir):
        """Test that curated memory file is created when promoting."""
        from memory_curation import MemoryCuration
        curation = MemoryCuration(memory_dir=temp_memory_dir)

        # Promote an insight
        curation.promote_insight("Test insight about agent behavior")

        # Check that MEMORY.md exists
        memory_file = os.path.join(temp_memory_dir, "MEMORY.md")
        assert os.path.exists(memory_file)

    def test_promote_insight_adds_to_memory(self, temp_memory_dir):
        """Test promoting an insight adds it to MEMORY.md."""
        from memory_curation import MemoryCuration
        curation = MemoryCuration(memory_dir=temp_memory_dir)

        curation.promote_insight("Agents should have file-based persistence")

        memory_file = os.path.join(temp_memory_dir, "MEMORY.md")
        with open(memory_file, 'r') as f:
            content = f.read()

        assert "Agents should have file-based persistence" in content
        assert "---" in content  # YAML frontmatter separator

    def test_curated_memory_has_frontmatter(self, temp_memory_dir):
        """Test that curated memory has proper frontmatter."""
        from memory_curation import MemoryCuration
        curation = MemoryCuration(memory_dir=temp_memory_dir)

        curation.promote_insight("Test insight")

        memory_file = os.path.join(temp_memory_dir, "MEMORY.md")
        with open(memory_file, 'r') as f:
            content = f.read()

        assert "---" in content
        assert "curated_insights:" in content or "Curated Insights" in content

    def test_promote_multiple_insights(self, temp_memory_dir):
        """Test promoting multiple insights."""
        from memory_curation import MemoryCuration
        curation = MemoryCuration(memory_dir=temp_memory_dir)

        curation.promote_insight("First insight")
        curation.promote_insight("Second insight")

        memory_file = os.path.join(temp_memory_dir, "MEMORY.md")
        with open(memory_file, 'r') as f:
            content = f.read()

        assert "First insight" in content
        assert "Second insight" in content

    def test_extract_insights_from_logs(self, temp_memory_dir):
        """Test extracting insights from daily logs."""
        from memory_curation import MemoryCuration
        curation = MemoryCuration(memory_dir=temp_memory_dir)

        # Create a fake daily log with insights
        log_content = """
## What I Did
- Built a new feature
- Important: File persistence is crucial for agent continuity
- Also noted: Memory layers help organize thoughts

## Challenges
- Testing was difficult
- Key learning: Always test before shipping
"""
        # Write a fake daily log
        log_file = os.path.join(temp_memory_dir, "2026-02-04.md")
        with open(log_file, 'w') as f:
            f.write(log_content)

        # Extract insights
        insights = curation.extract_insights_from_logs(days=1)

        # Should find lines starting with "Important:" or "Key learning:"
        assert len(insights) > 0
        # Fixed: check i['text'] instead of i
        found_insight = any("File persistence" in i.get('text', '') or "Always test" in i.get('text', '') for i in insights)
        assert found_insight, f"Expected to find insights but got: {insights}"

    def test_show_curated_memory(self, temp_memory_dir):
        """Test showing curated memory."""
        from memory_curation import MemoryCuration
        curation = MemoryCuration(memory_dir=temp_memory_dir)

        curation.promote_insight("Test insight 1")
        curation.promote_insight("Test insight 2")

        output = curation.show_curated_memory()

        assert "Test insight 1" in output
        assert "Test insight 2" in output

    def test_search_memories(self, temp_memory_dir):
        """Test searching memories."""
        from memory_curation import MemoryCuration
        curation = MemoryCuration(memory_dir=temp_memory_dir)

        curation.promote_insight("Python is great")
        curation.promote_insight("JavaScript is also nice")

        # Search for Python
        results = curation.search_memories("Python")
        assert len(results) >= 1
        assert any("Python is great" in r for r in results)

        # Search for JavaScript
        results = curation.search_memories("JavaScript")
        assert len(results) >= 1
        assert any("JavaScript is also nice" in r for r in results)
