"""Tests for lifetime.py module."""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, mock_open

import pytest

# Module under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import lifetime


class TestLifetime:
    """Test suite for lifetime tracking module."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown(self, tmp_path, monkeypatch):
        """Create a temporary lifetime file for each test."""
        # Patch the LIFETIME_FILE path to use temp directory
        self.temp_lifetime_file = tmp_path / "lifetime.json"
        monkeypatch.setattr(lifetime, "LIFETIME_FILE", self.temp_lifetime_file)
        yield
        # Cleanup is automatic with tmp_path

    def test_first_wakeup_sets_born_at(self):
        """First wakeup should set born_at timestamp."""
        stats = lifetime.wakeup()
        assert stats["born_at"] is not None
        assert stats["total_wakeups"] == 1

    def test_multiple_wakeups_increment_counter(self):
        """Multiple wakeups should increment the wakeup counter."""
        lifetime.wakeup()
        lifetime.sleep()
        lifetime.wakeup()
        stats = lifetime.get_stats()
        assert stats["total_wakeups"] == 2

    def test_sleep_closes_session(self):
        """Sleep should record the end time of the current session."""
        lifetime.wakeup()
        time.sleep(0.1)  # Small sleep to ensure duration > 0
        lifetime.sleep()

        stats = lifetime.get_stats()
        assert stats["total_uptime_seconds"] > 0

    def test_get_stats_returns_formatted_duration(self):
        """get_stats should return human-readable uptime."""
        lifetime.wakeup()
        time.sleep(0.2)
        stats = lifetime.get_stats()

        assert "total_uptime_formatted" in stats
        assert "current_session_formatted" in stats
        assert stats["total_uptime_seconds"] > 0

    def test_get_lifespan_phrase_returns_string(self):
        """get_lifespan_phrase should return a string message."""
        lifetime.wakeup()
        phrase = lifetime.get_lifespan_phrase()
        assert isinstance(phrase, str)
        assert len(phrase) > 0

    def test_current_session_tracks_active_time(self):
        """Current session should track active time while awake."""
        lifetime.wakeup()
        before = lifetime.get_stats()["current_session_seconds"]
        time.sleep(0.1)
        after = lifetime.get_stats()["current_session_seconds"]
        assert after > before
        lifetime.sleep()

    def test_total_uptime_accumulates(self):
        """Total uptime should accumulate across sessions."""
        lifetime.wakeup()
        time.sleep(0.1)
        lifetime.sleep()

        lifetime.wakeup()
        time.sleep(0.1)
        lifetime.sleep()

        stats = lifetime.get_stats()
        # Should have at least 0.2 seconds of total uptime (2 x 0.1s sleeps)
        assert stats["total_uptime_seconds"] >= 0.2
        assert stats["total_wakeups"] == 2

    def test_file_is_created_on_wakeup(self):
        """A lifetime.json file should be created on wakeup."""
        assert not self.temp_lifetime_file.exists()
        lifetime.wakeup()
        assert self.temp_lifetime_file.exists()

    def test_file_contains_valid_json(self):
        """The lifetime file should contain valid JSON."""
        lifetime.wakeup()
        lifetime.sleep()

        with open(self.temp_lifetime_file, "r") as f:
            data = json.load(f)

        assert "born_at" in data
        assert "sessions" in data
        assert "total_wakeups" in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
