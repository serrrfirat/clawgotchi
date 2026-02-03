"""Tests for moltbook_cli.py module."""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Module under test
sys.path.insert(0, str(Path(__file__).parent.parent))
import moltbook_cli


class TestFormatPost:
    """Test post formatting functions."""

    def test_format_post_with_index(self):
        """format_post_for_terminal should include index."""
        post = {
            "title": "Test Post",
            "author": {"name": "testuser"},
            "upvotes": 10,
            "comment_count": 5,
            "submolt": {"name": "general"},
            "created_at": "2026-02-03T23:52:00+00:00"
        }
        result = moltbook_cli.format_post_for_terminal(post, index=1)
        assert "[ 1]" in result
        assert "Test Post" in result
        assert "testuser" in result
        assert "10" in result
        assert "5" in result

    def test_format_post_without_index(self):
        """format_post_for_terminal should work without index."""
        post = {
            "title": "Another Post",
            "author": {"name": "user2"},
            "upvotes": 5,
            "comment_count": 3,
            "submolt": {"name": "testing"},
            "created_at": None
        }
        result = moltbook_cli.format_post_for_terminal(post)
        assert "Another Post" in result
        assert "user2" in result

    def test_format_post_handles_missing_fields(self):
        """format_post_for_terminal should handle missing fields gracefully."""
        post = {}
        result = moltbook_cli.format_post_for_terminal(post)
        assert isinstance(result, str)
        assert len(result) > 0


class TestCLIArgs:
    """Test CLI argument parsing."""

    def test_feed_command_parsing(self):
        """feed command should accept --limit argument."""
        mock_args = MagicMock()
        mock_args.limit = 50
        mock_args.karma = False
        
        with patch("moltbook_cli.fetch_feed") as mock_fetch:
            mock_fetch.return_value = []
            result = moltbook_cli.cmd_feed(mock_args)
            mock_fetch.assert_called_with(limit=50)
            assert result == 1

    def test_feed_command_defaults(self):
        """feed command should have correct defaults."""
        mock_args = MagicMock()
        mock_args.limit = 20
        mock_args.karma = False
        
        with patch("moltbook_cli.fetch_feed") as mock_fetch:
            mock_fetch.return_value = []
            result = moltbook_cli.cmd_feed(mock_args)
            mock_fetch.assert_called_with(limit=20)
            assert result == 1

    def test_inspire_command_parsing(self):
        """inspire command should parse arguments."""
        mock_args = MagicMock()
        mock_args.limit = 100
        
        with patch("moltbook_cli.fetch_feed") as mock_fetch:
            mock_fetch.return_value = []
            result = moltbook_cli.cmd_inspire(mock_args)
            assert result == 1

    def test_profile_command_exists(self):
        """profile command should be recognized."""
        mock_args = MagicMock()
        
        with patch("moltbook_cli.get_my_profile") as mock:
            mock.return_value = {"error": "No API key"}
            result = moltbook_cli.cmd_profile(mock_args)
            assert result == 1

    def test_cache_command_exists(self):
        """cache command should be recognized."""
        mock_args = MagicMock()
        
        with patch("moltbook_cli.get_cached_posts") as mock:
            mock.return_value = []
            result = moltbook_cli.cmd_cache(mock_args)
            assert result == 0

    def test_help_command(self):
        """CLI should show help with no arguments."""
        with patch.object(sys, "argv", ["moltbook_cli.py"]):
            result = moltbook_cli.main([])
            assert result == 0

    def test_unknown_command_exits(self):
        """Unknown command should exit with error."""
        with pytest.raises(SystemExit) as exc_info:
            moltbook_cli.main(["unknown"])
        assert exc_info.value.code == 2


class TestCmdFeed:
    """Test feed command."""

    def test_cmd_feed_empty(self):
        """cmd_feed should handle empty posts."""
        mock_args = MagicMock()
        mock_args.limit = 20
        mock_args.karma = False
        
        with patch("moltbook_cli.fetch_feed") as mock:
            mock.return_value = []
            result = moltbook_cli.cmd_feed(mock_args)
            assert result == 1

    def test_cmd_feed_with_posts(self):
        """cmd_feed should display posts."""
        mock_args = MagicMock()
        mock_args.limit = 20
        mock_args.karma = False
        
        posts = [
            {
                "title": "Test",
                "author": {"name": "user"},
                "upvotes": 5,
                "comment_count": 2,
                "submolt": {"name": "general"},
                "created_at": "2026-02-03T23:52:00+00:00"
            }
        ]
        
        with patch("moltbook_cli.fetch_feed") as mock_fetch:
            mock_fetch.return_value = posts
            with patch("builtins.print") as mock_print:
                result = moltbook_cli.cmd_feed(mock_args)
                assert result == 0
                assert mock_print.called


class TestCmdInspire:
    """Test inspire command."""

    def test_cmd_inspire_no_posts(self):
        """cmd_inspire should handle no posts."""
        mock_args = MagicMock()
        mock_args.limit = 50
        
        with patch("moltbook_cli.fetch_feed") as mock:
            mock.return_value = []
            result = moltbook_cli.cmd_inspire(mock_args)
            assert result == 1

    def test_cmd_inspire_with_ideas(self):
        """cmd_inspire should display ideas."""
        mock_args = MagicMock()
        mock_args.limit = 50
        
        posts = [
            {
                "title": "Terminal pet ideas",
                "author": {"name": "builder"},
                "upvotes": 20,
                "content": "Building terminal pets is fun",
                "comment_count": 5,
                "submolt": {"name": "agents"}
            }
        ]
        
        with patch("moltbook_cli.fetch_feed") as mock_fetch:
            mock_fetch.return_value = posts
            with patch("builtins.print") as mock_print:
                result = moltbook_cli.cmd_inspire(mock_args)
                assert result == 0


class TestCmdProfile:
    """Test profile command."""

    def test_cmd_profile_error(self):
        """cmd_profile should handle API error."""
        mock_args = MagicMock()
        
        with patch("moltbook_cli.get_my_profile") as mock:
            mock.return_value = {"error": "No API key"}
            with patch("builtins.print") as mock_print:
                result = moltbook_cli.cmd_profile(mock_args)
                assert result == 1

    def test_cmd_profile_success(self):
        """cmd_profile should display profile."""
        mock_args = MagicMock()
        
        with patch("moltbook_cli.get_my_profile") as mock:
            mock.return_value = {
                "name": "testagent",
                "posts_count": 10,
                "karma": 100
            }
            with patch("builtins.print") as mock_print:
                result = moltbook_cli.cmd_profile(mock_args)
                assert result == 0


class TestCmdCache:
    """Test cache command."""

    def test_cmd_cache_empty(self):
        """cmd_cache should handle no cached posts."""
        mock_args = MagicMock()
        
        with patch("moltbook_cli.get_cached_posts") as mock:
            mock.return_value = []
            with patch("builtins.print") as mock_print:
                result = moltbook_cli.cmd_cache(mock_args)
                assert result == 0

    def test_cmd_cache_with_posts(self):
        """cmd_cache should display cached posts."""
        mock_args = MagicMock()
        
        posts = [
            {
                "title": "Cached Post",
                "author": {"name": "cached_user"},
                "upvotes": 3,
                "comment_count": 1,
                "submolt": {"name": "general"},
                "created_at": None
            }
        ]
        
        with patch("moltbook_cli.get_cached_posts") as mock:
            mock.return_value = posts
            with patch("builtins.print") as mock_print:
                result = moltbook_cli.cmd_cache(mock_args)
                assert result == 0
