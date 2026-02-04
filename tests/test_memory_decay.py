"""
Tests for Memory Decay System.
"""

import os
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from cognition.memory_decay import (
    MemoryAccessTracker,
    MemoryDecayEngine,
    DEFAULT_DECAY_DAYS,
    ACCESS_LOG_FILE
)


class TestMemoryAccessTracker:
    """Tests for MemoryAccessTracker."""

    def setup_method(self):
        """Create a temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.tracker = MemoryAccessTracker(memory_dir=self.temp_dir)

    def teardown_method(self):
        """Clean up after each test."""
        shutil.rmtree(self.temp_dir)

    def test_record_access(self):
        """Test recording memory access."""
        self.tracker.record_access("test_memory.md", source="test")

        assert "test_memory.md" in self.tracker.access_log
        info = self.tracker.access_log["test_memory.md"]
        assert info["access_count"] == 1
        assert info["last_access"] is not None
        assert "test" in info["sources"]
        assert len(info["sources"]["test"]) == 1

    def test_record_multiple_accesses(self):
        """Test recording multiple accesses to same memory."""
        self.tracker.record_access("test_memory.md", source="test")
        self.tracker.record_access("test_memory.md", source="search")
        self.tracker.record_access("test_memory.md", source="test")

        info = self.tracker.access_log["test_memory.md"]
        assert info["access_count"] == 3
        assert len(info["sources"]["test"]) == 2
        assert len(info["sources"]["search"]) == 1

    def test_get_access_info(self):
        """Test getting access info for a memory."""
        self.tracker.record_access("new_memory.md", source="test")

        info = self.tracker.get_access_info("new_memory.md")
        assert info["access_count"] == 1
        assert info["last_access"] is not None

    def test_get_access_info_nonexistent(self):
        """Test getting info for nonexistent memory."""
        info = self.tracker.get_access_info("nonexistent.md")
        assert info["access_count"] == 0
        assert info["last_access"] is None

    def test_get_stale_memories(self):
        """Test getting stale memories."""
        # Create some access entries
        self.tracker.access_log["fresh_memory.md"] = {
            "access_count": 5,
            "last_access": datetime.now().isoformat(),
            "sources": {"test": []},
            "created": datetime.now().isoformat()
        }

        # Old memory (91 days ago)
        old_date = datetime.now() - timedelta(days=91)
        self.tracker.access_log["stale_memory.md"] = {
            "access_count": 2,
            "last_access": old_date.isoformat(),
            "sources": {"test": []},
            "created": old_date.isoformat()
        }

        # Very old memory
        very_old_date = datetime.now() - timedelta(days=200)
        self.tracker.access_log["very_stale_memory.md"] = {
            "access_count": 1,
            "last_access": very_old_date.isoformat(),
            "sources": {"test": []},
            "created": very_old_date.isoformat()
        }

        self.tracker._save_access_log()

        stale = self.tracker.get_stale_memories(days=90)

        # Should have 2 stale memories
        stale_files = [s["file"] for s in stale]
        assert "stale_memory.md" in stale_files
        assert "very_stale_memory.md" in stale_files
        assert "fresh_memory.md" not in stale_files

    def test_get_frequently_accessed(self):
        """Test getting frequently accessed memories."""
        self.tracker.access_log["frequent_1.md"] = {
            "access_count": 10,
            "last_access": datetime.now().isoformat(),
            "sources": {"test": []},
            "created": datetime.now().isoformat()
        }

        self.tracker.access_log["frequent_2.md"] = {
            "access_count": 5,
            "last_access": datetime.now().isoformat(),
            "sources": {"test": []},
            "created": datetime.now().isoformat()
        }

        self.tracker.access_log["rare.md"] = {
            "access_count": 2,
            "last_access": datetime.now().isoformat(),
            "sources": {"test": []},
            "created": datetime.now().isoformat()
        }

        frequent = self.tracker.get_frequently_accessed(min_count=5)

        assert len(frequent) == 2
        frequent_files = [f["file"] for f in frequent]
        assert "frequent_1.md" in frequent_files
        assert "frequent_2.md" in frequent_files
        assert "rare.md" not in frequent_files

    def test_calculate_freshness(self):
        """Test freshness score calculation."""
        # Recently accessed memory
        recent_info = {
            "access_count": 10,
            "last_access": datetime.now().isoformat()
        }
        recent_score = self.tracker._calculate_freshness(recent_info)
        assert recent_score > 80  # Should be very fresh

        # Old memory
        old_info = {
            "access_count": 5,
            "last_access": (datetime.now() - timedelta(days=60)).isoformat()
        }
        old_score = self.tracker._calculate_freshness(old_info)
        assert old_score < recent_score

        # Never accessed
        never_info = {
            "access_count": 0,
            "last_access": None
        }
        never_score = self.tracker._calculate_freshness(never_info)
        assert never_score == 0


class TestMemoryDecayEngine:
    """Tests for MemoryDecayEngine."""

    def setup_method(self):
        """Create a temporary directory for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.engine = MemoryDecayEngine(memory_dir=self.temp_dir)

    def teardown_method(self):
        """Clean up after each test."""
        shutil.rmtree(self.temp_dir)

    def test_archive_stale_memories_dry_run(self):
        """Test dry-run archive of stale memories."""
        # Create a stale memory file
        stale_file = os.path.join(self.temp_dir, "stale_memory.md")
        with open(stale_file, 'w') as f:
            f.write("# Stale Memory\n\nThis is old.")

        # Add to access log with old date
        old_date = datetime.now() - timedelta(days=100)
        self.engine.tracker.access_log["stale_memory.md"] = {
            "access_count": 2,
            "last_access": old_date.isoformat(),
            "sources": {"test": []},
            "created": old_date.isoformat()
        }
        self.engine.tracker._save_access_log()

        # Run dry-run
        archived = self.engine.archive_stale_memories(stale_days=90, dry_run=True)

        assert len(archived) == 1
        assert archived[0]["action"] == "would_archive"
        assert archived[0]["file"] == "stale_memory.md"

        # File should still exist
        assert os.path.exists(stale_file)

    def test_archive_stale_memories_execute(self):
        """Test actual archive of stale memories."""
        # Create a stale memory file
        stale_file = os.path.join(self.temp_dir, "stale_memory.md")
        with open(stale_file, 'w') as f:
            f.write("# Stale Memory\n\nThis is old.")

        # Add to access log with old date
        old_date = datetime.now() - timedelta(days=100)
        self.engine.tracker.access_log["stale_memory.md"] = {
            "access_count": 2,
            "last_access": old_date.isoformat(),
            "sources": {"test": []},
            "created": old_date.isoformat()
        }
        self.engine.tracker._save_access_log()

        # Execute archive
        archived = self.engine.archive_stale_memories(stale_days=90, dry_run=False)

        assert len(archived) == 1
        assert archived[0]["action"] == "archived"

        # File should be moved to archive
        assert not os.path.exists(stale_file)
        assert os.path.exists(os.path.join(self.engine.archive_dir, "stale_memory.md"))

    def test_compress_negative_outcomes_dry_run(self):
        """Test dry-run compression of negative outcomes."""
        from datetime import datetime

        # Create a log with negative outcome using today's date
        today = datetime.now()
        today_str = today.strftime('%Y-%m-%d')
        log_file = os.path.join(self.temp_dir, f"{today_str}.md")
        with open(log_file, 'w') as f:
            f.write(f"""# Failed Approach

- Tried to use regex but it didn't work
- Lesson: Use proper parsing library instead
- Error: The pattern crashed

Next time I'll do it differently.
""")

        # Run dry-run
        compressed = self.engine.compress_negative_outcomes(dry_run=True)

        assert len(compressed) == 1
        assert compressed[0]["action"] == "would_compress"
        assert "lessons" in compressed[0]

    def test_extract_lessons(self):
        """Test lesson extraction."""
        content = """# Daily Log

- Lesson: Always test before shipping
- Key: Memory systems need decay
- Remember: Don't break tests
"""

        lessons = self.engine._extract_lessons(content)

        assert len(lessons) > 0
        assert any("test" in l.lower() for l in lessons)

    def test_cleanup_unaccessed_dry_run(self):
        """Test dry-run cleanup of unaccessed memories."""
        # Create some memory files
        with open(os.path.join(self.temp_dir, "unaccessed_1.md"), 'w') as f:
            f.write("# Unaccessed 1")

        with open(os.path.join(self.temp_dir, "unaccessed_2.md"), 'w') as f:
            f.write("# Unaccessed 2")

        # Track only one of them
        self.engine.tracker.record_access("unaccessed_1.md", source="test")
        self.engine.tracker._save_access_log()

        # Run cleanup (dry-run)
        cleaned = self.engine.cleanup_unaccessed(dry_run=True)

        assert len(cleaned) == 1
        assert cleaned[0]["file"] == "unaccessed_2.md"

    def test_get_decay_report(self):
        """Test getting comprehensive decay report."""
        # Add some data
        self.engine.tracker.record_access("memory_1.md", source="test")
        self.engine.tracker.record_access("memory_1.md", source="search")
        self.engine.tracker.record_access("memory_2.md", source="test")

        # Create a stale memory
        old_date = datetime.now() - timedelta(days=100)
        self.engine.tracker.access_log["stale.md"] = {
            "access_count": 1,
            "last_access": old_date.isoformat(),
            "sources": {"test": []},
            "created": old_date.isoformat()
        }
        self.engine.tracker._save_access_log()

        report = self.engine.get_decay_report(days=90)

        assert "stale_count" in report
        assert "frequent_count" in report
        assert "total_memory_files" in report
        assert report["stale_count"] >= 1

    def test_preserves_important_files(self):
        """Test that important files like MEMORY.md are preserved."""
        # Create important files
        with open(os.path.join(self.temp_dir, "MEMORY.md"), 'w') as f:
            f.write("# Curated Memory")

        with open(os.path.join(self.temp_dir, "WORKING.md"), 'w') as f:
            f.write("# Working Memory")

        # Add them to access log as stale
        old_date = datetime.now() - timedelta(days=100)
        self.engine.tracker.access_log["MEMORY.md"] = {
            "access_count": 1,
            "last_access": old_date.isoformat(),
            "sources": {"test": []},
            "created": old_date.isoformat()
        }
        self.engine.tracker._save_access_log()

        # Cleanup
        cleaned = self.engine.cleanup_unaccessed(dry_run=True)

        # Important files should not be in cleanup list
        cleaned_files = [c["file"] for c in cleaned]
        assert "MEMORY.md" not in cleaned_files
        assert "WORKING.md" not in cleaned_files


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
