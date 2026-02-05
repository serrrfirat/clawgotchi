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
