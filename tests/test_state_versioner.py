"""Test suite for utils/state_versioner.py"""
import json
import pytest
import os
import shutil
from datetime import datetime, timedelta
from unittest.mock import patch, mock_open

# Import the module we'll test
import utils.state_versioner as state_versioner


@pytest.fixture
def temp_state_dir(tmp_path, monkeypatch):
    """Create a temporary directory for state files."""
    state_dir = tmp_path / "memory"
    state_dir.mkdir()
    backups_dir = state_dir / "backups"
    backups_dir.mkdir()
    
    # Monkeypatch the paths
    monkeypatch.setattr(state_versioner, 'STATE_DIR', str(state_dir))
    monkeypatch.setattr(state_versioner, 'BACKUPS_DIR', str(backups_dir))
    
    return str(state_dir), str(backups_dir)


@pytest.fixture
def sample_agent_state():
    """Create a sample agent state for testing."""
    return {
        "version": "1.0",
        "last_wake": "2026-02-06T06:55:12.522216",
        "current_state": "SLEEPING",
        "health_score": 95,
        "total_wakes": 715,
        "current_goal": "Test goal",
        "current_thought": "Test thought",
        "health_history": [],
        "git_status": "clean",
        "errors": [],
        "updated_at": "2026-02-06T06:55:26.202488"
    }


class TestSaveVersion:
    """Tests for save_version function."""
    
    def test_save_version_creates_backup_file(self, temp_state_dir, sample_agent_state):
        """Save version should create a backup file in backups directory."""
        state_dir, backups_dir = temp_state_dir
        
        with patch("builtins.open", mock_open()) as mock_file:
            with patch('json.dump') as mock_json_dump:
                state_versioner.save_version(sample_agent_state)
                
                # Verify file was opened for writing
                assert mock_file.called
                
                # Verify json.dump was called
                assert mock_json_dump.called


class TestListVersions:
    """Tests for list_versions function."""
    
    def test_list_versions_returns_empty_list_when_no_backups(self, temp_state_dir):
        """List versions should return empty list when no backups exist."""
        state_dir, backups_dir = temp_state_dir
        
        versions = state_versioner.list_versions()
        
        assert versions == []
    
    def test_list_versions_returns_sorted_version_list(self, temp_state_dir, sample_agent_state):
        """List versions should return sorted list of version info."""
        state_dir, backups_dir = temp_state_dir
        
        # Create mock backup files
        now = datetime.now()
        for i, suffix in enumerate(["_100000", "_100001", "_100002"]):
            # Create file content with modified timestamp
            backup_path = os.path.join(backups_dir, f"state_{now.strftime('%Y%m%d')}{suffix}.json")
            with open(backup_path, 'w') as f:
                json.dump(sample_agent_state, f)
        
        versions = state_versioner.list_versions()
        
        # Should return list of dicts with filename, timestamp, size
        assert len(versions) == 3
        assert all('filename' in v for v in versions)
        assert all('timestamp' in v for v in versions)


class TestRestoreVersion:
    """Tests for restore_version function."""
    
    def test_restore_version_returns_state_dict(self, temp_state_dir, sample_agent_state):
        """Restore version should return the state dictionary."""
        state_dir, backups_dir = temp_state_dir
        
        # Create a backup file
        now = datetime.now()
        backup_filename = f"state_{now.strftime('%Y%m%d')}_100000.json"
        backup_path = os.path.join(backups_dir, backup_filename)
        
        with open(backup_path, 'w') as f:
            json.dump(sample_agent_state, f)
        
        # Restore should return the state
        restored = state_versioner.restore_version(backup_filename)
        
        # Verify the restored state matches original
        assert restored == sample_agent_state
        assert restored['current_goal'] == 'Test goal'
        assert restored['current_state'] == 'SLEEPING'


class TestGetLatestVersion:
    """Tests for get_latest_version function."""
    
    def test_get_latest_version_returns_none_when_no_backups(self, temp_state_dir):
        """Get latest version should return None when no backups exist."""
        state_dir, backups_dir = temp_state_dir
        
        latest = state_versioner.get_latest_version()
        
        assert latest is None
    
    def test_get_latest_version_returns_most_recent_file(self, temp_state_dir, sample_agent_state):
        """Get latest version should return the most recent backup file."""
        state_dir, backups_dir = temp_state_dir
        
        now = datetime.now()
        # Create files with different timestamps
        timestamps = ["_100000", "_100001", "_100002"]
        for suffix in timestamps:
            backup_path = os.path.join(backups_dir, f"state_{now.strftime('%Y%m%d')}{suffix}.json")
            with open(backup_path, 'w') as f:
                json.dump(sample_agent_state, f)
        
        latest = state_versioner.get_latest_version()
        
        assert latest.endswith("_100002.json")


class TestParseVersionFilename:
    """Tests for _parse_version_filename helper function."""
    
    def test_parse_valid_filename(self):
        """Parse should extract timestamp from valid filename."""
        filename = "state_20260206_100000.json"
        parsed = state_versioner._parse_version_filename(filename)
        
        assert parsed is not None
        assert parsed.year == 2026
        assert parsed.month == 2
        assert parsed.day == 6
        assert parsed.hour == 10
        assert parsed.minute == 0
        assert parsed.second == 0
    
    def test_parse_invalid_filename(self):
        """Parse should return None for invalid filename."""
        filename = "not_a_version_file.json"
        parsed = state_versioner._parse_version_filename(filename)
        
        assert parsed is None
