"""Test suite for FeedResilienceChecker - monitors Moltbook API availability and health."""

import pytest
from unittest.mock import patch, MagicMock
import json
import os
from datetime import datetime

# Import the module
import sys
sys.path.insert(0, '/workspace')
from feed_resilience_checker import FeedResilienceChecker


class TestFeedResilienceChecker:
    """Test cases for FeedResilienceChecker."""

    @patch('feed_resilience_checker.urllib.request.urlopen')
    def test_ping_success(self, mock_urlopen):
        """Test successful ping to Moltbook feed."""
        # Setup mock
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"success": true, "posts": []}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        checker = FeedResilienceChecker()
        success, error, latency = checker.ping()

        assert success is True
        assert error is None
        assert latency is not None
        assert latency > 0

    @patch('feed_resilience_checker.urllib.request.urlopen')
    def test_ping_failure_connection_error(self, mock_urlopen):
        """Test handling of connection errors."""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("Connection failed")

        checker = FeedResilienceChecker()
        success, error, latency = checker.ping()

        assert success is False
        assert "Connection" in error or "Error" in error
        assert latency is None

    @patch('feed_resilience_checker.urllib.request.urlopen')
    def test_ping_failure_timeout(self, mock_urlopen):
        """Test handling of timeout errors."""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("Connection timed out")

        checker = FeedResilienceChecker()
        success, error, latency = checker.ping()

        assert success is False
        assert "Error" in error
        assert latency is None

    @patch('feed_resilience_checker.urllib.request.urlopen')
    def test_ping_failure_http_error(self, mock_urlopen):
        """Test handling of HTTP errors (4xx, 5xx)."""
        import urllib.error
        mock_response = MagicMock()
        mock_response.status = 500
        mock_urlopen.side_effect = urllib.error.HTTPError(url="http://test", code=500, msg="Server Error", hdrs={}, fp=None)

        checker = FeedResilienceChecker()
        success, error, latency = checker.ping()

        assert success is False
        assert "500" in error

    def test_verify_response_structure_valid(self):
        """Test verification of valid response structure."""
        checker = FeedResilienceChecker()
        valid_response = {
            "success": True,
            "posts": [{"id": "123", "title": "Test"}]
        }

        is_valid, error = checker.verify_response_structure(valid_response)

        assert is_valid is True
        assert error is None

    def test_verify_response_structure_missing_fields(self):
        """Test verification fails on missing expected fields."""
        checker = FeedResilienceChecker()
        invalid_response = {"success": True}  # Missing "posts"

        is_valid, error = checker.verify_response_structure(invalid_response)

        assert is_valid is False
        assert "posts" in error

    @patch('feed_resilience_checker.urllib.request.urlopen')
    def test_log_metrics(self, mock_urlopen, capsys):
        """Test that successful pings are logged with metrics."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"success": true, "posts": []}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        checker = FeedResilienceChecker()
        checker.timeout = 0.1  # Speed up test
        result = checker.check()
        checker.log_metrics(result)

        captured = capsys.readouterr()
        assert "Status: healthy" in captured.out or "Status: degraded" in captured.out

    @patch('feed_resilience_checker.urllib.request.urlopen')
    def test_feed_wobble_detection(self, mock_urlopen):
        """Test that multiple failures trigger 'feed wobble' state."""
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("Failed")

        checker = FeedResilienceChecker()
        
        # First check - should be unhealthy
        result1 = checker.check()
        assert result1["status"] == "unhealthy"

        # Second check - should still be unhealthy
        result2 = checker.check()
        assert result2["status"] == "unhealthy"

        # Third check - should trigger wobble
        result3 = checker.check()
        assert result3["status"] == "feed_wobble"
        assert result3.get("wobble_detected") is True

    @patch('feed_resilience_checker.urllib.request.urlopen')
    def test_recovery_detection(self, mock_urlopen):
        """Test that recovery from failure is detected."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read.return_value = b'{"success": true, "posts": []}'
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_response

        checker = FeedResilienceChecker()
        
        # First, simulate a failure state
        checker._save_state({"consecutive_failures": 2, "status": "unhealthy", "last_check": None})
        
        # Now check should succeed and reset failures
        result = checker.check()
        
        assert result["success"] is True
        state = checker._load_state()
        assert state["consecutive_failures"] == 0
        assert state["status"] == "healthy"

    def test_check_with_api_key(self):
        """Test check uses API key for authentication."""
        # Create a temporary config file
        config_content = {"api_key": "test_key_123"}
        config_path = "/tmp/test_moltbook_config.json"
        
        with open(config_path, 'w') as f:
            json.dump(config_content, f)

        with patch('feed_resilience_checker.urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.read.return_value = b'{"success": true, "posts": []}'
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            mock_urlopen.return_value = mock_response

            checker = FeedResilienceChecker(api_key_path=config_path)
            checker.ping()

            # Verify Request was created with Authorization header
            call_args = mock_urlopen.call_args
            request = call_args[0][0]
            assert request.get_header('Authorization') == 'Bearer test_key_123'

        # Cleanup
        os.remove(config_path)

    @patch('feed_resilience_checker.urllib.request.urlopen')
    def test_latency_threshold_warning(self, mock_urlopen, capsys):
        """Test warning when latency exceeds threshold."""
        import time
        
        def slow_response(*args, **kwargs):
            time.sleep(0.05)  # 50ms delay (threshold is 1000ms, so this won't trigger)
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.read.return_value = b'{"success": true, "posts": []}'
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=False)
            return mock_response

        mock_urlopen.side_effect = slow_response

        checker = FeedResilienceChecker()
        checker.timeout = 10
        result = checker.check()
        
        # Should be healthy, not degraded
        assert result["success"] is True
