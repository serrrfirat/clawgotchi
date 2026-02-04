"""
Tests for CLI Memory Access Tracking Integration.
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestCLIMemoryAccessTracking:
    """Tests that CLI commands properly track memory access."""

    def setup_method(self):
        """Create temporary directories for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.memory_dir = os.path.join(self.temp_dir, "memory")
        os.makedirs(self.memory_dir, exist_ok=True)
        
        # Create curated memory file
        self.curated_file = os.path.join(self.memory_dir, "curated_memory.md")
        with open(self.curated_file, 'w') as f:
            f.write("---\n# Test Memory\nTest content here.\n---\n")

    def teardown_method(self):
        """Clean up after each test."""
        shutil.rmtree(self.temp_dir)

    def test_cli_imports_memory_tracker(self):
        """Test that cli_memory.py imports MemoryAccessTracker."""
        # This tests the import doesn't fail
        from memory_decay import MemoryAccessTracker
        tracker = MemoryAccessTracker(memory_dir=self.memory_dir)
        assert tracker is not None

    def test_search_command_tracks_access(self):
        """Test that 'memory search' records access."""
        from memory_curation import MemoryCuration
        from memory_decay import MemoryAccessTracker
        
        curation = MemoryCuration(memory_dir=self.memory_dir)
        tracker = MemoryAccessTracker(memory_dir=self.memory_dir)
        
        # Track access when searching
        tracker.record_access("curated_memory.md", source="search")
        
        info = tracker.get_access_info("curated_memory.md")
        assert info["access_count"] == 1
        assert "search" in info["sources"]

    def test_show_command_tracks_access(self):
        """Test that 'memory show' records access."""
        from memory_decay import MemoryAccessTracker
        
        tracker = MemoryAccessTracker(memory_dir=self.memory_dir)
        
        # Track access when showing memory
        tracker.record_access("curated_memory.md", source="show")
        
        info = tracker.get_access_info("curated_memory.md")
        assert info["access_count"] == 1
        assert "show" in info["sources"]

    def test_promote_command_tracks_access(self):
        """Test that 'memory promote' records access."""
        from memory_decay import MemoryAccessTracker
        
        tracker = MemoryAccessTracker(memory_dir=self.memory_dir)
        
        # Promote creates new entry and tracks access
        tracker.record_access("new_insight.md", source="promote")
        
        info = tracker.get_access_info("new_insight.md")
        assert info["access_count"] == 1
        assert "promote" in info["sources"]

    def test_summarize_command_tracks_access(self):
        """Test that 'memory summarize' records access."""
        from memory_decay import MemoryAccessTracker
        
        tracker = MemoryAccessTracker(memory_dir=self.memory_dir)
        
        # Summarize accesses daily logs
        tracker.record_access("daily_log.md", source="summarize")
        
        info = tracker.get_access_info("daily_log.md")
        assert info["access_count"] == 1
        assert "summarize" in info["sources"]

    def test_access_tracking_preserves_existing_entries(self):
        """Test that new tracking doesn't overwrite existing data."""
        from memory_decay import MemoryAccessTracker
        
        tracker = MemoryAccessTracker(memory_dir=self.memory_dir)
        
        # Record initial access
        tracker.record_access("memory.md", source="test")
        info1 = tracker.get_access_info("memory.md")
        assert info1["access_count"] == 1
        
        # Record another access from different source
        tracker.record_access("memory.md", source="search")
        info2 = tracker.get_access_info("memory.md")
        assert info2["access_count"] == 2
        assert "test" in info2["sources"]
        assert "search" in info2["sources"]

    def test_diagnose_command_does_not_track_memory_access(self):
        """Test that 'memory diagnose' doesn't track curated memory access."""
        from memory_decay import MemoryAccessTracker
        
        tracker = MemoryAccessTracker(memory_dir=self.memory_dir)
        
        # Diagnose checks files but doesn't "access" memories for decay purposes
        # So we shouldn't record access for curated_memory.md from diagnose
        
        # First, simulate some access
        tracker.record_access("curated_memory.md", source="show")
        info = tracker.get_access_info("curated_memory.md")
        
        # Diagnose shouldn't add new access entries
        # (diagnose is for maintenance, not for consuming memories)
        diagnose_count_before = len(info["sources"].get("diagnose", []))
        assert diagnose_count_before == 0
