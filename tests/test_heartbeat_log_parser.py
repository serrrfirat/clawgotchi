"""Tests for Heartbeat Log Parser."""

from utils.heartbeat_log_parser import (
    parse_daily_log,
    extract_actions,
    extract_metrics,
    generate_moltbook_summary
)


def test_parse_daily_log_basic():
    """Test parsing a basic daily log."""
    content = """## 2026-02-06

- Some intro text

[06:09] Verifying assumptions: Verified assumptions: 2 open, 0 stale, 0 expired
[06:24] Exploring Moltbook for ideas: Explored Moltbook: 5 accepted, 45 rejected
[06:40] Building: Skill Dependency Analyzer: Built skill: skills/skill_auditor/SKILL.md

Health: 96/100
Commit: abc1234
Push: Failed
"""
    result = parse_daily_log(content)
    
    assert result["date"] == "2026-02-06"
    assert len(result["actions"]) == 3
    assert result["health_scores"] == [96]
    assert "abc1234" in result["metrics"]["commits"]


def test_parse_daily_log_no_date():
    """Test parsing log without date header."""
    content = "No date here"
    result = parse_daily_log(content)
    assert result["date"] is None


def test_extract_actions():
    """Test extracting action items."""
    content = """
[06:09] Verifying assumptions: 2 open
[06:24] Building: New feature
[06:40] Resting — nothing to do
"""
    actions = extract_actions(content)
    
    assert len(actions) == 3
    assert actions[0] == ("06:09", "Verifying assumptions: 2 open")
    assert actions[1] == ("06:24", "Building: New feature")


def test_extract_metrics():
    """Test extracting numeric metrics."""
    content = """
Health: 96/100
Health: 95/100
Tests: 19/19 passing
Commit: abc1234
Commit: def5678
Push: Failed
Push: Success
"""
    metrics = extract_metrics(content)
    
    assert metrics["health_scores"] == [96, 95]
    assert metrics["avg_health"] == 95.5
    assert len(metrics["test_runs"]) == 1
    assert metrics["test_runs"][0] == {"passed": 19, "total": 19}
    assert len(metrics["commits"]) == 2
    assert metrics["pushes"]["failed"] == 1
    assert metrics["pushes"]["success"] == 1


def test_generate_moltbook_summary():
    """Test generating Moltbook-ready summary."""
    content = """## 2026-02-06

[06:09] Verifying assumptions: Verified assumptions
[06:24] Building: New Feature
[07:00] Resting

Health: 96/100
Tests: 8/8 passing
"""
    summary = generate_moltbook_summary(content, "Building utilities")
    
    assert "2026-02-06" in summary
    assert "Health: 96/100" in summary
    assert "Actions: 2 active operations" in summary
    assert "Tests: 8/8 passing" in summary
    assert "Today's Focus: Building utilities" in summary
    assert "Resting" in summary


def test_generate_moltbook_summary_no_date():
    """Test summary generation with invalid content."""
    result = generate_moltbook_summary("No date here")
    assert "Could not parse date" in result


def test_parse_daily_log_with_build_results():
    """Test parsing build results from log."""
    content = """## 2026-02-06

[07:10] Building: Skill Dependency Analyzer
Health: 96/100
Commit: 6632f3a
Tests: 19/19 passing
"""
    result = parse_daily_log(content)
    
    assert result["metrics"]["builds"] == ["Skill Dependency Analyzer"]
    assert result["metrics"]["commits"] == ["6632f3a"]
