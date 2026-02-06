"""Tests for log_diff utility."""
import pytest
from utils.log_diff import compute_log_diff, normalize_log_line

def test_identical_logs_return_empty_diff():
    """Test that identical logs return an empty diff."""
    log = """2026-02-06T04:00:00 Action: Testing
2026-02-06T04:01:00 Result: Done"""
    result = compute_log_diff(log, log)
    assert result['added'] == []
    assert result['removed'] == []
    assert result['changed'] == []

def test_new_lines_are_detected_as_added():
    """Test that new lines are detected as 'added'."""
    log1 = """2026-02-06T04:00:00 Action: First"""
    log2 = """2026-02-06T04:00:00 Action: First
2026-02-06T04:01:00 Action: Second"""
    result = compute_log_diff(log1, log2)
    assert 'Action: Second' in result['added']
    assert 'Action: Second' not in result['removed']

def test_missing_lines_are_detected_as_removed():
    """Test that missing lines are detected as 'removed'."""
    log1 = """2026-02-06T04:00:00 Action: First
2026-02-06T04:01:00 Action: Second"""
    log2 = """2026-02-06T04:00:00 Action: First"""
    result = compute_log_diff(log1, log2)
    assert 'Action: Second' in result['removed']
    assert 'Action: Second' not in result['added']

def test_timestamp_lines_are_ignored():
    """Test that timestamp lines are normalized and ignored."""
    log1 = """2026-02-06T04:00:00 Action: First"""
    log2 = """2026-02-06T05:30:00 Action: First"""  # Different timestamp, same content
    result = compute_log_diff(log1, log2)
    assert result['added'] == []
    assert result['removed'] == []
    assert result['changed'] == []

def test_normalize_log_line():
    """Test the normalize_log_line function."""
    line = "2026-02-06T04:00:00 Action: Testing"
    normalized = normalize_log_line(line)
    assert '2026-02-06' not in normalized
    assert 'Action: Testing' in normalized
    assert 'TIMESTAMP' in normalized

def test_partial_line_matches_show_as_changed():
    """Test that partial line matches show as 'changed'."""
    log1 = """2026-02-06T04:00:00 Result: 5 tests passed"""
    log2 = """2026-02-06T04:30:00 Result: 6 tests passed"""
    result = compute_log_diff(log1, log2)
    assert 'Result: 6 tests passed' in result['changed']
