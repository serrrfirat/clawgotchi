"""Tests for Session Memory Extractor"""
import pytest
from utils.session_memory_extractor import SessionMemoryExtractor


def test_extract_single_fact():
    """Extract a single atomic fact from text"""
    extractor = SessionMemoryExtractor()
    text = "Session Cost Tracker built successfully. 14 tests passing."
    facts = extractor.extract_facts(text)
    assert len(facts) >= 1
    assert any("Session Cost Tracker" in f for f in facts)


def test_extract_multiple_facts():
    """Extract multiple distinct facts from longer text"""
    extractor = SessionMemoryExtractor()
    text = """Wake Cycle #711:
    - Built Skill Dependency Analyzer
    - 19 tests passing
    - Commit: 6632f3a"""
    facts = extractor.extract_facts(text)
    assert len(facts) >= 2


def test_extract_dates():
    """Extract and normalize date patterns"""
    extractor = SessionMemoryExtractor()
    text = "On 2026-02-06, I built the Context Compressor."
    facts = extractor.extract_facts(text)
    assert any("2026-02-06" in f for f in facts)


def test_extract_tools():
    """Extract tool/utility names with specific patterns"""
    extractor = SessionMemoryExtractor()
    text = "Used utils/session_cost_tracker.py and tests/test_session_cost_tracker.py"
    facts = extractor.extract_facts(text)
    assert any("session_cost_tracker" in f for f in facts)


def test_filter_noise():
    """Filter out low-value entries"""
    extractor = SessionMemoryExtractor()
    text = "Reading file: /Users/firatsertgoz/Documents/clawgotchi/SOUL.md"
    facts = extractor.extract_facts(text)
    # Should not include routine file reads unless marked important
    assert all(len(f) > 10 for f in facts)


def test_mark_importance():
    """Rank facts by importance score"""
    extractor = SessionMemoryExtractor()
    text = """Built Session Cost Tracker (important)
    - 14 tests passing
    - Health: 96/100
    - Pushed to Moltbook (important)"""
    ranked = extractor.extract_and_rank(text)
    important = [f for f in ranked if f["importance"] >= 0.7]
    assert len(important) >= 1


def test_format_for_memory():
    """Format extracted facts for memory storage"""
    extractor = SessionMemoryExtractor()
    text = "Wake Cycle #724: Built Context Compressor"
    formatted = extractor.format_for_memory(text, "2026-02-06")
    assert "date" in formatted
    assert "content" in formatted
    assert "tags" in formatted
