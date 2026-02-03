"""Clawgotchi status reporter — displays current stats and health."""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import lifetime


def get_lifetime_stats() -> dict:
    """Get lifetime stats from the lifetime module."""
    try:
        return lifetime.get_stats()
    except Exception:
        return {
            "born_at": None,
            "total_wakeups": 0,
            "total_uptime_formatted": "unknown",
            "current_session_seconds": 0,
            "current_session_formatted": "unknown",
            "is_current_session": False
        }


def format_status_line() -> str:
    """Format a one-line status summary for the terminal pet."""
    stats = get_lifetime_stats()
    
    uptime = stats.get("current_session_formatted", "unknown")
    total = stats.get("total_uptime_formatted", "unknown")
    wakeups = stats.get("total_wakeups", 0)
    
    return f"[STATUS] Session: {uptime} | Total: {total} | Wakeups: {wakeups}"


def get_status_report() -> dict:
    """Get a full status report dictionary."""
    stats = get_lifetime_stats()
    
    return {
        "lifetime": stats,
        "generated_at": datetime.now().isoformat()
    }


def main(args=None):
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Clawgotchi Status Reporter")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("mode", nargs="?", default="cli", choices=["cli", "report"])
    
    parsed_args = parser.parse_args(args)
    
    stats = get_lifetime_stats()
    
    if parsed_args.json:
        import json
        report = get_status_report()
        print(json.dumps(report, indent=2))
        return
    
    # Default CLI output - pretty formatted
    print("╔══════════════════════════════════════╗")
    print("║       🐱 CLAWOTCHI STATUS 🐱         ║")
    print("╠══════════════════════════════════════╣")
    print(f"║  Born:     {stats.get('born_at', 'Unknown')[:19] or 'Unknown':<26}║")
    print(f"║  Wakeups:  {stats.get('total_wakeups', 0):<26}║")
    print(f"║  Uptime:   {stats.get('total_uptime_formatted', 'Unknown'):<26}║")
    print(f"║  Session:  {stats.get('current_session_formatted', 'Unknown'):<26}║")
    print("╚══════════════════════════════════════╝")


if __name__ == "__main__":
    main()
