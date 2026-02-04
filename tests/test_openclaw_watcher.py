"""Tests for openclaw_watcher.py — Clawgotchi's gateway watcher and feed builder."""

import pytest
import time
from unittest.mock import patch, MagicMock
from pathlib import Path

# Import classes to test
from integrations.openclaw_watcher import (
    FeedItem,
    GatewayState,
    OpenClawWatcher,
    KNOWN_AGENTS,
    KEYWORD_AGENT_MAP,
)


class TestFeedItem:
    """Test FeedItem dataclass."""

    def test_feed_item_creation(self):
        """FeedItem should store timestamp, source, and summary."""
        item = FeedItem(
            timestamp=1234567890.0,
            source="Jarvis",
            summary="Session active (5m ago, 1000 tokens, claude-opus-4)",
        )
        assert item.timestamp == 1234567890.0
        assert item.source == "Jarvis"
        assert "Session active" in item.summary

    def test_time_str_format(self):
        """time_str should format as HH:MM in local timezone."""
        # Fixed timestamp for testing - use timezone-aware datetime
        import datetime
        from datetime import timezone
        # 2024-01-01 00:00:00 UTC
        dt = datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        item = FeedItem(timestamp=dt.timestamp(), source="test", summary="test")
        # Get expected format from the datetime object in the system's timezone
        # The test should pass regardless of the system's timezone
        # We just verify it formats as HH:MM pattern
        assert ":" in item.time_str
        parts = item.time_str.split(":")
        assert len(parts) == 2
        assert len(parts[0]) == 2  # HH
        assert len(parts[1]) == 2  # MM


class TestGatewayState:
    """Test GatewayState dataclass."""

    def test_default_state(self):
        """Default state should have offline=False and zero counts."""
        state = GatewayState()
        assert state.online is False
        assert state.active_agents == 0
        assert state.active_sessions == 0
        assert state.channels == []
        assert state.last_poll_at == 0.0

    def test_state_with_values(self):
        """State should store provided values."""
        state = GatewayState(
            online=True,
            active_agents=3,
            active_sessions=2,
            channels=["telegram", "discord"],
        )
        assert state.online is True
        assert state.active_agents == 3
        assert state.active_sessions == 2
        assert len(state.channels) == 2


class TestIdentifyAgent:
    """Test agent identification logic."""

    def test_known_agent_match(self):
        """Should identify agents in KNOWN_AGENTS list."""
        watcher = OpenClawWatcher()
        assert watcher._identify_agent("Jarvis is processing") == "Jarvis"
        assert watcher._identify_agent("Shuri Report: done") == "Shuri"
        assert watcher._identify_agent("Fury research task") == "Fury"

    def test_keyword_fallback(self):
        """Should use keyword mapping when agent name not in text."""
        watcher = OpenClawWatcher()
        assert watcher._identify_agent("design task complete") == "Wanda"
        assert watcher._identify_agent("email from user") == "Pepper"
        assert watcher._identify_agent("docs updated") == "Wong"

    def test_cron_fallback(self):
        """Should return [cron] when no agent identified."""
        watcher = OpenClawWatcher()
        result = watcher._identify_agent("some random event")
        assert result == "[cron]"


class TestExtractSummary:
    """Test summary extraction from event text."""

    def test_removes_markdown(self):
        """Should strip markdown bold/italic markers."""
        watcher = OpenClawWatcher()
        summary = watcher._extract_summary("**Bold** and *italic* text")
        assert "**" not in summary
        assert "*" not in summary

    def test_removes_headers(self):
        """Should strip markdown headers."""
        watcher = OpenClawWatcher()
        summary = watcher._extract_summary("# Main Header\n## Subheader\nContent here")
        assert "#" not in summary

    def test_takes_first_meaningful_line(self):
        """Should return first non-empty line."""
        watcher = OpenClawWatcher()
        summary = watcher._extract_summary("\n\nFirst line\nSecond line")
        assert "First line" in summary

    def test_skips_heartbeat(self):
        """Should skip HEARTBEAT_OK events."""
        watcher = OpenClawWatcher()
        summary = watcher._extract_summary("HEARTBEAT_OK")
        assert "Standing by" in summary  # Returns default


class TestWatcherInit:
    """Test OpenClawWatcher initialization."""

    def test_initial_state(self):
        """Watcher should start with empty feed and default state."""
        watcher = OpenClawWatcher()
        assert watcher.state.online is False
        assert watcher.state.active_agents == 0
        assert watcher.feed == []
        assert watcher._stop is not None  # _stop event exists

    def test_empty_feed_rate(self):
        """Empty feed should return 0 events per minute."""
        watcher = OpenClawWatcher()
        rate = watcher.feed_rate()
        assert rate == 0.0

    def test_get_feed_empty(self):
        """Empty feed should return empty list."""
        watcher = OpenClawWatcher()
        feed = watcher.get_feed()
        assert feed == []


class TestWatcherMethods:
    """Test OpenClawWatcher public methods."""

    def test_add_feed_item(self):
        """Should add items to feed."""
        watcher = OpenClawWatcher()
        item = FeedItem(timestamp=time.time(), source="test", summary="test")
        watcher._add_feed(item)
        assert len(watcher.feed) == 1
        assert watcher.feed[0].source == "test"

    def test_feed_max_size(self):
        """Feed should trim to MAX_FEED size."""
        watcher = OpenClawWatcher()
        # Add more than MAX_FEED items
        for i in range(600):
            watcher._add_feed(FeedItem(timestamp=time.time(), source=f"src{i}", summary="test"))
        assert len(watcher.feed) <= 500  # MAX_FEED

    def test_get_channel_str_none(self):
        """No channels should return 'none'."""
        watcher = OpenClawWatcher()
        assert watcher.get_channel_str() == "none"

    def test_get_channel_str_telegram(self):
        """Telegram channel should return 'tg'."""
        watcher = OpenClawWatcher()
        watcher.state.channels = ["telegram:configured"]
        assert watcher.get_channel_str() == "tg"

    def test_get_channel_str_multiple(self):
        """Multiple channels should be joined with /."""
        watcher = OpenClawWatcher()
        watcher.state.channels = ["telegram:configured", "discord:configured"]
        result = watcher.get_channel_str()
        assert "tg" in result
        assert "dc" in result

    def test_get_channel_str_slack(self):
        """Slack channel should return 'sl'."""
        watcher = OpenClawWatcher()
        watcher.state.channels = ["slack:configured"]
        assert watcher.get_channel_str() == "sl"

    def test_get_channel_str_unknown_truncates(self):
        """Unknown channel names should be truncated to 6 chars."""
        watcher = OpenClawWatcher()
        watcher.state.channels = ["signal:configured"]
        result = watcher.get_channel_str()
        assert result == "signal"

    def test_get_channel_str_three_channels(self):
        """Three channels should all be included."""
        watcher = OpenClawWatcher()
        watcher.state.channels = ["telegram:configured", "discord:configured", "slack:configured"]
        result = watcher.get_channel_str()
        assert "tg" in result
        assert "dc" in result
        assert "sl" in result


class TestKnownAgents:
    """Test that known agents list exists."""

    def test_known_agents_not_empty(self):
        """KNOWN_AGENTS should have entries."""
        assert len(KNOWN_AGENTS) > 0
        assert "Jarvis" in KNOWN_AGENTS

    def test_keyword_map_not_empty(self):
        """KEYWORD_AGENT_MAP should have entries."""
        assert len(KEYWORD_AGENT_MAP) > 0
        assert "squad" in KEYWORD_AGENT_MAP
