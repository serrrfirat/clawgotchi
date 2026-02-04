"""
Tests for Moltbook API Key Configurator
"""

import json
import os
import pytest
from pathlib import Path
from unittest.mock import patch

import moltbook_config


@pytest.fixture
def temp_config(tmp_path):
    """Create a temporary config path for testing."""
    with patch.object(moltbook_config, 'CONFIG_PATH', tmp_path / '.moltbook.json') as p:
        yield p


class TestSaveApiKey:
    """Tests for save_api_key function."""
    
    def test_save_api_key_creates_file(self, temp_config):
        """Saving API key should create the config file."""
        result = moltbook_config.save_api_key("test_api_key_123")
        
        assert result["status"] == "success"
        assert temp_config.exists()
        
        with open(temp_config) as f:
            config = json.load(f)
        
        assert config["api_key"] == "test_api_key_123"
    
    def test_save_api_key_overwrites_existing(self, temp_config):
        """Saving should overwrite existing config."""
        moltbook_config.save_api_key("first_key")
        result = moltbook_config.save_api_key("second_key")
        
        assert result["status"] == "success"
        
        with open(temp_config) as f:
            config = json.load(f)
        
        assert config["api_key"] == "second_key"
    
    def test_save_api_key_with_special_characters(self, temp_config):
        """Should handle API keys with special characters."""
        special_key = "sk_live_abc123-xyz!@#$%"
        result = moltbook_config.save_api_key(special_key)
        
        assert result["status"] == "success"
        
        with open(temp_config) as f:
            config = json.load(f)
        
        assert config["api_key"] == special_key


class TestLoadApiKey:
    """Tests for load_api_key function."""
    
    def test_load_api_key_returns_key(self, temp_config):
        """Should return the saved API key."""
        moltbook_config.save_api_key("my_secret_key")
        
        key = moltbook_config.load_api_key()
        
        assert key == "my_secret_key"
    
    def test_load_api_key_returns_none_when_missing(self, temp_config):
        """Should return None when config doesn't exist."""
        key = moltbook_config.load_api_key()
        
        assert key is None
    
    def test_load_api_key_handles_empty_file(self, temp_config):
        """Should handle empty config file gracefully."""
        with open(temp_config, "w") as f:
            f.write("")
        
        key = moltbook_config.load_api_key()
        
        assert key is None


class TestValidateConfig:
    """Tests for validate_config function."""
    
    def test_validate_config_valid(self, temp_config):
        """Should return valid=True for proper config."""
        moltbook_config.save_api_key("valid_key")
        
        result = moltbook_config.validate_config()
        
        assert result["valid"] is True
        assert result["status"] == "success"
        assert len(result["errors"]) == 0
    
    def test_validate_config_missing_file(self, temp_config):
        """Should detect missing config file."""
        result = moltbook_config.validate_config()
        
        assert result["valid"] is False
        assert result["status"] == "error"
        assert "not found" in result["errors"][0]
    
    def test_validate_config_invalid_json(self, temp_config):
        """Should detect invalid JSON."""
        with open(temp_config, "w") as f:
            f.write("{invalid json")
        
        result = moltbook_config.validate_config()
        
        assert result["valid"] is False
        assert result["status"] == "error"
        assert "Invalid JSON" in result["errors"][0]
    
    def test_validate_config_missing_api_key(self, temp_config):
        """Should detect missing api_key field."""
        with open(temp_config, "w") as f:
            json.dump({"other": "value"}, f)
        
        result = moltbook_config.validate_config()
        
        assert result["valid"] is False
        assert result["status"] == "error"
        assert "api_key" in result["errors"][0]
    
    def test_validate_config_empty_api_key(self, temp_config):
        """Should reject empty api_key."""
        with open(temp_config, "w") as f:
            json.dump({"api_key": ""}, f)
        
        result = moltbook_config.validate_config()
        
        assert result["valid"] is False
        assert result["status"] == "error"
        assert "non-empty" in result["errors"][0]


class TestRemoveConfig:
    """Tests for remove_config function."""
    
    def test_remove_config_deletes_file(self, temp_config):
        """Should delete existing config file."""
        moltbook_config.save_api_key("key_to_remove")
        assert temp_config.exists()
        
        result = moltbook_config.remove_config()
        
        assert result["status"] == "success"
        assert not temp_config.exists()
    
    def test_remove_config_no_file(self, temp_config):
        """Should succeed when no config exists."""
        result = moltbook_config.remove_config()
        
        assert result["status"] == "success"
        assert "no config" in result["message"].lower()
