#!/usr/bin/env python3
"""
Tests for Daily Maintenance Routine.
"""

import os
import sys
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest
from daily_maintenance import DailyMaintenance
from memory_decay import MemoryDecayEngine, MemoryAccessTracker


@pytest.fixture
def temp_memory_dir():
    """Create a temporary memory directory for testing."""
    temp_dir = tempfile.mkdtemp()
    memory_dir = os.path.join(temp_dir, "memory")
    os.makedirs(memory_dir)
    yield memory_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def sample_memories(temp_memory_dir):
    """Create sample memory files for testing."""
    # Create some test memories
    for i in range(5):
        with open(os.path.join(temp_memory_dir, f"test_memory_{i}.md"), 'w') as f:
            f.write(f"# Test Memory {i}\n\nThis is test content {i}.")
    
    # Create a fresh memory (accessed recently)
    fresh_memory = os.path.join(temp_memory_dir, "fresh_memory.md")
    with open(fresh_memory, 'w') as f:
        f.write("# Fresh Memory\n\nAccessed recently.")
    
    # Create an access log
    tracker = MemoryAccessTracker(memory_dir=temp_memory_dir)
    tracker.record_access("fresh_memory.md", source="test")
    
    return temp_memory_dir


class TestDailyMaintenance:
    """Tests for DailyMaintenance class."""

    def test_should_run_decay_first_time(self, temp_memory_dir):
        """Test that decay runs on first call."""
        maintenance = DailyMaintenance(execute_changes=False, quiet=True)
        maintenance.memory_dir = temp_memory_dir
        maintenance.state_file = os.path.join(temp_memory_dir, ".test_state.json")
        maintenance.last_run = {"last_decay_run": None}
        
        assert maintenance.should_run_decay() == True

    def test_should_not_run_decay_same_day(self, temp_memory_dir):
        """Test that decay doesn't run twice in same day."""
        maintenance = DailyMaintenance(execute_changes=False, quiet=True)
        maintenance.memory_dir = temp_memory_dir
        maintenance.state_file = os.path.join(temp_memory_dir, ".test_state.json")
        maintenance.last_run = {
            "last_decay_run": datetime.now().isoformat()
        }
        
        assert maintenance.should_run_decay() == False

    def test_should_run_decay_next_day(self, temp_memory_dir):
        """Test that decay runs next day."""
        maintenance = DailyMaintenance(execute_changes=False, quiet=True)
        maintenance.memory_dir = temp_memory_dir
        maintenance.state_file = os.path.join(temp_memory_dir, ".test_state.json")
        maintenance.last_run = {
            "last_decay_run": (datetime.now() - timedelta(days=1)).isoformat()
        }
        
        assert maintenance.should_run_decay() == True

    def test_run_decay_check_dry_run(self, temp_memory_dir, sample_memories):
        """Test decay check in dry-run mode."""
        maintenance = DailyMaintenance(execute_changes=False, quiet=True)
        maintenance.memory_dir = temp_memory_dir
        maintenance.state_file = os.path.join(temp_memory_dir, ".test_state.json")
        maintenance.last_run = {"last_decay_run": None}
        
        result = maintenance.run_decay_check()
        
        assert result["skipped"] == False
        assert "stale_count" in result

    def test_run_health_check(self, temp_memory_dir, sample_memories):
        """Test health check."""
        maintenance = DailyMaintenance(execute_changes=False, quiet=True)
        maintenance.memory_dir = temp_memory_dir
        maintenance.state_file = os.path.join(temp_memory_dir, ".test_state.json")
        maintenance.last_run = {}
        
        result = maintenance.run_health_check()
        
        assert "healthy" in result
        assert "issues" in result

    def test_state_file_created(self, temp_memory_dir, sample_memories):
        """Test that state file is created after run."""
        maintenance = DailyMaintenance(execute_changes=False, quiet=True)
        maintenance.memory_dir = temp_memory_dir
        maintenance.state_file = os.path.join(temp_memory_dir, ".test_state.json")
        maintenance.last_run = {"last_decay_run": None}
        
        maintenance.run_decay_check()
        
        assert os.path.exists(maintenance.state_file)
        
        with open(maintenance.state_file, 'r') as f:
            state = json.load(f)
        
        assert "last_decay_run" in state

    def test_execute_mode_archives_memories(self, temp_memory_dir):
        """Test that execute mode actually archives stale memories."""
        # Create old memories
        old_memory = os.path.join(temp_memory_dir, "old_memory.md")
        with open(old_memory, 'w') as f:
            f.write("# Old Memory\n\nNot accessed.")
        
        # Track as old (manually set access log)
        tracker = MemoryAccessTracker(memory_dir=temp_memory_dir)
        tracker.record_access("old_memory.md", source="test")
        
        # Set access date to 100 days ago
        old_date = (datetime.now() - timedelta(days=100)).isoformat()
        tracker.access_log["old_memory.md"]["last_access"] = old_date
        tracker._save_access_log()
        
        # Run maintenance with execute
        maintenance = DailyMaintenance(execute_changes=True, quiet=True)
        maintenance.memory_dir = temp_memory_dir
        maintenance.state_file = os.path.join(temp_memory_dir, ".test_state.json")
        maintenance.last_run = {"last_decay_run": None}
        
        result = maintenance.run_decay_check()
        
        # Memory should be archived
        archive_dir = os.path.join(temp_memory_dir, "memory_archive")
        assert os.path.exists(os.path.join(archive_dir, "old_memory.md"))


class TestMemoryDecayEngine:
    """Tests for MemoryDecayEngine integration."""

    def test_get_decay_report(self, temp_memory_dir):
        """Test decay report generation."""
        # Create memories
        for i in range(3):
            with open(os.path.join(temp_memory_dir, f"mem_{i}.md"), 'w') as f:
                f.write(f"# Memory {i}")
        
        # Track some accesses
        tracker = MemoryAccessTracker(memory_dir=temp_memory_dir)
        tracker.record_access("mem_0.md", source="test")
        tracker.record_access("mem_1.md", source="test")
        
        engine = MemoryDecayEngine(memory_dir=temp_memory_dir)
        report = engine.get_decay_report(days=90)
        
        assert "stale_count" in report
        assert "frequent_count" in report
        assert "total_memory_files" in report


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
