"""
Tests for the Health Checker module.
"""

import os
import sys
import tempfile
import pytest
from datetime import datetime, timedelta
from pathlib import Path

# Add workspace to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from health_checker import HealthChecker


class TestHealthChecker:
    """Test cases for HealthChecker."""
    
    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace with minimal structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create memory directory
            mem_dir = os.path.join(tmpdir, 'memory')
            os.makedirs(mem_dir)
            
            # Create a test memory file
            with open(os.path.join(mem_dir, 'test_memory.md'), 'w') as f:
                f.write("# Test Memory\n\nSome test content.\n")
            
            # Create assumption tracker
            with open(os.path.join(tmpdir, 'assumption_tracker.py'), 'w') as f:
                f.write("""
class Assumption:
    def __init__(self, text, confidence):
        self.text = text
        self.confidence = confidence

assumptions = []
""")
            
            # Create state file
            with open(os.path.join(tmpdir, 'pet_state.py'), 'w') as f:
                f.write("""
class PetState:
    def __init__(self):
        self.moods = {}
    
    def update(self, mood):
        pass
""")
            
            # Create .git directory
            git_dir = os.path.join(tmpdir, '.git')
            os.makedirs(git_dir)
            
            yield tmpdir
    
    def test_memory_directory_exists(self, temp_workspace):
        """Test that memory directory check passes when it exists."""
        checker = HealthChecker(workspace=temp_workspace)
        result = checker._check_memory_directory()
        assert result['status'] == 'pass'
        assert 'exists' in result['details']
        assert result['details']['exists'] is True
    
    def test_memory_directory_missing(self):
        """Test that memory directory check fails when missing."""
        checker = HealthChecker(workspace='/nonexistent/path')
        result = checker._check_memory_directory()
        assert result['status'] == 'fail'
    
    def test_memory_files_check(self, temp_workspace):
        """Test memory files check."""
        checker = HealthChecker(workspace=temp_workspace)
        result = checker._check_memory_files()
        assert result['status'] == 'pass'
        assert result['details']['total_files'] >= 1
    
    def test_assumption_tracker_valid(self, temp_workspace):
        """Test assumption tracker validation with valid Python."""
        checker = HealthChecker(workspace=temp_workspace)
        result = checker._check_assumption_tracker()
        assert result['status'] == 'pass'
    
    def test_assumption_tracker_syntax_error(self, temp_workspace):
        """Test assumption tracker with syntax error."""
        with open(os.path.join(temp_workspace, 'assumption_tracker.py'), 'w') as f:
            f.write("this is invalid python syntax !!!")
        
        checker = HealthChecker(workspace=temp_workspace)
        result = checker._check_assumption_tracker()
        assert result['status'] == 'fail'
    
    def test_state_file_valid(self, temp_workspace):
        """Test state file validation."""
        checker = HealthChecker(workspace=temp_workspace)
        result = checker._check_state_file()
        assert result['status'] == 'pass'
    
    def test_recent_crash_no_indicators(self, temp_workspace):
        """Test crash detection with no indicators."""
        checker = HealthChecker(workspace=temp_workspace)
        result = checker._check_recent_crash()
        assert result['status'] == 'pass'
    
    def test_run_all_checks_returns_structure(self, temp_workspace):
        """Test that run_all_checks returns expected structure."""
        checker = HealthChecker(workspace=temp_workspace)
        results = checker.run_all_checks()
        
        assert 'timestamp' in results
        assert 'score' in results
        assert 'status' in results
        assert 'checks' in results
        assert 'warnings' in results
        assert 'issues' in results
    
    def test_health_score_calculation(self, temp_workspace):
        """Test that health score is calculated correctly."""
        checker = HealthChecker(workspace=temp_workspace)
        results = checker.run_all_checks()
        
        # Should have reasonable score for valid workspace
        assert 0 <= results['score'] <= 100
    
    def test_is_healthy_method(self, temp_workspace):
        """Test is_healthy convenience method."""
        checker = HealthChecker(workspace=temp_workspace)
        
        # With valid workspace, should be healthy
        # (unless other checks fail, which they shouldn't)
        result = checker.is_healthy()
        assert isinstance(result, bool)
    
    def test_get_health_summary(self, temp_workspace):
        """Test health summary string generation."""
        checker = HealthChecker(workspace=temp_workspace)
        summary = checker.get_health_summary()
        
        assert isinstance(summary, str)
        assert len(summary) > 0
        assert 'Health Report' in summary


class TestHealthCheckerEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_workspace(self):
        """Test health checker with empty workspace."""
        with tempfile.TemporaryDirectory() as tmpdir:
            checker = HealthChecker(workspace=tmpdir)
            results = checker.run_all_checks()
            
            # Should complete without error
            assert 'timestamp' in results
            assert 'score' in results
    
    def test_unreadable_files(self):
        """Test handling of unreadable files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mem_dir = os.path.join(tmpdir, 'memory')
            os.makedirs(mem_dir)
            
            # Create unreadable file
            unreadable = os.path.join(mem_dir, 'locked.md')
            with open(unreadable, 'w') as f:
                f.write("locked content")
            os.chmod(unreadable, 0o000)
            
            try:
                checker = HealthChecker(workspace=tmpdir)
                result = checker._check_memory_files()
                # Should handle gracefully
                assert 'status' in result
            finally:
                # Restore permissions for cleanup
                os.chmod(unreadable, 0o644)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
