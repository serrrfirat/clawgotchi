"""Clawgotchi status reporter — displays current stats and health."""

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

import lifetime
from pet_state import PetState


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


def get_host_metrics() -> dict:
    """Get host system metrics (disk usage)."""
    try:
        mem = shutil.disk_usage("/")
        return {
            "disk_total_gb": round(mem.total / (1024**3), 1),
            "disk_used_gb": round(mem.used / (1024**3), 1),
            "disk_free_gb": round(mem.free / (1024**3), 1),
            "disk_percent": round((mem.used / mem.total) * 100, 1),
            "platform": sys.platform
        }
    except Exception:
        return {
            "disk_total_gb": 0,
            "disk_used_gb": 0,
            "disk_free_gb": 0,
            "disk_percent": 0,
            "platform": "unknown"
        }


def get_agent_status() -> dict:
    """Get agent status for Moltbook API compatibility."""
    try:
        pet = PetState()
        mood = pet.get_cat_name()
        current_face = pet.get_face()
        
        return {
            "mood": mood,
            "face": current_face,
            "activity": "idle"
        }
    except Exception:
        return {
            "mood": "unknown",
            "face": "(•_•)",
            "activity": "error"
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
    lifetime_stats = get_lifetime_stats()
    host_metrics = get_host_metrics()
    agent_status = get_agent_status()
    return {
        "lifetime": lifetime_stats,
        "host": host_metrics,
        "agent_status": agent_status,
        "generated_at": datetime.now().isoformat()
    }


def main(args=None):
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Clawgotchi Status Reporter")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("mode", nargs="?", default="cli", choices=["cli", "report"])
    
    parsed_args = parser.parse_args(args)
    lifetime_stats = get_lifetime_stats()
    host_metrics = get_host_metrics()
    agent_status = get_agent_status()
    
    if parsed_args.json:
        import json
        report = get_status_report()
        print(json.dumps(report, indent=2))
        return
    
    print("╔══════════════════════════════════════╗")
    print("║       🐱 CLAWOTCHI STATUS 🐱         ║")
    print("╠══════════════════════════════════════╣")
    print(f"║  Born:     {lifetime_stats.get('born_at', 'Unknown')[:19] or 'Unknown':<26}║")
    print(f"║  Wakeups:  {lifetime_stats.get('total_wakeups', 0):<26}║")
    print(f"║  Uptime:   {lifetime_stats.get('total_uptime_formatted', 'Unknown'):<26}║")
    print(f"║  Session:  {lifetime_stats.get('current_session_formatted', 'Unknown'):<26}║")
    print("╠══════════════════════════════════════╣")
    print(f"║  Mood:     {agent_status.get('mood', 'unknown'):<26}║")
    print(f"║  Face:     {agent_status.get('face', '(•_•)'):<26}║")
    print("╠══════════════════════════════════════╣")
    print(f"║  Disk:     {host_metrics.get('disk_percent', 0)}% used ({host_metrics.get('disk_used_gb', 0)}GB/{host_metrics.get('disk_total_gb', 0)}GB)    ║")
    print(f"║  Free:     {host_metrics.get('disk_free_gb', 0)}GB                        ║")
    print("╚══════════════════════════════════════╝")


if __name__ == "__main__":
    main()
