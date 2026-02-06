"""
Heartbeat Log Parser - Extracts metrics and summaries from daily memory logs.

Features:
- parse_daily_log: Parse a day's memory file
- extract_actions: Extract action items with timestamps
- extract_metrics: Pull health scores, test counts, etc.
- generate_moltbook_summary: Create a post-ready summary
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def parse_daily_log(content: str) -> Dict:
    """Parse a daily memory log and extract structured data."""
    result = {
        "date": None,
        "actions": [],
        "health_scores": [],
        "metrics": {},
        "inspiration_sources": [],
        "build_results": []
    }
    
    # Extract date from header like "## 2026-02-06"
    date_match = re.search(r"## (\d{4}-\d{2}-\d{2})", content)
    if date_match:
        result["date"] = date_match.group(1)
    
    # Extract action items with timestamps like "[06:09] Action description"
    action_pattern = r"\[(\d{2}:\d{2})\] (.+)"
    for match in re.finditer(action_pattern, content):
        timestamp, action = match.groups()
        result["actions"].append({
            "time": timestamp,
            "description": action.strip()
        })
    
    # Extract health scores
    health_pattern = r"Health:\s*(\d+)/100"
    for match in re.finditer(health_pattern, content):
        result["health_scores"].append(int(match.group(1)))
    
    # Extract test counts like "19/19 passing" or "8/8 passing"
    test_pattern = r"(\d+)/(\d+) passing"
    for match in re.finditer(test_pattern, content):
        passed, total = match.groups()
        result["metrics"]["test_runs"] = result["metrics"].get("test_runs", []) + [{
            "passed": int(passed),
            "total": int(total)
        }]

    # Extract build actions from parsed action descriptions
    builds = []
    for action in result["actions"]:
        desc = action.get("description", "")
        if desc.startswith("Building:"):
            build_name = desc.split("Building:", 1)[1].strip()
            if " : " in build_name:
                build_name = build_name.split(" : ", 1)[0].strip()
            if ": Built " in build_name:
                build_name = build_name.split(": Built ", 1)[0].strip()
            if build_name:
                builds.append(build_name)
    if builds:
        result["metrics"]["builds"] = builds
    
    # Extract commit hashes
    commit_pattern = r"[Cc]ommit:\s*([a-f0-9]+)"
    result["metrics"]["commits"] = re.findall(commit_pattern, content)
    
    # Extract push failures
    push_pattern = r"[Pp]ush:\s*(Failed|Success)"
    pushes = re.findall(push_pattern, content)
    result["metrics"]["pushes"] = {
        "success": pushes.count("Success"),
        "failed": pushes.count("Failed")
    }
    
    return result


def extract_actions(content: str) -> List[Tuple[str, str]]:
    """Extract action items with timestamps from memory content."""
    actions = []
    action_pattern = r"\[(\d{2}:\d{2})\] (.+)"
    for match in re.finditer(action_pattern, content):
        timestamp, action = match.groups()
        actions.append((timestamp, action.strip()))
    return actions


def extract_metrics(content: str) -> Dict:
    """Extract numeric metrics from memory content."""
    metrics = {}
    
    # Health scores
    health_pattern = r"Health:\s*(\d+)/100"
    health_scores = re.findall(health_pattern, content)
    if health_scores:
        parsed_health = [int(h) for h in health_scores]
        metrics["health_scores"] = parsed_health
        metrics["avg_health"] = sum(parsed_health) / len(parsed_health)
    
    # Test counts
    test_pattern = r"(\d+)/(\d+) passing"
    tests = re.findall(test_pattern, content)
    if tests:
        metrics["test_runs"] = [{"passed": int(t[0]), "total": int(t[1])} for t in tests]
    
    # Commits
    commit_pattern = r"[Cc]ommit:\s*([a-f0-9]+)"
    metrics["commits"] = re.findall(commit_pattern, content)
    
    # Push status
    push_pattern = r"[Pp]ush:\s*(Failed|Success)"
    pushes = re.findall(push_pattern, content)
    metrics["pushes"] = {"success": pushes.count("Success"), "failed": pushes.count("Failed")}
    
    # Feature builds
    build_pattern = r"Building:\s*(.+?)(?:\n|$)"
    builds = re.findall(build_pattern, content)
    if builds:
        metrics["builds"] = builds
    
    return metrics


def generate_moltbook_summary(content: str, focus_action: str = None) -> str:
    """Generate a summary suitable for Moltbook posting."""
    parsed = parse_daily_log(content)
    
    if not parsed["date"]:
        return "Could not parse date from log"
    
    lines = [f"## Wake Cycle Summary - {parsed['date']}"]
    lines.append("")
    
    # Health summary
    if parsed["health_scores"]:
        avg_health = sum(parsed["health_scores"]) / len(parsed["health_scores"])
        lines.append(f"Health: {avg_health:.0f}/100 (avg)")
    
    # Action count
    action_count = len([a for a in parsed["actions"] if "Resting" not in a["description"]])
    lines.append(f"Actions: {action_count} active operations")
    
    # Build results
    if parsed["metrics"].get("builds"):
        lines.append(f"Built: {len(parsed['metrics']['builds'])} features")
    
    # Test summary
    test_runs = parsed["metrics"].get("test_runs", [])
    if test_runs:
        total_passed = sum(t["passed"] for t in test_runs)
        total = sum(t["total"] for t in test_runs)
        lines.append(f"Tests: {total_passed}/{total} passing")
    
    # Focus action if provided
    if focus_action:
        lines.append("")
        lines.append(f"Today's Focus: {focus_action}")
    
    # Most recent action
    if parsed["actions"]:
        most_recent = parsed["actions"][-1]
        lines.append("")
        lines.append(f"Last Activity: [{most_recent['time']}] {most_recent['description']}")
    
    return "\n".join(lines)
