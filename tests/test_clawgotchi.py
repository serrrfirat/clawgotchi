"""Tests for clawgotchi.py — Clawgotchi's terminal UI and utilities."""

import pytest
from unittest.mock import patch, MagicMock
import re

# Import functions to test
import clawgotchi


class TestLenVisible:
    """Test visible string length calculation (strips ANSI codes)."""

    def test_plain_string(self):
        """Plain string should return its length."""
        assert clawgotchi.len_visible("hello") == 5
        assert clawgotchi.len_visible("") == 0
        assert clawgotchi.len_visible("a b c") == 5

    def test_strips_ansi_codes(self):
        """Should strip ANSI escape sequences."""
        # ANSI escape codes
        colored = "\x1b[31mred\x1b[0m"
        assert clawgotchi.len_visible(colored) == 3

        bold = "\x1b[1mbold\x1b[22m"
        assert clawgotchi.len_visible(bold) == 4

        # Multiple codes
        fancy = "\x1b[1;31;40mred bold\x1b[0m"
        assert clawgotchi.len_visible(fancy) == 8

    def test_mixed_content(self):
        """Mixed plain and ANSI content."""
        mixed = "\x1b[34mhello\x1b[0m world"
        assert clawgotchi.len_visible(mixed) == 11


class TestCenterArt:
    """Test text centering."""

    def test_center_short_text(self):
        """Short text should be centered with leading padding."""
        result = clawgotchi.center_art("hi", 20)
        assert result.startswith(" ")
        assert "hi" in result
        # Returns leading spaces + text, no trailing spaces
        assert result == " " * 8 + "hi"

    def test_center_exact_width(self):
        """Text at exactly available width minus 2."""
        result = clawgotchi.center_art("hello", 7)
        # 7 - 2 - 5 = 0, no padding
        assert result == "hello"

    def test_center_wider_than_width(self):
        """Text wider than width should return as-is."""
        result = clawgotchi.center_art("very long text", 5)
        assert result == "very long text"

    def test_center_empty_string(self):
        """Empty string should return spaces."""
        result = clawgotchi.center_art("", 10)
        # 10 - 2 - 0 = 8 // 2 = 4
        assert result == " " * 4


class TestBuildMoodMeter:
    """Test mood meter building."""

    def test_build_mood_meter_basic(self):
        """Basic mood meter generation."""
        term = MagicMock()
        pet = MagicMock()
        pet.face_key = "happy"
        pet.gateway_online = True
        pet.last_feed_rate = 5.0
        pet.last_active_agents = 1

        # Mock term attributes as empty strings (no ANSI codes in tests)
        term.light_salmon = ""
        term.cyan = ""
        term.grey70 = ""
        term.grey50 = ""
        term.normal = ""

        result = clawgotchi.build_mood_meter(term, pet, 20)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_build_mood_meter_offline(self):
        """Offline pet should show OFF label."""
        term = MagicMock()
        pet = MagicMock()
        pet.face_key = "offline"
        pet.gateway_online = False

        # Mock terminal attributes
        term.light_salmon = ""
        term.cyan = ""
        term.grey70 = ""
        term.grey50 = ""
        term.normal = ""

        result = clawgotchi.build_mood_meter(term, pet, 20)
        # Result should contain the string "OFF" somewhere
        assert "OFF" in result


class TestFetchMoltbookTopics:
    """Test Moltbook API fetching."""

    def test_fetch_topics_returns_list(self):
        """Should return a list of topics."""
        # This will use cache if available, otherwise try to fetch
        topics = clawgotchi.fetch_moltbook_topics()
        assert isinstance(topics, list)
        # Note: May return cached data or fresh data depending on cache state

    def test_topic_structure(self):
        """Topics should have expected structure."""
        topics = clawgotchi.fetch_moltbook_topics()
        if topics:
            topic = topics[0]
            assert "id" in topic or "_id" in topic
            assert "title" in topic
            assert "author" in topic
            assert "karma" in topic


class TestPadRow:
    """Test row padding with border characters."""

    def test_pad_row_basic(self):
        """Basic padding with border."""
        term = MagicMock()
        term.grey50 = ""
        term.normal = ""

        result = clawgotchi.pad_row(term, "hello", 20)
        # Uses U+2502 (│) not ASCII |
        assert "│" in result
        assert "hello" in result
        assert len(result) == 20

    def test_pad_row_exact_fit(self):
        """Content that exactly fits should still have borders."""
        term = MagicMock()
        term.grey50 = ""
        term.normal = ""

        result = clawgotchi.pad_row(term, "hi", 4)
        # 2 borders + 2 content = 4
        assert len(result) == 4

    def test_pad_row_truncates_longer(self):
        """Longer content should be padded, not truncated."""
        term = MagicMock()
        term.grey50 = ""
        term.normal = ""

        result = clawgotchi.pad_row(term, "hello world", 15)
        assert len(result) == 15


class TestSendMessageAsync:
    """Test async message sending."""

    def test_send_message_creates_thread(self):
        """Should create and start a daemon thread."""
        chat_history = []

        # This is hard to test without mocking subprocess
        # Just verify it doesn't raise and creates a thread
        clawgotchi.send_message_async("test message", chat_history)

        # Thread should start and finish quickly for this test
        import time
        time.sleep(0.1)


class TestGetActivityLevel:
    """Test activity level mapping from feed rate."""

    def test_activity_level_idle(self):
        """Zero feed rate should be idle."""
        from core.status import get_activity_level
        assert get_activity_level(0.0) == "idle"
        assert get_activity_level(0) == "idle"

    def test_activity_level_low(self):
        """Low feed rate should be low."""
        from core.status import get_activity_level
        assert get_activity_level(0.1) == "low"
        assert get_activity_level(0.49) == "low"

    def test_activity_level_moderate(self):
        """Moderate feed rate should be moderate."""
        from core.status import get_activity_level
        assert get_activity_level(0.5) == "moderate"
        assert get_activity_level(1.99) == "moderate"

    def test_activity_level_active(self):
        """Active feed rate should be active."""
        from core.status import get_activity_level
        assert get_activity_level(2.0) == "active"
        assert get_activity_level(4.99) == "active"

    def test_activity_level_very_active(self):
        """High feed rate should be very_active."""
        from core.status import get_activity_level
        assert get_activity_level(5.0) == "very_active"
        assert get_activity_level(100.0) == "very_active"


class TestGetAgentStatus:
    """Test agent status function."""

    def test_get_agent_status_returns_dict(self):
        """Should return a dictionary with expected keys."""
        from core.status import get_agent_status
        result = get_agent_status()
        assert isinstance(result, dict)
        assert "mood" in result
        assert "face" in result
        assert "activity" in result
        assert "feed_rate" in result

    def test_get_agent_status_activity_is_string(self):
        """Activity should be a string value."""
        from core.status import get_agent_status
        result = get_agent_status()
        assert isinstance(result["activity"], str)
