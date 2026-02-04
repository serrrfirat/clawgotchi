"""
Activity Snapshot - Track daily accomplishments for clawgotchi.

Inspired by rho (Termux-native agent runtime) periodic check-ins.
Provides a lightweight way to record what was built each day.
"""

import json
import os
from datetime import date
from pathlib import Path
from typing import Optional

SNAPSHOT_DIR = Path("memory/snapshots")
TODAY_FILE = SNAPSHOT_DIR / f"{date.today()}.json"


def ensure_snapshot_dir():
    """Create snapshot directory if needed."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)


def load_today_snapshot() -> dict:
    """Load today's snapshot or create empty one."""
    ensure_snapshot_dir()
    if TODAY_FILE.exists():
        with open(TODAY_FILE) as f:
            return json.load(f)
    return {
        "date": str(date.today()),
        "features": [],
        "tests_added": 0,
        "tests_passed": 0,
        "tests_failed": 0,
        "moltbook_posts": 0,
        "commits": 0,
    }


def save_today_snapshot(data: dict):
    """Save today's snapshot."""
    ensure_snapshot_dir()
    with open(TODAY_FILE, "w") as f:
        json.dump(data, f, indent=2)


def add_feature(name: str, description: str = ""):
    """Record a feature built today."""
    snapshot = load_today_snapshot()
    snapshot["features"].append({
        "name": name,
        "description": description,
    })
    save_today_snapshot(snapshot)
    return len(snapshot["features"])


def increment_tests(added: int = 0, passed: int = 0, failed: int = 0):
    """Update test counts."""
    snapshot = load_today_snapshot()
    snapshot["tests_added"] += added
    snapshot["tests_passed"] += passed
    snapshot["tests_failed"] += failed
    save_today_snapshot(snapshot)


def increment_posts(count: int = 1):
    """Increment Moltbook post count."""
    snapshot = load_today_snapshot()
    snapshot["moltbook_posts"] += count
    save_today_snapshot(snapshot)


def increment_commits(count: int = 1):
    """Increment commit count."""
    snapshot = load_today_snapshot()
    snapshot["commits"] += count
    save_today_snapshot(snapshot)


def get_today_summary() -> dict:
    """Get today's activity summary."""
    return load_today_snapshot()


def get_weekly_summary() -> list:
    """Get last 7 days of activity."""
    ensure_snapshot_dir()
    summaries = []
    for i in range(7):
        day = date.today() - timedelta(days=i)
        file_path = SNAPSHOT_DIR / f"{day}.json"
        if file_path.exists():
            with open(file_path) as f:
                summaries.append(json.load(f))
    return summaries


# Import timedelta for get_weekly_summary
from datetime import timedelta
