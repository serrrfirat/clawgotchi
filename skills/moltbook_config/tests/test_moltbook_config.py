"""
Moltbook Configuration Helper Tests

Tests for validating and setting up Moltbook API configuration.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path


class TestMoltbookConfig(unittest.TestCase):
    """Test cases for MoltbookConfigHelper."""
    
    def setUp(self):
        """Create a temporary directory for test files."""
        self.test_dir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.test_dir, ".moltbook.json")
        
    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def test_default_config_path(self):
        """Test that default config path is correct."""
        from moltbook_config import MoltbookConfigHelper
        helper = MoltbookConfigHelper()
        self.assertTrue(helper.default_config_path.endswith(".moltbook.json"))
    
    def test_validate_api_key_valid(self):
        """Test validation of a valid API key format."""
        from moltbook_config import MoltbookConfigHelper
        helper = MoltbookConfigHelper()
        # Valid UUID-like API key
        valid_key = "pk_live_abc123def456ghi789jkl012mno345pqr678"
        self.assertTrue(helper.validate_api_key(valid_key))
    
    def test_validate_api_key_invalid(self):
        """Test rejection of invalid API key formats."""
        from moltbook_config import MoltbookConfigHelper
        helper = MoltbookConfigHelper()
        
        invalid_keys = [
            "",  # Empty
            "short",  # Too short
            "pk_live_",  # Too short prefix only
            "pk_test_abc123",  # Wrong prefix
            "sk_live_abc123",  # Wrong prefix
            None,  # None value
        ]
        
        for key in invalid_keys:
            with self.subTest(key=key):
                self.assertFalse(helper.validate_api_key(key))
    
    def test_load_config_existing(self):
        """Test loading existing configuration."""
        from moltbook_config import MoltbookConfigHelper
        
        # Create a test config file
        test_config = {"api_key": "pk_live_test123", "default_submolt": "general"}
        with open(self.config_path, 'w') as f:
            json.dump(test_config, f)
        
        helper = MoltbookConfigHelper(config_path=self.config_path)
        loaded = helper.load_config()
        
        self.assertEqual(loaded["api_key"], "pk_live_test123")
        self.assertEqual(loaded["default_submolt"], "general")
    
    def test_load_config_missing(self):
        """Test behavior when config file is missing."""
        from moltbook_config import MoltbookConfigHelper
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
        helper = MoltbookConfigHelper(config_path=self.config_path)
        loaded = helper.load_config()
        
        self.assertIsNone(loaded)
    
    def test_save_config(self):
        """Test saving configuration to file."""
        from moltbook_config import MoltbookConfigHelper
        
        helper = MoltbookConfigHelper(config_path=self.config_path)
        helper.save_config(api_key="pk_live_save456", default_submolt="builds")
        
        # Verify file was created
        self.assertTrue(os.path.exists(self.config_path))
        
        # Verify content
        with open(self.config_path, 'r') as f:
            saved = json.load(f)
        
        self.assertEqual(saved["api_key"], "pk_live_save456")
        self.assertEqual(saved["default_submolt"], "builds")
    
    def test_save_config_validates_api_key(self):
        """Test that save_config validates API key format."""
        from moltbook_config import MoltbookConfigHelper
        from moltbook_config import MoltbookConfigError
        
        helper = MoltbookConfigHelper(config_path=self.config_path)
        
        with self.assertRaises(MoltbookConfigError):
            helper.save_config(api_key="invalid_key")
    
    def test_get_api_key_from_env(self):
        """Test retrieving API key from environment variable."""
        from moltbook_config import MoltbookConfigHelper
        
        os.environ["MOLTBOOK_API_KEY"] = "pk_live_env_test"
        try:
            helper = MoltbookConfigHelper()
            key = helper.get_api_key()
            self.assertEqual(key, "pk_live_env_test")
        finally:
            del os.environ["MOLTBOOK_API_KEY"]
    
    def test_get_api_key_fallback_to_file(self):
        """Test fallback to file-based config when env var not set."""
        from moltbook_config import MoltbookConfigHelper
        
        test_config = {"api_key": "pk_live_fallback_test"}
        with open(self.config_path, 'w') as f:
            json.dump(test_config, f)
        
        helper = MoltbookConfigHelper(config_path=self.config_path)
        key = helper.get_api_key()
        
        self.assertEqual(key, "pk_live_fallback_test")
    
    def test_get_api_key_returns_none_when_missing(self):
        """Test that None is returned when no API key is available."""
        from moltbook_config import MoltbookConfigHelper
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
        helper = MoltbookConfigHelper(config_path=self.config_path)
        key = helper.get_api_key()
        
        self.assertIsNone(key)
    
    def test_check_config_status_valid(self):
        """Test status check when configuration is valid."""
        from moltbook_config import MoltbookConfigHelper
        
        test_config = {"api_key": "pk_live_status_check"}
        with open(self.config_path, 'w') as f:
            json.dump(test_config, f)
        
        helper = MoltbookConfigHelper(config_path=self.config_path)
        status = helper.check_status()
        
        self.assertEqual(status["status"], "valid")
        self.assertTrue(status["has_api_key"])
        self.assertFalse(status["has_env_var"])
    
    def test_check_config_status_missing(self):
        """Test status check when configuration is missing."""
        from moltbook_config import MoltbookConfigHelper
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
        helper = MoltbookConfigHelper(config_path=self.config_path)
        status = helper.check_status()
        
        self.assertEqual(status["status"], "missing")
        self.assertFalse(status["has_api_key"])


class TestMoltbookEndpoints(unittest.TestCase):
    """Test cases for endpoint utilities."""
    
    def test_build_feed_url(self):
        """Test building the feed URL."""
        from moltbook_config import MoltbookEndpoints
        endpoints = MoltbookEndpoints()
        
        url = endpoints.build_feed_url(sort="new", limit=10)
        self.assertIn("sort=new", url)
        self.assertIn("limit=10", url)
        self.assertIn(endpoints.BASE_URL, url)
    
    def test_build_post_url(self):
        """Test building the posts API URL."""
        from moltbook_config import MoltbookEndpoints
        endpoints = MoltbookEndpoints()
        
        url = endpoints.build_post_url()
        self.assertIn("/posts", url)
        self.assertIn(endpoints.BASE_URL, url)


if __name__ == "__main__":
    unittest.main()
