"""Tests for activity_snapshot.py - Daily activity tracking."""

import json
import os
from datetime import date
from pathlib import Path
from unittest.mock import patch
import pytest

# Import the module under test
import core.activity_snapshot as activity_snapshot


class TestActivitySnapshot:
    """Test activity snapshot functionality."""
    
    @pytest.fixture(autouse=True)
    def setup(self, tmp_path, monkeypatch):
        """Set up test environment."""
        self.test_snapshot_dir = tmp_path / "snapshots"
        monkeypatch.setattr(activity_snapshot, "SNAPSHOT_DIR", self.test_snapshot_dir)
        monkeypatch.setattr(activity_snapshot, "TODAY_FILE", self.test_snapshot_dir / f"{date.today()}.json")
        
        # Clean up any existing test files
        if self.test_snapshot_dir.exists():
            for f in self.test_snapshot_dir.glob("*.json"):
                f.unlink()
    
    def test_load_today_snapshot_creates_new(self):
        """Test that loading non-existent snapshot creates empty one."""
        snapshot = activity_snapshot.load_today_snapshot()
        
        assert snapshot["date"] == str(date.today())
        assert snapshot["features"] == []
        assert snapshot["tests_added"] == 0
        assert snapshot["tests_passed"] == 0
        assert snapshot["tests_failed"] == 0
        assert snapshot["moltbook_posts"] == 0
        assert snapshot["commits"] == 0
    
    def test_add_feature(self):
        """Test adding a feature to today's snapshot."""
        count = activity_snapshot.add_feature("Test Feature", "A test description")
        
        assert count == 1
        
        snapshot = activity_snapshot.load_today_snapshot()
        assert len(snapshot["features"]) == 1
        assert snapshot["features"][0]["name"] == "Test Feature"
        assert snapshot["features"][0]["description"] == "A test description"
    
    def test_add_multiple_features(self):
        """Test adding multiple features."""
        activity_snapshot.add_feature("Feature 1")
        activity_snapshot.add_feature("Feature 2")
        activity_snapshot.add_feature("Feature 3")
        
        snapshot = activity_snapshot.load_today_snapshot()
        assert len(snapshot["features"]) == 3
    
    def test_increment_tests(self):
        """Test incrementing test counts."""
        activity_snapshot.increment_tests(added=10, passed=8, failed=2)
        
        snapshot = activity_snapshot.load_today_snapshot()
        assert snapshot["tests_added"] == 10
        assert snapshot["tests_passed"] == 8
        assert snapshot["tests_failed"] == 2
    
    def test_increment_tests_cumulative(self):
        """Test that test increments are cumulative."""
        activity_snapshot.increment_tests(added=5, passed=5)
        activity_snapshot.increment_tests(added=3, passed=3)
        
        snapshot = activity_snapshot.load_today_snapshot()
        assert snapshot["tests_added"] == 8
        assert snapshot["tests_passed"] == 8
    
    def test_increment_posts(self):
        """Test incrementing Moltbook post count."""
        activity_snapshot.increment_posts(2)
        
        snapshot = activity_snapshot.load_today_snapshot()
        assert snapshot["moltbook_posts"] == 2
    
    def test_increment_commits(self):
        """Test incrementing commit count."""
        activity_snapshot.increment_commits(3)
        
        snapshot = activity_snapshot.load_today_snapshot()
        assert snapshot["commits"] == 3
    
    def test_get_today_summary(self):
        """Test getting today's summary."""
        activity_snapshot.add_feature("My Feature")
        activity_snapshot.increment_tests(added=5)
        
        summary = activity_snapshot.get_today_summary()
        
        assert "features" in summary
        assert "tests_added" in summary
        assert summary["date"] == str(date.today())
    
    def test_snapshot_file_created(self):
        """Test that snapshot file is actually created."""
        activity_snapshot.add_feature("Test")
        
        assert activity_snapshot.TODAY_FILE.exists()
        
        with open(activity_snapshot.TODAY_FILE) as f:
            data = json.load(f)
        
        assert data["date"] == str(date.today())
        assert len(data["features"]) == 1
