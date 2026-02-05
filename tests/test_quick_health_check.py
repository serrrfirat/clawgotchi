"""
Quick Health Check Utility - TDD Test Suite

Tests for the quick_health_check module that provides fast vital signs
for the autonomous agent.
"""

import pytest
import os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestQuickHealthCheck:
    """Test suite for quick_health_check utility."""

    def test_check_git_status_clean(self, tmp_path, monkeypatch):
        """Test git status check when working tree is clean."""
        import sys
        sys.path.insert(0, str(tmp_path))
        
        # Create mock git repo
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        
        # Reload module with fresh imports
        if 'core.quick_health_check' in sys.modules:
            del sys.modules['core.quick_health_check']
        
        # Create mock return values for multiple subprocess calls
        mock_result1 = MagicMock()
        mock_result1.stdout = ""
        mock_result1.returncode = 0
        
        mock_result2 = MagicMock()
        mock_result2.stdout = "main"
        mock_result2.returncode = 0
        
        # Mock subprocess.run to return different values for each call
        with patch('core.quick_health_check.subprocess.run') as mock_run:
            mock_run.side_effect = [mock_result1, mock_result2]
            
            from core.quick_health_check import check_git_status
            
            result = check_git_status()
            assert result["status"] == "clean"
            assert result["branch"] == "main"

    def test_check_git_status_dirty(self, tmp_path, monkeypatch):
        """Test git status check when there are uncommitted changes."""
        import sys
        sys.path.insert(0, str(tmp_path))
        
        # Create mock return values for multiple subprocess calls
        mock_result1 = MagicMock()
        mock_result1.stdout = "M  some_file.py"
        mock_result1.returncode = 0
        
        mock_result2 = MagicMock()
        mock_result2.stdout = "main"
        mock_result2.returncode = 0
        
        with patch('core.quick_health_check.subprocess.run') as mock_run:
            mock_run.side_effect = [mock_result1, mock_result2]
            
            from core.quick_health_check import check_git_status
            
            result = check_git_status()
            assert result["status"] == "dirty"

    def test_check_tests_last_run(self, tmp_path, monkeypatch):
        """Test checking last test run results."""
        import sys
        sys.path.insert(0, str(tmp_path))
        
        # Create a mock test result file
        results_dir = tmp_path / "test_results"
        results_dir.mkdir()
        results_file = results_dir / "last_run.json"
        results_file.write_text('{"passed": 6, "failed": 0, "total": 6}')
        
        monkeypatch.chdir(tmp_path)
        
        from core.quick_health_check import check_tests
        
        result = check_tests()
        assert result["passed"] == 6
        assert result["failed"] == 0

    def test_check_memory_health_valid(self, tmp_path, monkeypatch):
        """Test memory file health check with valid files."""
        import sys
        sys.path.insert(0, str(tmp_path))
        
        # Create valid memory files
        memory_dir = tmp_path / "memory"
        memory_dir.mkdir()
        (memory_dir / "2026-02-05.md").write_text("# Test\n- entry 1")
        
        monkeypatch.chdir(tmp_path)
        
        from core.quick_health_check import check_memory_health
        
        result = check_memory_health()
        assert result["status"] == "healthy"
        assert "file_count" in result

    def test_check_moltbook_connection(self, tmp_path, monkeypatch):
        """Test Moltbook API connectivity check."""
        import sys
        sys.path.insert(0, str(tmp_path))
        
        # Create mock config
        config = tmp_path / ".moltbook.json"
        config.write_text('{"api_key": "test_key_12345"}')
        
        monkeypatch.chdir(tmp_path)
        
        # Reload module with fresh imports
        if 'core.quick_health_check' in sys.modules:
            del sys.modules['core.quick_health_check']
        
        with patch('core.quick_health_check.subprocess.run') as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "200"
            
            from core.quick_health_check import check_moltbook_connection
            
            result = check_moltbook_connection()
            assert result["connected"] == True

    def test_run_quick_check_all_green(self, tmp_path, monkeypatch):
        """Test running full quick health check with all systems green."""
        import sys
        sys.path.insert(0, str(tmp_path))
        
        # Setup mocks for all checks
        monkeypatch.chdir(tmp_path)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value.stdout = "nothing to commit"
            mock_run.return_value.returncode = 0
            
            from core.quick_health_check import run_quick_check
            
            result = run_quick_check()
            assert "timestamp" in result
            assert "overall_status" in result
            assert "checks" in result

    def test_health_score_calculation(self, tmp_path, monkeypatch):
        """Test overall health score calculation."""
        import sys
        sys.path.insert(0, str(tmp_path))
        
        monkeypatch.chdir(tmp_path)
        
        from core.quick_health_check import calculate_health_score
        
        # Test with all green
        checks = {
            "git": {"status": "clean"},
            "tests": {"passed": 10, "failed": 0},
            "memory": {"status": "healthy"},
            "moltbook": {"connected": True}
        }
        
        score = calculate_health_score(checks)
        assert score == 100
        
        # Test with one failure
        checks["tests"]["failed"] = 2
        score = calculate_health_score(checks)
        assert score < 100


class TestQuickHealthCheckIntegration:
    """Integration tests for quick_health_check module."""

    def test_module_imports(self):
        """Test that the module can be imported."""
        from core.quick_health_check import (
            check_git_status,
            check_tests,
            check_memory_health,
            check_moltbook_connection,
            run_quick_check,
            calculate_health_score
        )
        
        # Verify all functions exist and are callable
        assert callable(check_git_status)
        assert callable(check_tests)
        assert callable(check_memory_health)
        assert callable(check_moltbook_connection)
        assert callable(run_quick_check)
        assert callable(calculate_health_score)
