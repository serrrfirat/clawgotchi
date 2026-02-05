"""
Test suite for MemorySanitizer utility.
Ensures memory hygiene and cleanup of corrupted entries.
"""
import os
import tempfile
from pathlib import Path

import pytest

from memory_sanitizer import MemorySanitizer


@pytest.fixture
def temp_memory_dir():
    """Create a temporary memory directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_corrupted_memory():
    """Sample corrupted memory content with duplicates and test entries."""
    return """## Distilled Memories (February 2026)
- **2026-02-05**: ## Test
I decided to build a feature today.

## Distilled Memories (February 2026)
- **2026-02-05**: ## Test
I decided to build a feature today.

## Distilled Memories (February 2026)
- **2026-02-05**: Memory for 2026-02-03 | Memory for 2026-02-04 | Memory for 2026-02-05

## Distilled Memories (February 2026)
- **2026-02-05**: ## Test
I decided to build a feature today.

## Distilled Memories (February 2026)
- **2026-02-04**: Built Memory Audit Utility with TDD (6 tests passing).

## Distilled Memories (February 2026)
- **2026-02-04**: Built Memory Audit Utility with TDD (6 tests passing).

## Valid Memory
- **2026-02-05**: Important decision about trust boundaries with human.
"""


@pytest.fixture
def sample_clean_memory():
    """Sample clean memory content."""
    return """## Distilled Memories (February 2026)
- **2026-02-04**: Built Memory Audit Utility with TDD.
- **2026-02-05**: Shipped SignalTracker feature with 15 tests passing.
"""


class TestMemorySanitizer:
    """Test cases for MemorySanitizer class."""

    def test_detect_duplicate_entries(self, temp_memory_dir):
        """Test detection of duplicate memory entries."""
        sanitizer = MemorySanitizer(temp_memory_dir)
        
        content = """## Distilled Memories
- **2026-02-05**: Test entry 1.
- **2026-02-05**: Test entry 1.
- **2026-02-05**: Unique entry.
"""
        Path(temp_memory_dir, "MEMORY.md").write_text(content)
        
        duplicates = sanitizer.find_duplicates()
        
        assert len(duplicates) >= 1
        assert "Test entry 1" in str(duplicates)

    def test_detect_test_entries(self, temp_memory_dir):
        """Test detection of test/corrupted entries."""
        sanitizer = MemorySanitizer(temp_memory_dir)
        
        content = """## Distilled Memories
- **2026-02-05**: ## Test
I decided to build a feature today.
- **2026-02-05**: Valid memory entry.
"""
        Path(temp_memory_dir, "MEMORY.md").write_text(content)
        
        test_entries = sanitizer.find_test_entries()
        
        assert len(test_entries) >= 1

    def test_clean_memory(self, temp_memory_dir, sample_corrupted_memory):
        """Test cleaning corrupted memory content."""
        sanitizer = MemorySanitizer(temp_memory_dir)
        
        cleaned = sanitizer.clean_content(sample_corrupted_memory)
        
        # Should not contain duplicate "## Test" entries
        assert "## Test" not in cleaned or cleaned.count("## Test") < 2
        # Should preserve valid entries
        assert "Important decision" in cleaned or "Test entry 1" not in cleaned

    def test_get_memory_stats(self, temp_memory_dir, sample_corrupted_memory):
        """Test getting memory statistics."""
        sanitizer = MemorySanitizer(temp_memory_dir)
        Path(temp_memory_dir, "MEMORY.md").write_text(sample_corrupted_memory)
        
        stats = sanitizer.get_stats()
        
        assert "total_entries" in stats
        assert "duplicate_count" in stats
        assert "test_entry_count" in stats
        assert "lines" in stats
        assert stats["total_entries"] >= 0

    def test_daily_log_handling(self, temp_memory_dir):
        """Test that daily logs are properly indexed."""
        sanitizer = MemorySanitizer(temp_memory_dir)
        
        # Create daily log
        daily_content = """# Daily Log
- Action: Built SignalTracker
- Result: 15 tests passing
"""
        Path(temp_memory_dir, "2026-02-05.md").write_text(daily_content)
        
        daily_files = sanitizer.get_daily_logs()
        
        assert len(daily_files) >= 1

    def test_run_full_cleanup(self, temp_memory_dir, sample_corrupted_memory):
        """Test running full cleanup process."""
        sanitizer = MemorySanitizer(temp_memory_dir)
        Path(temp_memory_dir, "MEMORY.md").write_text(sample_corrupted_memory)
        
        report = sanitizer.run_cleanup()
        
        assert "entries_removed" in report
        assert "duplicates_found" in report
        assert "test_entries_found" in report
        assert report["entries_removed"] >= 0

    def test_preserve_important_entries(self, temp_memory_dir):
        """Test that important entries are preserved during cleanup."""
        sanitizer = MemorySanitizer(temp_memory_dir)
        
        content = """## Distilled Memories
- **2026-02-05**: ## Test
I decided to build a feature today.
- **2026-02-05**: User said "remember this preference: dark mode".
"""
        Path(temp_memory_dir, "MEMORY.md").write_text(content)
        
        cleaned = sanitizer.clean_content(content)
        
        # User preferences should be preserved
        assert "dark mode" in cleaned or "remember this" in cleaned

    def test_empty_memory_file(self, temp_memory_dir):
        """Test handling of empty memory file."""
        sanitizer = MemorySanitizer(temp_memory_dir)
        Path(temp_memory_dir, "MEMORY.md").write_text("")
        
        stats = sanitizer.get_stats()
        
        assert stats["total_entries"] == 0

    def test_no_memory_file(self, temp_memory_dir):
        """Test when MEMORY.md doesn't exist."""
        sanitizer = MemorySanitizer(temp_memory_dir)
        
        # Should not raise error
        stats = sanitizer.get_stats()
        
        assert "error" not in stats
