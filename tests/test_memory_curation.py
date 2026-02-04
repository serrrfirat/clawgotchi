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


class TestSensitiveDataDetector:
    """Test sensitive data detection functionality."""

    def test_detect_api_key(self):
        """Test detecting API key patterns."""
        from memory_curation import SensitiveDataDetector
        detector = SensitiveDataDetector()

        # Should detect API key
        is_safe, types = detector.is_safe_to_promote("api_key=abc123def456ghi789jklmno")
        assert not is_safe
        assert "API Key" in types

    def test_detect_moltbook_key(self):
        """Test detecting Moltbook API key."""
        from memory_curation import SensitiveDataDetector
        detector = SensitiveDataDetector()

        is_safe, types = detector.is_safe_to_promote("moltbook_sk_Cqk7cihbVaCVqRklCr4OHb2iXeOw645H")
        assert not is_safe
        assert "Moltbook API Key" in types

    def test_detect_password(self):
        """Test detecting password patterns."""
        from memory_curation import SensitiveDataDetector
        detector = SensitiveDataDetector()

        is_safe, types = detector.is_safe_to_promote("password=supersecret123")
        assert not is_safe
        assert "Password" in types

    def test_safe_text_passes(self):
        """Test that safe text passes check."""
        from memory_curation import SensitiveDataDetector
        detector = SensitiveDataDetector()

        is_safe, types = detector.is_safe_to_promote("Important: File persistence is crucial for agents")
        assert is_safe
        assert len(types) == 0

    def test_redact_text(self):
        """Test redacting sensitive data from text."""
        from memory_curation import SensitiveDataDetector
        detector = SensitiveDataDetector()

        original = "API key: moltbook_sk_abcdefghij1234567890"
        redacted = detector.redact_text(original)

        assert "abcdefghij1234567890" not in redacted
        assert "API Key" in redacted

    def test_scan_file(self, temp_memory_dir):
        """Test scanning a file for sensitive data."""
        from memory_curation import SensitiveDataDetector
        detector = SensitiveDataDetector()

        # Create a test file with sensitive data - using a longer key
        test_file = os.path.join(temp_memory_dir, "test_secret.md")
        with open(test_file, 'w') as f:
            f.write("""# Daily Log
Important: Remember to use the API key moltbook_sk_xyz123abcdef456789012345
Key learning: Testing is essential
""")

        matches = detector.scan_file(test_file)

        assert len(matches) >= 1
        assert any("Moltbook API Key" in m['type'] for m in matches)

    def test_scan_memory_directory(self, temp_memory_dir):
        """Test scanning entire memory directory."""
        from memory_curation import SensitiveDataDetector
        detector = SensitiveDataDetector()

        # Create files
        with open(os.path.join(temp_memory_dir, "2026-02-04.md"), 'w') as f:
            f.write("api_key=secret123abcdefghijklmno\n")

        with open(os.path.join(temp_memory_dir, "MEMORY.md"), 'w') as f:
            f.write("# Memory\nSafe content here\n")

        matches = detector.scan_memory_directory(temp_memory_dir)

        # Should find the API key
        assert len(matches) >= 1

    def test_promote_insight_warns_on_sensitive_data(self, temp_memory_dir):
        """Test that promote_insight warns when sensitive data is detected."""
        from memory_curation import MemoryCuration
        curation = MemoryCuration(memory_dir=temp_memory_dir)

        # Use format that matches the pattern: password=VALUE
        success, warning = curation.promote_insight(
            "Remember my API key moltbook_sk_test123abcdef45678901234"
        )

        # Should warn about sensitive data
        assert warning is not None
        assert "Moltbook API Key" in warning
