import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clawgotchi.moltbook_cli import read_feed, post_update, get_api_key

class TestMoltbookCLI(unittest.TestCase):

    @patch('clawgotchi.moltbook_cli.get_api_key')
    def test_read_feed_success(self, mock_get_api_key):
        mock_get_api_key.return_value = "fake_api_key"
        mock_response = {
            "success": True,
            "posts": [{"id": "1", "title": "Test Post"}],
            "count": 1,
            "has_more": False
        }

        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(stdout='{"success": true, "posts": [], "count": 0, "has_more": false}', returncode=0)
            # Call the function
            result = read_feed()

            # Check if subprocess was called
            self.assertTrue(mock_run.called)

    @patch('clawgotchi.moltbook_cli.get_api_key')
    def test_read_feed_no_api_key(self, mock_get_api_key):
        mock_get_api_key.return_value = None
        result = read_feed()
        self.assertEqual(result["success"], False)
        self.assertEqual(result["error"], "API key not found")

    @patch('clawgotchi.moltbook_cli.get_api_key')
    @patch('subprocess.run')
    def test_post_update_success(self, mock_run, mock_get_api_key):
        mock_get_api_key.return_value = "fake_api_key"
        mock_run.return_value = MagicMock(stdout='{"success": true}', returncode=0)

        result = post_update("Test Title", "Test Content")
        self.assertTrue(mock_run.called)

    @patch('clawgotchi.moltbook_cli.get_api_key')
    def test_post_update_no_api_key(self, mock_get_api_key):
        mock_get_api_key.return_value = None
        result = post_update("Test Title", "Test Content")
        self.assertEqual(result["success"], False)
        self.assertEqual(result["error"], "API key not found")

if __name__ == '__main__':
    unittest.main()
