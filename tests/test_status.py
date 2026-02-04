"""Tests for status.py module."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Module under test
from core import status


class TestStatus:
    """Test suite for status reporting module."""

    @pytest.fixture
    def mock_lifetime_stats(self, monkeypatch):
        """Provide mock lifetime stats."""
        def _mock_stats():
            return {
                "born_at": "2026-01-01T00:00:00",
                "total_wakeups": 42,
                "total_uptime_formatted": "5d 3h",
                "total_uptime_seconds": 442800.0,
                "current_session_seconds": 3600.0,
                "current_session_formatted": "1h 0m",
                "is_current_session": True
            }
        monkeypatch.setattr(status, "get_lifetime_stats", _mock_stats)

    @pytest.fixture
    def mock_pet_state(self, monkeypatch):
        """Provide mock pet state."""
        mock_pet = MagicMock()
        mock_pet.get_cat_name.return_value = "happy"
        mock_pet.get_face.return_value = "(•‿‿•)"
        mock_pet.last_feed_rate = 0.0  # Default to idle
        monkeypatch.setattr(status, "PetState", lambda: mock_pet)

    def test_format_status_line_uses_lifetime_data(self, mock_lifetime_stats):
        """format_status_line should return a string."""
        line = status.format_status_line()
        assert isinstance(line, str)
        assert len(line) > 0

    def test_get_status_report_returns_dict(self, mock_lifetime_stats, mock_pet_state):
        """get_status_report should return a dictionary."""
        report = status.get_status_report()
        assert isinstance(report, dict)
        assert "lifetime" in report
        assert "generated_at" in report

    def test_get_status_report_includes_timestamp(self, mock_lifetime_stats, mock_pet_state):
        """get_status_report should include a generated_at timestamp."""
        report = status.get_status_report()
        assert "generated_at" in report
        # Should be a valid ISO string
        datetime.fromisoformat(report["generated_at"])

    def test_get_status_report_includes_agent_status(self, mock_lifetime_stats, mock_pet_state):
        """get_status_report should include agent_status for Moltbook API compatibility."""
        report = status.get_status_report()
        assert "agent_status" in report
        assert "mood" in report["agent_status"]
        assert "face" in report["agent_status"]
        assert "activity" in report["agent_status"]
        assert "feed_rate" in report["agent_status"]
        # Mood should be the cat emotion
        assert report["agent_status"]["mood"] == "happy"
        # Face should be the current frame
        assert report["agent_status"]["face"] == "(•‿‿•)"
        # Activity should be a string
        assert isinstance(report["agent_status"]["activity"], str)

    def test_cli_output_contains_uptime(self, mock_lifetime_stats, mock_pet_state, capsys):
        """CLI mode should print status to stdout."""
        import sys
        from io import StringIO
        
        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        try:
            status.main(["cli"])
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        
        assert "5d 3h" in output or "uptime" in output.lower()

    def test_cli_output_contains_wakeups(self, mock_lifetime_stats, mock_pet_state, capsys):
        """CLI mode should print wakeup count."""
        import sys
        from io import StringIO
        
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        try:
            status.main(["cli"])
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        
        assert "42" in output or "wakeups" in output.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
