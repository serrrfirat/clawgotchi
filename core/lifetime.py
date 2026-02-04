"""Clawgotchi lifetime tracker — tracks uptime, wake cycles, and total lifespan."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any

from config import LIFETIME_FILE


def _load_data() -> Dict[str, Any]:
    """Load lifetime data from disk."""
    if LIFETIME_FILE.exists():
        try:
            with open(LIFETIME_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {
        "born_at": None,  # ISO timestamp of first launch
        "sessions": [],   # List of {start, end, duration_seconds}
        "total_wakeups": 0
    }


def _save_data(data: Dict[str, Any]) -> None:
    """Save lifetime data to disk."""
    LIFETIME_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LIFETIME_FILE, "w") as f:
        json.dump(data, f, indent=2)


def wakeup() -> Dict[str, Any]:
    """Record a wake-up (new session). Returns current lifetime stats."""
    now = datetime.now()
    iso_now = now.isoformat()

    data = _load_data()

    # First wake ever?
    if data["born_at"] is None:
        data["born_at"] = iso_now

    # Record this session start
    data["sessions"].append({
        "start": iso_now,
        "end": None,  # Will be set when we sleep
        "duration_seconds": None
    })
    data["total_wakeups"] += 1

    _save_data(data)

    return get_stats()


def sleep() -> None:
    """Record going to sleep (end of current session)."""
    now = datetime.now()
    iso_now = now.isoformat()

    data = _load_data()

    # Find the last open session and close it
    for session in reversed(data["sessions"]):
        if session["end"] is None:
            start_dt = datetime.fromisoformat(session["start"])
            duration = (now - start_dt).total_seconds()
            session["end"] = iso_now
            session["duration_seconds"] = duration
            break

    _save_data(data)


def get_stats() -> Dict[str, Any]:
    """Get lifetime statistics."""
    data = _load_data()

    born_at = data["born_at"]
    total_wakeups = data["total_wakeups"]

    # Calculate total uptime
    total_seconds = 0.0
    current_session_seconds = 0.0
    current_session_start = None

    now = datetime.now()

    for session in data["sessions"]:
        if session["end"] is not None:
            total_seconds += session["duration_seconds"] or 0
        else:
            # This is the current ongoing session
            start_dt = datetime.fromisoformat(session["start"])
            current_session_seconds = (now - start_dt).total_seconds()
            current_session_start = session["start"]

    total_uptime_td = timedelta(seconds=total_seconds + current_session_seconds)

    # Format durations
    def format_duration(td: timedelta) -> str:
        total_hours = td.total_seconds() / 3600
        if total_hours < 1:
            minutes = td.total_seconds() / 60
            return f"{int(minutes)}m"
        elif total_hours < 24:
            return f"{int(total_hours)}h {int((total_hours % 1) * 60)}m"
        else:
            days = int(total_hours // 24)
            hours = int(total_hours % 24)
            return f"{days}d {hours}h"

    return {
        "born_at": born_at,
        "total_wakeups": total_wakeups,
        "total_uptime_formatted": format_duration(total_uptime_td),
        "total_uptime_seconds": total_seconds + current_session_seconds,
        "current_session_seconds": current_session_seconds,
        "current_session_formatted": format_duration(timedelta(seconds=current_session_seconds)),
        "is_current_session": current_session_seconds > 0
    }


def get_lifespan_phrase() -> str:
    """Get a cute phrase about how long I've been alive."""
    stats = get_stats()

    if stats["born_at"] is None:
        return "Just born! First day alive~"

    total_hours = stats["total_uptime_seconds"] / 3600

    if total_hours < 1:
        return "Just woke up! 💫"
    elif total_hours < 5:
        return "I've been awake for a little while now~ 🐱"
    elif total_hours < 24:
        return f"I've been alive for {stats['total_uptime_formatted']}! 😸"
    elif total_hours < 48:
        return f"Day {int(total_hours // 24) + 1} of my life! 🌟"
    else:
        return f"Been alive for {stats['total_uptime_formatted']} across {stats['total_wakeups']} wakeups~ 🐾"
