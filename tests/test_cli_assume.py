"""Tests for cli_assume.py - CLI interface for assumption tracking."""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from io import StringIO
from unittest.mock import patch

import pytest

# Add the workspace to path
sys.path.insert(0, '/workspace')

from assumption_tracker import AssumptionTracker


@pytest.fixture
def temp_tracker():
    """Create a tracker with temp storage."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        f.write('{"assumptions": [], "last_updated": "' + datetime.now().isoformat() + '"}')
        temp_path = f.name
    
    tracker = AssumptionTracker(storage_path=temp_path)
    yield tracker
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


class TestCLIRecord:
    """Test the record command."""
    
    def test_record_basic(self, temp_tracker, monkeypatch):
        """Test basic assumption recording."""
        from cli_assume import cmd_record
        import argparse
        
        # Create mock args
        args = argparse.Namespace(
            assumption="Test assumption content",
            category="test",
            context="Test context",
            days=None
        )
        
        with patch('cli_assume.AssumptionTracker', return_value=temp_tracker):
            cmd_record(args)
        
        assert len(temp_tracker.assumptions) == 1
        assert temp_tracker.assumptions[0].content == "Test assumption content"
        assert temp_tracker.assumptions[0].category == "test"
    
    def test_record_with_days(self, temp_tracker, monkeypatch):
        """Test recording with expected verification days."""
        from cli_assume import cmd_record
        import argparse
        
        args = argparse.Namespace(
            assumption="Will verify in 5 days",
            category="prediction",
            context=None,
            days="5"
        )
        
        with patch('cli_assume.AssumptionTracker', return_value=temp_tracker):
            cmd_record(args)
        
        assumption = temp_tracker.assumptions[0]
        expected = datetime.now() + timedelta(days=5)
        assert assumption.expected_verification is not None
        # Check it's approximately 5 days from now
        diff = abs((assumption.expected_verification - expected).total_seconds())
        assert diff < 5  # Within 5 seconds tolerance


class TestCLIVerify:
    """Test the verify command."""
    
    def test_verify_correct(self, temp_tracker, monkeypatch):
        """Test verifying an assumption as correct."""
        from cli_assume import cmd_verify
        import argparse
        
        # First record an assumption
        assumption_id = temp_tracker.record(
            content="Test assumption",
            category="test"
        )
        
        args = argparse.Namespace(
            assumption_id=assumption_id,
            correct=True,
            incorrect=False,
            evidence=["Test evidence"]
        )
        
        with patch('cli_assume.AssumptionTracker', return_value=temp_tracker):
            cmd_verify(args)
        
        assumption = temp_tracker.get(assumption_id)
        assert assumption.status.value == "verified"
        assert assumption.was_correct is True
        assert "Test evidence" in assumption.evidence
    
    def test_verify_incorrect(self, temp_tracker, monkeypatch):
        """Test verifying an assumption as incorrect."""
        from cli_assume import cmd_verify
        import argparse
        
        assumption_id = temp_tracker.record(
            content="Wrong prediction",
            category="test"
        )
        
        args = argparse.Namespace(
            assumption_id=assumption_id,
            correct=False,
            incorrect=True,
            evidence=[]
        )
        
        with patch('cli_assume.AssumptionTracker', return_value=temp_tracker):
            cmd_verify(args)
        
        assumption = temp_tracker.get(assumption_id)
        assert assumption.status.value == "verified"
        assert assumption.was_correct is False
    
    def test_verify_nonexistent(self, temp_tracker, monkeypatch):
        """Test verifying a non-existent assumption."""
        from cli_assume import cmd_verify
        import argparse
        
        args = argparse.Namespace(
            assumption_id="nonexistent-id",
            correct=True,
            incorrect=False,
            evidence=[]
        )
        
        with pytest.raises(SystemExit):
            with patch('cli_assume.AssumptionTracker', return_value=temp_tracker):
                cmd_verify(args)


class TestCLIList:
    """Test the list command."""
    
    def test_list_all(self, temp_tracker, capsys):
        """Test listing all assumptions."""
        from cli_assume import cmd_list
        import argparse
        
        # Record some assumptions
        temp_tracker.record(content="Assumption 1", category="fact")
        temp_tracker.record(content="Assumption 2", category="prediction")
        
        args = argparse.Namespace(
            open=False,
            stale=False,
            category=None
        )
        
        with patch('cli_assume.AssumptionTracker', return_value=temp_tracker):
            cmd_list(args)
        
        captured = capsys.readouterr()
        assert "All assumptions" in captured.out
        assert "2" in captured.out
    
    def test_list_stale(self, temp_tracker, capsys):
        """Test listing stale assumptions."""
        from cli_assume import cmd_list
        import argparse
        
        # Create old assumption
        old_id = temp_tracker.record(content="Old assumption", category="test")
        # Manually set timestamp to 10 days ago
        old = temp_tracker.get(old_id)
        old.timestamp = datetime.now() - timedelta(days=10)
        temp_tracker._save()
        
        args = argparse.Namespace(
            open=False,
            stale=True,
            category=None
        )
        
        with patch('cli_assume.AssumptionTracker', return_value=temp_tracker):
            cmd_list(args)
        
        captured = capsys.readouterr()
        assert "Stale assumptions" in captured.out


class TestCLISummary:
    """Test the summary command."""
    
    def test_summary_empty(self, temp_tracker, capsys):
        """Test summary with no assumptions."""
        from cli_assume import cmd_summary
        import argparse
        
        args = argparse.Namespace()
        
        with patch('cli_assume.AssumptionTracker', return_value=temp_tracker):
            cmd_summary(args)
        
        captured = capsys.readouterr()
        assert "Assumption Tracker Summary" in captured.out
        assert "Total: 0" in captured.out
    
    def test_summary_with_data(self, temp_tracker, capsys):
        """Test summary with recorded assumptions."""
        from cli_assume import cmd_summary
        import argparse
        
        temp_tracker.record(content="Fact 1", category="fact")
        temp_tracker.record(content="Fact 2", category="fact")
        
        # Verify one
        assumptions = temp_tracker.get_open()
        temp_tracker.verify(assumptions[0].id, correct=True)
        
        args = argparse.Namespace()
        
        with patch('cli_assume.AssumptionTracker', return_value=temp_tracker):
            cmd_summary(args)
        
        captured = capsys.readouterr()
        assert "Total: 2" in captured.out
        assert "fact: 2" in captured.out
        assert "Accuracy" in captured.out


class TestCLIStale:
    """Test the stale command."""
    
    def test_no_stale(self, temp_tracker, capsys):
        """Test stale check with no stale assumptions."""
        from cli_assume import cmd_stale
        import argparse
        
        temp_tracker.record(content="Recent assumption", category="test")
        
        args = argparse.Namespace()
        
        with patch('cli_assume.AssumptionTracker', return_value=temp_tracker):
            cmd_stale(args)
        
        captured = capsys.readouterr()
        assert "No stale assumptions" in captured.out
    
    def test_has_stale(self, temp_tracker, capsys):
        """Test stale check with stale assumptions."""
        from cli_assume import cmd_stale
        import argparse
        
        # Create stale assumption
        stale_id = temp_tracker.record(content="Stale assumption", category="test")
        stale = temp_tracker.get(stale_id)
        stale.timestamp = datetime.now() - timedelta(days=10)
        temp_tracker._save()
        
        args = argparse.Namespace()
        
        with patch('cli_assume.AssumptionTracker', return_value=temp_tracker):
            cmd_stale(args)
        
        captured = capsys.readouterr()
        assert "stale assumptions" in captured.out.lower()
        assert "Stale assumption" in captured.out


class TestCLIConfidence:
    """Test the confidence command."""
    
    def test_record_with_confidence(self, temp_tracker, capsys):
        """Test recording with custom confidence."""
        from cli_assume import cmd_record
        import argparse
        
        args = argparse.Namespace(
            assumption="High confidence assumption",
            category="test",
            context="Very sure about this",
            days=None,
            confidence="0.9"
        )
        
        with patch('cli_assume.AssumptionTracker', return_value=temp_tracker):
            cmd_record(args)
        
        assumption = temp_tracker.assumptions[0]
        assert assumption.confidence == 0.9
        assert len(assumption.confidence_history) == 1
    
    def test_record_default_confidence(self, temp_tracker, capsys):
        """Test that default confidence is 0.8."""
        from cli_assume import cmd_record
        import argparse
        
        args = argparse.Namespace(
            assumption="Default confidence",
            category="test",
            context=None,
            days=None,
            confidence=None
        )
        
        with patch('cli_assume.AssumptionTracker', return_value=temp_tracker):
            cmd_record(args)
        
        assumption = temp_tracker.assumptions[0]
        assert assumption.confidence == 0.8
    
    def test_confidence_update(self, temp_tracker, capsys):
        """Test updating confidence of an assumption."""
        from cli_assume import cmd_confidence
        import argparse
        
        # Create an assumption
        assumption_id = temp_tracker.record(
            content="Updating confidence",
            category="test"
        )
        
        args = argparse.Namespace(
            assumption_id=assumption_id,
            new_confidence=0.5
        )
        
        with patch('cli_assume.AssumptionTracker', return_value=temp_tracker):
            cmd_confidence(args)
        
        assumption = temp_tracker.get(assumption_id)
        assert assumption.confidence == 0.5
        assert len(assumption.confidence_history) == 2  # Initial + update
    
    def test_confidence_invalid_range(self, temp_tracker, capsys):
        """Test that confidence outside 0-1 range is rejected."""
        from cli_assume import cmd_confidence
        import argparse
        
        assumption_id = temp_tracker.record(
            content="Test",
            category="test"
        )
        
        args = argparse.Namespace(
            assumption_id=assumption_id,
            new_confidence=1.5
        )
        
        with pytest.raises(SystemExit):
            with patch('cli_assume.AssumptionTracker', return_value=temp_tracker):
                cmd_confidence(args)
    
    def test_confidence_nonexistent(self, temp_tracker, capsys):
        """Test updating confidence of non-existent assumption."""
        from cli_assume import cmd_confidence
        import argparse
        
        args = argparse.Namespace(
            assumption_id="nonexistent-id",
            new_confidence=0.5
        )
        
        with pytest.raises(SystemExit):
            with patch('cli_assume.AssumptionTracker', return_value=temp_tracker):
                cmd_confidence(args)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
